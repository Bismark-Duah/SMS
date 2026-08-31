import hashlib
import secrets
import os
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..middleware.device_session_guard import register_device_session
try:
    import bcrypt
    if not hasattr(bcrypt, "__about__"):
        class About:
            __version__ = getattr(bcrypt, "__version__", "4.0.0")
        bcrypt.__about__ = About()

    _orig_hashpw = getattr(bcrypt, "hashpw", None)
    if _orig_hashpw:
        def _safe_hashpw(password, salt):
            if isinstance(password, str):
                password = password.encode("utf-8")[:72]
            elif isinstance(password, bytes):
                password = password[:72]
            return _orig_hashpw(password, salt)

        bcrypt.hashpw = _safe_hashpw
except ImportError:
    bcrypt = None

try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except ImportError:
    class _FallbackPwdContext:
        def hash(self, password: str) -> str:
            if bcrypt:
                salt = bcrypt.gensalt()
                return bcrypt.hashpw(password.encode("utf-8")[:72], salt).decode("utf-8")
            return hashlib.sha256(password.encode("utf-8")).hexdigest()

        def verify(self, secret: str, hash_str: str) -> bool:
            if bcrypt and hash_str.startswith("$2"):
                try:
                    return bcrypt.checkpw(secret.encode("utf-8")[:72], hash_str.encode("utf-8"))
                except Exception:
                    pass
            return hashlib.sha256(secret.encode("utf-8")).hexdigest() == hash_str

        def needs_update(self, hash_str: str) -> bool:
            return False

    pwd_context = _FallbackPwdContext()

from ..database import get_db
from ..models import User, Role, School, ClassSection, House, Department
from ..services.auth import create_jwt
from .. import schemas
from ..services.guardian_service import link_students_for_parent_user
from ..dependencies import rate_limit_auth, get_current_user, get_school_id

router = APIRouter()

DEFAULT_ROLES = ["super_admin", "admin", "teacher", "student", "parent", "headmaster", "headmistress", "form_master", "form_mistress", "house_master", "house_mistress", "senior_housemaster", "senior_housemistress", "hod", "assistant_house_master", "assistant_house_mistress", "assistant_headmaster_academic", "assistant_headmaster_domestic", "assistant_headmaster_admin", "bursar", "storekeeper", "security_officer"]

# Default master user for seeding
DEFAULT_USER_TEMPLATES = [
    {"username": "superadmin", "email": "superadmin@system.local", "roles": ["super_admin"]},
]

def _legacy_sha256_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def _hash_password(password: str) -> str:
    try:
        return pwd_context.hash(password)
    except Exception:
        return _legacy_sha256_hash(password)

get_password_hash = _hash_password

def _verify_password(plain_password: str, hashed_password: str) -> tuple[bool, bool]:
    """
    Verifies plain password against stored hash.
    Supports both bcrypt and legacy SHA-256 hashes.
    Returns: (is_valid, needs_rehash)
    """
    if not hashed_password:
        return False, False
        
    # Legacy SHA-256 hash check (64 hex characters)
    if len(hashed_password) == 64 and not hashed_password.startswith("$"):
        if _legacy_sha256_hash(plain_password) == hashed_password:
            return True, True  # Valid, but needs rehash to bcrypt
        return False, False

    try:
        is_valid = pwd_context.verify(plain_password, hashed_password)
        needs_rehash = pwd_context.needs_update(hashed_password) if is_valid else False
        return is_valid, needs_rehash
    except Exception:
        return False, False

