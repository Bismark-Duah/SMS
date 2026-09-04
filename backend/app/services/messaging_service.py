"""
Enterprise Multi-Tenant Messaging Service.
Supports school-specific approved 11-character Alphanumeric Sender IDs,
dynamic tenant configurations, and mNotify / Hubtel failover routing.
"""
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from ..models import Setting, MessageLog, TenantSmsConfig, School
from ..sms.gateway import sms_engine, normalize_ghana_phone, mask_phone_number

logger = logging.getLogger(__name__)

def send_sms_via_hubtel(
    recipient_phone: str,
    message_body: str,
    sender_id: Optional[str] = None,
    school_id: Optional[int] = None,
    message_type: str = "VOUCHER_PIN",
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Dispatches SMS using Enterprise Dual-Failover Engine (mNotify + Hubtel).
    """
    clean_phone = normalize_ghana_phone(recipient_phone)

    res = sms_engine.dispatch(
        recipient_phone=clean_phone,
        message_body=message_body,
        school_id=school_id,
        db=db,
        sender_id=sender_id,
        recipient_name="Applicant / Parent",
        message_type=message_type
    )

    is_success = res.get("status") in ["success", "offline_fallback"]
    return {
        "success": is_success,
        "status": "SENT" if res.get("status") == "success" else "QUEUED_OFFLINE",
        "sender_id": res.get("sender_id", "EDUMANAGE"),
        "recipient": clean_phone,
        "provider": res.get("gateway", "MNOTIFY"),
        "response": res
    }
