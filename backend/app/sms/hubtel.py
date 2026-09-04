"""
Hubtel SMS Integration Package for SaaS School Management System.
Handles Ghanaian phone number normalization (0XXXXXXXXX -> 233XXXXXXXXX),
dynamic approved Sender IDs per school, real-time SMS quota debits, and delivery logging.
Powered by the MultiGatewaySMSEngine with automatic mNotify / Hubtel failover.
"""
import os
import re
import urllib.request
import urllib.parse
import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from ..models import Setting, School, TenantSmsConfig, MessageLog
from .gateway import normalize_ghana_phone, mask_phone_number, sms_engine

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
    Sends school-branded SMS via Hubtel API with automatic mNotify failover and real-time atomic balance deduction.
    """
    return sms_engine.dispatch(
        recipient_phone=recipient_phone,
        message_body=message_body,
        school_id=school_id,
        db=db,
        sender_id=sender_id,
        sender_user_id=sender_user_id,
        student_id=student_id,
        recipient_name=recipient_name,
        message_type="TRANSACTIONAL"
    )
