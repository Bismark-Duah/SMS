from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ..database import get_db
from ..models import DisciplineRecord, Student, User, ClassSection, Notification, MessageLog
from ..dependencies import get_current_user, get_school_id

router = APIRouter()

INCIDENT_TYPES = ["Warning", "Detention", "Suspension", "Commendation", "Expulsion"]

# ── Auth helper ───────────────────────────────────────────────────────────────

def require_admin(current_user: User):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    roles = [r.name for r in current_user.roles]
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="Admin access required")


# ── Schemas ───────────────────────────────────────────────────────────────────

class RecordCreate(BaseModel):
    student_id: int
    incident_type: str           # Warning | Detention | Suspension | Commendation | Expulsion
    description: str
    action_taken: Optional[str] = None
    incident_date: Optional[datetime] = None
    notify_parent: bool = True   # auto-create a notification for the student


class RecordUpdate(BaseModel):
    incident_type: Optional[str] = None
    description: Optional[str] = None
    action_taken: Optional[str] = None
    incident_date: Optional[datetime] = None


# ── Enrich helper ─────────────────────────────────────────────────────────────

def _enrich(rec: DisciplineRecord) -> dict:
    student = rec.student
    class_name = None
    if student and student.class_section:
        class_name = student.class_section.name

    return {
        "id": rec.id,
        "student_id": rec.student_id,
        "student_name": student.full_name if student else None,
        "student_code": student.student_code if student else None,
        "class_name": class_name,
        "incident_type": rec.incident_type,
        "description": rec.description,
        "action_taken": rec.action_taken,
        "incident_date": rec.incident_date,
        "recorded_by": rec.recorded_by,
        "recorder_name": rec.recorder.username if rec.recorder else None,
        "parent_notified": rec.parent_notified,
        "created_at": rec.created_at,
    }


# ── Summary ───────────────────────────────────────────────────────────────────

@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: count by incident type."""
    require_admin(current_user)
    school_id = get_school_id(current_user)
    query = db.query(
        DisciplineRecord.incident_type,
        func.count(DisciplineRecord.id).label("count")
    )
    if school_id is not None:
        query = query.join(DisciplineRecord.student).filter(Student.school_id == school_id)
    rows = query.group_by(DisciplineRecord.incident_type).all()

    counts = {t: 0 for t in INCIDENT_TYPES}
    for row in rows:
        counts[row.incident_type] = row.count

    total = sum(counts.values())
    return {**counts, "total": total}


# ── Class-level records ───────────────────────────────────────────────────────

@router.get("/class/{class_section_id}")
def get_class_records(
    class_section_id: int,
    incident_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: get all discipline records for students in a class."""
    require_admin(current_user)

    student_ids = [
        s.id for s in db.query(Student)
        .filter(Student.class_section_id == class_section_id).all()
    ]
    query = db.query(DisciplineRecord).filter(DisciplineRecord.student_id.in_(student_ids))
    if incident_type:
        query = query.filter(DisciplineRecord.incident_type == incident_type)
    recs = query.order_by(desc(DisciplineRecord.incident_date)).all()
    return [_enrich(r) for r in recs]


# ── Per-student records ───────────────────────────────────────────────────────

