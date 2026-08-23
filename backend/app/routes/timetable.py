from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from ..database import get_db
from ..models import Timetable, ClassSection, Subject, User, Semester
from ..dependencies import get_current_user, get_school_id

router = APIRouter()

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def require_admin(current_user: User):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if "admin" not in [r.name for r in current_user.roles]:
        raise HTTPException(status_code=403, detail="Admin access required")


def _enrich(slot: Timetable) -> dict:
    return {
        "id": slot.id,
        "class_section_id": slot.class_section_id,
        "class_name": slot.class_section.name if slot.class_section else None,
        "subject_id": slot.subject_id,
        "subject_name": slot.subject.name if slot.subject else None,
        "teacher_id": slot.teacher_id,
        "teacher_name": slot.teacher.username if slot.teacher else None,
        "semester_id": slot.semester_id,
        "day_of_week": slot.day_of_week,
        "day_name": DAYS[slot.day_of_week] if 0 <= slot.day_of_week <= 4 else "Unknown",
        "period_number": slot.period_number,
        "start_time": slot.start_time,
        "end_time": slot.end_time,
        "room": slot.room,
    }


# ── Schemas ───────────────────────────────────────────────────────────────────

class SlotCreate(BaseModel):
    class_section_id: int
    subject_id: int
    teacher_id: Optional[int] = None
    semester_id: Optional[int] = None
    day_of_week: int          # 0=Mon … 4=Fri
    period_number: int        # 1-based
    start_time: Optional[str] = None   # "08:00"
    end_time: Optional[str] = None     # "09:00"
    room: Optional[str] = None


class SlotUpdate(BaseModel):
    subject_id: Optional[int] = None
    teacher_id: Optional[int] = None
    semester_id: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    room: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/class/{class_section_id}")
def get_class_timetable(
    class_section_id: int,
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the full weekly timetable for a class section."""
    school_id = get_school_id(current_user)
    cs = db.query(ClassSection).filter(ClassSection.id == class_section_id).first()
    if not cs or (school_id is not None and cs.school_id != school_id):
        raise HTTPException(status_code=404, detail="Class section not found")

    query = db.query(Timetable).filter(Timetable.class_section_id == class_section_id)
    if semester_id:
        query = query.filter(Timetable.semester_id == semester_id)
    slots = query.order_by(Timetable.day_of_week, Timetable.period_number).all()
    return [_enrich(s) for s in slots]


@router.get("/teacher/{teacher_id}")
def get_teacher_timetable(
    teacher_id: int,
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a teacher's complete teaching schedule across all classes."""
    query = db.query(Timetable).filter(Timetable.teacher_id == teacher_id)
    if semester_id:
        query = query.filter(Timetable.semester_id == semester_id)
    slots = query.order_by(Timetable.day_of_week, Timetable.period_number).all()
    return [_enrich(s) for s in slots]


@router.get("/conflicts")
def check_conflicts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: find all teacher double-booking conflicts."""
    require_admin(current_user)

    school_id = get_school_id(current_user)
    query = db.query(Timetable).join(Timetable.class_section)
    if school_id is not None:
        query = query.filter(ClassSection.school_id == school_id)

    # Group by teacher + day + period — any group with > 1 entry is a conflict
    all_slots = db.query(Timetable).filter(Timetable.teacher_id.isnot(None)).all()
    seen = {}
    conflicts = []
    for slot in all_slots:
        key = (slot.teacher_id, slot.day_of_week, slot.period_number)
        if key in seen:
            conflicts.append({
                "teacher_id": slot.teacher_id,
                "teacher_name": slot.teacher.username if slot.teacher else None,
                "day": DAYS[slot.day_of_week],
                "period": slot.period_number,
                "slot_1": _enrich(seen[key]),
                "slot_2": _enrich(slot),
            })
        else:
            seen[key] = slot
    return conflicts


@router.get("/")
def list_all_slots(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: list all timetable entries."""
    require_admin(current_user)
    slots = db.query(Timetable).order_by(
        Timetable.class_section_id, Timetable.day_of_week, Timetable.period_number
    ).all()
    return [_enrich(s) for s in slots]


@router.post("/", status_code=201)
def create_slot(
    payload: SlotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: create a timetable slot. Enforces no double-booking for teachers."""
    require_admin(current_user)

    if payload.day_of_week < 0 or payload.day_of_week > 4:
        raise HTTPException(status_code=400, detail="day_of_week must be 0 (Mon) to 4 (Fri)")
    if payload.period_number < 1:
        raise HTTPException(status_code=400, detail="period_number must be >= 1")

    # Check class already has something in this slot
    existing_class = db.query(Timetable).filter(
        Timetable.class_section_id == payload.class_section_id,
        Timetable.day_of_week == payload.day_of_week,
        Timetable.period_number == payload.period_number,
    ).first()
    if existing_class:
        raise HTTPException(
            status_code=409,
            detail=f"This class already has a subject assigned to {DAYS[payload.day_of_week]} Period {payload.period_number}"
        )

    # Check teacher conflict (if teacher supplied)
    if payload.teacher_id:
        existing_teacher = db.query(Timetable).filter(
            Timetable.teacher_id == payload.teacher_id,
            Timetable.day_of_week == payload.day_of_week,
            Timetable.period_number == payload.period_number,
        ).first()
        if existing_teacher:
            teacher = db.query(User).filter(User.id == payload.teacher_id).first()
            tname = teacher.username if teacher else f"Teacher #{payload.teacher_id}"
            raise HTTPException(
                status_code=409,
                detail=f"{tname} is already assigned to another class on {DAYS[payload.day_of_week]} Period {payload.period_number}"
            )

    slot = Timetable(**payload.model_dump())
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return _enrich(slot)


@router.put("/{slot_id}")
def update_slot(
    slot_id: int,
    payload: SlotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: update subject, teacher, time, or room for an existing slot."""
    require_admin(current_user)
    slot = db.query(Timetable).filter(Timetable.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Timetable slot not found")

    # If changing teacher, check conflicts
    new_teacher_id = payload.teacher_id if payload.teacher_id is not None else slot.teacher_id
    if new_teacher_id and new_teacher_id != slot.teacher_id:
        conflict = db.query(Timetable).filter(
            Timetable.teacher_id == new_teacher_id,
            Timetable.day_of_week == slot.day_of_week,
            Timetable.period_number == slot.period_number,
            Timetable.id != slot_id,
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Teacher conflict: already assigned in this period")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(slot, field, value)

    db.commit()
    db.refresh(slot)
    return _enrich(slot)


@router.delete("/{slot_id}", status_code=204)
def delete_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: remove a timetable slot."""
    require_admin(current_user)
    slot = db.query(Timetable).filter(Timetable.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Timetable slot not found")
    db.delete(slot)
    db.commit()


@router.delete("/class/{class_section_id}", status_code=204)
def clear_class_timetable(
    class_section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: wipe all timetable slots for a class section."""
    require_admin(current_user)
    db.query(Timetable).filter(Timetable.class_section_id == class_section_id).delete()
    db.commit()
