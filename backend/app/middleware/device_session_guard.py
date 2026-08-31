"""
Zero-Trust Multi-Device Session Guard & Anomaly Engine.
Enforces single active session for institutional staff and manages device security registries.
"""
import hashlib
import re
from datetime import datetime
from sqlalchemy.orm import Session
from ..models import UserDeviceSession, User

STAFF_ROLES = {
    "admin", "super_admin", "headmaster", "assistant_headmaster",
    "teacher", "hod", "form_master", "form_mistress",
    "house_master", "house_mistress", "senior_housemaster", "senior_housemistress",
    "bursar", "accountant", "storekeeper", "security"
}

def parse_device_name(user_agent: str) -> str:
    """Extracts human-readable device & browser label from User-Agent string."""
    if not user_agent:
        return "Unknown Device"
    
    ua = user_agent.lower()
    os_name = "Desktop"
    if "windows" in ua:
        os_name = "Windows PC"
    elif "macintosh" in ua or "mac os" in ua:
        os_name = "Mac"
    elif "android" in ua:
        os_name = "Android Device"
    elif "iphone" in ua or "ipad" in ua:
        os_name = "iPhone/iPad"
    elif "linux" in ua:
        os_name = "Linux PC"

    browser = "Browser"
    if "chrome" in ua and "edg" not in ua and "opr" not in ua:
        browser = "Chrome"
    elif "edg" in ua:
        browser = "Edge"
    elif "safari" in ua and "chrome" not in ua:
        browser = "Safari"
    elif "firefox" in ua:
        browser = "Firefox"

    return f"{browser} on {os_name}"


def hash_token(token: str) -> str:
    """Generates cryptographic SHA-256 digest of JWT token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def register_device_session(
    user_id: int,
    user_role: str,
    user_agent: str,
    client_ip: str,
    token: str,
    db: Session
) -> UserDeviceSession:
    """
    Registers a new device login session.
    Enforces strict 1-device policy for staff by terminating prior sessions.
    """
    token_digest = hash_token(token)
    device_fp = hashlib.sha256(f"{user_id}:{user_agent}".encode("utf-8")).hexdigest()
    device_name = parse_device_name(user_agent)

    # 1. If Staff / Admin, invalidate all existing active sessions
    role_clean = (user_role or "").lower()
    if role_clean in STAFF_ROLES or "admin" in role_clean or "master" in role_clean:
        db.query(UserDeviceSession).filter(
            UserDeviceSession.user_id == user_id,
            UserDeviceSession.is_active == True
        ).update({"is_active": False}, synchronize_session=False)
        db.flush()

    # 2. If Student/Parent, keep max 3 active devices
    else:
        active_sessions = db.query(UserDeviceSession).filter(
            UserDeviceSession.user_id == user_id,
            UserDeviceSession.is_active == True
        ).order_by(UserDeviceSession.last_active.desc()).all()
        
        if len(active_sessions) >= 3:
            for old_sess in active_sessions[2:]:
                old_sess.is_active = False

    # 3. Create or update active device session
    existing_session = db.query(UserDeviceSession).filter(
        UserDeviceSession.session_token_hash == token_digest
    ).first()

    if existing_session:
        existing_session.user_id = user_id
        existing_session.device_fingerprint = device_fp
        existing_session.device_name = device_name
        existing_session.ip_address = client_ip
        existing_session.user_agent = user_agent
        existing_session.is_active = True
        db.commit()
        db.refresh(existing_session)
        return existing_session

    new_session = UserDeviceSession(
        user_id=user_id,
        device_fingerprint=device_fp,
        device_name=device_name,
        ip_address=client_ip,
        user_agent=user_agent,
        session_token_hash=token_digest,
        is_active=True
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


def is_session_active(token: str, user_id: int, db: Session) -> bool:
    """
    Checks whether the JWT token's device session is currently active.
    Returns True if active or if no record exists yet (graceful backwards-compat).
    """
    token_digest = hash_token(token)
    session_record = db.query(UserDeviceSession).filter(
        UserDeviceSession.session_token_hash == token_digest,
        UserDeviceSession.user_id == user_id
    ).first()

    if not session_record:
        # If created prior to session tracking, allow
        return True

    return bool(session_record.is_active)


def revoke_all_other_sessions(user_id: int, current_token: str, db: Session) -> int:
    """Revokes all active sessions for this user except the current token."""
    token_digest = hash_token(current_token)
    count = db.query(UserDeviceSession).filter(
        UserDeviceSession.user_id == user_id,
        UserDeviceSession.session_token_hash != token_digest,
        UserDeviceSession.is_active == True
    ).update({"is_active": False}, synchronize_session=False)
    db.commit()
    return count
