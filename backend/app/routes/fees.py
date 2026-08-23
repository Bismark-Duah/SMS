from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, date
import urllib.request
import json
import hmac
import hashlib

from ..database import get_db
from ..models import Fee, Payment, Student, User, ClassSection, Notification, MessageLog, Setting
from ..dependencies import get_current_user, get_school_id

router = APIRouter()

# ── Helpers ───────────────────────────────────────────────────────────────────

def require_admin(current_user: User):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if "admin" not in [r.name for r in current_user.roles]:
        raise HTTPException(status_code=403, detail="Admin access required")


def recalculate_fee_status(fee: Fee) -> str:
    """Compute status based on amount_paid vs amount and due_date."""
    if fee.amount_paid >= fee.amount:
        return "Paid"
    if fee.status == "Waived":
        return "Waived"
    balance = fee.amount - fee.amount_paid
    if balance > 0:
        if fee.due_date and datetime.utcnow() > fee.due_date:
            return "Overdue"
        return "Partial" if fee.amount_paid > 0 else "Pending"
    return "Paid"


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
    amount: float
    due_date: Optional[datetime] = None
    academic_year: Optional[str] = None
    term: Optional[str] = None


class FeeBulkCreate(BaseModel):
    class_section_id: int
    fee_type: str
    description: Optional[str] = None
    amount: float
    due_date: Optional[datetime] = None
    academic_year: Optional[str] = None
    term: Optional[str] = None


class FeeUpdate(BaseModel):
    fee_type: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[float] = None
    due_date: Optional[datetime] = None
    academic_year: Optional[str] = None
    term: Optional[str] = None
    status: Optional[str] = None     # allow manual Waived override


