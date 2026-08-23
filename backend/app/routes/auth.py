import hashlib
import secrets
import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
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

from passlib.context import CryptContext
from ..database import get_db
from ..models import User, Role, School, ClassSection, House, Department
from ..services.auth import create_jwt
from .. import schemas
from ..services.guardian_service import link_students_for_parent_user
from ..dependencies import rate_limit_auth, get_current_user

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEFAULT_ROLES = ["admin", "teacher", "student", "parent", "form_master", "form_mistress", "house_master", "house_mistress", "senior_housemaster", "senior_housemistress", "hod", "assistant_house_master", "assistant_house_mistress", "assistant_headmaster_academic", "assistant_headmaster_domestic", "assistant_headmaster_admin", "bursar", "storekeeper", "security_officer"]

# Default user roles for seeding (passwords are randomly generated on first install)
DEFAULT_USER_TEMPLATES = [
    {"username": "superadmin", "email": "superadmin@system.local", "roles": ["super_admin"]},
    {"username": "admin", "email": "admin@school.local", "roles": ["admin"]},
    {"username": "teacher", "email": "teacher@school.local", "roles": ["teacher"]},
]

def _hash_password(password: str) -> str:
    return pwd_context.hash(password)

get_password_hash = _hash_password

def _legacy_sha256_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

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
        # Seed roles
        roles_map = {}
        for role_name in DEFAULT_ROLES:
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                role = Role(name=role_name)
                db.add(role)
                db.flush()
            roles_map[role_name] = role

        # Seed users — generate random passwords on first install only
        first_run_entries = []
        for user_data in DEFAULT_USER_TEMPLATES:
            existing = db.query(User).filter(User.username == user_data["username"]).first()
            if not existing:
                random_password = secrets.token_urlsafe(12)
                new_user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    password_hash=_hash_password(random_password),
                    is_active=True,
                )
                for role_name in user_data["roles"]:
                    if role_name in roles_map:
                        new_user.roles.append(roles_map[role_name])
                db.add(new_user)
                first_run_entries.append(f"  {user_data['username']}: {random_password}")
        db.commit()

        # Write first-run credentials to file so admin can find them
        if first_run_entries:
            BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            creds_path = os.path.join(BASE_DIR, "first_run_credentials.txt")
            with open(creds_path, "w") as f:
                f.write("SMS First-Run Credentials\n")
                f.write("=" * 40 + "\n")
                f.write("These are your auto-generated login passwords.\n")
                f.write("IMPORTANT: Change these after your first login!\n")
                f.write("DELETE this file once you have saved the passwords.\n")
                f.write("=" * 40 + "\n\n")
                f.write("\n".join(first_run_entries) + "\n")
    except Exception as e:
        db.rollback()


@router.post("/login", dependencies=[Depends(rate_limit_auth)])
def login(payload: dict, db: Session = Depends(get_db)):
    username = (payload or {}).get("username", "").strip()
    password = (payload or {}).get("password", "")

    if not username or not password:
        return JSONResponse(status_code=401, content={"detail": "Invalid username or password"})

    _seed_db(db)

    user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Invalid username or password"})

    is_valid, needs_rehash = _verify_password(password, user.password_hash)
    if not is_valid:
        return JSONResponse(status_code=401, content={"detail": "Invalid username or password"})

    # Transparently upgrade legacy SHA-256 hashes to bcrypt on successful login
    if needs_rehash:
        user.password_hash = _hash_password(password)
        db.commit()

    # Return primary role for UI dashboard routing (first role in list)
    primary_role = user.roles[0].name if user.roles else "teacher"
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

    is_super_admin = "super_admin" in role_names
    
    if is_super_admin:
        school_mode = "COMBINED"
        school_name = "Master System Portal"
        school_id = None
    else:
        school = user.school
        if not school and user.school_id:
            school = db.query(School).filter(School.id == user.school_id).first()
        if not school:
            school = db.query(School).filter(School.id == 1).first()

        school_mode = school.school_mode if school else "COMBINED"
        school_name = school.name if school else "School System"
        school_id = school.id if school else 1

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
            "access_token": token,
            "token_type": "bearer"
        },
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
        "email": current_user.email,
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
    admin_roles = {'admin', 'super_admin', 'headmaster', 'headmistress', 'assistant_headmaster_academic', 'assistant_head_academic', 'assistant_headmaster_admin', 'assistant_head_admin'}
    user_roles = {r.name.lower() for r in current_user.roles}
    if not user_roles.intersection(admin_roles):
        raise HTTPException(status_code=403, detail="Only administrators can impersonate users")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User to impersonate not found")

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
def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from ..dependencies import get_user_assigned_scope, get_school_id
    from ..models import TeacherAssignment, Department, Role
    school_id = get_school_id(current_user)
    
    current_roles = [r.name.lower() for r in current_user.roles] if hasattr(current_user, "roles") and current_user.roles else []
    is_super_admin = "super_admin" in current_roles

    query = db.query(User)

    super_role = db.query(Role).filter(Role.name == "super_admin").first()

    if is_super_admin:
        if school_id is not None:
            # Viewing a specific school tenant: filter to that school's users
            query = query.filter(User.school_id == school_id)
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
        
        target_school_id = school_id if school_id is not None else (current_user.school_id if current_user.school_id is not None else 1)
        query = query.filter(User.school_id == target_school_id)

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

    return query.all()

@router.post("/users", dependencies=[Depends(rate_limit_auth)])
def create_user(payload: dict, db: Session = Depends(get_db)):
    username = payload.get("username")
    email = payload.get("email")
    password = payload.get("password")
    gender = payload.get("gender")
    role_names = payload.get("roles", ["teacher"])

    # Enforce mutual exclusivity: Assistant Head executive roles strip generic admin
    assist_head_keys = {
        "assistant_headmaster_academic", "assistant_headmaster_domestic", "assistant_headmaster_admin",
        "assistant_head_academic", "assistant_head_domestic", "assistant_head_admin"
    }
    if any(r in assist_head_keys for r in role_names) and "super_admin" not in role_names and "admin" in role_names:
        role_names = [r for r in role_names if r != "admin"]

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already exists")

    new_user = User(
        username=username,
        email=email,
        password_hash=_hash_password(password),
        gender=gender,
        is_active=True
    )
    
    for r_name in role_names:
        role = db.query(Role).filter(Role.name == r_name).first()
        if role:
            new_user.roles.append(role)
            
    db.add(new_user)
    db.flush()
    link_students_for_parent_user(db, new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

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
            raw_password = clean_row.get("password") or clean_row.get("pass") or "Welcome123"

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
    db.commit()
    return {"status": "success", "message": "Password changed successfully"}


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
