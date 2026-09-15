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
from ..database import get_db
from ..models import User, Role, School, ClassSection, House, Department, Student, UserDeviceSession
from ..services.auth import create_jwt, decode_jwt, hash_password, verify_password
from ..services.audit_service import record_audit_event
from .. import schemas
from ..services.guardian_service import link_students_for_parent_user
from ..dependencies import rate_limit_auth, get_current_user, get_school_id

router = APIRouter()

DEFAULT_ROLES = ["super_admin", "admin", "proprietor", "headmaster", "headmistress", "assistant_headmaster_academic", "assistant_headmaster_domestic", "assistant_headmaster_admin", "school_administrator", "ict_coordinator", "bursar", "secretary", "teacher", "student", "parent", "form_master", "form_mistress", "house_master", "house_mistress", "senior_housemaster", "senior_housemistress", "hod", "assistant_house_master", "assistant_house_mistress", "storekeeper", "security_officer"]

# Default master user for seeding
DEFAULT_USER_TEMPLATES = [
    {"username": "superadmin", "email": "superadmin@system.local", "roles": ["super_admin"]},
]

def _legacy_sha256_hash(password: str) -> str:
    """Retained strictly for legacy verification and migration testing."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def _hash_password(password: str) -> str:
    """Produces modern secure bcrypt password hashes; refuses silent insecure fallbacks."""
    return hash_password(password)

get_password_hash = _hash_password
_verify_password = verify_password

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
        env_mode = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
        is_production = env_mode in ("production", "prod")

        # In production, require INITIAL_SUPERADMIN_PASSWORD; never create universal defaults
        bootstrap_pwd = os.getenv("INITIAL_SUPERADMIN_PASSWORD", "").strip()
        if not bootstrap_pwd:
            if is_production:
                bootstrap_pwd = None
            else:
                bootstrap_pwd = "superadmin123!"

        for user_data in DEFAULT_USER_TEMPLATES:
            existing = db.query(User).filter(User.username == user_data["username"]).first()
            target_roles = [roles_map[r] for r in user_data["roles"] if r in roles_map]

            if not existing:
                if bootstrap_pwd:
                    new_user = User(
                        username=user_data["username"],
                        email=user_data["email"],
                        password_hash=_hash_password(bootstrap_pwd),
                        school_id=None,
                        is_active=True,
                        is_first_login=True,
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
            (User.is_active == True) | (User.is_active == "1") | (User.is_active.is_(None))
        ).first()

        if not user:
            return JSONResponse(status_code=401, content={"detail": "Invalid username or password"})

        is_valid, needs_rehash = _verify_password(password, user.password_hash)
        if not is_valid:
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
            "roles": role_names,
            "token_version": getattr(user, "token_version", 1) or 1
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
        
        # Record forensic audit event with client device detection
        try:
            record_audit_event(
                db=db,
                request=request,
                actor=user,
                action="USER_LOGIN",
                details=f"User {user.username} successfully signed in ({primary_role})",
                entity_type="User",
                entity_id=str(user.id),
                school_id=school_id,
                is_super_admin_action=is_super_admin
            )
        except Exception as audit_err:
            print("Audit event record warning:", audit_err)

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
                "staff_id": getattr(user, "staff_id", None) or "",
                "email": user.email or "",
                "ownership_type": school.ownership_type if (not is_super_admin and school) else "PRIVATE",
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
        "staff_id": getattr(current_user, "staff_id", None) or "",
        "is_first_login": bool(getattr(current_user, "is_first_login", False)),
        "contact_verified": bool(getattr(current_user, "contact_verified", False)),
        "primary_role": primary_role,
        "roles": role_names,
        "is_super_admin": "super_admin" in role_names,
    }

@router.post("/logout")
def logout(
    request: Request,
    authorization: str = Header(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Terminates the current device session on the server.
    Marks the active UserDeviceSession as inactive and logs a forensic USER_LOGOUT audit event.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        try:
            db.query(UserDeviceSession).filter(
                UserDeviceSession.session_token_hash == token_digest,
                UserDeviceSession.user_id == current_user.id
            ).update({"is_active": False}, synchronize_session=False)
        except Exception:
            pass

    # Record forensic audit event
    record_audit_event(
        db=db,
        request=request,
        actor=current_user,
        action="USER_LOGOUT",
        details=f"User {current_user.username} successfully logged out.",
        entity_type="User",
        entity_id=str(current_user.id),
        school_id=current_user.school_id
    )

    db.commit()
    return {"status": "success", "message": "Successfully logged out"}

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

    if "super_admin" not in user_roles:
        if target_user.school_id != current_user.school_id:
            raise HTTPException(
                status_code=403, 
                detail="Access Denied: You cannot impersonate staff from another institution."
            )

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
        "impersonator_username": current_user.username,
        "token_version": getattr(target_user, "token_version", 1) or 1
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

    current_roles = [r.name.lower() for r in current_user.roles] if hasattr(current_user, "roles") and current_user.roles else []
    is_super_admin = "super_admin" in current_roles

    if is_super_admin:
        target_sch_id = int(school_id) if isinstance(school_id, (int, float)) else None
        if target_sch_id is None and isinstance(x_school_id, str) and x_school_id.strip():
            try:
                target_sch_id = int(x_school_id.strip())
            except ValueError:
                pass
    else:
        # Prompt 1 Requirement 5: Do not trust client-supplied X-School-Id for ordinary admins.
        target_sch_id = current_user.school_id

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
    caller_roles = [r.name.lower() for r in current_user.roles] if hasattr(current_user, "roles") and current_user.roles else []
    is_super_admin = "super_admin" in caller_roles

    if is_super_admin:
        target_sch_id = int(school_id) if isinstance(school_id, (int, float)) else None
        if target_sch_id is None and isinstance(x_school_id, str) and x_school_id.strip():
            try:
                target_sch_id = int(x_school_id.strip())
            except ValueError:
                pass
        elif target_sch_id is None and payload.get("school_id"):
            try:
                target_sch_id = int(payload.get("school_id"))
            except (ValueError, TypeError):
                pass
    else:
        # Prompt 1: Ordinary school admins can only create accounts within their own school
        target_sch_id = current_user.school_id

    username = (payload.get("username") or "").strip()
    raw_email = (payload.get("email") or "").strip()
    email = raw_email if raw_email else None
    raw_phone = (payload.get("phone_number") or "").strip()
    phone_number = raw_phone if raw_phone else None
    raw_staff_id = (payload.get("staff_id") or "").strip()
    staff_id = raw_staff_id if raw_staff_id else None
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
        staff_id=staff_id,
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

def _verify_managed_user_access(
    current_user: User,
    target_user: Optional[User],
    operation_name: str = "manage"
) -> User:
    """
    Enforces multi-tenant authorization boundary on user-management operations:
    1. Caller must have 'admin' or 'super_admin' role.
    2. If target_user is None, raise 404 (User not found).
    3. Super Admins may manage users across all schools.
    4. Ordinary School Admins must only manage users belonging to their own school (current_user.school_id).
       If target_user belongs to another school (or is a root system user without school), return 404
       to avoid leaking user existence across tenants.
    5. Ordinary Admins cannot modify, reset, or delete Super Admin accounts.
    """
    caller_roles = [r.name.lower() for r in current_user.roles] if current_user.roles else []
    is_super = "super_admin" in caller_roles
    is_admin = "admin" in caller_roles or is_super

    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_roles = [r.name.lower() for r in target_user.roles] if target_user.roles else []

    if not is_super:
        # Ordinary admins can NEVER modify, delete, or reset super_admin accounts
        if "super_admin" in target_roles or (target_user.username and target_user.username.lower() == "superadmin"):
            raise HTTPException(status_code=403, detail="Only Super-Admin can manage super_admin accounts")

        # Tenant boundary: Ordinary admin must belong to a school and match target user's school_id
        if current_user.school_id is None or target_user.school_id != current_user.school_id:
            # Return 404 to prevent cross-school user enumeration
            raise HTTPException(status_code=404, detail="User not found")

    return target_user

@router.put("/users/{user_id}/roles")
def update_user_roles(
    user_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin/Super-Admin only: update assigned roles for a user."""
    target = db.query(User).filter(User.id == user_id).first()
    _verify_managed_user_access(current_user, target, "update roles")

    role_names_caller = [r.name.lower() for r in current_user.roles] if current_user.roles else []
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
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    target = db.query(User).filter(User.id == user_id).first()
    _verify_managed_user_access(current_user, target, "delete user")

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
    "proprietor": "proprietor",
    "proprietress": "proprietor",
    "school owner": "proprietor",
    "board": "proprietor",
    "board of directors": "proprietor",
    "school administrator": "school_administrator",
    "school_administrator": "school_administrator",
    "school admin officer": "school_administrator",
    "school_admin_officer": "school_administrator",
    "administrative officer": "school_administrator",
    "administrative_officer": "school_administrator",
    "admin officer": "school_administrator",
    "admin_officer": "school_administrator",
    "ict coordinator": "ict_coordinator",
    "ict_coordinator": "ict_coordinator",
    "it coordinator": "ict_coordinator",
    "it_coordinator": "ict_coordinator",
    "school it officer": "ict_coordinator",
    "school_it_officer": "ict_coordinator",
    "system admin": "ict_coordinator",
    "system_admin": "ict_coordinator",
    "ict director": "ict_coordinator",
    "ict_director": "ict_coordinator",
    "secretary": "secretary",
    "school secretary": "secretary",
    "school_secretary": "secretary",
    "admissions officer": "secretary",
    "admissions_officer": "secretary",
    "registrar": "secretary",
    "principal": "headmaster",
    "headmaster": "headmaster",
    "headmistress": "headmistress",
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
def list_roles(
    db: Session = Depends(get_db),
    school_id: Optional[int] = Depends(get_school_id),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id")
):
    target_sch_id = int(school_id) if isinstance(school_id, (int, float)) else None
    if target_sch_id is None and isinstance(x_school_id, str) and x_school_id.strip():
        try:
            target_sch_id = int(x_school_id.strip())
        except ValueError:
            pass

    # Ensure core roles exist
    core_roles = [
        "super_admin", "admin", "proprietor", "headmaster", "headmistress",
        "assistant_headmaster_academic", "assistant_headmaster_admin", "assistant_headmaster_domestic",
        "school_administrator", "ict_coordinator", "bursar", "secretary",
        "teacher", "form_master", "form_mistress", "hod",
        "senior_house_master", "senior_house_mistress", "house_master", "house_mistress",
        "assistant_house_master", "assistant_house_mistress", "storekeeper", "security_officer",
        "parent", "student"
    ]
    existing_roles = {r.name.lower(): r for r in db.query(Role).all()}
    for r_name in core_roles:
        if r_name not in existing_roles:
            try:
                new_r = Role(name=r_name)
                db.add(new_r)
                db.commit()
            except Exception:
                db.rollback()

    roles = db.query(Role).order_by(Role.id).all()

    # Filter out proprietor if school is public
    if target_sch_id:
        sch = db.query(School).filter(School.id == target_sch_id).first()
        if sch and (sch.ownership_type or "").upper() == "PUBLIC":
            roles = [r for r in roles if r.name.lower() != "proprietor"]

    return roles

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
async def import_users_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    school_id: Optional[int] = Depends(get_school_id),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id")
):
    caller_roles = [r.name.lower() for r in current_user.roles] if current_user.roles else []
    is_super = "super_admin" in caller_roles
    is_admin = "admin" in caller_roles or is_super
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    if is_super:
        target_sch_id = int(school_id) if isinstance(school_id, (int, float)) else None
        if target_sch_id is None and isinstance(x_school_id, str) and x_school_id.strip():
            try:
                target_sch_id = int(x_school_id.strip())
            except ValueError:
                pass
    else:
        target_sch_id = current_user.school_id

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
            
            # Non-super-admins cannot grant super_admin or admin via CSV
            if not is_super:
                assigned_roles = [r for r in assigned_roles if r.name.lower() not in ["super_admin", "admin", "headmaster", "headmistress"]]

            if not assigned_roles and default_role:
                assigned_roles.append(default_role)

            new_user = User(
                username=username,
                email=email,
                password_hash=_hash_password(raw_password),
                gender=gender,
                is_active=True,
                school_id=target_sch_id
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
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Allow any authenticated user to change their own password."""
    old_password = payload.get("old_password", "")
    new_password = (payload.get("new_password") or "").strip()

    if not old_password or not new_password:
        raise HTTPException(status_code=400, detail="Both old and new passwords are required")

    is_valid, _ = _verify_password(old_password, current_user.password_hash)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    current_user.password_hash = _hash_password(new_password)
    current_user.is_first_login = False
    current_user.token_version = (getattr(current_user, "token_version", 1) or 1) + 1

    # Invalidate active device sessions for this user
    try:
        db.query(UserDeviceSession).filter(UserDeviceSession.user_id == current_user.id).update(
            {"is_active": False}, synchronize_session=False
        )
    except Exception:
        pass

    # Record audit event
    record_audit_event(
        db,
        request=request,
        actor=current_user,
        action="PASSWORD_CHANGED",
        details=f"User {current_user.username} successfully changed their password.",
        entity_type="User",
        entity_id=str(current_user.id),
        school_id=current_user.school_id
    )

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
    raw_staff_id = (payload.get("staff_id") or "").strip()
    new_password = (payload.get("new_password") or "").strip()

    if not phone:
        raise HTTPException(status_code=400, detail="Mobile Phone Number is required to secure your account.")

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

    if raw_staff_id:
        current_user.staff_id = raw_staff_id

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
            "staff_id": current_user.staff_id or "",
            "is_first_login": False,
            "contact_verified": True
        }
    }


# ── Admin: Reset another user's password ─────────────────────────────────────

@router.patch("/users/{user_id}/reset-password")
def admin_reset_password(
    user_id: int,
    payload: dict,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin only: reset any user's password."""
    target = db.query(User).filter(User.id == user_id).first()
    _verify_managed_user_access(current_user, target, "reset password")

    new_password = (payload.get("new_password") or "").strip()
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    target.password_hash = _hash_password(new_password)
    target.is_first_login = True
    target.token_version = (getattr(target, "token_version", 1) or 1) + 1

    # Invalidate active device sessions for target user
    try:
        db.query(UserDeviceSession).filter(UserDeviceSession.user_id == target.id).update(
            {"is_active": False}, synchronize_session=False
        )
    except Exception:
        pass

    # Record forensic audit event
    record_audit_event(
        db,
        request=request,
        actor=current_user,
        action="ADMIN_RESET_PASSWORD",
        details=f"Admin {current_user.username} reset password for user {target.username} (ID: {target.id}).",
        entity_type="User",
        entity_id=str(target.id),
        school_id=target.school_id
    )

    db.commit()
    return {"status": "success", "message": f"Password reset for {target.username}"}


# ── Admin: Deactivate / Reactivate user ──────────────────────────────────────

@router.patch("/users/{user_id}/status")
def set_user_status(
    user_id: int,
    payload: dict,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin only: activate or deactivate a user account."""
    target = db.query(User).filter(User.id == user_id).first()
    _verify_managed_user_access(current_user, target, "change status")

    is_active = payload.get("is_active", True)
    target.is_active = is_active

    # When deactivating, invalidate active device sessions and advance token version immediately
    if not is_active:
        target.token_version = (getattr(target, "token_version", 1) or 1) + 1
        try:
            db.query(UserDeviceSession).filter(UserDeviceSession.user_id == target.id).update(
                {"is_active": False}, synchronize_session=False
            )
        except Exception:
            pass

    status_str = "activated" if is_active else "deactivated"

    # Record forensic audit event
    record_audit_event(
        db,
        request=request,
        actor=current_user,
        action="USER_STATUS_CHANGE",
        details=f"Admin {current_user.username} {status_str} account for user {target.username} (ID: {target.id}).",
        entity_type="User",
        entity_id=str(target.id),
        school_id=target.school_id
    )

    db.commit()
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


# ── Enterprise Offline Self-Service Password Recovery Engine ───────────────────
import time
import uuid
import hmac

_recovery_rate_limit = {}  # {client_key: {"attempts": [...], "locked_until": float}}
_used_recovery_jtis = set()  # Revoked single-use reset token nonces

def _get_client_recovery_key(request: Request, username: str) -> str:
    client_ip = request.client.host if request.client else "127.0.0.1"
    clean_user = (username or "").strip().lower()
    return f"{client_ip}:{clean_user}"

def _check_recovery_rate_limit(client_key: str) -> None:
    now = time.time()
    record = _recovery_rate_limit.get(client_key, {"attempts": [], "locked_until": 0})
    if record["locked_until"] > now:
        remaining_mins = max(1, int((record["locked_until"] - now) / 60))
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Recovery locked for {remaining_mins} minute(s) for security."
        )
    # Filter attempts in last 15 minutes (900 seconds)
    record["attempts"] = [t for t in record["attempts"] if (now - t) < 900]
    if len(record["attempts"]) >= 5:
        record["locked_until"] = now + 1800  # 30-minute lockout
        _recovery_rate_limit[client_key] = record
        raise HTTPException(
            status_code=429,
            detail="Too many failed verification attempts. Account recovery locked for 30 minutes for security."
        )
    _recovery_rate_limit[client_key] = record

def _record_recovery_failure(client_key: str) -> None:
    now = time.time()
    record = _recovery_rate_limit.get(client_key, {"attempts": [], "locked_until": 0})
    record["attempts"].append(now)
    if len(record["attempts"]) >= 5:
        record["locked_until"] = now + 1800
    _recovery_rate_limit[client_key] = record

def _clear_recovery_rate_limit(client_key: str) -> None:
    if client_key in _recovery_rate_limit:
        del _recovery_rate_limit[client_key]

def _normalize_phone(phone: Optional[str]) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if digits.startswith("233") and len(digits) == 12:
        digits = "0" + digits[3:]
    return digits


@router.post("/forgot-password/verify")
def verify_forgot_password_identity(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Enterprise Offline Identity Verification for Self-Service Password Reset.
    Validates Username/Email + Registered Phone + Secondary Verification (Staff ID / DOB / PIN / Security Answer).
    Enforces sliding-window rate limiting, timing-attack resistance, and role-based privilege checks.
    """
    username_raw = (payload.get("username") or "").strip()
    phone_raw = (payload.get("phone_number") or "").strip()
    identifier_raw = (payload.get("identifier") or "").strip()
    recovery_pin_raw = (payload.get("recovery_pin") or "").strip()
    recovery_answer_raw = (payload.get("recovery_answer") or "").strip()

    if not username_raw:
        raise HTTPException(status_code=400, detail="Username or email is required.")

    client_key = _get_client_recovery_key(request, username_raw)
    _check_recovery_rate_limit(client_key)

    # 1. Lookup User by username or email
    user = db.query(User).filter(func.lower(User.username) == username_raw.lower()).first()
    if not user and "@" in username_raw:
        user = db.query(User).filter(func.lower(User.email) == username_raw.lower()).first()

    # Timing attack defense: compute dummy hash verification if user not found
    if not user:
        _verify_password("dummy_password_timing_defense", "$2b$12$ASt15rUBYvNa3mT/KQ8LUOOlTQrett/pL/NCLK6QDw3.Hsciw3csm")
        _record_recovery_failure(client_key)
        raise HTTPException(status_code=400, detail="Invalid verification details. Please verify your identity credentials.")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is deactivated. Please contact your school administrator.")

    input_phone_clean = _normalize_phone(phone_raw)
    user_phone_clean = _normalize_phone(user.phone_number)
    
    # 2. Phone Verification
    phone_matched = False
    if input_phone_clean and user_phone_clean and input_phone_clean == user_phone_clean:
        phone_matched = True
    
    # Check student / parent phone records if not matched directly on user record
    if not phone_matched and input_phone_clean:
        student_records = db.query(Student).filter(
            (Student.parent_id == user.id) | (func.lower(Student.student_code) == username_raw.lower())
        ).all()
        for st in student_records:
            if _normalize_phone(st.phone) == input_phone_clean:
                phone_matched = True
                break

    # 3. Secondary Identifier / Secret Verification
    secondary_matched = False
    
    # Check Recovery PIN if user configured one
    if user.recovery_pin_hash:
        test_pin = recovery_pin_raw or identifier_raw
        if test_pin and _verify_password(test_pin, user.recovery_pin_hash)[0]:
            secondary_matched = True

    # Check Security Answer if user configured one
    if not secondary_matched and user.recovery_answer_hash:
        test_ans = (recovery_answer_raw or identifier_raw).strip().lower()
        if test_ans and _verify_password(test_ans, user.recovery_answer_hash)[0]:
            secondary_matched = True

    # Check Staff ID for teachers & staff
    if not secondary_matched and user.staff_id and identifier_raw:
        if user.staff_id.strip().lower() == identifier_raw.lower():
            secondary_matched = True

    # Check Student DOB / Index Number / Enrolment Code for students & parents
    if not secondary_matched and identifier_raw:
        student_records = db.query(Student).filter(
            (Student.parent_id == user.id) | (func.lower(Student.student_code) == username_raw.lower())
        ).all()
        clean_ident = identifier_raw.strip().lower().replace("/", "-")
        for st in student_records:
            dob_str = str(st.date_of_birth or "").replace("/", "-")
            if (st.bece_index_number and st.bece_index_number.lower() == clean_ident) or \
               (st.enrolment_code and st.enrolment_code.lower() == clean_ident) or \
               (st.student_code and st.student_code.lower() == clean_ident) or \
               (dob_str and clean_ident in dob_str):
                secondary_matched = True
                break

    # Fallback for initial unconfigured accounts if phone matches
    user_roles = [r.name.lower() for r in user.roles] if user.roles else []
    is_high_privilege = any(r in {"super_admin", "admin", "bursar", "proprietor", "headmaster", "headmistress", "school_administrator"} for r in user_roles)

    if not is_high_privilege and phone_matched and (not user.staff_id and not user.recovery_pin_hash and not user.recovery_answer_hash):
        # Regular teacher without staff ID entered yet: phone match is accepted
        secondary_matched = True

    if not (phone_matched and secondary_matched):
        _record_recovery_failure(client_key)
        raise HTTPException(status_code=400, detail="Identity verification failed. Please check your phone number and identification.")

    # 4. Identity Verified -> Clear rate limit & Issue short-lived, single-use JWT Reset Token
    _clear_recovery_rate_limit(client_key)
    reset_jti = uuid.uuid4().hex
    
    reset_token = create_jwt(
        payload={
            "sub": str(user.id),
            "user_id": user.id,
            "username": user.username,
            "scope": "password_reset",
            "jti": reset_jti,
            "token_version": getattr(user, "token_version", 1) or 1
        },
        expires_in=600  # 10 minutes expiry
    )

    return {
        "status": "success",
        "message": "Identity verified successfully. You may now set a new password.",
        "reset_token": reset_token,
        "username": user.username,
        "requires_pin_setup": not bool(user.recovery_pin_hash)
    }


@router.post("/forgot-password/reset")
def reset_forgot_password(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Consumes single-use reset token to securely set a new password.
    Burns the token nonce, invalidates all existing active device sessions, and records audit telemetry.
    """
    reset_token = (payload.get("reset_token") or "").strip()
    new_password = (payload.get("new_password") or "").strip()
    confirm_password = (payload.get("confirm_password") or "").strip()

    if not reset_token:
        raise HTTPException(status_code=400, detail="Missing password reset token.")

    if not new_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters long.")

    if confirm_password and new_password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    try:
        token_payload = decode_jwt(reset_token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired reset token: {str(e)}")

    if token_payload.get("scope") != "password_reset":
        raise HTTPException(status_code=403, detail="Invalid token scope for password reset.")

    jti = token_payload.get("jti")
    if not jti or jti in _used_recovery_jtis:
        raise HTTPException(status_code=401, detail="This reset token has already been used. Please request a new one.")

    # Burn token nonce immediately
    _used_recovery_jtis.add(jti)

    user_id = token_payload.get("user_id")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    # Update password and advance token version to revoke previous sessions
    user.password_hash = _hash_password(new_password)
    user.is_first_login = False
    user.token_version = (getattr(user, "token_version", 1) or 1) + 1

    # Invalidate all active device sessions for this user
    try:
        db.query(UserDeviceSession).filter(UserDeviceSession.user_id == user.id).delete(synchronize_session=False)
    except Exception:
        pass

    # Record immutable audit event
    record_audit_event(
        db,
        request=request,
        actor=user,
        action="PASSWORD_RESET_SELF_SERVICE",
        details=f"User {user.username} successfully self-reset password via offline identity verification.",
        entity_type="User",
        entity_id=str(user.id),
        school_id=user.school_id
    )

    db.commit()

    return {
        "status": "success",
        "message": "Password successfully updated! You can now log in with your new password."
    }


# ── Authenticated User: Recovery Profile Settings ─────────────────────────────

@router.get("/profile/recovery-settings")
def get_user_recovery_settings(
    current_user: User = Depends(get_current_user)
):
    """Returns recovery configuration status for the currently authenticated user."""
    return {
        "status": "success",
        "username": current_user.username,
        "phone_number": current_user.phone_number or "",
        "staff_id": current_user.staff_id or "",
        "has_recovery_question": bool(current_user.recovery_question and current_user.recovery_answer_hash),
        "recovery_question": current_user.recovery_question or "",
        "has_recovery_pin": bool(current_user.recovery_pin_hash)
    }


@router.post("/profile/recovery-settings")
def update_user_recovery_settings(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Allows user to set or update their secret Recovery PIN and Security Question/Answer."""
    phone_number = payload.get("phone_number")
    staff_id = payload.get("staff_id")
    recovery_question = (payload.get("recovery_question") or "").strip()
    recovery_answer = (payload.get("recovery_answer") or "").strip()
    recovery_pin = (payload.get("recovery_pin") or "").strip()

    if phone_number is not None:
        current_user.phone_number = str(phone_number).strip()

    if staff_id is not None:
        current_user.staff_id = str(staff_id).strip()

    if recovery_question:
        current_user.recovery_question = recovery_question
        if recovery_answer:
            current_user.recovery_answer_hash = _hash_password(recovery_answer.lower())

    if recovery_pin:
        if not (recovery_pin.isdigit() and 4 <= len(recovery_pin) <= 8):
            raise HTTPException(status_code=400, detail="Recovery PIN must be 4 to 8 digits.")
        current_user.recovery_pin_hash = _hash_password(recovery_pin)

    db.commit()
    return {
        "status": "success",
        "message": "Recovery settings updated successfully."
    }

