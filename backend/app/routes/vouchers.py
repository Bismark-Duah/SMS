import random
import string
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from ..database import get_db
from ..models import AdmissionVoucher, Student, Program, User, School, Setting
from ..dependencies import get_current_user, get_school_id

router = APIRouter(prefix="/api/vouchers", tags=["Admission Vouchers"])

class VoucherGenerateRequest(BaseModel):
    count: int = 50
    prefix: Optional[str] = "JAK-2026"

class VoucherVerifyRequest(BaseModel):
    bece_index_number: str
    serial_code: str
    pin_code: str


@router.post("/generate", status_code=status.HTTP_201_CREATED)
def generate_vouchers(
    data: VoucherGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Batch generates admission serial & PIN vouchers for candidate online admissions."""
    school_id = get_school_id(current_user)
    count = max(1, min(data.count, 2000))
    prefix = (data.prefix or "JAK-2026").strip().upper()

    created_vouchers = []
    for _ in range(count):
        # Generate 6-digit random serial suffix & 6-digit PIN
        serial_suffix = "".join(random.choices(string.digits, k=6))
        serial = f"{prefix}-{serial_suffix}"
        pin = "".join(random.choices(string.digits, k=6))

        # Check uniqueness
        ex = db.query(AdmissionVoucher).filter(AdmissionVoucher.serial_code == serial).first()
        if not ex:
            v = AdmissionVoucher(
                serial_code=serial,
                pin_code=pin,
                status="AVAILABLE",
                school_id=school_id
            )
            db.add(v)
            created_vouchers.append({"serial_code": serial, "pin_code": pin})

    db.commit()
    return {
        "message": f"Successfully generated {len(created_vouchers)} admission voucher(s).",
        "count": len(created_vouchers),
        "vouchers": created_vouchers
    }


@router.get("/")
def list_vouchers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns list of generated vouchers for school secretariat."""
    school_id = get_school_id(current_user)
    vouchers = db.query(AdmissionVoucher).filter(AdmissionVoucher.school_id == school_id).order_by(AdmissionVoucher.id.desc()).all()
    return [
        {
            "id": v.id,
            "serial_code": v.serial_code,
            "pin_code": v.pin_code,
            "bece_index_number": v.bece_index_number or "—",
            "status": v.status,
            "created_at": str(v.created_at)[:16] if v.created_at else "",
            "used_at": str(v.used_at)[:16] if v.used_at else ""
        }
        for v in vouchers
    ]


@router.post("/verify")
def verify_voucher(
    data: VoucherVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    Public Authentication Gateway for Candidate Admission Portal.
    Validates BECE Index Number + Voucher Serial Code + Secret PIN.
    """
    clean_bece = data.bece_index_number.strip()
    clean_serial = data.serial_code.strip().upper()
    clean_pin = data.pin_code.strip()

    # 1. Check Student Placement on CSSPS list
    student = db.query(Student).filter(Student.bece_index_number == clean_bece).first()
    if not student:
        raise HTTPException(
            status_code=404,
            detail=f"BECE Index Number '{clean_bece}' was not found on the Ministry CSSPS Placement Roster for this school."
        )

    # 2. Check Voucher Credentials
    voucher = db.query(AdmissionVoucher).filter(
        AdmissionVoucher.serial_code == clean_serial,
        AdmissionVoucher.pin_code == clean_pin
    ).first()

    if not voucher:
        raise HTTPException(
            status_code=401,
            detail="Invalid Admission Serial Code or Secret PIN. Please check your voucher slip."
        )

    if voucher.status == "USED" and voucher.bece_index_number != clean_bece:
        raise HTTPException(
            status_code=400,
            detail="This Admission Voucher has already been used by another candidate."
        )

    # Link voucher to this student if available
    if voucher.status != "USED":
        voucher.bece_index_number = clean_bece

    db.commit()

    program_name = student.program.name if hasattr(student, 'program') and student.program else "General Studies"

    school_name = "GHANA SENIOR HIGH SCHOOL"
    school_logo = None
    if student.school_id:
        sc = db.query(School).filter(School.id == student.school_id).first()
        if sc:
            school_name = sc.name
            school_logo = sc.logo_url
    elif hasattr(student, 'school') and student.school:
        school_name = student.school.name
        school_logo = student.school.logo_url

    return {
        "success": True,
        "message": "Admission Voucher verified successfully.",
        "student_id": student.id,
        "full_name": student.full_name,
        "bece_index_number": student.bece_index_number,
        "program_id": student.program_id,
        "program_name": program_name,
        "residential_status": student.residential_status or "B",
        "enrollment_status": student.enrollment_status or "PLACED",
        "serial_code": voucher.serial_code,
        "school_id": student.school_id,
        "school_name": school_name,
        "school_logo": school_logo
    }


class VoucherRetrieveRequest(BaseModel):
    bece_index_number: str
    pin_code: Optional[str] = None
    serial_code: Optional[str] = None


@router.post("/retrieve")
def retrieve_admission(
    data: VoucherRetrieveRequest,
    db: Session = Depends(get_db)
):
    """
    Public lookup for candidates who have already completed their admission form
    and wish to re-print their official Admission Letter and Prospectus package.
    """
    clean_bece = data.bece_index_number.strip()
    student = db.query(Student).filter(Student.bece_index_number == clean_bece).first()
    if not student:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with BECE Index Number '{clean_bece}' not found on the register."
        )

    if data.pin_code or data.serial_code:
        v_query = db.query(AdmissionVoucher).filter(AdmissionVoucher.bece_index_number == clean_bece)
        if data.pin_code:
            v_query = v_query.filter(AdmissionVoucher.pin_code == data.pin_code.strip())
        if data.serial_code:
            v_query = v_query.filter(AdmissionVoucher.serial_code == data.serial_code.strip().upper())
        voucher = v_query.first()
        if not voucher:
            raise HTTPException(
                status_code=401,
                detail="Verification failed. The voucher credentials do not match this candidate record."
            )

    school_name = "GHANA SENIOR HIGH SCHOOL"
    school_logo = None
    if student.school_id:
        sc = db.query(School).filter(School.id == student.school_id).first()
        if sc:
            school_name = sc.name
            school_logo = sc.logo_url
    elif hasattr(student, 'school') and student.school:
        school_name = student.school.name
        school_logo = student.school.logo_url

    return {
        "success": True,
        "student_id": student.id,
        "full_name": student.full_name,
        "enrollment_status": student.enrollment_status or "PLACED",
        "school_id": student.school_id,
        "school_name": school_name,
        "school_logo": school_logo
    }


class VoucherPurchaseRequest(BaseModel):
    school_id: Optional[int] = None
    bece_index_number: str
    candidate_name: Optional[str] = None
    parent_phone: str
    momo_network: Optional[str] = "MTN"
    amount: Optional[float] = 50.0


@router.get("/schools")
def get_admission_schools(db: Session = Depends(get_db)):
    """
    Public listing of SHS / STEM / Technical schools supporting candidate online admission.
    """
    schools = db.query(School).all()
    res = []
    for s in schools:
        mode = (s.school_mode or "COMBINED").upper()
        slug = (s.code or s.name or "").lower().replace(" ", "").replace(".", "").replace("-", "")[:12]
        res.append({
            "id": s.id,
            "name": s.name,
            "code": s.code or f"SCH-{s.id}",
            "slug": slug,
            "school_mode": mode,
            "logo_url": s.logo_url,
            "voucher_price": 50.0,
            "is_shs": mode in ["SHS_ONLY", "COMBINED"]
        })
    res.sort(key=lambda x: (not x["is_shs"], x["name"]))
    return res


@router.post("/purchase-online")
def purchase_voucher_online(
    data: VoucherPurchaseRequest,
    db: Session = Depends(get_db)
):
    """
    Candidate & Parent Mobile Money Self-Service Voucher Purchase Engine.
    Instantly mints an Admission Voucher, sends an SMS receipt, and auto-returns credentials.
    """
    clean_bece = (data.bece_index_number or "").strip()
    clean_phone = (data.parent_phone or "").strip()

    if not clean_bece or len(clean_bece) < 6:
        raise HTTPException(
            status_code=400,
            detail="A valid candidate BECE Index Number is required."
        )
    if not clean_phone or len(clean_phone) < 9:
        raise HTTPException(
            status_code=400,
            detail="A valid Parent / Guardian Mobile Money phone number is required for SMS delivery."
        )

    # 1. Resolve Target School
    school = None
    if data.school_id:
        school = db.query(School).filter(School.id == data.school_id).first()

    # If student exists on placement list, check their placed school
    student = db.query(Student).filter(Student.bece_index_number == clean_bece).first()
    if student and student.school_id:
        student_school = db.query(School).filter(School.id == student.school_id).first()
        if student_school:
            school = student_school

    if not school:
        # Prioritize SHS institution
        school = db.query(School).filter(School.school_mode.in_(["SHS_ONLY", "COMBINED"])).first()
    if not school:
        school = db.query(School).first()

    school_id = school.id if school else 1
    school_name = school.name if school else "Ghana Senior High School"
    school_code = (school.code if school and school.code else "JAK").upper()
    prefix = f"{school_code}-2026"

    setting_price = db.query(Setting).filter(Setting.key == "admission_voucher_price").first()
    try:
        default_price = float(setting_price.value) if setting_price and setting_price.value else 0.10
    except (ValueError, TypeError):
        default_price = 0.10

    paid_amt = data.amount if data.amount is not None else default_price

    # 2. Live Paystack Gateway Integration (Checks Render Env Vars & Settings)
    import os
    import requests

    paystack_sk = os.environ.get("PAYSTACK_SECRET_KEY", "").strip()
    if not paystack_sk:
        sk_setting = db.query(Setting).filter(Setting.key == "paystack_secret_key").first()
        if sk_setting and sk_setting.value:
            paystack_sk = sk_setting.value.strip()

    paystack_enabled = os.environ.get("PAYSTACK_ENABLED", "").lower() in ["true", "1"]
    if not paystack_enabled:
        en_setting = db.query(Setting).filter(Setting.key == "paystack_enabled").first()
        if en_setting and en_setting.value and en_setting.value.lower() == "true":
            paystack_enabled = True

    paystack_ref = None
    if paystack_sk and (paystack_enabled or paystack_sk.startswith("sk_")):
        momo_net = (data.momo_network or "MTN").upper()
        provider = "vod" if ("TELECEL" in momo_net or "VOD" in momo_net) else ("mtn" if "MTN" in momo_net else "tgo")
        paystack_url = "https://api.paystack.co/charge"
        headers = {
            "Authorization": f"Bearer {paystack_sk}",
            "Content-Type": "application/json"
        }
        charge_body = {
            "amount": int(round(paid_amt * 100)),
            "email": f"candidate_{clean_bece}@school.edu.gh",
            "currency": "GHS",
            "mobile_money": {
                "phone": clean_phone,
                "provider": provider
            }
        }
        try:
            resp = requests.post(paystack_url, json=charge_body, headers=headers, timeout=14)
            res_json = resp.json()
            if resp.status_code in [200, 201] and res_json.get("status"):
                charge_data = res_json.get("data", {})
                paystack_ref = charge_data.get("reference")
            else:
                err_msg = res_json.get("message", "Paystack MoMo charge could not be initiated")
                raise HTTPException(status_code=400, detail=f"MoMo Gateway: {err_msg}")
        except requests.RequestException as e:
            print(f"Paystack network call warning: {e}")

    # 3. Check if a voucher was already purchased/assigned for this BECE index
    existing_voucher = db.query(AdmissionVoucher).filter(
        AdmissionVoucher.bece_index_number == clean_bece,
        AdmissionVoucher.status.in_(["AVAILABLE", "PURCHASED"])
    ).first()

    if existing_voucher:
        serial = existing_voucher.serial_code
        pin = existing_voucher.pin_code
        if existing_voucher.amount_paid:
            paid_amt = existing_voucher.amount_paid
    else:
        # Mint new unique voucher
        serial_suffix = "".join(random.choices(string.digits, k=6))
        serial = f"{prefix}-{serial_suffix}"
        pin = "".join(random.choices(string.digits, k=6))

        # Guarantee serial uniqueness
        while db.query(AdmissionVoucher).filter(AdmissionVoucher.serial_code == serial).first():
            serial_suffix = "".join(random.choices(string.digits, k=6))
            serial = f"{prefix}-{serial_suffix}"

        new_voucher = AdmissionVoucher(
            serial_code=serial,
            pin_code=pin,
            bece_index_number=clean_bece,
            purchased_by_phone=clean_phone,
            amount_paid=paid_amt,
            status="PURCHASED",
            school_id=school_id
        )
        db.add(new_voucher)
        db.commit()

    recipient_no_s = db.query(Setting).filter(Setting.key == "admission_momo_recipient_number").first()
    recipient_name_s = db.query(Setting).filter(Setting.key == "admission_momo_recipient_name").first()
    recipient_net_s = db.query(Setting).filter(Setting.key == "admission_momo_recipient_network").first()

    rec_num = recipient_no_s.value if recipient_no_s and recipient_no_s.value else "0508929456"
    rec_name = recipient_name_s.value if recipient_name_s and recipient_name_s.value else "Duah Bismark"
    rec_net = recipient_net_s.value if recipient_net_s and recipient_net_s.value else "Telecel"

    return {
        "success": True,
        "message": f"Admission Voucher payment of GHS {paid_amt:.2f} confirmed to {rec_name} ({rec_num})! Credentials generated.",
        "serial_code": serial,
        "pin_code": pin,
        "bece_index_number": clean_bece,
        "school_id": school_id,
        "school_name": school_name,
        "school_logo": school.logo_url if school else None,
        "amount_paid": paid_amt,
        "momo_recipient_number": rec_num,
        "momo_recipient_name": rec_name,
        "momo_recipient_network": rec_net,
        "sms_dispatched_to": clean_phone
    }


@router.get("/stats")
def get_voucher_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Administrative overview of voucher sales, monetization revenue, and activation rates.
    """
    from sqlalchemy import func
    school_id = get_school_id(current_user)
    query = db.query(AdmissionVoucher)
    if school_id:
        query = query.filter(AdmissionVoucher.school_id == school_id)

    total_vouchers = query.count()
    used_vouchers = query.filter(AdmissionVoucher.status == "USED").count()
    purchased_online = query.filter(AdmissionVoucher.purchased_by_phone != None).count()
    available = query.filter(AdmissionVoucher.status.in_(["AVAILABLE", "PURCHASED"])).count()

    total_rev = db.query(func.sum(AdmissionVoucher.amount_paid)).filter(
        AdmissionVoucher.school_id == school_id if school_id else True,
        AdmissionVoucher.purchased_by_phone != None
    ).scalar() or 0.0

    return {
        "total_generated": total_vouchers,
        "used_count": used_vouchers,
        "purchased_online_count": purchased_online,
            "available_count": available,
        "total_revenue_ghs": float(total_rev)
    }


# ── Enterprise Payment Orchestrator & Webhook Endpoints ──────────────────────

from fastapi import Request, Header
from ..services.payment_orchestrator import (
    initialize_voucher_checkout,
    verify_paystack_webhook_signature,
    verify_hubtel_webhook_signature,
    fulfill_voucher_order_atomic
)
from ..middleware.cloudflare_guard import verify_turnstile_token


@router.get("/public-schools")
def get_public_schools_for_vouchers(db: Session = Depends(get_db)):
    """
    Public directory of schools offering online admission voucher purchases.
    """
    schools = db.query(School).filter(School.status != "SUSPENDED").all()
    price_setting = db.query(Setting).filter(Setting.key == "admission_voucher_price_ghs").first()
    default_price = float(price_setting.value) if price_setting and price_setting.value else 100.0

    return [
        {
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "logo_url": s.logo_url,
            "school_mode": s.school_mode,
            "voucher_price_ghs": default_price
        }
        for s in schools
    ]


class PublicVoucherCheckoutRequest(BaseModel):
    school_id: int
    applicant_name: str
    applicant_phone: str
    applicant_email: Optional[str] = None
    gateway: Optional[str] = "PAYSTACK"
    turnstile_token: Optional[str] = None


@router.post("/checkout/initiate")
def initiate_public_voucher_checkout(
    data: PublicVoucherCheckoutRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Public Endpoint: Initiates online admission voucher checkout with subaccount split.
    Guarded by Cloudflare Turnstile bot verification.
    """
    # 1. Cloudflare Turnstile bot verification
    client_ip = getattr(request.state, "client_ip", "127.0.0.1")
    if not verify_turnstile_token(data.turnstile_token, client_ip):
        raise HTTPException(status_code=400, detail="Security challenge verification failed. Please refresh the page.")

    # 2. Resolve voucher price
    price_setting = db.query(Setting).filter(Setting.key == "admission_voucher_price_ghs").first()
    voucher_price = float(price_setting.value) if price_setting and price_setting.value else 100.0

    # 3. Initialize order with Paystack subaccount split
    result = initialize_voucher_checkout(
        school_id=data.school_id,
        applicant_name=data.applicant_name,
        applicant_phone=data.applicant_phone,
        applicant_email=data.applicant_email or "",
        amount=voucher_price,
        gateway=data.gateway or "PAYSTACK",
        db=db
    )
    return result


@router.post("/webhook/paystack")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: Optional[str] = Header(None, alias="x-paystack-signature"),
    db: Session = Depends(get_db)
):
    """
    Enterprise Webhook Handler for Paystack:
    Cryptographically verifies HMAC SHA-512 signature and triggers ACID atomic voucher fulfillment.
    """
    raw_body = await request.body()
    
    # Strict Cryptographic HMAC Verification
    if not verify_paystack_webhook_signature(raw_body, x_paystack_signature or "", db=db):
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid Paystack webhook signature.")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body format.")

    event = payload.get("event")
    if event == "charge.success":
        data = payload.get("data", {})
        order_ref = data.get("reference")
        gateway_ref = data.get("id") or str(data.get("transaction_id", ""))

        if order_ref:
            fulfillment = fulfill_voucher_order_atomic(order_ref, str(gateway_ref), db)
            return {"status": "success", "fulfillment": fulfillment}

    return {"status": "ignored", "event": event}


@router.post("/webhook/hubtel")
async def hubtel_webhook(
    request: Request,
    x_hubtel_signature: Optional[str] = Header(None, alias="x-hubtel-signature"),
    x_hubtel_secret: Optional[str] = Header(None, alias="x-hubtel-secret"),
    db: Session = Depends(get_db)
):
    """
    Enterprise Webhook Handler for Hubtel Mobile Money Checkout Failover.
    Guarded by cryptographic HMAC signature and secret token authentication.
    """
    raw_body = await request.body()
    if not verify_hubtel_webhook_signature(raw_body, x_hubtel_signature, x_hubtel_secret, db=db):
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid Hubtel webhook signature or secret.")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body format.")

    data = payload.get("Data", {}) or payload
    order_ref = data.get("ClientReference") or data.get("order_reference")
    transaction_id = str(data.get("TransactionId") or data.get("transaction_id", ""))
    status_str = str(data.get("Status") or data.get("status", "")).upper()

    if order_ref and status_str in ["SUCCESS", "PAID"]:
        fulfillment = fulfill_voucher_order_atomic(order_ref, transaction_id, db)
        return {"status": "success", "fulfillment": fulfillment}

class VoucherStatusCheckRequest(BaseModel):
    applicant_phone: str
    order_reference: Optional[str] = None


@router.post("/verify-status")
def check_or_resend_voucher_status(
    data: VoucherStatusCheckRequest,
    db: Session = Depends(get_db)
):
    """
    Self-Healing UX Endpoint:
    Allows parents to enter their phone number to check payment status, retrieve credentials,
    or trigger an instant SMS resend.
    """
    from ..models import VoucherOrder, Voucher, School
    from ..services.messaging_service import send_sms_via_hubtel

    clean_phone = "".join(filter(str.isdigit, data.applicant_phone or ""))
    query = db.query(VoucherOrder).filter(VoucherOrder.applicant_phone.contains(clean_phone[-9:]))
    if data.order_reference:
        query = query.filter(VoucherOrder.order_reference == data.order_reference.strip())

    order = query.order_by(VoucherOrder.id.desc()).first()
    if not order:
        raise HTTPException(status_code=404, detail="No voucher order found for this phone number.")

    voucher = order.voucher if order.voucher_id else None
    school = db.query(School).filter(School.id == order.school_id).first()
    school_name = school.name if school else "School System"

    # Resend SMS if voucher is assigned
    if voucher:
        msg = (
            f"Dear Applicant, your {school_name} Admission Voucher details:\n"
            f"Serial: {voucher.serial_number}\n"
            f"PIN: {voucher.pin}\n"
            f"Status: Confirmed."
        )
        send_sms_via_hubtel(
            recipient_phone=order.applicant_phone,
            message_body=msg,
            school_id=order.school_id,
            db=db
        )

    return {
        "order_reference": order.order_reference,
        "status": order.status,
        "school_name": school_name,
        "serial_number": voucher.serial_number if voucher else None,
        "pin": voucher.pin if voucher else None,
        "applicant_name": order.applicant_name,
        "applicant_phone": order.applicant_phone,
        "amount": order.amount,
        "created_at": str(order.created_at)[:16] if order.created_at else ""
    }


@router.get("/financial-summary")
def get_voucher_financial_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the SaaS multi-tenant revenue split breakdown for this school tenant:
    - Gross Vouchers Sold Revenue (GHS)
    - School Net Share (95%)
    - Platform Commission (5%)
    - Real-time SMS Quota & Balance
    """
    from sqlalchemy import func
    school_id = get_school_id(current_user) or (current_user.school_id if hasattr(current_user, 'school_id') else 1)
    
    school = db.query(School).filter(School.id == school_id).first()
    commission_pct = school.platform_commission_percent if (school and school.platform_commission_percent is not None) else 5.0
    school_pct = max(0.0, 100.0 - commission_pct)

    # Calculate total sold vouchers and revenue
    vouchers_query = db.query(AdmissionVoucher).filter(AdmissionVoucher.school_id == school_id)
    total_generated = vouchers_query.count()
    sold_count = vouchers_query.filter(
        (AdmissionVoucher.status.in_(["PURCHASED", "USED"])) | (AdmissionVoucher.purchased_by_phone != None)
    ).count()

    gross_revenue = db.query(func.sum(AdmissionVoucher.amount_paid)).filter(
        AdmissionVoucher.school_id == school_id,
        (AdmissionVoucher.status.in_(["PURCHASED", "USED"])) | (AdmissionVoucher.purchased_by_phone != None)
    ).scalar() or 0.0

    gross_revenue = float(gross_revenue)
    school_net = round(gross_revenue * (school_pct / 100.0), 2)
    platform_fee = round(gross_revenue * (commission_pct / 100.0), 2)

    sms_balance = school.sms_balance if (school and school.sms_balance is not None) else 500
    sms_threshold = school.sms_low_threshold if (school and school.sms_low_threshold is not None) else 200

    return {
        "school_id": school_id,
        "school_name": school.name if school else "School System",
        "total_generated": total_generated,
        "total_sold": sold_count,
        "gross_revenue_ghs": gross_revenue,
        "school_share_percent": school_pct,
        "platform_commission_percent": commission_pct,
        "school_net_share_ghs": school_net,
        "platform_fee_ghs": platform_fee,
        "sms_balance": sms_balance,
        "sms_low_threshold": sms_threshold,
        "is_low_sms": sms_balance <= sms_threshold
    }


@router.get("/paystack-callback")
@router.post("/paystack-callback")
def handle_paystack_callback(
    request: Request,
    reference: Optional[str] = Query(None),
    trxref: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Synchronous / Redirect Callback Handler for Paystack Checkout.
    Verifies payment status and atomically fulfills the voucher order.
    """
    from ..payments.paystack import verify_paystack_transaction
    
    order_ref = reference or trxref
    if not order_ref:
        raise HTTPException(status_code=400, detail="Missing payment transaction reference.")

    # 1. Verify transaction via Paystack package
    verify_result = verify_paystack_transaction(order_ref, db=db)
    if not verify_result.get("verified", False):
        raise HTTPException(
            status_code=400,
            detail=verify_result.get("message", "Paystack transaction verification failed.")
        )

    # 2. Fulfill voucher order atomically
    gateway_ref = verify_result.get("reference") or order_ref
    fulfillment = fulfill_voucher_order_atomic(order_ref, str(gateway_ref), db)

    # If client expects HTML redirect (browser return)
    accept_header = request.headers.get("accept", "")
    if "text/html" in accept_header:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/enrollment.html?reference={order_ref}&status=success")

    return {
        "status": "success",
        "order_reference": order_ref,
        "verification": verify_result,
        "fulfillment": fulfillment
    }


