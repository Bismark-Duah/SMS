from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, date
import urllib.request
import json
import hmac
import hashlib
import io
from xhtml2pdf import pisa

from ..database import get_db
from ..models import Fee, Payment, Student, User, ClassSection, Notification, MessageLog, Setting, School
from ..dependencies import get_current_user, get_school_id
from ..services.communication_service import CommunicationService
from ..payments.paystack import initialize_paystack_transaction, verify_paystack_transaction, verify_paystack_signature
from ..sms.hubtel import send_sms_hubtel

router = APIRouter()

# ── Helpers ───────────────────────────────────────────────────────────────────

def require_admin(current_user: User):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    role_names = [r.name.lower() for r in current_user.roles] if hasattr(current_user, 'roles') else []
    allowed_roles = {
        "admin", "super_admin", "proprietor", "headmaster", "headmistress",
        "bursar", "accountant", "assistant_headmaster_admin", "assistant_head_admin"
    }
    if not any(r in allowed_roles for r in role_names):
        raise HTTPException(status_code=403, detail="Finance or Administrative access required")


def recalculate_fee_status(fee: Fee) -> str:
    """Compute status based on amount_paid vs amount and due_date."""
    if (fee.amount_paid or 0.0) >= fee.amount:
        return "Paid"
    if fee.status == "Waived":
        return "Waived"
    balance = fee.amount - (fee.amount_paid or 0.0)
    if balance > 0:
        if fee.due_date and datetime.utcnow() > fee.due_date:
            return "Overdue"
        return "Partial" if (fee.amount_paid or 0.0) > 0 else "Pending"
    return "Paid"


def generate_receipt_number(db: Session, school_id: Optional[int] = None, payment_date: Optional[datetime] = None) -> str:
    """
    Generates a tenant-scoped, collision-proof receipt number.
    Format: REC/{SCHOOL_CODE}/{YEAR}/{RAND_HEX} e.g. REC/GSHS/2026/F4E8B2
    """
    import uuid
    school_code = "SCH"
    if school_id:
        sch = db.query(School).filter(School.id == school_id).first()
        if sch and sch.code:
            school_code = sch.code.upper().strip()
        elif sch and sch.name:
            words = sch.name.split()
            school_code = "".join(w[0] for w in words if w).upper()[:6]
    
    year_str = (payment_date or datetime.utcnow()).strftime("%Y")
    rand_suffix = uuid.uuid4().hex[:6].upper()
    return f"REC/{school_code}/{year_str}/{rand_suffix}"


def update_overdue_statuses(db: Session):
    """Find all Pending/Partial fees whose due_date has passed, and mark them as Overdue."""
    now = datetime.utcnow()
    overdue_fees = db.query(Fee).filter(
        Fee.status.in_(["Pending", "Partial"]),
        Fee.due_date < now
    ).all()

    for fee in overdue_fees:
        fee.status = "Overdue"
        student = fee.student
        if student and student.phone and len(student.phone.strip()) >= 7:
            rem_balance = max(0.0, fee.amount - fee.amount_paid)
            fee_title = fee.description or f"{fee.fee_type} Fee"
            guardian_name = student.guardian_name or (student.parent.username if student.parent else "Parent/Guardian")
            msg_body = (
                f"Dear {guardian_name}, please be reminded that GHS {rem_balance:.2f} for {student.full_name} "
                f"({fee_title}) is OVERDUE. Kindly arrange payment."
            )

            msg_pattern = f"%{fee_title}%OVERDUE%"
            existing_log = db.query(MessageLog).filter(
                MessageLog.student_id == student.id,
                MessageLog.message_type == "FEE_NOTICE",
                MessageLog.message_body.like(msg_pattern)
            ).first()

            if not existing_log:
                db.add(MessageLog(
                    sender_id=None,
                    student_id=student.id,
                    recipient_name=guardian_name,
                    recipient_phone=student.phone,
                    channel="SMS",
                    message_type="FEE_NOTICE",
                    message_body=msg_body,
                    overall_grade="OVERDUE",
                    status="PENDING"
                ))

    db.commit()



# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class FeeCreate(BaseModel):
    student_id: int
    fee_type: str           # Tuition | Boarding | Activity | Exam | Other
    description: Optional[str] = None
    amount: float = Field(..., gt=0, description="Fee amount must be greater than zero")
    due_date: Optional[datetime] = None
    academic_year: Optional[str] = None
    term: Optional[str] = None


class FeeBulkCreate(BaseModel):
    class_section_id: int
    fee_type: str
    description: Optional[str] = None
    amount: float = Field(..., gt=0, description="Fee amount must be greater than zero")
    due_date: Optional[datetime] = None
    academic_year: Optional[str] = None
    term: Optional[str] = None


class FeeUpdate(BaseModel):
    fee_type: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0, description="Fee amount must be greater than zero")
    due_date: Optional[datetime] = None
    academic_year: Optional[str] = None
    term: Optional[str] = None
    status: Optional[str] = None     # allow manual Waived override


