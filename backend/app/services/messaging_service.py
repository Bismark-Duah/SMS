"""
Hubtel Enterprise Multi-Tenant Messaging Service.
Supports school-specific approved 11-character Alphanumeric Sender IDs,
dynamic tenant configurations, and offline-safe fallback logging.
"""
import json
import logging
import urllib.request
import urllib.parse
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from ..models import Setting, MessageLog, TenantSmsConfig, School

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
    Dispatches SMS using Hubtel Enterprise Gateway with Dynamic School Sender ID.
    If in local offline development or credentials missing, logs safely to SQLite without errors.
    """
    clean_phone = "".join(filter(str.isdigit, recipient_phone or ""))
    if clean_phone.startswith("0") and len(clean_phone) == 10:
        clean_phone = "233" + clean_phone[1:]
    elif not clean_phone.startswith("233") and len(clean_phone) == 9:
        clean_phone = "233" + clean_phone

    # 1. Resolve Dynamic School Sender ID
    active_sender_id = sender_id
    client_id = None
    client_secret = None

    if db and school_id:
        sms_cfg = db.query(TenantSmsConfig).filter(TenantSmsConfig.school_id == school_id).first()
        if sms_cfg:
            if sms_cfg.status == "ACTIVE" and sms_cfg.sender_id:
                active_sender_id = sms_cfg.sender_id[:11]
            client_id = sms_cfg.hubtel_client_id
            client_secret = sms_cfg.hubtel_client_secret

    if not active_sender_id:
        active_sender_id = "EDUMANAGE"

    # Fallback to system-wide Hubtel credentials if tenant did not provide custom keys
    if db and not client_id:
        s_client = db.query(Setting).filter(Setting.key == "hubtel_client_id").first()
        s_secret = db.query(Setting).filter(Setting.key == "hubtel_client_secret").first()
        client_id = s_client.value if s_client else None
        client_secret = s_secret.value if s_secret else None

    # 2. Attempt Hubtel HTTP Dispatch if credentials present
    status_str = "SENT"
    response_payload = None

    if client_id and client_secret:
        try:
            url = (
                f"https://smsc.hubtel.com/v1/messages/send?"
                f"From={urllib.parse.quote(active_sender_id)}&"
                f"To={clean_phone}&"
                f"Content={urllib.parse.quote(message_body)}&"
                f"ClientId={client_id}&"
                f"ClientSecret={client_secret}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "EduManage360/Hubtel-Engine"})
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                res_body = resp.read().decode("utf-8")
                status_str = "SENT" if resp.status == 200 else "FAILED"
                response_payload = res_body
        except Exception as e:
            logger.warning(f"Hubtel API dispatch offline fallback: {e}")
            status_str = "QUEUED_OFFLINE"
    else:
        # Offline development mode -> simulate instant delivery
        status_str = "DELIVERED_SIMULATED"

    # 3. Log to MessageLog database table
    if db:
        try:
            log_entry = MessageLog(
                sender_id=None,
                student_id=None,
                recipient_name="Applicant / Parent",
                recipient_phone=clean_phone,
                channel="SMS",
                message_type=message_type,
                message_body=message_body,
                status=status_str
            )
            db.add(log_entry)
            db.commit()
        except Exception as log_err:
            print("Message log error:", log_err)
            db.rollback()

    return {
        "success": status_str in ["SENT", "DELIVERED_SIMULATED", "QUEUED_OFFLINE"],
        "status": status_str,
        "sender_id": active_sender_id,
        "recipient": clean_phone,
        "provider": "HUBTEL",
        "response": response_payload
    }
