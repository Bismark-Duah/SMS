"""
Enterprise Multi-Gateway SMS Integration Package for eduManage360.
Implements Abstract Base Gateway, mNotify v2 REST Client, Hubtel REST Client,
Automatic Failover Routing, Ghanaian Phone Normalization (E.164), Bulk Batching,
and Admission Package Voucher / PIN Delivery.
"""

import os
import re
import json
import logging
import urllib.request
import urllib.parse
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from ..models import Setting, School, TenantSmsConfig, MessageLog

logger = logging.getLogger("sms_gateway")

# ── Ghanaian Phone Normalization & Masking ───────────────────────────────────

def normalize_ghana_phone(phone: Any) -> str:
    """
    Sanitizes Ghanaian mobile numbers to standard E.164 format: 233XXXXXXXXX.
    Handles:
    - 0244123456 -> 233244123456
    - +233244123456 -> 233244123456
    - 244123456 -> 233244123456
    - 233244123456 -> 233244123456
    - Spaces, dashes, and parentheses stripping.
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

def mask_phone_number(phone: str) -> str:
    """
    Masks a phone number for privacy and Act 843 compliance: 23324****567.
    """
    p = str(phone or "").strip()
    if len(p) <= 6:
        return p
    return f"{p[:5]}****{p[-3:]}"


# ── Base Gateway Interface ───────────────────────────────────────────────────

class BaseSMSGateway(ABC):
    """Abstract Base Class for SMS Gateway Providers."""

    @abstractmethod
    def send_sms(
        self,
        recipient_phone: str,
        message_body: str,
        sender_id: str,
        credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Dispatches a single SMS."""
        pass

    @abstractmethod
    def send_bulk_sms(
        self,
        recipient_phones: List[str],
        message_body: str,
        sender_id: str,
        credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Dispatches bulk SMS to an array of recipients."""
        pass

    @abstractmethod
    def check_balance(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Checks gateway wallet/SMS balance."""
        pass


# ── mNotify Gateway Implementation ──────────────────────────────────────────

class MNotifySMSGateway(BaseSMSGateway):
    """
    mNotify v2 REST SMS Gateway.
    Official Endpoints:
    - Quick SMS: https://api.mnotify.com/api/sms/quick
    - Balance Check: https://api.mnotify.com/api/balance/sms
    """

    QUICK_SMS_URL = "https://api.mnotify.com/api/sms/quick"
    BALANCE_URL = "https://api.mnotify.com/api/balance/sms"

    def send_sms(
        self,
        recipient_phone: str,
        message_body: str,
        sender_id: str,
        credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self.send_bulk_sms([recipient_phone], message_body, sender_id, credentials)

    def send_bulk_sms(
        self,
        recipient_phones: List[str],
        message_body: str,
        sender_id: str,
        credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        api_key = credentials.get("api_key") or credentials.get("mnotify_api_key")
        if not api_key:
            return {"status": "unconfigured", "message": "mNotify API key missing."}

        clean_recipients = [normalize_ghana_phone(p) for p in recipient_phones if normalize_ghana_phone(p)]
        if not clean_recipients:
            return {"status": "error", "message": "No valid recipient phone numbers provided."}

        # Format payload for mNotify API
        payload = {
            "recipient[]": clean_recipients,
            "sender": (sender_id or "EDUMANAGE")[:11],
            "message": message_body,
            "is_schedule": False
        }
        encoded_data = json.dumps(payload).encode("utf-8")
        url = f"{self.QUICK_SMS_URL}?key={urllib.parse.quote(api_key.strip())}"

        req = urllib.request.Request(
            url,
            data=encoded_data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "EduManage360-SMS-Engine/1.0",
                "Accept": "application/json"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                resp_text = resp.read().decode("utf-8")
                resp_json = json.loads(resp_text)
                status_code = resp.status

                is_success = status_code in [200, 201] and resp_json.get("status") in ["success", "1000", 200, "200"]
                message_id = (
                    resp_json.get("summary", {}).get("_id")
                    or resp_json.get("message_id")
                    or resp_json.get("id")
                    or f"MNOTIFY_{abs(hash(message_body)) % 1000000}"
                )

                return {
                    "status": "success" if is_success else "failed",
                    "gateway": "MNOTIFY",
                    "message_id": str(message_id),
                    "recipients_count": len(clean_recipients),
                    "response": resp_json
                }
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8") if he.fp else str(he)
            logger.warning(f"mNotify HTTP Error {he.code}: {err_body}")
            return {
                "status": "error",
                "gateway": "MNOTIFY",
                "http_code": he.code,
                "message": f"mNotify HTTP {he.code}: {err_body}"
            }
        except Exception as e:
            logger.warning(f"mNotify network failure: {e}")
            return {
                "status": "error",
                "gateway": "MNOTIFY",
                "message": f"mNotify network failure: {str(e)}"
            }

    def check_balance(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        api_key = credentials.get("api_key") or credentials.get("mnotify_api_key")
        if not api_key:
            return {"status": "unconfigured", "balance": 0, "message": "mNotify API key missing."}

        url = f"{self.BALANCE_URL}?key={urllib.parse.quote(api_key.strip())}"
        req = urllib.request.Request(url, headers={"User-Agent": "EduManage360-SMS-Engine/1.0"})

        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                balance = data.get("balance") or data.get("sms_balance") or 0
                return {
                    "status": "connected",
                    "gateway": "MNOTIFY",
                    "sms_balance": balance,
                    "raw": data
                }
        except Exception as e:
            return {
                "status": "error",
                "gateway": "MNOTIFY",
                "message": f"Could not fetch mNotify balance: {str(e)}"
            }


# ── Hubtel Gateway Implementation ───────────────────────────────────────────

class HubtelSMSGateway(BaseSMSGateway):
    """
    Hubtel QuickSMS REST Gateway.
    Official Endpoint: https://sms.hubtel.com/v1/messages/send
    """

    SEND_URL = "https://sms.hubtel.com/v1/messages/send"

    def send_sms(
        self,
        recipient_phone: str,
        message_body: str,
        sender_id: str,
        credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        client_id = credentials.get("client_id") or credentials.get("hubtel_client_id")
        client_secret = credentials.get("client_secret") or credentials.get("hubtel_client_secret")

        if not client_id or not client_secret:
            return {"status": "unconfigured", "message": "Hubtel credentials missing."}

        clean_phone = normalize_ghana_phone(recipient_phone)
        if not clean_phone:
            return {"status": "error", "message": "Invalid recipient phone."}

        params = {
            "clientid": client_id.strip(),
            "clientsecret": client_secret.strip(),
            "from": (sender_id or "EDUMANAGE")[:11],
            "to": clean_phone,
            "content": message_body
        }
        url = f"{self.SEND_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "EduManage360-SMS-Engine/1.0"})

        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                hubtel_id = resp_data.get("messageid") or resp_data.get("id") or str(resp_data.get("status"))
                is_success = resp_data.get("status") in [0, "0", "Success", "Scheduled", 200]

                return {
                    "status": "success" if is_success else "failed",
                    "gateway": "HUBTEL",
                    "message_id": str(hubtel_id),
                    "recipients_count": 1,
                    "response": resp_data
                }
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8") if he.fp else str(he)
            logger.warning(f"Hubtel HTTP Error {he.code}: {err_body}")
            return {
                "status": "error",
                "gateway": "HUBTEL",
                "http_code": he.code,
                "message": f"Hubtel HTTP {he.code}: {err_body}"
            }
        except Exception as e:
            logger.warning(f"Hubtel network failure: {e}")
            return {
                "status": "error",
                "gateway": "HUBTEL",
                "message": f"Hubtel network failure: {str(e)}"
            }

    def send_bulk_sms(
        self,
        recipient_phones: List[str],
        message_body: str,
        sender_id: str,
        credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        results = []
        for p in recipient_phones:
            res = self.send_sms(p, message_body, sender_id, credentials)
            results.append(res)
        return {
            "status": "bulk_completed",
            "gateway": "HUBTEL",
            "results": results,
            "recipients_count": len(recipient_phones)
        }

    def check_balance(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "active" if credentials.get("client_id") else "unconfigured",
            "gateway": "HUBTEL",
            "message": "Hubtel credentials registered."
        }


# ── Multi-Gateway Failover Engine ────────────────────────────────────────────

class MultiGatewaySMSEngine:
    """
    Enterprise SMS Dispatch Engine with Dual Failover & Quota Management.
    Provider Chain: Preferred Gateway (mNotify / Hubtel) -> Secondary Gateway -> Offline SQLite Outbox.
    """

    def __init__(self):
        self.mnotify = MNotifySMSGateway()
        self.hubtel = HubtelSMSGateway()

    def resolve_credentials(
        self,
        db: Optional[Session] = None,
        school_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Resolves gateway credentials from Tenant Config, Database Settings, and Environment.
        """
        creds = {
            "mnotify_api_key": os.getenv("MNOTIFY_API_KEY", "").strip(),
            "mnotify_sender_id": os.getenv("MNOTIFY_SENDER_ID", "EDUMANAGE").strip(),
            "hubtel_client_id": os.getenv("HUBTEL_CLIENT_ID", "").strip(),
            "hubtel_client_secret": os.getenv("HUBTEL_CLIENT_SECRET", "").strip(),
            "primary_gateway": os.getenv("SMS_PRIMARY_GATEWAY", "mnotify").strip().lower(),
            "auto_failover": True,
            "school_sender_id": None
        }

        if not db:
            return creds

        # 1. School Tenant Config
        if school_id:
            cfg = db.query(TenantSmsConfig).filter(TenantSmsConfig.school_id == school_id).first()
            if cfg:
                if cfg.sender_id:
                    creds["school_sender_id"] = cfg.sender_id.strip()[:11]
                if getattr(cfg, "mnotify_api_key", None):
                    creds["mnotify_api_key"] = cfg.mnotify_api_key.strip()
                if cfg.hubtel_client_id:
                    creds["hubtel_client_id"] = cfg.hubtel_client_id.strip()
                if cfg.hubtel_client_secret:
                    creds["hubtel_client_secret"] = cfg.hubtel_client_secret.strip()
                if cfg.provider:
                    creds["primary_gateway"] = cfg.provider.strip().lower()

        # 2. System Settings fallback
        settings = db.query(Setting).filter(
            Setting.key.in_([
                "mnotify_api_key",
                "mnotify_sender_id",
                "hubtel_client_id",
                "hubtel_client_secret",
                "sms_primary_gateway",
                "sms_auto_failover"
            ])
        ).all()
        s_map = {s.key: s.value for s in settings if s.value}

        if s_map.get("mnotify_api_key"):
            creds["mnotify_api_key"] = s_map["mnotify_api_key"].strip()
        if s_map.get("mnotify_sender_id"):
            creds["mnotify_sender_id"] = s_map["mnotify_sender_id"].strip()
        if s_map.get("hubtel_client_id"):
            creds["hubtel_client_id"] = s_map["hubtel_client_id"].strip()
        if s_map.get("hubtel_client_secret"):
            creds["hubtel_client_secret"] = s_map["hubtel_client_secret"].strip()
        if s_map.get("sms_primary_gateway"):
            creds["primary_gateway"] = s_map["sms_primary_gateway"].strip().lower()

        return creds

    def dispatch(
        self,
        recipient_phone: str,
        message_body: str,
        school_id: Optional[int] = None,
        db: Optional[Session] = None,
        sender_id: Optional[str] = None,
        sender_user_id: Optional[int] = None,
        student_id: Optional[int] = None,
        recipient_name: Optional[str] = None,
        message_type: str = "TRANSACTIONAL"
    ) -> Dict[str, Any]:
        """
        Dispatches SMS through the multi-gateway failover chain.
        """
        clean_phone = normalize_ghana_phone(recipient_phone)
        if not clean_phone:
            return {"status": "error", "message": "Invalid recipient phone number."}

        creds = self.resolve_credentials(db, school_id)
        active_sender = sender_id or creds.get("school_sender_id") or creds.get("mnotify_sender_id") or "EDUMANAGE"
        active_sender = active_sender[:11]

        # 1. School Balance Quota Validation (if school_id and db provided)
        current_balance = 0
        school = None
        if db and school_id:
            school = db.query(School).filter(School.id == school_id).with_for_update().first()
            if school:
                current_balance = school.sms_balance if school.sms_balance is not None else 0
                if current_balance <= 0:
                    return {
                        "status": "error",
                        "message": f"School SMS quota depleted ({current_balance} units). Please top up to continue."
                    }

        primary_gw = creds.get("primary_gateway", "mnotify")
        mnotify_has_keys = bool(creds.get("mnotify_api_key"))
        hubtel_has_keys = bool(creds.get("hubtel_client_id") and creds.get("hubtel_client_secret"))

        # Order of gateways to attempt
        gateway_order = []
        if primary_gw == "hubtel":
            if hubtel_has_keys:
                gateway_order.append(("HUBTEL", self.hubtel, {"client_id": creds["hubtel_client_id"], "client_secret": creds["hubtel_client_secret"]}))
            if mnotify_has_keys:
                gateway_order.append(("MNOTIFY", self.mnotify, {"api_key": creds["mnotify_api_key"]}))
        else:
            # Default to mNotify first
            if mnotify_has_keys:
                gateway_order.append(("MNOTIFY", self.mnotify, {"api_key": creds["mnotify_api_key"]}))
            if hubtel_has_keys:
                gateway_order.append(("HUBTEL", self.hubtel, {"client_id": creds["hubtel_client_id"], "client_secret": creds["hubtel_client_secret"]}))

        last_error = "No active SMS gateway configured."

        # 2. Attempt Gateway Dispatch with Automatic Failover
        for gw_name, gateway_instance, gw_creds in gateway_order:
            try:
                res = gateway_instance.send_sms(clean_phone, message_body, active_sender, gw_creds)
                if res.get("status") == "success":
                    # Deduct quota and log success
                    if school and db:
                        school.sms_balance = current_balance - 1
                        self._log_message(
                            db=db,
                            school_id=school_id,
                            sender_user_id=sender_user_id,
                            student_id=student_id,
                            recipient_name=recipient_name or clean_phone,
                            recipient_phone=clean_phone,
                            message_type=message_type,
                            message_body=message_body,
                            status="SENT",
                            message_id=res.get("message_id"),
                            cost=1.0
                        )
                    return {
                        "status": "success",
                        "gateway": gw_name,
                        "sender_id": active_sender,
                        "recipient": mask_phone_number(clean_phone),
                        "message_id": res.get("message_id"),
                        "remaining_balance": school.sms_balance if school else None
                    }
                else:
                    last_error = res.get("message") or f"{gw_name} dispatch failed."
                    logger.warning(f"Primary SMS Gateway {gw_name} failed: {last_error}. Attempting fallback...")
            except Exception as ex:
                last_error = str(ex)
                logger.warning(f"Exception on gateway {gw_name}: {ex}. Attempting fallback...")

        # 3. Fallback to Offline / Queued Mode
        if school and db:
            school.sms_balance = max(0, current_balance - 1)

        sim_msg_id = f"OFFLINE_QUEUE_{abs(hash(message_body)) % 1000000}"
        if db:
            self._log_message(
                db=db,
                school_id=school_id,
                sender_user_id=sender_user_id,
                student_id=student_id,
                recipient_name=recipient_name or clean_phone,
                recipient_phone=clean_phone,
                message_type=message_type,
                message_body=message_body,
                status="QUEUED_OFFLINE",
                message_id=sim_msg_id,
                cost=1.0
            )

        return {
            "status": "offline_fallback",
            "message": f"Message safely queued in local offline outbox ({last_error}).",
            "sender_id": active_sender,
            "recipient": mask_phone_number(clean_phone),
            "message_id": sim_msg_id,
            "remaining_balance": school.sms_balance if school else None
        }

    def _log_message(
        self,
        db: Session,
        school_id: Optional[int],
        sender_user_id: Optional[int],
        student_id: Optional[int],
        recipient_name: str,
        recipient_phone: str,
        message_type: str,
        message_body: str,
        status: str,
        message_id: Optional[str] = None,
        cost: float = 1.0
    ):
        try:
            log = MessageLog(
                school_id=school_id,
                sender_id=sender_user_id,
                student_id=student_id,
                recipient_name=recipient_name,
                recipient_phone=recipient_phone,
                channel="SMS",
                message_type=message_type,
                message_body=message_body,
                status=status,
                hubtel_message_id=str(message_id) if message_id else None,
                cost=cost
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to record message log: {e}")
            db.rollback()


# Singleton Instance
sms_engine = MultiGatewaySMSEngine()


# ── Admission Package & Voucher PIN Dispatcher ───────────────────────────────

def send_admission_voucher_sms(
    guardian_phone: str,
    applicant_name: str,
    school_name: str,
    serial_no: str,
    pin: str,
    portal_url: Optional[str] = None,
    school_id: Optional[int] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Dispatches standard Admission E-Voucher Serial Number & PIN SMS to the applicant's guardian.
    Formatted to fit within a single 160-character SMS page.
    """
    clean_school = (school_name or "eduManage360").strip()
    clean_applicant = (applicant_name or "Applicant").strip()
    clean_url = portal_url or "sms-nald.onrender.com/apply.html"

    # Compact single-unit SMS template
    message_body = (
        f"[{clean_school}] Admission Portal:\n"
        f"Applicant: {clean_applicant}\n"
        f"Serial: {serial_no}\n"
        f"PIN: {pin}\n"
        f"Apply: {clean_url}\n"
        f"Keep PIN confidential."
    )

    return sms_engine.dispatch(
        recipient_phone=guardian_phone,
        message_body=message_body,
        school_id=school_id,
        db=db,
        recipient_name=clean_applicant,
        message_type="VOUCHER_PIN"
    )
