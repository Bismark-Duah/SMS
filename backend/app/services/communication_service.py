import json
import logging
import smtplib
import urllib.request
import urllib.parse
import urllib.error
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from ..models import Setting, MessageLog, Student, ExeatRecord, User, School

logger = logging.getLogger(__name__)

# ── Supported Provider Constants ──────────────────────────────────────────────
SMS_PROVIDER_NONE = "NONE"
SMS_PROVIDER_ARKESEL = "ARKESEL"
SMS_PROVIDER_HUBTEL = "HUBTEL"
SMS_PROVIDER_MNOTIFY = "MNOTIFY"
SMS_PROVIDER_TWILIO = "TWILIO"
SMS_PROVIDER_CUSTOM = "CUSTOM_WEBHOOK"

WA_PROVIDER_NONE = "NONE"
WA_PROVIDER_TWILIO = "TWILIO"
WA_PROVIDER_ARKESEL = "ARKESEL_WA"
WA_PROVIDER_META = "META_CLOUD"

# Default fallback sender IDs
DEFAULT_SENDER_ID = "EduManage"


class CommunicationService:
    """
    Enterprise Hybrid Multi-Channel Communication Engine.
    Supports Cloud SMS (Arkesel, Hubtel, mNotify, Twilio), WhatsApp Cloud/Twilio,
    Standard SMTP Email, and safe offline-first fallback logging.
    """

    @staticmethod
    def get_setting_val(db: Session, key: str, default: str = "") -> str:
        s = db.query(Setting).filter(Setting.key == key).first()
        return s.value if s and s.value else default

    @staticmethod
    def set_setting_val(db: Session, key: str, value: str) -> None:
        s = db.query(Setting).filter(Setting.key == key).first()
        if s:
            s.value = value
        else:
            db.add(Setting(key=key, value=value))
        db.commit()

    @classmethod
    def get_gateway_config(cls, db: Session) -> Dict[str, Any]:
        """Retrieve all gateway configurations, masking sensitive keys."""
        sms_api_key = cls.get_setting_val(db, "sms_api_key", "")
        smtp_password = cls.get_setting_val(db, "smtp_password", "")
        wa_api_key = cls.get_setting_val(db, "whatsapp_api_key", "")

        def mask(v: str) -> str:
            if not v or len(v) < 6:
                return "••••••" if v else ""
            return v[:3] + "••••••••" + v[-2:]

        return {
            # SMS Configuration
            "sms_provider": cls.get_setting_val(db, "sms_provider", SMS_PROVIDER_NONE),
            "sms_sender_id": cls.get_setting_val(db, "sms_sender_id", DEFAULT_SENDER_ID),
            "sms_api_key": mask(sms_api_key),
            "sms_api_key_set": bool(sms_api_key),
            "sms_api_url": cls.get_setting_val(db, "sms_api_url", ""),
            "sms_client_id": cls.get_setting_val(db, "sms_client_id", ""),
            
            # WhatsApp Configuration
            "whatsapp_provider": cls.get_setting_val(db, "whatsapp_provider", WA_PROVIDER_NONE),
            "whatsapp_sender_number": cls.get_setting_val(db, "whatsapp_sender_number", ""),
            "whatsapp_api_key": mask(wa_api_key),
            "whatsapp_api_key_set": bool(wa_api_key),
            "whatsapp_account_sid": cls.get_setting_val(db, "whatsapp_account_sid", ""),

            # SMTP Email Configuration
            "smtp_enabled": cls.get_setting_val(db, "smtp_enabled", "false").lower() == "true",
            "smtp_host": cls.get_setting_val(db, "smtp_host", "smtp.gmail.com"),
            "smtp_port": int(cls.get_setting_val(db, "smtp_port", "587")),
            "smtp_username": cls.get_setting_val(db, "smtp_username", ""),
            "smtp_password": mask(smtp_password),
            "smtp_password_set": bool(smtp_password),
            "smtp_from_email": cls.get_setting_val(db, "smtp_from_email", "noreply@school.edu.gh"),
            "smtp_use_tls": cls.get_setting_val(db, "smtp_use_tls", "true").lower() == "true",

            # Automated Notification Event Toggles
            "auto_notify_exeat_gateout": cls.get_setting_val(db, "auto_notify_exeat_gateout", "true").lower() == "true",
            "auto_notify_exeat_gatein": cls.get_setting_val(db, "auto_notify_exeat_gatein", "true").lower() == "true",
            "auto_notify_fee_payment": cls.get_setting_val(db, "auto_notify_fee_payment", "true").lower() == "true",
            "auto_notify_report_published": cls.get_setting_val(db, "auto_notify_report_published", "false").lower() == "true",
            "auto_notify_absence": cls.get_setting_val(db, "auto_notify_absence", "false").lower() == "true",
        }

    @classmethod
    def save_gateway_config(cls, db: Session, payload: Dict[str, Any]) -> None:
        """Save gateway configuration keys securely."""
        for k, v in payload.items():
            if v is None:
                continue
            # Don't overwrite secret keys if they were passed back as masked strings
            if k in ["sms_api_key", "smtp_password", "whatsapp_api_key"] and ("••••" in str(v) or not str(v).strip()):
                continue
            cls.set_setting_val(db, k, str(v).strip() if isinstance(v, str) else str(v))

    @staticmethod
    def _clean_phone(phone: Optional[str]) -> str:
        if not phone:
            return ""
        clean = "".join(c for c in phone if c.isdigit() or c == "+")
        # Format local Ghanaian number 0244... -> 233244...
        if clean.startswith("0") and len(clean) == 10:
            clean = "233" + clean[1:]
        elif clean.startswith("+233"):
            clean = clean[1:]
        elif clean.startswith("+"):
            clean = clean[1:]
        return clean

    # ── SMS Dispatcher ────────────────────────────────────────────────────────
    @classmethod
    def send_sms(
        cls,
        db: Session,
        to_phone: str,
        message: str,
        student_id: Optional[int] = None,
        recipient_name: Optional[str] = None,
        sender_id_user: Optional[int] = None,
        message_type: str = "GENERAL"
    ) -> Dict[str, Any]:
        """
        Sends SMS via configured cloud provider with zero-crash offline fallback.
        """
        provider = cls.get_setting_val(db, "sms_provider", SMS_PROVIDER_NONE).upper()
        sender_id = cls.get_setting_val(db, "sms_sender_id", DEFAULT_SENDER_ID) or DEFAULT_SENDER_ID
        api_key = cls.get_setting_val(db, "sms_api_key", "")
        clean_phone = cls._clean_phone(to_phone)

        if not clean_phone:
            cls._log_message(db, sender_id_user, student_id, recipient_name, to_phone, "SMS", message_type, message, "FAILED_NO_PHONE")
            return {"success": False, "provider": provider, "error": "Invalid or missing phone number", "status": "FAILED_NO_PHONE"}

        if provider == SMS_PROVIDER_NONE or not api_key:
            # Offline / Unconfigured mode: Log to outbox as QUEUED_FOR_DEVICE
            cls._log_message(db, sender_id_user, student_id, recipient_name, clean_phone, "SMS", message_type, message, "QUEUED")
            return {
                "success": True,
                "provider": SMS_PROVIDER_NONE,
                "status": "QUEUED",
                "message": "Gateway not configured. Message queued in local outbox for 1-click device/CSV export."
            }

        try:
            # 1. Arkesel Ghana SMS API v2
            if provider == SMS_PROVIDER_ARKESEL:
                url = "https://sms.arkesel.com/api/v2/sms/send"
                payload = json.dumps({
                    "sender": sender_id[:11],
                    "message": message,
                    "recipients": [clean_phone]
                }).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={
                        "api-key": api_key,
                        "Content-Type": "application/json",
                        "User-Agent": "EduManage360/SMS"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=4) as response:
                    res_body = response.read().decode("utf-8")
                    res_json = json.loads(res_body)
                    status_str = "SENT" if response.status in [200, 201] else "FAILED"
                    cls._log_message(db, sender_id_user, student_id, recipient_name, clean_phone, "SMS", message_type, message, status_str)
                    return {"success": True, "provider": provider, "status": status_str, "response": res_json}

            # 2. Hubtel Ghana SMS API
            elif provider == SMS_PROVIDER_HUBTEL:
                client_id = cls.get_setting_val(db, "sms_client_id", "")
                url = f"https://smsc.hubtel.com/v1/messages/send?From={urllib.parse.quote(sender_id)}&To={clean_phone}&Content={urllib.parse.quote(message)}&ClientId={client_id}&ClientSecret={api_key}"
                req = urllib.request.Request(url, headers={"User-Agent": "EduManage360/SMS"})
                with urllib.request.urlopen(req, timeout=4) as response:
                    res_body = response.read().decode("utf-8")
                    status_str = "SENT" if response.status == 200 else "FAILED"
                    cls._log_message(db, sender_id_user, student_id, recipient_name, clean_phone, "SMS", message_type, message, status_str)
                    return {"success": True, "provider": provider, "status": status_str, "response": res_body}

            # 3. mNotify Ghana SMS API
            elif provider == SMS_PROVIDER_MNOTIFY:
                url = f"https://api.mnotify.com/api/sms/quick?key={api_key}"
                payload = json.dumps({
                    "recipient[]": [clean_phone],
                    "sender": sender_id[:11],
                    "message": message,
                    "is_schedule": False
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "EduManage360/SMS"}, method="POST")
                with urllib.request.urlopen(req, timeout=4) as response:
                    res_body = response.read().decode("utf-8")
                    status_str = "SENT" if response.status in [200, 201] else "FAILED"
                    cls._log_message(db, sender_id_user, student_id, recipient_name, clean_phone, "SMS", message_type, message, status_str)
                    return {"success": True, "provider": provider, "status": status_str, "response": json.loads(res_body)}

            # 4. Twilio International SMS API
            elif provider == SMS_PROVIDER_TWILIO:
                account_sid = cls.get_setting_val(db, "sms_client_id", "") or cls.get_setting_val(db, "whatsapp_account_sid", "")
                auth_token = api_key
                twilio_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
                formatted_phone = "+" + clean_phone if not clean_phone.startswith("+") else clean_phone
                data_dict = {
                    "From": sender_id,
                    "To": formatted_phone,
                    "Body": message
                }
                encoded_data = urllib.parse.urlencode(data_dict).encode("utf-8")
                auth_header = "Basic " + urllib.request.base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
                req = urllib.request.Request(twilio_url, data=encoded_data, headers={"Authorization": auth_header, "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
                with urllib.request.urlopen(req, timeout=4) as response:
                    res_body = response.read().decode("utf-8")
                    status_str = "SENT" if response.status in [200, 201] else "FAILED"
                    cls._log_message(db, sender_id_user, student_id, recipient_name, clean_phone, "SMS", message_type, message, status_str)
                    return {"success": True, "provider": provider, "status": status_str, "response": json.loads(res_body)}

            else:
                cls._log_message(db, sender_id_user, student_id, recipient_name, clean_phone, "SMS", message_type, message, "QUEUED")
                return {"success": True, "provider": provider, "status": "QUEUED"}

        except Exception as e:
            logger.warning(f"SMS Dispatch through {provider} failed: {e}. Falling back to Outbox QUEUED state.")
            cls._log_message(db, sender_id_user, student_id, recipient_name, clean_phone, "SMS", message_type, message, "QUEUED_OFFLINE")
            return {
                "success": False,
                "provider": provider,
                "status": "QUEUED_OFFLINE",
                "error": str(e),
                "message": "Cloud gateway unreachable. Message safely queued in local outbox."
            }

    # ── WhatsApp Dispatcher ───────────────────────────────────────────────────
    @classmethod
    def send_whatsapp(
        cls,
        db: Session,
        to_phone: str,
        message: str,
        student_id: Optional[int] = None,
        recipient_name: Optional[str] = None,
        sender_id_user: Optional[int] = None,
        message_type: str = "GENERAL"
    ) -> Dict[str, Any]:
        """
        Sends WhatsApp notification via Twilio / Meta Cloud or returns instant wa.me intent URL.
        """
        provider = cls.get_setting_val(db, "whatsapp_provider", WA_PROVIDER_NONE).upper()
        clean_phone = cls._clean_phone(to_phone)
        encoded_text = urllib.parse.quote(message)
        intent_url = f"https://wa.me/{clean_phone}?text={encoded_text}" if clean_phone else ""

        if provider == WA_PROVIDER_NONE or not clean_phone:
            cls._log_message(db, sender_id_user, student_id, recipient_name, clean_phone or to_phone, "WHATSAPP", message_type, message, "INTENT_READY")
            return {
                "success": True,
                "provider": WA_PROVIDER_NONE,
                "status": "INTENT_READY",
                "intent_url": intent_url,
                "message": "WhatsApp direct device link prepared."
            }

        # Attempt cloud dispatch if Twilio is configured
        if provider == WA_PROVIDER_TWILIO:
            account_sid = cls.get_setting_val(db, "whatsapp_account_sid", "")
            auth_token = cls.get_setting_val(db, "whatsapp_api_key", "")
            sender_num = cls.get_setting_val(db, "whatsapp_sender_number", "whatsapp:+14155238886")
            if account_sid and auth_token:
                try:
                    twilio_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
                    data_dict = {
                        "From": sender_num if sender_num.startswith("whatsapp:") else f"whatsapp:{sender_num}",
                        "To": f"whatsapp:+{clean_phone}",
                        "Body": message
                    }
                    encoded_data = urllib.parse.urlencode(data_dict).encode("utf-8")
                    import base64
                    auth_header = "Basic " + base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
                    req = urllib.request.Request(twilio_url, data=encoded_data, headers={"Authorization": auth_header, "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
                    with urllib.request.urlopen(req, timeout=4) as response:
                        cls._log_message(db, sender_id_user, student_id, recipient_name, clean_phone, "WHATSAPP", message_type, message, "SENT")
                        return {"success": True, "provider": provider, "status": "SENT", "intent_url": intent_url}
                except Exception as e:
                    logger.warning(f"Cloud WhatsApp dispatch failed: {e}. Falling back to intent URL.")

        cls._log_message(db, sender_id_user, student_id, recipient_name, clean_phone, "WHATSAPP", message_type, message, "INTENT_READY")
        return {"success": True, "provider": provider, "status": "INTENT_READY", "intent_url": intent_url}

    # ── SMTP Email Dispatcher ─────────────────────────────────────────────────
    @classmethod
    def send_email(
        cls,
        db: Session,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        student_id: Optional[int] = None,
        recipient_name: Optional[str] = None,
        sender_id_user: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Sends standard SMTP Email with HTML formatting and graceful offline handling.
        """
        enabled = cls.get_setting_val(db, "smtp_enabled", "false").lower() == "true"
        host = cls.get_setting_val(db, "smtp_host", "smtp.gmail.com")
        port = int(cls.get_setting_val(db, "smtp_port", "587"))
        username = cls.get_setting_val(db, "smtp_username", "")
        password = cls.get_setting_val(db, "smtp_password", "")
        from_email = cls.get_setting_val(db, "smtp_from_email", "noreply@school.edu.gh")
        use_tls = cls.get_setting_val(db, "smtp_use_tls", "true").lower() == "true"

        if not enabled or not to_email or not username or not password:
            cls._log_message(db, sender_id_user, student_id, recipient_name, to_email, "EMAIL", "EMAIL_NOTICE", body_text, "QUEUED")
            return {"success": False, "status": "QUEUED", "message": "SMTP not enabled or credentials not supplied. Saved to outbox."}

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_email
            msg["To"] = to_email

            part1 = MIMEText(body_text, "plain")
            msg.attach(part1)

            if body_html:
                part2 = MIMEText(body_html, "html")
                msg.attach(part2)

            context = ssl.create_default_context()
            with smtplib.SMTP(host, port, timeout=5) as server:
                if use_tls:
                    server.starttls(context=context)
                server.login(username, password)
                server.sendmail(from_email, to_email, msg.as_string())

            cls._log_message(db, sender_id_user, student_id, recipient_name, to_email, "EMAIL", "EMAIL_NOTICE", body_text, "SENT")
            return {"success": True, "status": "SENT", "message": f"Email successfully dispatched to {to_email}"}

        except Exception as e:
            logger.warning(f"SMTP email send failed: {e}. Saving to outbox queue.")
            cls._log_message(db, sender_id_user, student_id, recipient_name, to_email, "EMAIL", "EMAIL_NOTICE", body_text, "QUEUED_OFFLINE")
            return {"success": False, "status": "QUEUED_OFFLINE", "error": str(e)}

    # ── Automated Event Notification Triggers ─────────────────────────────────
    @classmethod
    def trigger_event_notification(
        cls,
        event_type: str,
        context: Dict[str, Any],
        db: Session
    ) -> Dict[str, Any]:
        """
        Main trigger bus for automated system events (Exeat, Results, Fees, Attendance).
        """
        cfg = cls.get_gateway_config(db)
        school = db.query(School).first()
        school_name = school.name if school else "SHS Institutional Portal"

        student_id = context.get("student_id")
        student = db.query(Student).filter(Student.id == student_id).first() if student_id else None
        student_name = student.full_name if student else (context.get("student_name") or "Student")
        guardian_name = (student.guardian_name if student else None) or context.get("guardian_name") or "Parent/Guardian"
        guardian_phone = (student.phone if student else None) or context.get("parent_contact") or context.get("phone") or ""
        class_name = (student.class_section.name if (student and student.class_section) else None) or context.get("class_name") or "Class"

        results = {"event_type": event_type, "triggered": False, "notifications": []}

        # 1. Event: Ward Departed Gate on Exeat (EXEAT_GATE_OUT)
        if event_type == "EXEAT_GATE_OUT" and cfg.get("auto_notify_exeat_gateout"):
            dest = context.get("destination", "Home")
            ex_type = context.get("exeat_type", "General")
            ret_time = context.get("expected_return", "Scheduled Date")
            now_str = datetime.now().strftime("%d %b, %H:%M")

            sms_msg = (
                f"EXEAT DEPARTURE NOTICE: {student_name} ({class_name}) has departed campus for {dest} ({ex_type} Exeat) at {now_str}. "
                f"Expected return: {ret_time}. - {school_name}"
            )
            wa_msg = (
                f"🏡 *CAMPUS EXEAT DEPARTURE NOTICE*\n\n"
                f"Dear {guardian_name},\n"
                f"Please be informed that your ward *{student_name}* ({class_name}) has just passed the security gate and departed campus.\n\n"
                f"📍 *Destination:* {dest}\n"
                f"📋 *Exeat Category:* {ex_type}\n"
                f"🕒 *Departure Time:* {now_str}\n"
                f"📅 *Expected Return:* {ret_time}\n\n"
                f"📌 _{school_name} Domestic & Security Registry_"
            )

            res_sms = cls.send_sms(db, guardian_phone, sms_msg, student_id=student_id, recipient_name=guardian_name, message_type="EXEAT_NOTICE")
            res_wa = cls.send_whatsapp(db, guardian_phone, wa_msg, student_id=student_id, recipient_name=guardian_name, message_type="EXEAT_NOTICE")
            results["triggered"] = True
            results["notifications"] = [res_sms, res_wa]
            return results

        # 2. Event: Ward Safely Returned to Gate (EXEAT_GATE_IN)
        if event_type == "EXEAT_GATE_IN" and cfg.get("auto_notify_exeat_gatein"):
            now_str = datetime.now().strftime("%d %b, %H:%M")
            sms_msg = f"EXEAT RETURN CONFIRMED: {student_name} ({class_name}) has safely arrived back on campus at {now_str}. - {school_name}"
            wa_msg = (
                f"✅ *CAMPUS ARRIVAL CONFIRMATION*\n\n"
                f"Dear {guardian_name},\n"
                f"Your ward *{student_name}* ({class_name}) has safely returned to campus and checked in at the gatehouse on {now_str}.\n\n"
                f"📌 _{school_name} Security Registry_"
            )
            res_sms = cls.send_sms(db, guardian_phone, sms_msg, student_id=student_id, recipient_name=guardian_name, message_type="EXEAT_NOTICE")
            res_wa = cls.send_whatsapp(db, guardian_phone, wa_msg, student_id=student_id, recipient_name=guardian_name, message_type="EXEAT_NOTICE")
            results["triggered"] = True
            results["notifications"] = [res_sms, res_wa]
            return results

        # 3. Event: Fee Payment Confirmation Receipt (FEE_PAYMENT)
        if event_type == "FEE_PAYMENT" and cfg.get("auto_notify_fee_payment"):
            amount = context.get("amount", 0.0)
            receipt_no = context.get("receipt_no", "REC-000")
            balance = context.get("balance", 0.0)
            sms_msg = (
                f"PAYMENT RECEIPT: Received GHC {amount:,.2f} for {student_name} ({class_name}). "
                f"Receipt: {receipt_no}. Balance: GHC {balance:,.2f}. Thank you! - {school_name} Bursary"
            )
            wa_msg = (
                f"💳 *OFFICIAL SCHOOL FEE RECEIPT*\n\n"
                f"Dear {guardian_name},\n"
                f"We confirm receipt of payment for *{student_name}* ({class_name}).\n\n"
                f"💰 *Amount Paid:* GH₵ {amount:,.2f}\n"
                f"🧾 *Receipt No:* {receipt_no}\n"
                f"📊 *Outstanding Balance:* GH₵ {balance:,.2f}\n"
                f"📅 *Date:* {datetime.now().strftime('%d %b %Y, %H:%M')}\n\n"
                f"📌 _{school_name} Accounts & Finance Desk_"
            )
            res_sms = cls.send_sms(db, guardian_phone, sms_msg, student_id=student_id, recipient_name=guardian_name, message_type="FEE_RECEIPT")
            res_wa = cls.send_whatsapp(db, guardian_phone, wa_msg, student_id=student_id, recipient_name=guardian_name, message_type="FEE_RECEIPT")
            results["triggered"] = True
            results["notifications"] = [res_sms, res_wa]
            return results

        # 4. Event: Student Absent Alert (STUDENT_ABSENT)
        if event_type == "STUDENT_ABSENT" and cfg.get("auto_notify_absence"):
            date_str = context.get("date", datetime.now().strftime("%d %b %Y"))
            sms_msg = f"ABSENCE ALERT: {student_name} ({class_name}) was marked absent on {date_str}. Please contact school if unexpected. - {school_name}"
            wa_msg = (
                f"🔔 *ATTENDANCE / ABSENCE NOTICE*\n\n"
                f"Dear {guardian_name},\n"
                f"Please be informed that your child *{student_name}* ({class_name}) was marked ABSENT from roll-call on *{date_str}*.\n\n"
                f"If this absence is unexcused, please reach out to the Form Master immediately.\n\n"
                f"📌 _{school_name} Academic Register_"
            )
            res_sms = cls.send_sms(db, guardian_phone, sms_msg, student_id=student_id, recipient_name=guardian_name, message_type="ABSENCE_ALERT")
            results["triggered"] = True
            results["notifications"] = [res_sms]
            return results

        return results

    # ── Internal Message Logger ───────────────────────────────────────────────
    @staticmethod
    def _log_message(
        db: Session,
        sender_id: Optional[int],
        student_id: Optional[int],
        recipient_name: Optional[str],
        recipient_phone: Optional[str],
        channel: str,
        message_type: str,
        message_body: str,
        status: str
    ) -> MessageLog:
        try:
            log_entry = MessageLog(
                sender_id=sender_id,
                student_id=student_id,
                recipient_name=recipient_name or "Guardian",
                recipient_phone=recipient_phone or "",
                channel=channel,
                message_type=message_type,
                message_body=message_body,
                status=status,
                created_at=datetime.now()
            )
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)
            return log_entry
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to record message log: {e}")
            return None