@router.get("/student/{student_id}")
def get_student_records(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get discipline history for a student. Admin or linked parent."""
    school_id = get_school_id(current_user)
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student or (school_id is not None and student.school_id != school_id):
        raise HTTPException(status_code=404, detail="Student not found")

    roles = [r.name for r in current_user.roles]
    if "admin" not in roles and student.parent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    recs = db.query(DisciplineRecord).filter(
        DisciplineRecord.student_id == student_id
    ).order_by(desc(DisciplineRecord.incident_date)).all()
    return [_enrich(r) for r in recs]


# ── List all ──────────────────────────────────────────────────────────────────

@router.get("/")
def list_records(
    incident_type: Optional[str] = Query(None),
    class_section_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(200, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List discipline records. Admins see all; teachers see their assigned class students only."""
    from ..dependencies import get_user_assigned_scope

    school_id = get_school_id(current_user)
    scope = get_user_assigned_scope(current_user, db)

    query = db.query(DisciplineRecord)
    if school_id is not None:
        query = query.join(DisciplineRecord.student).filter(Student.school_id == school_id)

    # ── Role-based scoping ─────────────────────────────────────────────────────
    if not scope["is_admin"]:
        if scope["class_ids"]:
            # Teachers see records only for students in their assigned classes
            allowed_student_ids = [
                s.id for s in db.query(Student)
                .filter(Student.class_section_id.in_(scope["class_ids"])).all()
            ]
            query = query.filter(DisciplineRecord.student_id.in_(allowed_student_ids))
        else:
            return []

    if incident_type:
        query = query.filter(DisciplineRecord.incident_type == incident_type)
    if class_section_id:
        student_ids = [s.id for s in db.query(Student)
                       .filter(Student.class_section_id == class_section_id).all()]
        query = query.filter(DisciplineRecord.student_id.in_(student_ids))
    if date_from:
        query = query.filter(DisciplineRecord.incident_date >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(DisciplineRecord.incident_date <= datetime.fromisoformat(date_to))

    recs = query.order_by(desc(DisciplineRecord.incident_date)).limit(limit).all()

    # Client-side search filter by student name
    result = [_enrich(r) for r in recs]
    if search:
        s = search.lower()
        result = [r for r in result if s in (r["student_name"] or "").lower()
                                    or s in (r["student_code"] or "").lower()]
    return result


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("/", status_code=201)
def create_record(
    payload: RecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: log a new discipline record."""
    require_admin(current_user)

    if payload.incident_type not in INCIDENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid incident_type. Must be one of: {', '.join(INCIDENT_TYPES)}"
        )

    school_id = get_school_id(current_user)
    student = db.query(Student).filter(Student.id == payload.student_id).first()
    if not student or (school_id is not None and student.school_id != school_id):
        raise HTTPException(status_code=404, detail="Student not found")

    rec = DisciplineRecord(
        student_id=payload.student_id,
        incident_type=payload.incident_type,
        description=payload.description,
        action_taken=payload.action_taken,
        incident_date=payload.incident_date or datetime.utcnow(),
        recorded_by=current_user.id,
        parent_notified=False,
    )
    db.add(rec)
    db.flush()   # get rec.id before commit

    # Auto-notify parent if requested (for negative incidents)
    if payload.notify_parent:
        type_label = payload.incident_type
        action_str = f" Action taken: {payload.action_taken}." if payload.action_taken else ""
        notif_msg = (
            f"Discipline Notice [{type_label}]: {student.full_name} — "
            f"{payload.description}{action_str}"
        )
        notif = Notification(
            student_id=student.id,
            message=notif_msg,
            type="General",
        )
        db.add(notif)
        rec.parent_notified = True

        if student.phone and len(student.phone.strip()) >= 7:
            guardian_name = student.guardian_name or (student.parent.username if student.parent else "Parent/Guardian")
            sms_body = (
                f"Dear {guardian_name}, a discipline notice ({type_label}) has been logged for your child {student.full_name}: "
                f"{payload.description}.{action_str}"
            )
            msg_log = MessageLog(
                sender_id=current_user.id,
                student_id=student.id,
                recipient_name=guardian_name,
                recipient_phone=student.phone,
                channel="SMS",
                message_type="DISCIPLINE_NOTICE",
                message_body=sms_body,
                overall_grade=type_label,
                status="PENDING"
            )
            db.add(msg_log)

    db.commit()
    db.refresh(rec)
    return _enrich(rec)


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{record_id}")
def update_record(
    record_id: int,
    payload: RecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: update an existing discipline record."""
    require_admin(current_user)
    school_id = get_school_id(current_user)
    query = db.query(DisciplineRecord).filter(DisciplineRecord.id == record_id)
    if school_id is not None:
        query = query.join(DisciplineRecord.student).filter(Student.school_id == school_id)
    rec = query.first()
    if not rec:
        raise HTTPException(status_code=404, detail="Discipline record not found")

    if payload.incident_type and payload.incident_type not in INCIDENT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid incident_type")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rec, field, value)

    db.commit()
    db.refresh(rec)
    return _enrich(rec)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{record_id}", status_code=204)
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: remove a discipline record."""
    require_admin(current_user)
    school_id = get_school_id(current_user)
    query = db.query(DisciplineRecord).filter(DisciplineRecord.id == record_id)
    if school_id is not None:
        query = query.join(DisciplineRecord.student).filter(Student.school_id == school_id)
    rec = query.first()
    if not rec:
        raise HTTPException(status_code=404, detail="Discipline record not found")
    db.delete(rec)
    db.commit()
