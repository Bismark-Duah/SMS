from typing import Optional
from fastapi import Header, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from .database import get_db
from .models import User
from .services.auth import decode_jwt
from .middleware.device_session_guard import is_session_active

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    """
    Decodes JWT token from Authorization Bearer header to get the current user.
    Enforces multi-device zero-trust session validation.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in.")
        
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
        
    token = authorization.split(" ")[1]
    try:
        payload = decode_jwt(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")
        
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing user information")
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Multi-Device Zero-Trust Session Active Check
    if not is_session_active(token, user.id, db):
        raise HTTPException(status_code=401, detail="Session terminated: your account was logged in on another device.")

    return user


def get_current_user_optional(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> Optional[User]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        token = authorization.split(" ")[1]
        payload = decode_jwt(token)
        user_id = payload.get("user_id")
        if not user_id:
            return None
        return db.query(User).filter(User.id == user_id).first()
    except Exception:
        return None


from .middleware.tenant_subdomain import get_current_request_school_id

def get_school_id(
    current_user: Optional[User] = Depends(get_current_user_optional),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id"),
    request: Request = None
) -> Optional[int]:
    """
    Returns the school_id to scope all database queries for multi-tenancy.
    Zero-Trust Security Enforcement:
    1. If user is NOT a super_admin, STRICTLY lock queries to current_user.school_id (rejects spoofed X-School-Id).
    2. If user IS a super_admin, permit tenant switching via X-School-Id or Subdomain State.
    3. If unauthenticated (e.g. public branding/portal), allow X-School-Id or Subdomain State.
    """
    user = current_user if isinstance(current_user, User) else None
    if user:
        role_names = [r.name for r in user.roles] if hasattr(user, 'roles') else []
        is_super = "super_admin" in role_names

        # 1. Non-super admin is locked strictly to their school (BOLA / IDOR Defense)
        if not is_super:
            return user.school_id

    # 2. Super Admin or unauthenticated public requests: Check X-School-Id Header first
    if isinstance(x_school_id, str) and x_school_id.strip():
        try:
            return int(x_school_id.strip())
        except ValueError:
            pass
    elif isinstance(x_school_id, (int, float)):
        return int(x_school_id)

    # 3. Check ContextVar set by TenantSubdomainMiddleware
    ctx_id = get_current_request_school_id()
    if ctx_id is not None:
        return ctx_id

    # 4. Check Subdomain Middleware state
    req = request if hasattr(request, "state") else (current_user if hasattr(current_user, "state") else None)
    if req and hasattr(req, "state") and getattr(req.state, "school_id", None):
        return req.state.school_id

    return getattr(user, "school_id", None) if user else None


# ── In-Memory Rate Limiter (Brute-Force Protection) ──────────────────────────

import time
from collections import defaultdict
from fastapi import Request

class InMemoryRateLimiter:
    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

    def check_rate_limit(self, client_ip: str):
        now = time.time()
        # Clean up expired timestamps
        self.requests[client_ip] = [
            ts for ts in self.requests[client_ip] if now - ts < self.window_seconds
        ]
        if len(self.requests[client_ip]) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Too many login attempts. Maximum {self.max_requests} attempts per minute allowed."
            )
        self.requests[client_ip].append(now)


def get_user_assigned_scope(user: User, db: Session) -> dict:
    """
    Returns a dictionary of assigned resource IDs for data scoping based on user roles and assignments.
    If the user has administrative/executive roles, is_admin is True.
    """
    if not user or not hasattr(user, 'id'):
        return {"is_admin": True, "class_ids": [], "subject_ids": [], "house_ids": [], "department_ids": []}

    role_names = [r.name.lower() for r in user.roles] if hasattr(user, 'roles') and user.roles else []
    admin_roles = {
        "admin", "super_admin", "headmaster", "headmistress",
        "assistant_headmaster_academic", "assistant_head_academic",
        "assistant_headmaster_admin", "assistant_head_admin",
        "assistant_headmaster_domestic", "assistant_head_domestic"
    }

    if any(r in admin_roles for r in role_names):
        return {"is_admin": True, "class_ids": [], "subject_ids": [], "house_ids": [], "department_ids": []}

    from .models import TeacherAssignment, ClassSection, House, Department

    # 1. Subject teaching assignments
    t_assignments = db.query(TeacherAssignment).filter(TeacherAssignment.teacher_id == user.id).all()
    class_ids = set(a.class_section_id for a in t_assignments if a.class_section_id)
    subject_ids = set(a.subject_id for a in t_assignments if a.subject_id)

    # 2. Form master classes
    form_sections = db.query(ClassSection).filter(ClassSection.form_master_id == user.id).all()
    for s in form_sections:
        class_ids.add(s.id)

    # 3. House master houses
    houses = db.query(House).filter(House.house_master_id == user.id).all()
    house_ids = [h.id for h in houses]

    # 4. Department HOD
    depts = db.query(Department).filter(Department.hod_id == user.id).all()
    dept_ids = [d.id for d in depts]

    return {
        "is_admin": False,
        "class_ids": list(class_ids),
        "subject_ids": list(subject_ids),
        "house_ids": list(house_ids),
        "department_ids": list(dept_ids),
    }


auth_rate_limiter = InMemoryRateLimiter(max_requests=5, window_seconds=60)

def rate_limit_auth(request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    auth_rate_limiter.check_rate_limit(client_ip)


# Roles that are treated as admins for daily class register authorization
ATTENDANCE_ADMIN_ROLES = {
    "admin", "super_admin", "headmaster", "headmistress",
    "assistant_headmaster_academic", "assistant_head_academic",
    "assistant_headmaster_admin", "assistant_head_admin",
    "assistant_headmaster_domestic", "assistant_head_domestic",
}


def get_form_master_class_ids(user, db) -> list[int]:
    """
    Returns the list of class section IDs where `user` is the assigned Form Master.
    Also returns all class IDs if the user has an admin/executive role.
    """
    from .models import ClassSection

    if not user:
        return []

    role_names = [r.name.lower() for r in user.roles] if hasattr(user, "roles") and user.roles else []

    if any(r in ATTENDANCE_ADMIN_ROLES for r in role_names):
        # Admins can mark any class — return None as a sentinel for "all classes"
        return None  # type: ignore[return-value]

    sections = db.query(ClassSection).filter(ClassSection.form_master_id == user.id).all()
    return [s.id for s in sections]