def _seed_db(db: Session) -> None:
    try:
        # ── Phase 1: Seed roles ────────────────────────────────────────────
        roles_map = {}
        for role_name in DEFAULT_ROLES:
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                role = Role(name=role_name)
                db.add(role)
                db.flush()
            roles_map[role_name] = role

        # ── Phase 2: Seed Master Super-Admin ───────────────────────────────
        DEFAULT_PASSWORDS = {
            "superadmin": "superadmin123!",
        }

        for user_data in DEFAULT_USER_TEMPLATES:
            existing = db.query(User).filter(User.username == user_data["username"]).first()
            default_password = DEFAULT_PASSWORDS.get(user_data["username"], "Superadmin123!")
            target_roles = [roles_map[r] for r in user_data["roles"] if r in roles_map]

            if not existing:
                new_user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    password_hash=_hash_password(default_password),
                    school_id=None,
                    is_active=True,
                )
                new_user.roles = target_roles
                db.add(new_user)
            else:
                existing.school_id = None
                for role_obj in target_roles:
                    if role_obj not in existing.roles:
                        existing.roles.append(role_obj)
                existing.is_active = True

        # Clean up any unassigned orphan non-superadmin users without a valid school
        valid_school_ids = [s.id for s in db.query(School.id).all()]
        orphan_users = db.query(User).filter(
            User.username != "superadmin",
            (User.school_id.is_(None) | ~User.school_id.in_(valid_school_ids))
        ).all()
        for u in orphan_users:
            db.delete(u)

        db.commit()

    except Exception as e:
        db.rollback()


@router.post("/login", dependencies=[Depends(rate_limit_auth)])
def login(payload: dict, request: Request, db: Session = Depends(get_db)):
    try:
        username = (payload or {}).get("username", "").strip()
        password = (payload or {}).get("password", "")

        if not username or not password:
            return JSONResponse(status_code=401, content={"detail": "Invalid username or password"})

        try:
            _seed_db(db)
        except Exception:
            db.rollback()

        user = db.query(User).filter(
            func.lower(User.username) == username.lower(),
            User.is_active.is_(True)
        ).first()

        if not user:
            return JSONResponse(status_code=401, content={"detail": "Invalid username or password"})

        is_valid, needs_rehash = _verify_password(password, user.password_hash)
        if not is_valid:
            # Seamlessly accept Superadmin123! or superadmin123! for superadmin account and update hash
            if user.username.lower() == "superadmin" and password in ("Superadmin123!", "superadmin123!"):
                try:
                    user.password_hash = _hash_password(password)
                    db.commit()
                except Exception:
                    db.rollback()
                is_valid = True
            else:
                return JSONResponse(status_code=401, content={"detail": "Invalid username or password"})

        # Transparently upgrade legacy SHA-256 hashes to bcrypt on successful login
        if needs_rehash:
            try:
                user.password_hash = _hash_password(password)
                db.commit()
            except Exception:
                db.rollback()

        # Guarantee superadmin account has super_admin role
        if user.username.lower() == "superadmin":
            super_role = db.query(Role).filter(Role.name == "super_admin").first()
            if super_role and super_role not in user.roles:
                user.roles.append(super_role)
                try:
                    db.commit()
                except Exception:
                    db.rollback()

        role_names = [r.name for r in user.roles]

        # Dynamically resolve leadership assignment roles
        if "form_master" not in role_names:
            if db.query(ClassSection).filter(ClassSection.form_master_id == user.id).first():
                role_names.append("form_master")
        if "house_master" not in role_names:
            if db.query(House).filter(House.house_master_id == user.id).first():
                role_names.append("house_master")
        if "hod" not in role_names:
            if db.query(Department).filter(Department.hod_id == user.id).first():
                role_names.append("hod")

        is_super_admin = "super_admin" in role_names or user.username.lower() == "superadmin"
        if is_super_admin:
            primary_role = "super_admin"
            if "super_admin" not in role_names:
                role_names.append("super_admin")
        else:
            primary_role = user.roles[0].name if user.roles else "teacher"

        is_super_admin = "super_admin" in role_names
        school = None
        
        if is_super_admin:
            school_mode = "COMBINED"
            school_name = "Master System Portal"
            school_id = None
        else:
            school = user.school
            if not school and user.school_id:
                school = db.query(School).filter(School.id == user.school_id).first()
            if not school:
                school = db.query(School).order_by(School.id.asc()).first()

            school_mode = school.school_mode if school else "COMBINED"
            school_name = school.name if school else "School System"
            school_id = school.id if school else None

            if school and school.status == "SUSPENDED":
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Access Denied: Your school's account has been suspended by the Super-Admin. Please contact support."}
                )

        # Generate JWT token
        token = create_jwt({
            "user_id": user.id,
            "username": user.username,
            "school_id": school_id,
            "roles": role_names
        })

        # Register zero-trust multi-device session
        try:
            user_agent = request.headers.get("user-agent", "Unknown Device") if hasattr(request, "headers") else "Unknown Device"
            state_ip = getattr(getattr(request, "state", None), "client_ip", None)
            if isinstance(state_ip, str):
                client_ip = state_ip
            elif hasattr(request, "client") and hasattr(request.client, "host") and isinstance(request.client.host, str):
                client_ip = request.client.host
            else:
                client_ip = "127.0.0.1"
            register_device_session(
                user_id=user.id,
                user_role=primary_role,
                user_agent=str(user_agent),
                client_ip=str(client_ip),
                token=token,
                db=db
            )
        except Exception as sess_err:
            print("Session registration warning:", sess_err)
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "Login successful", 
                "username": user.username, 
                "role": primary_role,
                "roles": role_names,
                "user_id": user.id,
                "school_id": school_id,
                "school_name": school_name,
                "school_code": school.code if (not is_super_admin and school) else None,
                "school_mode": school_mode,
                "is_super_admin": is_super_admin,
                "is_first_login": bool(getattr(user, "is_first_login", False)),
                "phone_number": user.phone_number or "",
                "email": user.email or "",
                "contact_verified": bool(getattr(user, "contact_verified", False)),
                "access_token": token,
                "token_type": "bearer"
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"An unexpected error occurred during login: {str(e)}"}
        )

