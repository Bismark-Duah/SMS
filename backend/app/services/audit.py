import json
from datetime import datetime
from typing import Optional, Any
from sqlalchemy.orm import Session
from ..models import ActivityAuditLog, User

class AuditService:
    @staticmethod
    def log(
        db: Session,
        action: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        details: Optional[Any] = None,
        user: Optional[User] = None,
        user_id: Optional[int] = None,
        school_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> Optional[ActivityAuditLog]:
        """
        Records an operational event to the activity_audit_logs table.
        Gracefully handles exceptions so that core transactions are never blocked.
        """
        try:
            u_id = user_id or (user.id if user else None)
            u_name = user.username if user else None
            u_role = None
            if user and hasattr(user, "roles") and user.roles:
                u_role = ", ".join([r.name for r in user.roles])

            sch_id = school_id or (user.school_id if user else 1)

            detail_str = None
            if details is not None:
                if isinstance(details, (dict, list)):
                    detail_str = json.dumps(details, default=str)
                else:
                    detail_str = str(details)

            log_entry = ActivityAuditLog(
                school_id=sch_id,
                user_id=u_id,
                user_name=u_name,
                user_role=u_role,
                action=action.upper(),
                entity_type=entity_type,
                entity_id=entity_id,
                ip_address=ip_address,
                details=detail_str,
                timestamp=datetime.now()
            )
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)
            return log_entry
        except Exception as err:
            print("Warning: Failed to write audit log:", err)
            try:
                db.rollback()
            except Exception:
                pass
            return None