class PaymentCreate(BaseModel):
    amount_paid: float
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
    reference_no: Optional[str]
    notes: Optional[str]
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
        
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    roles = [r.name for r in current_user.roles]
    if "admin" not in roles and student.parent_id != current_user.id:
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
    update_overdue_statuses(db)

    query = _filter_fee_query(db.query(Fee), db)
    if status:
        query = query.filter(Fee.status == status)
    if fee_type:
        query = query.filter(Fee.fee_type == fee_type)
    if academic_year:
        query = query.filter(Fee.academic_year == academic_year)
    if class_section_id:
        student_ids = [s.id for s in db.query(Student).filter(Student.class_section_id == class_section_id).all()]
        query = query.filter(Fee.student_id.in_(student_ids))

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
    student = db.query(Student).filter(Student.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

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

    students = db.query(Student).filter(
        Student.class_section_id == payload.class_section_id,
        Student.is_active == True
    ).all()
    if not students:
        raise HTTPException(status_code=404, detail="No active students found in this class section")

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
    fee = db.query(Fee).filter(Fee.id == fee_id).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(fee, field, value)

    # Recalculate status unless manually set to Waived
    if payload.status != "Waived":
        fee.status = recalculate_fee_status(fee)

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
    fee = db.query(Fee).filter(Fee.id == fee_id).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
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
    fee = db.query(Fee).filter(Fee.id == fee_id).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")

    balance = fee.amount - fee.amount_paid
    if payload.amount_paid <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero")
    if payload.amount_paid > balance + 0.01:   # 0.01 tolerance for float rounding
        raise HTTPException(
            status_code=400,
            detail=f"Payment of {payload.amount_paid} exceeds remaining balance of {round(balance, 2)}"
        )

    payment = Payment(
        fee_id=fee_id,
        amount_paid=payload.amount_paid,
        payment_date=payload.payment_date or datetime.utcnow(),
        payment_method=payload.payment_method,
        reference_no=payload.reference_no,
        notes=payload.notes,
        recorded_by=current_user.id,
    )
    db.add(payment)

    # Update running total on fee
    fee.amount_paid = round(fee.amount_paid + payload.amount_paid, 2)
    fee.status = recalculate_fee_status(fee)

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

    # Draft SMS & WhatsApp payment receipt into MessageLog queue
    student = fee.student
    rem_balance = max(0.0, fee.amount - fee.amount_paid)
    if student and student.phone and len(student.phone.strip()) >= 7:
        fee_title = fee.description or f"{fee.fee_type} Fee"
        guardian_name = student.guardian_name or (student.parent.username if student.parent else "Parent/Guardian")
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        msg_body = (
            f"[PAYMENT RECEIPT]\n"
            f"Dear {guardian_name}, payment of GHS {payload.amount_paid:.2f} for {student.full_name} "
            f"({fee_title}) has been received on {now_str}. Remaining balance: GHS {rem_balance:.2f}. Thank you."
        )
        msg_log = MessageLog(
            sender_id=current_user.id,
            student_id=student.id,
            recipient_name=guardian_name,
            recipient_phone=student.phone,
            channel="WHATSAPP",
            message_type="FEE_NOTICE",
            message_body=msg_body,
            overall_grade=f"Paid: GHc {payload.amount_paid:.2f}",
            status="PENDING"
        )
        db.add(msg_log)

    db.commit()

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
        
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

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
    Initializes a Paystack Mobile Money transaction for fee payment.
    Falls back gracefully if server is 100% offline or unconfigured.
    """
    fee = db.query(Fee).filter(Fee.id == payload.fee_id).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee bill record not found.")

    def _setting_val(key, default=""):
        s = db.query(Setting).filter(Setting.key == key).first()
        return s.value if s else default

    secret_key = _setting_val("paystack_secret_key", "").strip()
    is_enabled = _setting_val("paystack_enabled", "false").lower() == "true"

    timestamp = int(datetime.utcnow().timestamp())
    reference = f"PSTK-SMS-{fee.id}-{timestamp}"

    if not secret_key or not is_enabled:
        return {
            "status": "offline_fallback",
            "message": "Paystack online gateway is unconfigured or operating in 100% Offline Mode. Switched to local USSD or Bursar entry.",
            "reference": reference,
            "amount_paid": payload.amount_paid
        }

    # Call Paystack API
    paystack_url = "https://api.paystack.co/transaction/initialize"
    req_body = json.dumps({
        "email": payload.email or "parent@school.local",
        "amount": int(round(payload.amount_paid * 100)),
        "currency": "GHS",
        "reference": reference,
        "metadata": {
            "fee_id": fee.id,
            "student_id": fee.student_id,
            "recorded_by": current_user.id
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        paystack_url,
        data=req_body,
        headers={
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status"):
                return {
                    "status": "success",
                    "authorization_url": data["data"]["authorization_url"],
                    "access_code": data["data"]["access_code"],
                    "reference": reference
                }
    except Exception as e:
        return {
            "status": "offline_fallback",
            "message": f"Online gateway connection unavailable ({str(e)}). Switched to 100% Offline Bursar Entry Mode.",
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
    Verifies a Paystack transaction status and completes fee payment recording.
    """
    def _setting_val(key, default=""):
        s = db.query(Setting).filter(Setting.key == key).first()
        return s.value if s else default

    secret_key = _setting_val("paystack_secret_key", "").strip()
    if not secret_key:
        raise HTTPException(status_code=400, detail="Paystack API secret key is not configured.")

    paystack_url = f"https://api.paystack.co/transaction/verify/{reference}"
    req = urllib.request.Request(
        paystack_url,
        headers={"Authorization": f"Bearer {secret_key}"},
        method="GET"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") and data["data"]["status"] == "success":
                pstk_data = data["data"]
                meta = pstk_data.get("metadata", {})
                fee_id = meta.get("fee_id")
                amount_paid = float(pstk_data["amount"]) / 100.0

                fee = db.query(Fee).filter(Fee.id == fee_id).first()
                if fee:
                    existing_pay = db.query(Payment).filter(Payment.reference_no == reference).first()
                    if not existing_pay:
                        pay_record = Payment(
                            fee_id=fee.id,
                            amount_paid=amount_paid,
                            payment_date=datetime.utcnow(),
                            payment_method="Paystack MoMo",
                            reference_no=reference,
                            notes="Paystack Online Gateway Verification",
                            recorded_by=current_user.id
                        )
                        db.add(pay_record)
                        fee.amount_paid = round(fee.amount_paid + amount_paid, 2)
                        fee.status = recalculate_fee_status(fee)
                        db.commit()
                        db.refresh(fee)

                    return _enrich(fee)

            raise HTTPException(status_code=400, detail="Paystack transaction verification failed or pending.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Paystack verification error: {str(e)}")


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
    
    s = db.query(Setting).filter(Setting.key == "paystack_secret_key").first()
    secret_key = s.value.strip() if s and s.value else ""
    if secret_key and x_paystack_signature:
        computed_sig = hmac.new(secret_key.encode("utf-8"), body_bytes, hashlib.sha512).hexdigest()
        if computed_sig.lower() != x_paystack_signature.lower():
            raise HTTPException(status_code=400, detail="Invalid Paystack Webhook Signature.")

    event_data = json.loads(body_bytes.decode("utf-8"))
    if event_data.get("event") == "charge.success":
        data = event_data.get("data", {})
        reference = data.get("reference")
        meta = data.get("metadata", {})
        fee_id = meta.get("fee_id")
        amount_paid = float(data.get("amount", 0)) / 100.0

        if fee_id and reference:
            fee = db.query(Fee).filter(Fee.id == fee_id).first()
            if fee:
                existing_pay = db.query(Payment).filter(Payment.reference_no == reference).first()
                if not existing_pay:
                    pay_record = Payment(
                        fee_id=fee.id,
                        amount_paid=amount_paid,
                        payment_date=datetime.utcnow(),
                        payment_method="Paystack MoMo",
                        reference_no=reference,
                        notes="Automated Paystack Webhook Confirmation",
                        recorded_by=meta.get("recorded_by", 1)
                    )
                    db.add(pay_record)
                    fee.amount_paid = round(fee.amount_paid + amount_paid, 2)
                    fee.status = recalculate_fee_status(fee)
                    db.commit()

    return {"status": "success"}

