import random
import string
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from ..database import get_db
from ..models import AdmissionVoucher, Student, Program, User
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
        "serial_code": voucher.serial_code
    }