class PaymentCreate(BaseModel):
    amount_paid: float = Field(..., gt=0, description="Payment amount must be greater than zero")
    payment_date: Optional[datetime] = None
    payment_method: str = "Cash"    # Cash | Cheque | Bank Transfer | Mobile Money
    reference_no: Optional[str] = None
    notes: Optional[str] = None


class PaymentOut(BaseModel):
    id: int
    fee_id: int
    amount_paid: float
    payment_date: datetime
    payment_method: str
    reference_no: Optional[str] = None
    receipt_number: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FeeOut(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    student_code: Optional[str] = None
    class_name: Optional[str] = None
    fee_type: str
    description: Optional[str]
    amount: float
    amount_paid: float
    balance: float
    due_date: Optional[datetime]
    academic_year: Optional[str]
    term: Optional[str]
    status: str
    created_at: datetime
    payments: List[PaymentOut] = []

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

from ..models import Fee, Payment, Student, User, ClassSection, Notification, Setting, SchoolStage, School

def _get_school_mode(db: Session, school_id: Optional[int] = None) -> str:
    if school_id:
        sch = db.query(School).filter(School.id == school_id).first()
        if sch and sch.school_mode:
            return sch.school_mode
    setting = db.query(Setting).filter(Setting.key == "school_mode").first()
    return setting.value if setting and setting.value else "COMBINED"

def _filter_fee_query(query, db: Session, school_id=None):
    """Apply school and school_mode filters to a Fee query."""
    if school_id is not None:
        query = query.join(Fee.student).filter(Student.school_id == school_id)
    mode = _get_school_mode(db, school_id)
    if mode == "BASIC_ONLY":
        return query.join(Fee.student, isouter=True).join(Student.class_section, isouter=True).join(ClassSection.stage, isouter=True).filter(SchoolStage.school_type == "Basic")
    elif mode == "SHS_ONLY":
        return query.join(Fee.student, isouter=True).join(Student.class_section, isouter=True).join(ClassSection.stage, isouter=True).filter(SchoolStage.school_type == "SHS")
    return query

@router.get("/summary")
def get_fee_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: high-level finance summary."""
    require_admin(current_user)
    school_id = get_school_id(current_user)
    update_overdue_statuses(db)
    query = _filter_fee_query(db.query(Fee), db, school_id=school_id)
    fees = query.all()

    total_billed   = sum(f.amount for f in fees)
    total_paid     = sum(f.amount_paid for f in fees)
    total_balance  = total_billed - total_paid
    count_overdue  = sum(1 for f in fees if f.status == "Overdue")
    count_paid     = sum(1 for f in fees if f.status == "Paid")
    count_pending  = sum(1 for f in fees if f.status in ("Pending", "Partial"))

    return {
        "total_billed":   round(total_billed, 2),
        "total_paid":     round(total_paid, 2),
        "total_balance":  round(total_balance, 2),
        "count_overdue":  count_overdue,
        "count_paid":     count_paid,
        "count_pending":  count_pending,
        "total_fees":     len(fees),
    }


@router.get("/overdue")
def get_overdue_fees(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: list all overdue fees."""
    require_admin(current_user)
    school_id = get_school_id(current_user)
    update_overdue_statuses(db)
    query = _filter_fee_query(db.query(Fee).filter(Fee.status == "Overdue"), db, school_id=school_id)
    fees = query.all()
    return [_enrich(f) for f in fees]


@router.get("/student/{student_id}", response_model=List[FeeOut])
def get_student_fees(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get fee records for a specific student."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    school_id = get_school_id(current_user)
    st_q = db.query(Student).filter(Student.id == student_id)
    if school_id is not None:
        st_q = st_q.filter(Student.school_id == school_id)
    student = st_q.first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found in your school")

    roles = [r.name.lower() for r in current_user.roles] if hasattr(current_user, 'roles') else []
    admin_roles = {"admin", "super_admin", "headmaster", "headmistress", "bursar", "accountant", "assistant_headmaster_admin", "assistant_head_admin"}
    if not any(r in admin_roles for r in roles) and student.parent_id != current_user.id and current_user.username != student.student_code:
        raise HTTPException(status_code=403, detail="Access denied")

    fees = db.query(Fee).filter(Fee.student_id == student_id).order_by(desc(Fee.created_at)).all()
    return [_enrich(f) for f in fees]


@router.get("/", response_model=List[FeeOut])
def list_fees(
    status: Optional[str] = Query(None),
    fee_type: Optional[str] = Query(None),
    academic_year: Optional[str] = Query(None),
    class_section_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: list all fees with optional filters."""
    require_admin(current_user)
    school_id = get_school_id(current_user)
    update_overdue_statuses(db)

    query = _filter_fee_query(db.query(Fee), db, school_id=school_id)
    if status:
        query = query.filter(Fee.status == status)
    if fee_type:
        query = query.filter(Fee.fee_type == fee_type)
    if academic_year:
        query = query.filter(Fee.academic_year == academic_year)
    if class_section_id:
        st_ids_q = db.query(Student.id).filter(Student.class_section_id == class_section_id)
        if school_id is not None:
            st_ids_q = st_ids_q.filter(Student.school_id == school_id)
        query = query.filter(Fee.student_id.in_(st_ids_q))

    fees = query.order_by(desc(Fee.created_at)).all()
    return [_enrich(f) for f in fees]


@router.post("/", status_code=201)
def create_fee(
    payload: FeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: create a fee for a single student."""
    require_admin(current_user)
    school_id = get_school_id(current_user)
    st_q = db.query(Student).filter(Student.id == payload.student_id)
    if school_id is not None:
        st_q = st_q.filter(Student.school_id == school_id)
    student = st_q.first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found in your school")

    fee = Fee(
        student_id=payload.student_id,
        fee_type=payload.fee_type,
        description=payload.description,
        amount=payload.amount,
        amount_paid=0.0,
        due_date=payload.due_date,
        academic_year=payload.academic_year,
        term=payload.term,
        status="Pending",
    )
    db.add(fee)
    db.commit()
    db.refresh(fee)
    return _enrich(fee)


@router.post("/bulk", status_code=201)
def bulk_create_fees(
    payload: FeeBulkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: assign the same fee to all active students in a class section."""
    require_admin(current_user)
    school_id = get_school_id(current_user)

    st_q = db.query(Student).filter(
        Student.class_section_id == payload.class_section_id,
        Student.is_active == True
    )
    if school_id is not None:
        st_q = st_q.filter(Student.school_id == school_id)
    students = st_q.all()
    if not students:
        raise HTTPException(status_code=404, detail="No active students found in this class section for your school")

    fees = [
        Fee(
            student_id=s.id,
            fee_type=payload.fee_type,
            description=payload.description,
            amount=payload.amount,
            amount_paid=0.0,
            due_date=payload.due_date,
            academic_year=payload.academic_year,
            term=payload.term,
            status="Pending",
        )
        for s in students
    ]
    db.add_all(fees)
    db.commit()
    return {"message": f"Fee assigned to {len(fees)} students", "count": len(fees)}


@router.get("/{fee_id}")
def get_fee(
    fee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific fee record."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    school_id = get_school_id(current_user)
    fee_q = db.query(Fee).join(Fee.student).filter(Fee.id == fee_id)
    if school_id is not None:
        fee_q = fee_q.filter(Student.school_id == school_id)
    fee = fee_q.first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
        
    roles = [r.name.lower() for r in current_user.roles] if hasattr(current_user, 'roles') else []
    admin_roles = {"admin", "super_admin", "headmaster", "headmistress", "bursar", "accountant", "assistant_headmaster_admin", "assistant_head_admin", "teacher"}
    if not any(r in admin_roles for r in roles):
        student = fee.student
        is_parent = student and student.parent_id == current_user.id
        is_student = student and current_user.username == student.student_code
        if not is_parent and not is_student:
            raise HTTPException(status_code=403, detail="Access denied")
            
    return _enrich(fee)



@router.put("/{fee_id}")
def update_fee(
    fee_id: int,
    payload: FeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: update a fee record."""
    require_admin(current_user)
    school_id = get_school_id(current_user)
    fee_q = db.query(Fee).join(Fee.student).filter(Fee.id == fee_id)
    if school_id is not None:
        fee_q = fee_q.filter(Student.school_id == school_id)
    fee = fee_q.first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")

    # Anti-Fraud Constraint: Cannot reduce billed amount below what has already been collected
    if payload.amount is not None and payload.amount < (fee.amount_paid or 0.0) - 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"Financial Guard: Cannot reduce billed fee to GHS {payload.amount:.2f}, which is less than the GHS {fee.amount_paid:.2f} already paid by the student."
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(fee, field, value)

    # Recalculate status unless manually set to Waived
    if payload.status != "Waived":
        fee.status = recalculate_fee_status(fee)

    # Audit log
    try:
        from ..models import ActivityAuditLog
        student = fee.student
        target_sch_id = student.school_id if student else school_id
        db.add(ActivityAuditLog(
            user_id=current_user.id,
            action="UPDATE_FEE",
            entity_type="Fee",
            entity_id=fee.id,
            details=f"Updated fee record #{fee.id} for Student {student.student_code if student else ''}: amount=GHS {fee.amount:.2f}, status={fee.status}.",
            school_id=target_sch_id
        ))
    except Exception:
        pass

    db.commit()
    db.refresh(fee)
    return _enrich(fee)


@router.delete("/{fee_id}", status_code=204)
def delete_fee(
    fee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: delete a fee and all its payments."""
    require_admin(current_user)
    school_id = get_school_id(current_user)
    fee_q = db.query(Fee).join(Fee.student).filter(Fee.id == fee_id)
    if school_id is not None:
        fee_q = fee_q.filter(Student.school_id == school_id)
    fee = fee_q.first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")

    # Anti-Fraud Constraint: Block deletion of fee records that have completed payments
    if (fee.amount_paid or 0.0) > 0.0 or (fee.payments and len(fee.payments) > 0):
        raise HTTPException(
            status_code=400,
            detail=f"Financial Guard: Cannot delete fee record #{fee.id} because GHS {fee.amount_paid:.2f} in payments has already been recorded. Adjust or waive the fee instead."
        )

    # Audit log
    try:
        from ..models import ActivityAuditLog
        student = fee.student
        target_sch_id = student.school_id if student else school_id
        db.add(ActivityAuditLog(
            user_id=current_user.id,
            action="DELETE_FEE",
            entity_type="Fee",
            entity_id=fee.id,
            details=f"Deleted uncollected fee record #{fee.id} ({fee.fee_type}) for Student {student.student_code if student else ''}.",
            school_id=target_sch_id
        ))
    except Exception:
        pass

    db.delete(fee)
    db.commit()


@router.post("/{fee_id}/payments", status_code=201)
def record_payment(
    fee_id: int,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: record a payment against a fee."""
    require_admin(current_user)
    school_id = get_school_id(current_user)
    fee_q = db.query(Fee).join(Fee.student).filter(Fee.id == fee_id)
    if school_id is not None:
        fee_q = fee_q.filter(Student.school_id == school_id)
    fee = fee_q.first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")

    if payload.amount_paid <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero")

    student = fee.student
    target_school_id = student.school_id if student else school_id

    # Atomic sum of existing payments from database
    current_total_paid = db.query(func.coalesce(func.sum(Payment.amount_paid), 0.0))\
        .filter(Payment.fee_id == fee_id).scalar()
    
    balance = max(0.0, fee.amount - float(current_total_paid))
    if payload.amount_paid > balance + 0.01:   # 0.01 tolerance for float rounding
        raise HTTPException(
            status_code=400,
            detail=f"Payment of GHS {payload.amount_paid:.2f} exceeds remaining balance of GHS {round(balance, 2):.2f}"
        )

    # Generate persistent unique tenant receipt number
    receipt_no = generate_receipt_number(db, target_school_id, payload.payment_date)

    payment = Payment(
        fee_id=fee_id,
        amount_paid=payload.amount_paid,
        payment_date=payload.payment_date or datetime.utcnow(),
        payment_method=payload.payment_method,
        reference_no=payload.reference_no,
        receipt_number=receipt_no,
        notes=payload.notes,
        recorded_by=current_user.id,
    )
    db.add(payment)
    db.flush()

    # Atomically re-aggregate total payments
    new_total_paid = db.query(func.coalesce(func.sum(Payment.amount_paid), 0.0))\
        .filter(Payment.fee_id == fee_id).scalar()
    
    if new_total_paid > fee.amount + 0.01:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Concurrent payment detected. Total payments (GHS {new_total_paid:.2f}) would exceed billed fee of GHS {fee.amount:.2f}."
        )

    fee.amount_paid = round(float(new_total_paid), 2)
    fee.status = recalculate_fee_status(fee)

    # Activity Audit Log
    try:
        from ..models import ActivityAuditLog
        db.add(ActivityAuditLog(
            user_id=current_user.id,
            action="RECORD_PAYMENT",
            entity_type="FeePayment",
            entity_id=payment.id,
            details=f"Recorded GHS {payload.amount_paid:.2f} for Student {student.student_code if student else ''} (Receipt: {receipt_no}).",
            school_id=target_school_id
        ))
    except Exception:
        pass

    db.commit()
    db.refresh(fee)

    # Send notification to student if fully paid
    if fee.status == "Paid":
        notif = Notification(
            student_id=fee.student_id,
            message=f"Your {fee.fee_type} fee of {fee.amount:,.2f} for {fee.academic_year or ''} {fee.term or ''} has been fully paid. Thank you!",
            type="General",
        )
        db.add(notif)

    # Automated Event Notification Trigger: Fee Payment Receipt
    rem_balance = max(0.0, fee.amount - fee.amount_paid)
    if student and student.phone and len(student.phone.strip()) >= 7:
        try:
            CommunicationService.trigger_event_notification(
                "FEE_PAYMENT",
                {
                    "student_id": student.id,
                    "student_name": student.full_name,
                    "class_name": student.class_section.name if student.class_section else "",
                    "guardian_name": student.guardian_name,
                    "phone": student.phone,
                    "amount": payload.amount_paid,
                    "receipt_no": receipt_no,
                    "balance": rem_balance
                },
                db
            )
        except Exception as err:
            pass

    return _enrich(fee)


@router.get("/{fee_id}/payments", response_model=List[PaymentOut])
def get_payments(
    fee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get payment history for a fee."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    fee = db.query(Fee).filter(Fee.id == fee_id).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
        
    roles = [r.name for r in current_user.roles]
    if "admin" not in roles and "teacher" not in roles:
        student = fee.student
        is_parent = student and student.parent_id == current_user.id
        is_student = student and current_user.username == student.student_code
        if not is_parent and not is_student:
            raise HTTPException(status_code=403, detail="Access denied")
            
    return fee.payments



# ── Internal helpers ──────────────────────────────────────────────────────────

def _enrich(fee: Fee) -> dict:
    """Add computed fields to a fee for API response."""
    student = fee.student
    class_name = None
    if student and student.class_section:
        class_name = student.class_section.name

    return {
        "id": fee.id,
        "student_id": fee.student_id,
        "student_name": student.full_name if student else None,
        "student_code": student.student_code if student else None,
        "class_name": class_name,
        "fee_type": fee.fee_type,
        "description": fee.description,
        "amount": fee.amount,
        "amount_paid": fee.amount_paid,
        "balance": round(fee.amount - fee.amount_paid, 2),
        "due_date": fee.due_date,
        "academic_year": fee.academic_year,
        "term": fee.term,
        "status": fee.status,
        "created_at": fee.created_at,
        "payments": [
            {
                "id": p.id,
                "fee_id": p.fee_id,
                "amount_paid": p.amount_paid,
                "payment_date": p.payment_date,
                "payment_method": p.payment_method,
                "reference_no": p.reference_no,
                "receipt_number": p.receipt_number or f"REC-{p.id:06d}",
                "notes": p.notes,
                "created_at": p.created_at,
            }
            for p in (fee.payments or [])
        ],
    }


# ── Student Fee Summary (Parent Portal) ──────────────────────────────────────

@router.get("/student/{student_id}/summary")
def get_student_fee_summary(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all fees + total billed, paid, and balance for a student."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    school_id = get_school_id(current_user)
    st_q = db.query(Student).filter(Student.id == student_id)
    if school_id is not None:
        st_q = st_q.filter(Student.school_id == school_id)
    student = st_q.first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found in your school")

    roles = [r.name for r in current_user.roles]
    if "admin" not in roles and "teacher" not in roles:
        is_parent = student.parent_id == current_user.id
        is_student = current_user.username == student.student_code
        if not is_parent and not is_student:
            raise HTTPException(status_code=403, detail="Access denied")

    fees = db.query(Fee).filter(Fee.student_id == student_id).all()
    total_billed = sum(f.amount for f in fees)
    total_paid   = sum(f.amount_paid for f in fees)
    total_balance = total_billed - total_paid

    fee_list = []
    for f in fees:
        fee_list.append({
            "id": f.id,
            "fee_type": f.fee_type,
            "description": f.description,
            "amount": f.amount,
            "amount_paid": f.amount_paid,
            "balance": round(f.amount - f.amount_paid, 2),
            "status": f.status,
            "due_date": str(f.due_date) if f.due_date else None,
            "academic_year": f.academic_year,
            "term": f.term,
            "latest_payment_id": f.payments[-1].id if f.payments else None
        })

    return {
        "student_id": student_id,
        "total_billed": round(total_billed, 2),
        "total_paid": round(total_paid, 2),
        "total_balance": round(total_balance, 2),
        "fees": fee_list,
    }


# ── Paystack Ghana MoMo Payment Gateway ─────────────────────────────────────

class PaystackInitPayload(BaseModel):
    fee_id: int
    amount_paid: float
    email: Optional[str] = "parent@school.local"
    mobile_number: Optional[str] = None
    network: Optional[str] = "MTN MoMo"


@router.post("/paystack/initialize")
def initialize_paystack_payment(
    payload: PaystackInitPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Initializes a Paystack Mobile Money transaction for fee payment with subaccount split.
    Enforces parent authorization, fee amount validation, and minimum >= GHS 1.00.
    """
    fee = db.query(Fee).filter(Fee.id == payload.fee_id).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee bill record not found.")

    student = fee.student
    if not student:
        raise HTTPException(status_code=404, detail="Student associated with fee not found.")

    # Role Scoping: If user is parent, ensure this is their child
    roles = [r.name.lower() for r in current_user.roles] if hasattr(current_user, 'roles') and current_user.roles else []
    admin_or_staff = {
        "admin", "super_admin", "headmaster", "headmistress",
        "assistant_headmaster_academic", "assistant_head_academic",
        "assistant_headmaster_admin", "assistant_head_admin", "teacher"
    }
    if not any(r in admin_or_staff for r in roles):
        if "parent" in roles:
            if student.parent_id != current_user.id:
                raise HTTPException(status_code=403, detail="You can only make fee payments for your linked child.")
        elif "student" in roles:
            if current_user.username != student.student_code:
                raise HTTPException(status_code=403, detail="You can only make payments for your own account.")
        else:
            raise HTTPException(status_code=403, detail="Not authorized to initiate fee payment.")

    # Validation: Amount must be >= GHS 1.00
    if payload.amount_paid < 1.0:
        raise HTTPException(status_code=400, detail="Payment amount must be at least GHS 1.00 (100 pesewas).")

    # Validation: Amount cannot exceed remaining balance + small tolerance
    remaining_balance = max(0.0, fee.amount - fee.amount_paid)
    if remaining_balance <= 0:
        raise HTTPException(status_code=400, detail="This fee bill has already been fully paid.")
    if payload.amount_paid > remaining_balance + 0.01:
        raise HTTPException(status_code=400, detail=f"Payment amount GHS {payload.amount_paid:.2f} exceeds outstanding balance of GHS {remaining_balance:.2f}.")

    target_school_id = student.school_id or (current_user.school_id or 1)
    timestamp = int(datetime.utcnow().timestamp())
    reference = f"PSTK-FEE-{fee.id}-{student.id}-{timestamp}"
    amount_pesewas = int(round(payload.amount_paid * 100))

    try:
        init_res = initialize_paystack_transaction(
            email=payload.email or current_user.email or "parent@school.local",
            amount_pesewas=amount_pesewas,
            school_id=target_school_id,
            reference=reference,
            callback_url="/parent-view.html?payment_status=callback",
            db=db,
            custom_metadata={
                "fee_id": fee.id,
                "student_id": student.id,
                "student_code": student.student_code,
                "fee_type": fee.fee_type,
                "payer_user_id": current_user.id,
                "mobile_number": payload.mobile_number,
                "network": payload.network
            }
        )
        return init_res
    except Exception as e:
        # Graceful fallback for offline mode
        return {
            "status": "offline_fallback",
            "message": f"Online gateway unavailable ({str(e)}). You can record manual Bursar payments offline.",
            "reference": reference,
            "amount_paid": payload.amount_paid
        }


@router.get("/paystack/verify/{reference}")
def verify_paystack_payment(
    reference: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verifies a Paystack transaction status, atomically logs Payment record,
    updates Fee balance, and dispatches Hubtel SMS confirmation to parent.
    """
    existing_pay = db.query(Payment).filter(Payment.reference_no == reference).first()
    if existing_pay:
        fee = existing_pay.fee
        return {
            "status": "success",
            "message": "Payment already verified and recorded.",
            "payment_id": existing_pay.id,
            "fee": _enrich(fee) if fee else None
        }

    verification = verify_paystack_transaction(reference, db)
    if not verification.get("verified"):
        raise HTTPException(status_code=400, detail=verification.get("message", "Paystack transaction verification failed or unconfirmed."))

    # Extract meta
    meta = verification.get("metadata", {})
    fee_id = meta.get("fee_id")
    if not fee_id:
        # Parse from reference if available: PSTK-FEE-<fee_id>-<student_id>-<timestamp>
        parts = reference.split("-")
        if len(parts) >= 3 and parts[2].isdigit():
            fee_id = int(parts[2])

    fee = db.query(Fee).filter(Fee.id == fee_id).first() if fee_id else None
    if not fee:
        raise HTTPException(status_code=404, detail="Associated fee bill could not be resolved.")

    amount_paid = float(verification.get("amount", fee.amount - fee.amount_paid))

    student = fee.student
    target_sch_id = student.school_id if student else getattr(current_user, 'school_id', None)
    receipt_no = generate_receipt_number(db, target_sch_id, datetime.utcnow())

    # Create Payment record atomically
    pay_record = Payment(
        fee_id=fee.id,
        amount_paid=amount_paid,
        payment_date=datetime.utcnow(),
        payment_method="Paystack MoMo",
        reference_no=reference,
        receipt_number=receipt_no,
        notes=f"Paystack Online MoMo Verification ({verification.get('channel', 'mobile_money')})",
        recorded_by=current_user.id
    )
    db.add(pay_record)
    db.flush()

    new_tot = db.query(func.coalesce(func.sum(Payment.amount_paid), 0.0)).filter(Payment.fee_id == fee.id).scalar()
    fee.amount_paid = round(float(new_tot), 2)
    fee.status = recalculate_fee_status(fee)
    db.commit()
    db.refresh(pay_record)
    db.refresh(fee)

    # Dispatch SMS Payment Receipt via Hubtel / CommunicationService
    if student and student.phone:
        school = student.school
        sch_name = school.name if school else "School"
        bal_now = max(0.0, fee.amount - fee.amount_paid)
        sms_text = (
            f"PAYMENT RECEIPT [{receipt_no}]: GHS {amount_paid:.2f} received for {student.full_name} "
            f"({fee.fee_type}). Outstanding balance: GHS {bal_now:.2f}. Thank you! - {sch_name}"
        )
        try:
            CommunicationService.send_sms(
                db=db,
                recipient_phone=student.phone,
                message=sms_text,
                student_id=student.id,
                recipient_name=student.guardian_name or current_user.username,
                message_type="FEE_RECEIPT"
            )
        except Exception:
            pass

    return {
        "status": "success",
        "message": "Payment verified and recorded successfully.",
        "payment_id": pay_record.id,
        "amount_paid": amount_paid,
        "fee": _enrich(fee)
    }


@router.post("/paystack/webhook")
async def paystack_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_paystack_signature: Optional[str] = Header(None, alias="x-paystack-signature")
):
    """
    Paystack Webhook Handler for automated real-time MoMo payment confirmation.
    """
    body_bytes = await request.body()
    
    # Authenticate webhook signature if configured
    if not verify_paystack_signature(body_bytes, x_paystack_signature, db):
        raise HTTPException(status_code=400, detail="Invalid Paystack Webhook Signature.")

    try:
        data = json.loads(body_bytes.decode('utf-8'))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event = data.get("event")
    if event != "charge.success":
        return {"status": "ignored", "message": f"Event {event} not handled."}

    charge_data = data.get("data", {})
    reference = charge_data.get("reference")
    if not reference:
        return {"status": "ignored", "message": "No reference found."}

    existing_pay = db.query(Payment).filter(Payment.reference_no == reference).first()
    if existing_pay:
        return {"status": "success", "message": "Payment already processed."}

    meta = charge_data.get("metadata", {})
    fee_id = meta.get("fee_id")
    if not fee_id:
        parts = reference.split("-")
        if len(parts) >= 3 and parts[2].isdigit():
            fee_id = int(parts[2])

    fee = db.query(Fee).filter(Fee.id == fee_id).first() if fee_id else None
    if not fee:
        return {"status": "error", "message": "Associated fee bill not found."}

    amount_paid = float(charge_data.get("amount", 0)) / 100.0  # Paystack amounts in pesewas
    if amount_paid <= 0:
        amount_paid = fee.amount - fee.amount_paid

    student = fee.student
    target_sch_id = student.school_id if student else None
    receipt_no = generate_receipt_number(db, target_sch_id, datetime.utcnow())

    pay_record = Payment(
        fee_id=fee.id,
        amount_paid=amount_paid,
        payment_date=datetime.utcnow(),
        payment_method="Paystack MoMo Webhook",
        reference_no=reference,
        receipt_number=receipt_no,
        notes=f"Paystack Webhook Auto-Verification ({charge_data.get('channel', 'mobile_money')})",
        recorded_by=meta.get("payer_user_id")
    )
    db.add(pay_record)
    db.flush()

    new_tot = db.query(func.coalesce(func.sum(Payment.amount_paid), 0.0)).filter(Payment.fee_id == fee.id).scalar()
    fee.amount_paid = round(float(new_tot), 2)
    fee.status = recalculate_fee_status(fee)
    db.commit()

    return {"status": "success"}


@router.get("/receipt/{payment_id}/pdf")
def download_payment_receipt_pdf(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generates and returns an official printable/downloadable School Fee Payment Receipt PDF.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found.")

    fee = payment.fee
    if not fee or not fee.student:
        raise HTTPException(status_code=404, detail="Associated fee or student record not found.")

    student = fee.student
    school = student.school
    school_name = school.name if school else "SENIOR HIGH SCHOOL"

    # Role Scoping
    roles = [r.name.lower() for r in current_user.roles] if hasattr(current_user, 'roles') and current_user.roles else []
    admin_or_staff = {
        "admin", "super_admin", "proprietor", "headmaster", "headmistress",
        "bursar", "accountant", "assistant_headmaster_academic", "assistant_head_academic",
        "assistant_headmaster_admin", "assistant_head_admin", "teacher"
    }
    if not any(r in admin_or_staff for r in roles):
        if "parent" in roles:
            if student.parent_id != current_user.id:
                raise HTTPException(status_code=403, detail="You can only access receipts for your linked child.")
        elif "student" in roles:
            if current_user.username != student.student_code:
                raise HTTPException(status_code=403, detail="You can only access your own receipts.")
        else:
            raise HTTPException(status_code=403, detail="Not authorized to access payment receipt.")

    def _setting(key: str, default: str = "") -> str:
        s = db.query(Setting).filter(Setting.key == key).first()
        return s.value if s else default

    school_address = _setting("school_address", "Ghana, West Africa")
    school_phone = _setting("school_phone", "")
    school_email = _setting("school_email", "")
    bursar_name = _setting("school_bursar", "Head of Accounts / Bursar")

    school_code = (school.code if school and school.code else "SCH").upper().strip()
    year_str = (payment.payment_date or datetime.utcnow()).strftime("%Y")
    receipt_no = payment.receipt_number or f"REC/{school_code}/{year_str}/{payment.id:05d}"
    token_code = f"FEE-{student.student_code}-{payment.id}-{payment.reference_no or 'LOCAL'}"
    date_str = payment.payment_date.strftime("%d %B, %Y %I:%M %p") if payment.payment_date else datetime.utcnow().strftime("%d %B, %Y")
    rem_bal = max(0.0, fee.amount - fee.amount_paid)

    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: a5 landscape;
                margin: 0.8cm 1cm 0.8cm 1cm;
            }}
            body {{
                font-family: Helvetica, Arial, sans-serif;
                font-size: 9px;
                color: #0f172a;
                line-height: 1.4;
            }}
            .header-table {{
                width: 100%;
                border-bottom: 2px solid #0f172a;
                padding-bottom: 6px;
                margin-bottom: 8px;
            }}
            .school-name {{
                font-size: 14px;
                font-weight: bold;
                text-transform: uppercase;
                color: #0f172a;
            }}
            .receipt-title {{
                font-size: 11px;
                font-weight: bold;
                color: #0369a1;
                text-transform: uppercase;
                margin-top: 4px;
            }}
            .info-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 8px 0;
            }}
            .info-table td {{
                padding: 4px 6px;
                font-size: 9px;
                border: 1px solid #cbd5e1;
            }}
            .fee-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 8px 0;
            }}
            .fee-table th {{
                background: #f1f5f9;
                font-size: 9px;
                font-weight: bold;
                padding: 5px;
                border: 1px solid #94a3b8;
                text-align: left;
            }}
            .fee-table td {{
                padding: 5px;
                border: 1px solid #cbd5e1;
                font-size: 9px;
            }}
        </style>
    </head>
    <body>
        <table class="header-table">
            <tr>
                <td style="width:70%;">
                    <div class="school-name">{school_name}</div>
                    <div style="font-size:8px; color:#475569;">{school_address} &bull; Tel: {school_phone or 'General Office'} &bull; {school_email}</div>
                    <div class="receipt-title">OFFICIAL STUDENT FEE PAYMENT RECEIPT</div>
                </td>
                <td style="width:30%; text-align:right; vertical-align:top;">
                    <div style="font-size:10px; font-weight:bold; color:#dc2626;">No: {receipt_no}</div>
                    <div style="font-size:8px; color:#64748b;">Date: {date_str}</div>
                </td>
            </tr>
        </table>

        <table class="info-table">
            <tr>
                <td style="width:50%;"><strong>Student Name:</strong> {student.full_name}</td>
                <td style="width:50%;"><strong>Student ID / Code:</strong> {student.student_code}</td>
            </tr>
            <tr>
                <td><strong>Class / Stream:</strong> {student.class_section.name if student.class_section else 'Form 1'}</td>
                <td><strong>Academic Term:</strong> {fee.academic_year or '2025/2026'} ({fee.term or 'Term 1'})</td>
            </tr>
            <tr>
                <td><strong>Payment Method:</strong> {payment.payment_method}</td>
                <td><strong>Transaction Ref:</strong> <span style="font-family:monospace;">{payment.reference_no or 'CASH-MANUAL'}</span></td>
            </tr>
        </table>

        <table class="fee-table">
            <thead>
                <tr>
                    <th>Fee Description / Category</th>
                    <th style="text-align:right;">Total Billed</th>
                    <th style="text-align:right;">Amount Paid Now</th>
                    <th style="text-align:right;">Outstanding Balance</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>{fee.fee_type} Fee</strong> - {fee.description or 'Academic Term Billing'}</td>
                    <td style="text-align:right;">GHS {fee.amount:.2f}</td>
                    <td style="text-align:right; font-weight:bold; color:#059669;">GHS {payment.amount_paid:.2f}</td>
                    <td style="text-align:right; font-weight:bold; color:{'#059669' if rem_bal <= 0 else '#dc2626'};">GHS {rem_bal:.2f}</td>
                </tr>
            </tbody>
        </table>

        <table style="width:100%; margin-top:14px; border:none;">
            <tr>
                <td style="width:60%; vertical-align:bottom;">
                    <div style="font-size:8px; color:#64748b;">
                        <strong>Verification Token:</strong> <span style="font-family:monospace; color:#0369a1;">{token_code}</span><br/>
                        <em>This official electronic receipt is generated by the School Management System.</em>
                    </div>
                </td>
                <td style="width:40%; text-align:right; vertical-align:bottom;">
                    <div style="border-bottom:1px solid #000; width:140px; height:18px; margin-bottom:2px; margin-left:auto;"></div>
                    <div style="font-size:8.5px; font-weight:bold;">{bursar_name}</div>
                    <div style="font-size:7.5px; color:#64748b;">Authorized Accounts Secretariat</div>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)
    if pisa_status.err:
        raise HTTPException(status_code=500, detail="Failed to compile PDF receipt.")

    clean_receipt_no = receipt_no.replace("/", "_")
    filename = f"Receipt_{clean_receipt_no}_{student.student_code}.pdf"
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


