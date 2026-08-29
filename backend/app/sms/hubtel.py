"""
Hubtel SMS Integration Package for SaaS School Management System.
Handles Ghanaian phone number normalization (0XXXXXXXXX -> 233XXXXXXXXX),
dynamic approved Sender IDs per school, real-time SMS quota debits, and delivery logging.
"""
import os
import re
import urllib.request
import urllib.parse
import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from ..models import Setting, School, TenantSmsConfig, MessageLog

def normalize_ghana_phone(phone: str) -> str:
    """
    Sanitizes Ghanaian mobile numbers to standard E.164 format: 233XXXXXXXXX.
    Handles:
    - 0244123456 -> 233244123456
    - +233244123456 -> 233244123456
    - 244123456 -> 233244123456
    """
    if not phone:
        return ""
    cleaned = re.sub(r"[^\d+]", "", str(phone).strip())
    if cleaned.startswith("+233"):
        return cleaned[1:]
    if cleaned.startswith("233"):
        return cleaned
    if cleaned.startswith("0") and len(cleaned) == 10:
        return "233" + cleaned[1:]
    if len(cleaned) == 9:
        return "233" + cleaned
    return cleaned

def get_hubtel_credentials(db: Optional[Session] = None, school_id: Optional[int] = None) -> tuple[str, str]:
    client_id = ""
    client_secret = ""
    
    # 1. Check Tenant-specific SMS config
    if db and school_id:
        cfg = db.query(TenantSmsConfig).filter(TenantSmsConfig.school_id == school_id).first()
        if cfg and cfg.hubtel_client_id and cfg.hubtel_client_secret:
            return cfg.hubtel_client_id.strip(), cfg.hubtel_client_secret.strip()

    # 2. Check System Settings
    if db:
        id_setting = db.query(Setting).filter(Setting.key == "hubtel_client_id").first()
        secret_setting = db.query(Setting).filter(Setting.key == "hubtel_client_secret").first()
        if id_setting and id_setting.value:
            client_id = id_setting.value.strip()
        if secret_setting and secret_setting.value:
            client_secret = secret_setting.value.strip()

    # 3. Environment Fallback
    if not client_id:
        client_id = os.getenv("HUBTEL_CLIENT_ID", "").strip()
    if not client_secret:
        client_secret = os.getenv("HUBTEL_CLIENT_SECRET", "").strip()

    return client_id, client_secret

def send_sms_hubtel(
    recipient_phone: str,
    message_body: str,
    school_id: int,
    db: Session,
    sender_id: Optional[str] = None,
    sender_user_id: Optional[int] = None,
    student_id: Optional[int] = None,
    recipient_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sends school-branded SMS via Hubtel API with real-time atomic balance deduction.
    """
    normalized_phone = normalize_ghana_phone(recipient_phone)
    if not normalized_phone:
        return {"status": "error", "message": "Invalid recipient phone number."}

    # 1. Check and lock School SMS Quota
    school = db.query(School).filter(School.id == school_id).with_for_update().first()
    if not school:
        return {"status": "error", "message": f"School ID {school_id} not found."}

    current_balance = school.sms_balance if school.sms_balance is not None else 0
    if current_balance <= 0:
        return {
            "status": "error",
            "message": f"SMS quota depleted ({current_balance} units). Please top up SMS credits to continue sending messages."
        }

    # 2. Resolve Dynamic Sender ID
    active_sender = "EDUMANAGE"
    if sender_id and len(sender_id.strip()) <= 11:
        active_sender = sender_id.strip()
    else:
        sms_cfg = db.query(TenantSmsConfig).filter(TenantSmsConfig.school_id == school_id).first()
        if sms_cfg and sms_cfg.status == "ACTIVE" and sms_cfg.sender_id:
            active_sender = sms_cfg.sender_id.strip()

    client_id, client_secret = get_hubtel_credentials(db, school_id)

    # 3. Handle Offline / Unconfigured Gateway Simulation
    if not client_id or not client_secret:
        # Atomic deduction for simulation
        school.sms_balance = current_balance - 1
        log = MessageLog(
            school_id=school_id,
            sender_id=sender_user_id,
            student_id=student_id,
            recipient_name=recipient_name or normalized_phone,
            recipient_phone=normalized_phone,
            channel="SMS",
            message_type="TRANSACTIONAL",
            message_body=message_body,
            status="SENT",
            hubtel_message_id=f"MOCK_MSG_{abs(hash(message_body)) % 1000000}",
            cost=1.0
        )
        db.add(log)
        db.commit()
        return {
            "status": "offline_fallback",
            "message": "Hubtel unconfigured; message queued and logged locally in offline mode.",
            "sender_id": active_sender,
            "recipient": normalized_phone,
            "remaining_balance": school.sms_balance
        }

    # 4. Dispatch via Hubtel QuickSMS Endpoint
    params = {
        "clientid": client_id,
        "clientsecret": client_secret,
        "from": active_sender[:11],
        "to": normalized_phone,
        "content": message_body
    }
    url = f"https://sms.hubtel.com/v1/messages/send?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            hubtel_id = resp_data.get("messageid") or resp_data.get("id") or str(resp_data.get("status"))

            # Atomic quota deduction
            school.sms_balance = current_balance - 1
            log = MessageLog(
                school_id=school_id,
                sender_id=sender_user_id,
                student_id=student_id,
                recipient_name=recipient_name or normalized_phone,
                recipient_phone=normalized_phone,
                channel="SMS",
                message_type="TRANSACTIONAL",
                message_body=message_body,
                status="SENT" if resp_data.get("status") in [0, "0", "Success", "Scheduled"] else "FAILED",
                hubtel_message_id=str(hubtel_id),
                cost=1.0
            )
            db.add(log)
            db.commit()

            return {
                "status": "success",
                "hubtel_response": resp_data,
                "sender_id": active_sender,
                "recipient": normalized_phone,
                "remaining_balance": school.sms_balance
            }
    except Exception as e:
        db.rollback()
        # Log failure
        try:
            failed_log = MessageLog(
                school_id=school_id,
                sender_id=sender_user_id,
                student_id=student_id,
                recipient_name=recipient_name or normalized_phone,
                recipient_phone=normalized_phone,
                channel="SMS",
                message_type="TRANSACTIONAL",
                message_body=message_body,
                status="FAILED",
                cost=0.0
            )
            db.add(failed_log)
            db.commit()
        except Exception:
            db.rollback()

        return {"status": "error", "message": f"Hubtel dispatch error: {str(e)}"}
