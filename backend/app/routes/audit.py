"""
audit.py — School Tenant Forensic Audit Feed Routes
Provides school administrators (Headmasters, Bursars, Admins) with scoped activity logs of their staff and students.
Super Admin platform actions are strictly filtered out for privacy and confidentiality.
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, User, School
from ..routes.auth import get_current_user

router = APIRouter(prefix="/audit", tags=["Tenant Forensic Audit Feed"])


def require_school_staff(current_user: User = Depends(get_current_user)):
    """
    Ensure the user is authenticated and has administrative or leadership role in their school.
    """
    role_names = [r.name for r in current_user.roles]
    allowed = ["admin", "super_admin", "headmaster", "headmistress", "principal", "assistant_headmaster_academic", "assistant_headmaster_domestic", "assistant_headmaster_admin", "bursar", "accountant"]
    if not any(r in allowed for r in role_names):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to access school audit records."
        )
    return current_user


@router.get("/school-feed")
def get_school_audit_feed(
    action: Optional[str] = None,
    page: int = 1,
    limit: int = 15,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_school_staff)
):
    """
    Returns activity and device telemetry strictly scoped to the user's school.
    Super Admin platform activities are strictly filtered out (is_super_admin_action == False and actor_role != 'super_admin').
    """
    import math
    page = max(1, page)
    limit = max(1, min(100, limit))
    offset = (page - 1) * limit

    user_roles = [r.name for r in current_user.roles]
    is_super = "super_admin" in user_roles

    query = db.query(AuditLog)

    if not is_super:
        if not current_user.school_id:
            return {"total": 0, "page": page, "limit": limit, "total_pages": 1, "logs": []}
        # Strict tenant boundary + hide Super Admin actions
        query = query.filter(
            AuditLog.school_id == current_user.school_id,
            AuditLog.is_super_admin_action == False,
            AuditLog.actor_role != "super_admin",
            AuditLog.actor_username != "superadmin"
        )
    else:
        # If Super Admin visits this endpoint without school_id parameter, scope to their active school
        if current_user.school_id:
            query = query.filter(AuditLog.school_id == current_user.school_id)

    if action:
        query = query.filter(AuditLog.action == action)

    total_count = query.count()
    logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    results = []
    for log in logs:
        results.append({
            "id": log.id,
            "school_id": log.school_id,
            "actor_username": log.actor_username,
            "actor_role": log.actor_role,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "ip_address": log.ip_address or "127.0.0.1",
            "device_category": log.device_category or "Desktop",
            "device_brand": log.device_brand or "Personal Computer",
            "browser_name": log.browser_name or "Web Browser",
            "os_name": log.os_name or "Operating System",
            "created_at": log.created_at.isoformat() if log.created_at else datetime.utcnow().isoformat()
        })

    return {
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": math.ceil(total_count / limit) if total_count > 0 else 1,
        "logs": results
    }
