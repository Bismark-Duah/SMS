"""
audit.py — School Tenant Forensic Audit Feed Routes
Provides school administrators (Headmasters, Bursars, Admins) with scoped activity logs of their staff and students.
Super Admin platform actions are strictly filtered out for privacy and confidentiality.
"""
import math
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, User, School
from ..routes.auth import get_current_user
from ..services.import_export_service import generate_safe_csv_content, sanitize_filename

router = APIRouter(tags=["Tenant Forensic Audit Feed"])


def require_school_staff(current_user: User = Depends(get_current_user)):
    """
    Ensure the user is authenticated and has administrative or leadership role in their school.
    """
    role_names = [r.name for r in current_user.roles] if hasattr(current_user, "roles") and current_user.roles else []
    allowed = [
        "admin", "super_admin", "headmaster", "headmistress", "principal",
        "assistant_headmaster_academic", "assistant_headmaster_domestic",
        "assistant_headmaster_admin", "bursar", "accountant"
    ]
    if not any(r in allowed for r in role_names):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to access school audit records."
        )
    return current_user


def _build_audit_query(
    db: Session,
    current_user: User,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    actor_username: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    school_id: Optional[int] = None
):
    user_roles = [r.name for r in current_user.roles] if hasattr(current_user, "roles") and current_user.roles else []
    is_super = "super_admin" in user_roles

    query = db.query(AuditLog)

    if not is_super:
        # Non-super admins cannot target any other school
        if school_id is not None and school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only inspect audit records for your own institution."
            )

        if not current_user.school_id:
            return query.filter(AuditLog.id == -1)

        # Strict tenant boundary + hide Super Admin platform actions
        query = query.filter(
            AuditLog.school_id == current_user.school_id,
            AuditLog.is_super_admin_action == False,
            AuditLog.actor_role != "super_admin",
            AuditLog.actor_username != "superadmin"
        )
    else:
        # Super Admin can view specific school or global
        target_school = school_id if school_id is not None else current_user.school_id
        if target_school is not None:
            query = query.filter(AuditLog.school_id == target_school)

    if action:
        query = query.filter(AuditLog.action == action.strip())

    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type.strip())

    if actor_username:
        query = query.filter(AuditLog.actor_username == actor_username.strip())

    if start_date:
        try:
            s_dt = datetime.fromisoformat(start_date.strip())
            query = query.filter(AuditLog.created_at >= s_dt)
        except ValueError:
            try:
                s_dt = datetime.strptime(start_date.strip(), "%Y-%m-%d")
                query = query.filter(AuditLog.created_at >= s_dt)
            except ValueError:
                pass

    if end_date:
        try:
            e_dt = datetime.fromisoformat(end_date.strip())
            query = query.filter(AuditLog.created_at <= e_dt)
        except ValueError:
            try:
                e_dt = datetime.strptime(end_date.strip(), "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                query = query.filter(AuditLog.created_at <= e_dt)
            except ValueError:
                pass

    if search:
        s_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                AuditLog.action.ilike(s_term),
                AuditLog.details.ilike(s_term),
                AuditLog.actor_username.ilike(s_term),
                AuditLog.entity_type.ilike(s_term),
                AuditLog.ip_address.ilike(s_term)
            )
        )

    return query


@router.get("/school-feed")
@router.get("/logs")
def get_school_audit_feed(
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    actor_username: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    school_id: Optional[int] = None,
    page: int = 1,
    limit: int = 15,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_school_staff)
):
    """
    Returns activity and device telemetry strictly scoped to the user's school.
    Super Admin platform activities are strictly filtered out (is_super_admin_action == False and actor_role != 'super_admin').
    Supports filtering by action, entity_type, username, date range, and free text search.
    """
    page = max(1, page)
    limit = max(1, min(100, limit))
    offset = (page - 1) * limit

    query = _build_audit_query(
        db=db,
        current_user=current_user,
        action=action,
        entity_type=entity_type,
        actor_username=actor_username,
        start_date=start_date,
        end_date=end_date,
        search=search,
        school_id=school_id
    )

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


@router.get("/export")
def export_audit_logs(
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    actor_username: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    school_id: Optional[int] = None,
    limit: int = Query(1000, ge=1, le=10000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_school_staff)
):
    """
    Exports filtered forensic audit records as an RFC 4180 compliant CSV file.
    Enforces tenant boundaries and formula injection defense (CWE-1236).
    """
    query = _build_audit_query(
        db=db,
        current_user=current_user,
        action=action,
        entity_type=entity_type,
        actor_username=actor_username,
        start_date=start_date,
        end_date=end_date,
        search=search,
        school_id=school_id
    )

    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()

    headers = [
        "ID", "Timestamp (UTC)", "School ID", "Actor Username", "Actor Role",
        "Action", "Entity Type", "Entity ID", "IP Address",
        "Device Category", "Browser", "Operating System", "Details"
    ]

    rows = []
    for log in logs:
        ts_str = log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else ""
        rows.append([
            log.id,
            ts_str,
            log.school_id or "",
            log.actor_username or "",
            log.actor_role or "",
            log.action or "",
            log.entity_type or "",
            log.entity_id or "",
            log.ip_address or "127.0.0.1",
            log.device_category or "Desktop",
            log.browser_name or "",
            log.os_name or "",
            log.details or ""
        ])

    csv_content = generate_safe_csv_content(headers, rows)
    safe_filename = sanitize_filename(f"audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv")

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"'
        }
    )


# Backward-compatible alias for existing verification scripts
get_audit_logs = get_school_audit_feed
