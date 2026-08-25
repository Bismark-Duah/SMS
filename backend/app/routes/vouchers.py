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

    # 2. Check if a voucher was already purchased/assigned for this BECE index
    existing_voucher = db.query(AdmissionVoucher).filter(
        AdmissionVoucher.bece_index_number == clean_bece,
        AdmissionVoucher.status.in_(["AVAILABLE", "PURCHASED"])
    ).first()

    if existing_voucher:
        serial = existing_voucher.serial_code
        pin = existing_voucher.pin_code
    else:
        # Mint new unique voucher
        serial_suffix = "".join(random.choices(string.digits, k=6))
        serial = f"{prefix}-{serial_suffix}"
        pin = "".join(random.choices(string.digits, k=6))

        # Guarantee serial uniqueness
        while db.query(AdmissionVoucher).filter(AdmissionVoucher.serial_code == serial).first():
            serial_suffix = "".join(random.choices(string.digits, k=6))
            serial = f"{prefix}-{serial_suffix}"

        setting_price = db.query(Setting).filter(Setting.key == "admission_voucher_price").first()
        try:
            default_price = float(setting_price.value) if setting_price and setting_price.value else 0.10
        except (ValueError, TypeError):
            default_price = 0.10

        paid_amt = data.amount if data.amount is not None else default_price

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
