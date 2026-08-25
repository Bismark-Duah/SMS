from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from ..database import get_db
from ..models import ActivityAuditLog, User
from ..dependencies import get_current_user, get_school_id

router = APIRouter(tags=["Institutional Audit Trail"])

AUDIT_VIEW_ROLES = {
    "admin", "super_admin", "headmaster", "headmistress",
    "assistant_headmaster_academic", "assistant_head_academic",
    "assistant_headmaster_admin", "assistant_head_admin"
}

@router.get("/logs")
def get_audit_logs(
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns paginated audit trail logs for the school.
    Accessible to School Admins, Headmasters, and Assistant Heads.
    """
    user_roles = [r.name.lower() for r in current_user.roles] if hasattr(current_user, "roles") else []
    if not any(r in AUDIT_VIEW_ROLES for r in user_roles):
        raise HTTPException(status_code=403, detail="You do not have permission to inspect institutional audit logs.")

    school_id = get_school_id(current_user)

    query = db.query(ActivityAuditLog)
    if school_id is not None:
        query = query.filter(ActivityAuditLog.school_id == school_id)

    if action:
        query = query.filter(ActivityAuditLog.action == action.upper())

    if entity_type:
        query = query.filter(ActivityAuditLog.entity_type == entity_type)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                ActivityAuditLog.user_name.ilike(search_pattern),
                ActivityAuditLog.action.ilike(search_pattern),
                ActivityAuditLog.details.ilike(search_pattern)
            )
        )

    total_count = query.count()
    logs = query.order_by(desc(ActivityAuditLog.timestamp)).offset(offset).limit(limit).all()

    return {
        "total": total_count,
        "offset": offset,
        "limit": limit,
        "logs": [
            {
                "id": log.id,
                "school_id": log.school_id,
                "user_id": log.user_id,
                "user_name": log.user_name,
                "user_role": log.user_role,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "ip_address": log.ip_address,
                "details": log.details,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None
            }
            for log in logs
        ]
    }