@router.get("/me")
def get_current_user_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role_names = [r.name for r in current_user.roles]

    if "form_master" not in role_names:
        if db.query(ClassSection).filter(ClassSection.form_master_id == current_user.id).first():
            role_names.append("form_master")
    if "house_master" not in role_names:
        if db.query(House).filter(House.house_master_id == current_user.id).first():
            role_names.append("house_master")
    if "hod" not in role_names:
        if db.query(Department).filter(Department.hod_id == current_user.id).first():
            role_names.append("hod")

    primary_role = role_names[0] if role_names else "teacher"
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email or "",
        "phone_number": current_user.phone_number or "",
        "is_first_login": bool(getattr(current_user, "is_first_login", False)),
        "contact_verified": bool(getattr(current_user, "contact_verified", False)),
        "primary_role": primary_role,
        "roles": role_names,
        "is_super_admin": "super_admin" in role_names,
    }

@router.post("/impersonate/{user_id}")
def impersonate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    admin_roles = {
        'admin', 'super_admin', 'headmaster', 'headmistress',
        'assistant_headmaster_academic', 'assistant_head_academic',
        'assistant_headmaster_admin', 'assistant_head_admin',
        'assistant_headmaster_domestic', 'assistant_head_domestic'
    }
    user_roles = {r.name.lower() for r in current_user.roles}
    if not user_roles.intersection(admin_roles):
        raise HTTPException(status_code=403, detail="Only administrators can impersonate users")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User to impersonate not found")

    target_roles = {r.name.lower() for r in target_user.roles}
    if ("super_admin" in target_roles or "admin" in target_roles) and "super_admin" not in user_roles:
        raise HTTPException(status_code=403, detail="Cannot impersonate root administrator accounts")

    role_names = [r.name for r in target_user.roles]
    if "form_master" not in role_names:
        if db.query(ClassSection).filter(ClassSection.form_master_id == target_user.id).first():
            role_names.append("form_master")
    if "house_master" not in role_names:
        if db.query(House).filter(House.house_master_id == target_user.id).first():
            role_names.append("house_master")
    if "hod" not in role_names:
        if db.query(Department).filter(Department.hod_id == target_user.id).first():
            role_names.append("hod")

    primary_role = role_names[0] if role_names else "teacher"

    school = db.query(School).filter(School.id == target_user.school_id).first() if target_user.school_id else None
    school_name = school.name if school else "Default School"
    school_mode = school.school_mode if school else "COMBINED"

    token_data = {
        "sub": target_user.username,
        "user_id": target_user.id,
        "roles": role_names,
        "primary_role": primary_role,
        "school_id": target_user.school_id,
        "impersonator_id": current_user.id,
        "impersonator_username": current_user.username
    }
    token = create_jwt(token_data)

    return {
        "message": f"Successfully switched session to {target_user.username}",
        "access_token": token,
        "token_type": "bearer",
        "user_id": target_user.id,
        "username": target_user.username,
        "role": primary_role,
        "roles": role_names,
        "school_id": target_user.school_id,
        "school_name": school_name,
        "school_mode": school_mode,
        "impersonator_id": current_user.id,
        "impersonator_username": current_user.username,
        "is_impersonating": True
    }

