"""
audit_service.py — Enterprise Dual-Tier Audit Logging & Device Forensics Service
Centralized event recording for authentication, academic, financial, and governance mutations.
"""
from typing import Optional, Any, Dict
from sqlalchemy.orm import Session
from fastapi import Request

from ..models import AuditLog, User
from .device_parser import parse_device_forensics, get_client_ip


def record_audit_event(
    db: Session,
    request: Optional[Request] = None,
    actor: Optional[Any] = None,
    action: str = "GENERIC_ACTION",
    details: Optional[str] = None,
    entity_type: str = "System",
    entity_id: Optional[str] = None,
    school_id: Optional[int] = None,
    ip_override: Optional[str] = None,
    user_agent_override: Optional[str] = None,
    actor_username_override: Optional[str] = None,
    actor_role_override: Optional[str] = None,
    is_super_admin_action: Optional[bool] = None
) -> Optional[AuditLog]:
    """
    Record an immutable, forensic audit event with client device detection and tiered scoping.
    """
    try:
        # Extract headers and IP from FastAPI Request if provided
        headers_dict = {}
        client_ip = ip_override
        user_agent_str = user_agent_override

        if request:
            try:
                headers_dict = dict(request.headers)
            except Exception:
                headers_dict = {}

            if not client_ip:
                fallback_host = None
                if getattr(request, "client", None):
                    fallback_host = request.client.host
                client_ip = get_client_ip(headers_dict, fallback_host)

            if not user_agent_str:
                user_agent_str = request.headers.get("user-agent", "")

        # Fallback defaults
        client_ip = client_ip or "127.0.0.1"
        user_agent_str = user_agent_str or "Internal Engine / CLI"

        # Parse Device Forensics
        forensics = parse_device_forensics(user_agent_str, headers_dict)

        # Resolve Actor details
        actor_id = None
        actor_username = actor_username_override or "system"
        actor_role = actor_role_override or "system"

        if actor:
            if hasattr(actor, "id"):
                actor_id = actor.id
            elif isinstance(actor, dict) and "id" in actor:
                actor_id = actor["id"]

            if hasattr(actor, "username"):
                actor_username = str(actor.username)
            elif isinstance(actor, dict) and "username" in actor:
                actor_username = str(actor["username"])

            if hasattr(actor, "roles") and actor.roles:
                first_r = actor.roles[0]
                actor_role = first_r.name if hasattr(first_r, "name") else str(first_r)
            elif hasattr(actor, "role") and actor.role:
                first_r = actor.role
                actor_role = first_r.name if hasattr(first_r, "name") else str(first_r)
            elif isinstance(actor, dict):
                r_val = actor.get("role") or (actor.get("roles", ["user"])[0] if actor.get("roles") else "user")
                actor_role = r_val.name if hasattr(r_val, "name") else str(r_val)

        actor_role = str(actor_role) if actor_role else "user"

        # Resolve School ID
        if school_id is None:
            if actor and hasattr(actor, "school_id") and actor.school_id:
                school_id = actor.school_id
            elif isinstance(actor, dict) and actor.get("school_id"):
                school_id = actor["school_id"]

        # Determine if Super Admin action
        if is_super_admin_action is None:
            is_super_admin_action = (
                actor_role.lower() == "super_admin" or
                (hasattr(actor, "is_super_admin") and actor.is_super_admin) or
                (isinstance(actor, dict) and actor.get("is_super_admin")) or
                action.startswith("SUPER_ADMIN_") or
                action in ["CREATE_SCHOOL", "PURGE_SCHOOL", "SUSPEND_SCHOOL", "UPDATE_GATEWAY_CONFIG", "IMPERSONATION_VIEW"]
            )

        audit_entry = AuditLog(
            school_id=school_id,
            actor_id=actor_id,
            actor_username=str(actor_username),
            actor_role=str(actor_role),
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details,
            ip_address=client_ip,
            user_agent=user_agent_str,
            device_category=forensics["device_category"],
            device_brand=forensics["device_brand"],
            browser_name=forensics["browser_name"],
            os_name=forensics["os_name"],
            is_super_admin_action=bool(is_super_admin_action)
        )

        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)
        return audit_entry

    except Exception as e:
        # Audit logging should never crash the primary business transaction
        try:
            db.rollback()
        except Exception:
            pass
        return None
