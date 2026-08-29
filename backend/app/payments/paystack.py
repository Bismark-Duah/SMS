"""
Paystack Payment Integration Package (Subaccounts, Split Settlements & Webhook Signature Guard).
Implements automated 95/5 percentage splits, live >= 1.00 GHS minimum validation,
and HMAC-SHA512 cryptographic verification.
"""
import os
import hmac
import hashlib
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from ..models import Setting, School, SchoolSubaccount

def get_paystack_secret_key(db: Optional[Session] = None) -> str:
    if db:
        try:
            s = db.query(Setting).filter(Setting.key == "paystack_secret_key").first()
            if s and s.value and s.value.strip():
                return s.value.strip()
        except Exception:
            pass
    return os.getenv("PAYSTACK_SECRET_KEY", "").strip()

def get_paystack_public_key(db: Optional[Session] = None) -> str:
    if db:
        try:
            s = db.query(Setting).filter(Setting.key == "paystack_public_key").first()
            if s and s.value and s.value.strip():
                return s.value.strip()
        except Exception:
            pass
    return os.getenv("PAYSTACK_PUBLIC_KEY", "").strip()

def verify_paystack_signature(payload_bytes: bytes, signature_header: str, db: Optional[Session] = None) -> bool:
    """
    Cryptographic HMAC-SHA512 verification of Paystack webhook payloads.
    """
    secret = get_paystack_secret_key(db)
    if not secret:
        return False
    computed_hmac = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha512).hexdigest()
    return hmac.compare_digest(computed_hmac, signature_header.strip())

def create_paystack_subaccount(
    school_name: str,
    settlement_bank: str,
    account_number: str,
    percentage_charge: float = 95.0,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Calls https://api.paystack.co/subaccount to provision a Dedicated Settlement Subaccount.
    percentage_charge: % credited to the school (default 95.0%).
    """
    secret_key = get_paystack_secret_key(db)
    if not secret_key:
        return {
            "status": "offline_fallback",
            "subaccount_code": f"ACCT_OFFLINE_{abs(hash(school_name)) % 1000000}",
            "message": "Paystack unconfigured; generated local mock subaccount."
        }

    url = "https://api.paystack.co/subaccount"
    payload = {
        "business_name": school_name,
        "settlement_bank": settlement_bank,
        "account_number": account_number,
        "percentage_charge": float(percentage_charge),
        "primary_contact_name": school_name[:50]
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status"):
                return {
                    "status": "success",
                    "subaccount_code": data["data"]["subaccount_code"],
                    "id": data["data"]["id"],
                    "data": data["data"]
                }
            return {"status": "error", "message": data.get("message", "Paystack subaccount creation failed")}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def initialize_paystack_transaction(
    email: str,
    amount_pesewas: int,
    school_id: int,
    reference: str,
    callback_url: Optional[str] = None,
    db: Optional[Session] = None,
    custom_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Initializes a Paystack transaction with automated Subaccount split and platform commission.
    Enforces minimum live amount of 100 pesewas (1.00 GHS).
    """
    # 1. Enforce live minimum amount
    if amount_pesewas < 100:
        raise ValueError("Transaction amount must be at least 100 pesewas (1.00 GHS).")

    secret_key = get_paystack_secret_key(db)
    
    # 2. Resolve School Subaccount Code and Commission
    subaccount_code = None
    platform_commission_percent = 5.0

    if db:
        sub = db.query(SchoolSubaccount).filter(SchoolSubaccount.school_id == school_id).first()
        if sub and sub.paystack_subaccount_code:
            subaccount_code = sub.paystack_subaccount_code

        school = db.query(School).filter(School.id == school_id).first()
        if school and school.platform_commission_percent is not None:
            platform_commission_percent = school.platform_commission_percent

    platform_fee_pesewas = int(round(amount_pesewas * (platform_commission_percent / 100.0)))

    if not secret_key:
        # Offline or Dev Mode Fallback
        return {
            "status": "offline_fallback",
            "authorization_url": f"/paystack-callback?reference={reference}&status=success",
            "reference": reference,
            "access_code": f"ACCESS_{reference}"
        }

    url = "https://api.paystack.co/transaction/initialize"
    metadata = {
        "school_id": school_id,
        "custom_fields": [
            {"display_name": "School ID", "variable_name": "school_id", "value": str(school_id)}
        ]
    }
    if custom_metadata:
        metadata.update(custom_metadata)

    payload: Dict[str, Any] = {
        "email": email,
        "amount": amount_pesewas,
        "reference": reference,
        "currency": "GHS",
        "metadata": metadata
    }

    if callback_url:
        payload["callback_url"] = callback_url

    if subaccount_code:
        payload["subaccount"] = subaccount_code
        payload["transaction_charge"] = platform_fee_pesewas
        payload["bearer"] = "subaccount"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status"):
                return {
                    "status": "success",
                    "authorization_url": data["data"]["authorization_url"],
                    "access_code": data["data"]["access_code"],
                    "reference": data["data"]["reference"]
                }
            return {"status": "error", "message": data.get("message", "Paystack transaction initialize failed")}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def verify_paystack_transaction(reference: str, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Verifies transaction status directly via https://api.paystack.co/transaction/verify/{reference}
    """
    secret_key = get_paystack_secret_key(db)
    if not secret_key:
        return {
            "status": "offline_fallback",
            "verified": True,
            "reference": reference,
            "message": "Offline fallback verification"
        }

    url = f"https://api.paystack.co/transaction/verify/{reference}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {secret_key}"},
        method="GET"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") and data.get("data", {}).get("status") == "success":
                tx_data = data["data"]
                return {
                    "status": "success",
                    "verified": True,
                    "reference": tx_data.get("reference"),
                    "amount": tx_data.get("amount", 0) / 100.0,
                    "channel": tx_data.get("channel"),
                    "customer": tx_data.get("customer", {}),
                    "metadata": tx_data.get("metadata", {}),
                    "paid_at": tx_data.get("paid_at")
                }
            return {
                "status": "failed",
                "verified": False,
                "message": data.get("data", {}).get("gateway_response", "Transaction not successful")
            }
    except Exception as e:
        return {"status": "error", "verified": False, "message": str(e)}