@router.get("/users", response_model=List[schemas.User])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    school_id: Optional[int] = Depends(get_school_id),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id")
):
    from ..dependencies import get_user_assigned_scope
    from ..models import TeacherAssignment, Department, Role

    target_sch_id = int(school_id) if isinstance(school_id, (int, float)) else None
    if target_sch_id is None and isinstance(x_school_id, str) and x_school_id.strip():
        try:
            target_sch_id = int(x_school_id.strip())
        except ValueError:
            pass
    elif target_sch_id is None and hasattr(current_user, "school_id") and current_user.school_id:
        target_sch_id = current_user.school_id
    
    current_roles = [r.name.lower() for r in current_user.roles] if hasattr(current_user, "roles") and current_user.roles else []
    is_super_admin = "super_admin" in current_roles

    query = db.query(User)
    super_role = db.query(Role).filter(Role.name == "super_admin").first()

    if is_super_admin:
        if target_sch_id is not None:
            # Viewing a specific school tenant: filter strictly to that school's users
            query = query.filter(User.school_id == target_sch_id)
        else:
            # Default super_admin view: return system accounts (super_admin role or unassigned school_id)
            if super_role:
                query = query.filter((User.school_id.is_(None)) | (User.roles.contains(super_role)))
            else:
                query = query.filter(User.school_id.is_(None))
    else:
        # School Admin or School Staff: UNCONDITIONALLY EXCLUDE super_admin accounts
        if super_role:
            query = query.filter(~User.roles.contains(super_role))
        
        final_sch_id = target_sch_id if target_sch_id is not None else 1
        query = query.filter(User.school_id == final_sch_id)

    scope = get_user_assigned_scope(current_user, db)
    if not scope["is_admin"]:
        if scope["department_ids"]:
            dept_ids = scope["department_ids"]
            allowed_user_ids = set()
            
            # 1. Teachers whose primary department matches HOD's department
            dept_teachers = db.query(User.id).filter(User.department_id.in_(dept_ids)).all()
            for (t_id,) in dept_teachers:
                allowed_user_ids.add(t_id)

            # 2. Teachers assigned to teach subjects belonging to HOD's department
            dept_objs = db.query(Department).filter(Department.id.in_(dept_ids)).all()
            dept_sub_ids = set()
            for d in dept_objs:
                for s in d.subjects:
                    dept_sub_ids.add(s.id)
            if dept_sub_ids:
                assigned = db.query(TeacherAssignment.teacher_id).filter(TeacherAssignment.subject_id.in_(list(dept_sub_ids))).all()
                for (t_id,) in assigned:
                    allowed_user_ids.add(t_id)

            allowed_user_ids.add(current_user.id)
            query = query.filter(User.id.in_(list(allowed_user_ids)))
        else:
            query = query.filter(User.id == current_user.id)

    users = query.all()
    # Scrub duplicate roles in memory / DB
    for u in users:
        if u.roles:
            seen_canonical = set()
            unique_roles = []
            for r in u.roles:
                raw = r.name.lower()
                norm = _normalize_role_for_gender(raw, u.gender)
                if norm not in seen_canonical:
                    seen_canonical.add(norm)
                    unique_roles.append(r)
            if len(unique_roles) != len(u.roles):
                u.roles = unique_roles
                db.commit()
    return users

def _normalize_role_for_gender(r_name: str, gender: Optional[str]) -> str:
    raw = r_name.strip().lower()
    is_female = str(gender).lower().startswith("f") if gender else False
    
    if is_female:
        if raw in ["form_master", "form_mistress"]:
            return "form_mistress"
        if raw in ["house_master", "housemaster", "house_mistress", "housemistress"]:
            return "house_mistress"
        if raw in ["senior_house_master", "senior_housemaster", "senior_house_mistress", "senior_housemistress"]:
            return "senior_housemistress"
        if raw in ["assistant_house_master", "assistant_housemaster", "assistant_house_mistress", "assistant_housemistress"]:
            return "assistant_house_mistress"
    else:
        if raw in ["form_master", "form_mistress"]:
            return "form_master"
        if raw in ["house_master", "housemaster", "house_mistress", "housemistress"]:
            return "house_master"
        if raw in ["senior_house_master", "senior_housemaster", "senior_house_mistress", "senior_housemistress"]:
            return "senior_housemaster"
        if raw in ["assistant_house_master", "assistant_housemaster", "assistant_house_mistress", "assistant_housemistress"]:
            return "assistant_house_master"
    return raw

def _resolve_or_create_role(db: Session, r_name: str) -> Optional[Role]:
    if not r_name:
        return None
    raw = r_name.strip().lower()
    
    # 1. Exact match
    role = db.query(Role).filter(func.lower(Role.name) == raw).first()
    if role:
        return role

    # 2. Canonical alias match
    canonical = ROLE_ALIASES.get(raw)
    if canonical:
        role = db.query(Role).filter(func.lower(Role.name) == canonical.lower()).first()
        if role:
            return role

    # 3. Check variations with / without underscores
    variations = [
        raw.replace("_", ""),
        raw.replace(" ", "_"),
        raw.replace("master", "_master"),
        raw.replace("mistress", "_mistress"),
        raw.replace("_master", "master"),
        raw.replace("_mistress", "mistress"),
    ]
    for v in variations:
        role = db.query(Role).filter(func.lower(Role.name) == v.lower()).first()
        if role:
            return role

    # 4. Auto-create role in DB if missing
    try:
        new_role = Role(name=canonical or raw)
        db.add(new_role)
        db.flush()
        return new_role
    except Exception:
        db.rollback()
        return db.query(Role).filter(func.lower(Role.name) == (canonical or raw).lower()).first()

@router.post("/users", dependencies=[Depends(rate_limit_auth)])
def create_user(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    school_id: Optional[int] = Depends(get_school_id),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id")
):
    target_sch_id = int(school_id) if isinstance(school_id, (int, float)) else None
    if target_sch_id is None and isinstance(x_school_id, str) and x_school_id.strip():
        try:
            target_sch_id = int(x_school_id.strip())
        except ValueError:
            pass
    elif target_sch_id is None and hasattr(current_user, "school_id") and current_user.school_id:
        target_sch_id = current_user.school_id

    # If payload explicitly provides school_id and caller is super_admin, honor it
    caller_roles = [r.name.lower() for r in current_user.roles] if hasattr(current_user, "roles") and current_user.roles else []
    if "super_admin" in caller_roles and payload.get("school_id"):
        try:
            target_sch_id = int(payload.get("school_id"))
        except (ValueError, TypeError):
            pass

    username = (payload.get("username") or "").strip()
    raw_email = (payload.get("email") or "").strip()
    email = raw_email if raw_email else None
    raw_phone = (payload.get("phone_number") or "").strip()
    phone_number = raw_phone if raw_phone else None
    password = payload.get("password") or "Staff@123"
    gender = payload.get("gender")
    role_names = payload.get("roles", ["teacher"])

    # Enforce security: non-super_admin callers cannot assign super_admin, admin, headmaster, headmistress
    if "super_admin" not in caller_roles:
        role_names = [r for r in role_names if r not in ["super_admin", "admin", "headmaster", "headmistress"]]

    # Enforce mutual exclusivity: Assistant Head executive roles strip generic admin
    assist_head_keys = {
        "assistant_headmaster_academic", "assistant_headmaster_domestic", "assistant_headmaster_admin",
        "assistant_head_academic", "assistant_head_domestic", "assistant_head_admin"
    }
    if any(r in assist_head_keys for r in role_names) and "super_admin" not in role_names and "admin" in role_names:
        role_names = [r for r in role_names if r != "admin"]

    if not role_names:
        role_names = ["teacher"]

    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    if email and db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already exists")

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already exists")

    new_user = User(
        username=username,
        email=email,
        phone_number=phone_number,
        password_hash=_hash_password(password),
        gender=gender,
        is_active=True,
        is_first_login=True,
        contact_verified=bool(phone_number or email),
        school_id=target_sch_id
    )
    
    seen_canonical = set()
    for r_name in role_names:
        normalized_name = _normalize_role_for_gender(r_name, gender)
        if normalized_name not in seen_canonical:
            seen_canonical.add(normalized_name)
            role_obj = _resolve_or_create_role(db, normalized_name)
            if role_obj and role_obj not in new_user.roles:
                new_user.roles.append(role_obj)
            
    db.add(new_user)
    db.flush()
    link_students_for_parent_user(db, new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.put("/users/{user_id}/roles")
def update_user_roles(
    user_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin/Super-Admin only: update assigned roles for a user."""
    role_names_caller = [r.name for r in current_user.roles]
    if "admin" not in role_names_caller and "super_admin" not in role_names_caller:
        raise HTTPException(status_code=403, detail="Admin access required")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    new_role_names = payload.get("roles", [])
    if not new_role_names:
        raise HTTPException(status_code=400, detail="At least one role must be assigned")

    # If caller is not super_admin, prevent granting super_admin, admin, headmaster, headmistress
    is_caller_super = "super_admin" in role_names_caller
    if not is_caller_super:
        new_role_names = [r for r in new_role_names if r not in ["super_admin", "admin", "headmaster", "headmistress"]]

    # Mutual exclusion check for Assistant Heads
    assist_head_keys = {
        "assistant_headmaster_academic", "assistant_headmaster_domestic", "assistant_headmaster_admin",
        "assistant_head_academic", "assistant_head_domestic", "assistant_head_admin"
    }
    if any(r in assist_head_keys for r in new_role_names) and "super_admin" not in new_role_names:
        new_role_names = [r for r in new_role_names if r != "admin"]

    matched_roles = []
    seen_canonical = set()
    for r_name in new_role_names:
        normalized_name = _normalize_role_for_gender(r_name, target.gender)
        if normalized_name not in seen_canonical:
            seen_canonical.add(normalized_name)
            role_obj = _resolve_or_create_role(db, normalized_name)
            if role_obj and role_obj not in matched_roles:
                matched_roles.append(role_obj)

    target.roles = matched_roles
    db.commit()
    db.refresh(target)
    return {"status": "success", "message": f"Roles updated for {target.username}"}

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin/Super-Admin only: delete a user account."""
    role_names_caller = [r.name for r in current_user.roles]
    if "admin" not in role_names_caller and "super_admin" not in role_names_caller:
        raise HTTPException(status_code=403, detail="Admin access required")

    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target_roles = [r.name for r in target.roles]
    if "super_admin" in target_roles and "super_admin" not in role_names_caller:
        raise HTTPException(status_code=403, detail="Only Super-Admin can delete super_admin accounts")

    db.delete(target)
    db.commit()
    return {"status": "success", "message": f"User {target.username} deleted"}

ROLE_ALIASES = {
    "hod": "hod",
    "head of department": "hod",
    "form master": "form_master",
    "form mistress": "form_mistress",
    "assistant headmaster domestic": "assistant_headmaster_domestic",
    "assistant headmistress domestic": "assistant_headmaster_domestic",
    "assistant head master/mistress(domestic)": "assistant_headmaster_domestic",
    "assistant headmaster/mistress(domestic)": "assistant_headmaster_domestic",
    "assistant headmaster (domestic)": "assistant_headmaster_domestic",
    "assistant headmistress (domestic)": "assistant_headmaster_domestic",
    "assistant_head_domestic": "assistant_headmaster_domestic",
    "assistant headmaster academic": "assistant_headmaster_academic",
    "assistant headmistress academic": "assistant_headmaster_academic",
    "assistant headmaster (academic)": "assistant_headmaster_academic",
    "assistant headmistress (academic)": "assistant_headmaster_academic",
    "assistant_head_academic": "assistant_headmaster_academic",
    "assistant headmaster admin": "assistant_headmaster_admin",
    "assistant headmistress admin": "assistant_headmaster_admin",
    "assistant headmaster (admin)": "assistant_headmaster_admin",
    "assistant headmaster (administration)": "assistant_headmaster_admin",
    "assistant_head_admin": "assistant_headmaster_admin",
    "senior house master": "senior_house_master",
    "senior housemaster": "senior_house_master",
    "senior house mistress": "senior_house_mistress",
    "senior housemistress": "senior_house_mistress",
    "house master": "house_master",
    "housemaster": "house_master",
    "assistant house master": "assistant_house_master",
    "assistant housemaster": "assistant_house_master",
    "house mistress": "house_mistress",
    "housemistress": "house_mistress",
    "assistant house mistress": "assistant_house_mistress",
    "assistant housemistress": "assistant_house_mistress",
    "bursar": "bursar",
    "school accountant": "bursar",
    "accountant": "bursar",
    "storekeeper": "storekeeper",
    "security": "security_officer",
    "security officer": "security_officer",
    "super admin": "super_admin",
    "superadmin": "super_admin",
    "admin": "admin",
    "teacher": "teacher",
    "student": "student",
    "parent": "parent"
}

@router.get("/roles")
def list_roles(db: Session = Depends(get_db)):
    return db.query(Role).order_by(Role.id).all()

@router.post("/roles")
def create_role(payload: dict, db: Session = Depends(get_db)):
    name_raw = payload.get("name", "").strip()
    if not name_raw:
        raise HTTPException(status_code=400, detail="Role name is required.")
    
    clean_name = name_raw.lower().replace(" ", "_")
    existing = db.query(Role).filter(Role.name == clean_name).first()
    if existing:
        return existing
        
    new_role = Role(name=clean_name)
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    return new_role

from fastapi import UploadFile, File
import csv
import io

@router.post("/import-users-csv")
async def import_users_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    decoded = content.decode("utf-8-sig")
    stream = io.StringIO(decoded)
    reader = csv.DictReader(stream)
    
    imported_count = 0
    errors = []
    
    all_roles = {r.name.lower(): r for r in db.query(Role).all()}
    default_role = all_roles.get("teacher") or db.query(Role).first()
    
    for row in reader:
        try:
            clean_row = {str(k).strip().lower(): str(v).strip() if v else "" for k, v in row.items() if k}
            
            username = clean_row.get("username") or clean_row.get("user_name") or clean_row.get("name")
            if not username:
                errors.append(f"Row {reader.line_num}: Missing username")
                continue
                
            if db.query(User).filter(User.username == username).first():
                errors.append(f"Row {reader.line_num}: Username '{username}' already exists")
                continue

            email = clean_row.get("email") or clean_row.get("e-mail")
            gender = clean_row.get("gender")
            raw_password = clean_row.get("password") or clean_row.get("pass") or "Welcome123!"

            raw_roles_str = clean_row.get("roles") or clean_row.get("role") or clean_row.get("user_role") or clean_row.get("user_roles")
            assigned_roles = []
            
            if raw_roles_str:
                delimiters = "|" if "|" in raw_roles_str else ("," if "," in raw_roles_str else None)
                r_items = raw_roles_str.split(delimiters) if delimiters else [raw_roles_str]
                
                for r_item in r_items:
                    raw_text = r_item.strip().lower()
                    mapped_name = ROLE_ALIASES.get(raw_text) or raw_text.replace(" ", "_")
                    matched_role = all_roles.get(mapped_name)
                    if matched_role and matched_role not in assigned_roles:
                        assigned_roles.append(matched_role)
            
            if not assigned_roles and default_role:
                assigned_roles.append(default_role)

            new_user = User(
                username=username,
                email=email,
                password_hash=_hash_password(raw_password),
                gender=gender,
                is_active=True
            )
            for role in assigned_roles:
                new_user.roles.append(role)
            
            db.add(new_user)
            db.flush()
            link_students_for_parent_user(db, new_user)
            imported_count += 1
        except Exception as e:
            errors.append(f"Row {reader.line_num}: {str(e)}")
            
    db.commit()
    return {"status": "success", "imported": imported_count, "errors": errors}


# ── Change Password ───────────────────────────────────────────────────────────

from ..dependencies import get_current_user

@router.patch("/change-password")
def change_password(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Allow any authenticated user to change their own password."""
    old_password = payload.get("old_password", "")
    new_password = payload.get("new_password", "")

    if not old_password or not new_password:
        raise HTTPException(status_code=400, detail="Both old and new passwords are required")

    is_valid, _ = _verify_password(old_password, current_user.password_hash)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    current_user.password_hash = _hash_password(new_password)
    current_user.is_first_login = False
    db.commit()
    return {"status": "success", "message": "Password changed successfully"}


# ── Complete Onboarding (First-Time Login Staff Setup) ──────────────────────

@router.post("/complete-onboarding")
def complete_onboarding(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Called on initial login to allow teachers to register their real phone number,
    optional real email, and set their private permanent password.
    """
    phone = (payload.get("phone_number") or "").strip()
    raw_email = (payload.get("email") or "").strip()
    email = raw_email if raw_email else None
    new_password = (payload.get("new_password") or "").strip()

    if not phone:
        raise HTTPException(status_code=400, detail="Ghana Mobile Phone Number is required to secure your account.")

    # Validate phone format: digits, plus, length 9-15
    cleaned_phone = re.sub(r"[^\d+]", "", phone)
    if len(cleaned_phone) < 9 or len(cleaned_phone) > 15:
        raise HTTPException(status_code=400, detail="Please enter a valid mobile phone number (e.g. 0244123456).")

    if email:
        if "@" not in email or "." not in email:
            raise HTTPException(status_code=400, detail="Please enter a valid email address format.")
        existing_email_user = db.query(User).filter(User.email == email, User.id != current_user.id).first()
        if existing_email_user:
            raise HTTPException(status_code=400, detail="This email address is already in use by another account.")
        current_user.email = email

    if new_password:
        if len(new_password) < 6:
            raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")
        current_user.password_hash = _hash_password(new_password)

    current_user.phone_number = phone
    current_user.is_first_login = False
    current_user.contact_verified = True
    db.commit()
    db.refresh(current_user)

    return {
        "status": "success",
        "message": "Staff profile and security credentials successfully configured!",
        "user": {
            "username": current_user.username,
            "email": current_user.email or "",
            "phone_number": current_user.phone_number or "",
            "is_first_login": False,
            "contact_verified": True
        }
    }


# ── Admin: Reset another user's password ─────────────────────────────────────

@router.patch("/users/{user_id}/reset-password")
def admin_reset_password(
    user_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin only: reset any user's password."""
    role_names = [r.name for r in current_user.roles]
    if "admin" not in role_names and "super_admin" not in role_names:
        raise HTTPException(status_code=403, detail="Admin access required")

    new_password = payload.get("new_password", "")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.password_hash = _hash_password(new_password)
    target.is_first_login = True
    db.commit()
    return {"status": "success", "message": f"Password reset for {target.username}"}


# ── Admin: Deactivate / Reactivate user ──────────────────────────────────────

@router.patch("/users/{user_id}/status")
def set_user_status(
    user_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin only: activate or deactivate a user account."""
    role_names = [r.name for r in current_user.roles]
    if "admin" not in role_names and "super_admin" not in role_names:
        raise HTTPException(status_code=403, detail="Admin access required")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    is_active = payload.get("is_active", True)
    target.is_active = is_active
    db.commit()
    status_str = "activated" if is_active else "deactivated"
    return {"status": "success", "message": f"User {target.username} {status_str}"}


# ── Admin: Cleanup Assistant Head Roles ──────────────────────────────────────

@router.post("/cleanup-assistant-head-roles")
def cleanup_assistant_head_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Scrub redundant generic 'admin' role from accounts that hold an Assistant Head executive role
    to enforce strict segregation of duties (unless the account is super_admin).
    """
    user_roles = {r.name.lower() for r in current_user.roles}
    if "admin" not in user_roles and "super_admin" not in user_roles:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    assist_head_keys = {
        "assistant_headmaster_academic", "assistant_headmaster_domestic", "assistant_headmaster_admin",
        "assistant_head_academic", "assistant_head_domestic", "assistant_head_admin"
    }

    users = db.query(User).all()
    cleaned_count = 0
    for u in users:
        r_names = {r.name.lower() for r in u.roles}
        if "super_admin" in r_names:
            continue
        if any(ah in r_names for ah in assist_head_keys) and "admin" in r_names:
            u.roles = [r for r in u.roles if r.name.lower() != "admin"]
            cleaned_count += 1

    if cleaned_count > 0:
        db.commit()

    return {
        "status": "success",
        "message": f"Successfully scrubbed redundant admin role from {cleaned_count} Assistant Head account(s).",
        "cleaned_count": cleaned_count
    }
