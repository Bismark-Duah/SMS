import io
import json
import threading
from datetime import datetime, time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from xhtml2pdf import pisa

from ..database import get_db
from ..models import (
    Timetable, ClassSection, Subject, User, Semester, Program, School, Setting,
    TimetableConfig, TimetableReliefLog, TimetableSyllabusLog, TimetableSnapshot,
    TeacherAssignment, Department
)
from ..dependencies import get_current_user, get_school_id
from ..services.timetable_generator import TimetableSolver, smart_surgical_swap
from ..services.curriculum_presets import (
    DEFAULT_BREAK_SCHEDULES, DEFAULT_SUBJECT_CONFIGS, ROLE_WORKLOAD_LIMITS,
    get_active_facilities_for_subjects, FACILITY_REGISTRY
)

router = APIRouter()

# ARCH-6 FIX: Single in-process lock prevents concurrent timetable generation from
# causing a race condition (two admins generating at the same time corrupt each other's data).
_GENERATE_LOCK = threading.Lock()

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# ── Helpers ───────────────────────────────────────────────────────────────────

# BUG 13 FIX: Headmasters, school administrators, and assistant heads should all be
# able to manage their school timetable — not just users with role="admin".
_TIMETABLE_ADMIN_ROLES = {
    "admin", "super_admin", "headmaster", "headmistress", "principal",
    "school_administrator", "schooladmin",
    "assistant_head_academic", "assistant_head_admin",
    "assistant_head_domestic", "assistant_head"
}

def require_admin(current_user: User):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    roles = {r.name.lower() for r in current_user.roles} if current_user.roles else set()
    if not roles.intersection(_TIMETABLE_ADMIN_ROLES):
        raise HTTPException(status_code=403, detail="Admin or Headmaster access required")


def _check_class_school(cs: ClassSection, school_id: Optional[int]) -> bool:
    if not cs:
        return False
    if school_id is None:
        return True
    if hasattr(cs, "school_id") and cs.school_id is not None:
        return cs.school_id == school_id
    if cs.program and hasattr(cs.program, "school_id") and cs.program.school_id is not None:
        return cs.program.school_id == school_id
    return True


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


class AutoGenerateSchema(BaseModel):
    semester_id: Optional[int] = None
    periods_per_day: Optional[int] = 8
    friday_periods: Optional[int] = 6
    custom_quotas: Optional[Dict[int, int]] = None  # subject_id -> weekly_periods
    facility_counts: Optional[Dict[str, int]] = None  # fac_id -> quantity e.g. {"physics_lab": 1, ...}


class PreferencesUpdateSchema(BaseModel):
    start_time: Optional[str] = "08:00"
    period_duration_minutes: Optional[int] = 45
    periods_per_day: Optional[int] = 8
    friday_periods: Optional[int] = 6
    break_schedule: Optional[List[Dict[str, Any]]] = None
    facility_counts: Optional[Dict[str, int]] = None


class HandoverSchema(BaseModel):
    outgoing_teacher_id: int
    incoming_teacher_id: int


class ReliefDispatchSchema(BaseModel):
    absent_teacher_id: int
    reliever_teacher_id: int
    timetable_slot_id: int
    date: str
    reason: Optional[str] = "Staff Leave / Duty Absence"


class SyllabusLogSchema(BaseModel):
    timetable_slot_id: Optional[int] = None
    class_section_id: int
    subject_id: int
    topic_taught: str
    subtopic: Optional[str] = None
    remarks: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/profile-config")
def get_timetable_profile_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns auto-detected school profile (PUBLIC_BASIC, PRIVATE_BASIC, SHS, COMBINED),
    current timetable preferences, break configurations, and role workload caps.
    """
    school_id = get_school_id(current_user)
    school = db.query(School).filter(School.id == school_id).first() if school_id else None

    # Derive academic profile
    school_mode = getattr(school, "school_mode", "SHS_ONLY") or "SHS_ONLY"
    ownership = getattr(school, "ownership_type", "PRIVATE") or "PRIVATE"

    if school_mode == "BASIC_ONLY":
        profile = "PUBLIC_BASIC" if ownership.upper() == "PUBLIC" else "PRIVATE_BASIC"
    elif school_mode in ["SHS_ONLY", "TECHNICAL"]:
        profile = "SHS"
    else:
        profile = "COMBINED"

    config = db.query(TimetableConfig).filter(TimetableConfig.school_id == school_id).first() if school_id else None

    break_sched = None
    if config and config.break_schedule:
        try:
            break_sched = json.loads(config.break_schedule)
        except Exception:
            break_sched = DEFAULT_BREAK_SCHEDULES.get(profile, DEFAULT_BREAK_SCHEDULES["SHS"])
    else:
        break_sched = DEFAULT_BREAK_SCHEDULES.get(profile, DEFAULT_BREAK_SCHEDULES["SHS"])

    fac_counts = {}
    if config and config.facility_counts:
        try:
            fac_counts = json.loads(config.facility_counts)
        except Exception:
            fac_counts = {}

    return {
        "school_id": school_id,
        "school_name": school.name if school else "Ghana Senior High School",
        "school_mode": school_mode,
        "ownership_type": ownership,
        "derived_profile": profile,
        "start_time": config.start_time if config else "08:00",
        "period_duration_minutes": config.period_duration_minutes if config else 45,
        "periods_per_day": config.periods_per_day if config else 8,
        "friday_periods": config.friday_periods if config else 6,
        "break_schedule": break_sched,
        "facility_counts": fac_counts,
        "role_workload_limits": ROLE_WORKLOAD_LIMITS
    }


@router.put("/preferences")
def update_timetable_preferences(
    payload: PreferencesUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: update school-specific daily hours, period counts, break/chapel intervals, and facility counts."""
    require_admin(current_user)
    school_id = get_school_id(current_user)
    if not school_id:
        raise HTTPException(status_code=400, detail="Active school context required")

    config = db.query(TimetableConfig).filter(TimetableConfig.school_id == school_id).first()
    if not config:
        config = TimetableConfig(school_id=school_id)
        db.add(config)

    config.start_time = payload.start_time or "08:00"
    config.period_duration_minutes = payload.period_duration_minutes or 45
    config.periods_per_day = payload.periods_per_day or 8
    config.friday_periods = payload.friday_periods or 6

    if payload.break_schedule is not None:
        config.break_schedule = json.dumps(payload.break_schedule)

    if payload.facility_counts is not None:
        config.facility_counts = json.dumps(payload.facility_counts)

    db.commit()
    db.refresh(config)
    return {"status": "SUCCESS", "message": "Timetable preferences saved successfully."}


@router.get("/active-facilities")
def get_active_school_facilities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id"),
):
    """
    Returns only the specialized facilities (science labs, technical workshops,
    home econs units, etc.) relevant to the programs and subjects actively offered
    by this school, pre-populated with any saved room counts.
    """
    school_id = get_school_id(current_user, x_school_id)
    if not school_id:
        raise HTTPException(status_code=400, detail="Active school context required")

    # Find active subject names for this school
    classes = db.query(ClassSection).filter(ClassSection.school_id == school_id).all()
    active_subject_names = set()
    for c in classes:
        for s in (c.subjects or []):
            if s.name:
                active_subject_names.add(s.name.strip())
        if c.program and c.program.subjects:
            for s in c.program.subjects:
                if s.name:
                    active_subject_names.add(s.name.strip())

    if not active_subject_names:
        subjs = db.query(Subject).filter((Subject.school_id == school_id) | (Subject.school_id.is_(None))).all()
        for s in subjs:
            if s.name:
                active_subject_names.add(s.name.strip())

    config = db.query(TimetableConfig).filter(TimetableConfig.school_id == school_id).first()
    saved_counts = {}
    if config and config.facility_counts:
        try:
            saved_counts = json.loads(config.facility_counts)
        except Exception:
            saved_counts = {}

    facilities = get_active_facilities_for_subjects(list(active_subject_names), saved_counts)

    categories = {}
    for f in facilities:
        cat = f["category"]
        if cat not in categories:
            categories[cat] = {
                "category": cat,
                "title": f["category_title"],
                "items": []
            }
        categories[cat]["items"].append(f)

    return {
        "school_id": school_id,
        "has_specialized_facilities": len(facilities) > 0,
        "facilities": facilities,
        "categories": list(categories.values())
    }


@router.get("/snapshot-status")
def get_snapshot_status(
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id"),
):
    """Checks whether an undo snapshot is available for the current school and semester."""
    school_id = get_school_id(current_user, x_school_id)
    if not school_id:
        return {"has_snapshot": False}

    q = db.query(TimetableSnapshot).filter(TimetableSnapshot.school_id == school_id)
    if semester_id and isinstance(semester_id, int):
        q = q.filter((TimetableSnapshot.semester_id == semester_id) | (TimetableSnapshot.semester_id.is_(None)))
    latest = q.order_by(TimetableSnapshot.id.desc()).first()

    if not latest:
        return {"has_snapshot": False}

    return {
        "has_snapshot": True,
        "snapshot_id": latest.id,
        "slot_count": latest.slot_count,
        "created_at": latest.created_at.strftime("%Y-%m-%d %H:%M:%S") if latest.created_at else None
    }


@router.post("/revert")
def revert_timetable(
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id"),
):
    """
    1-Click Rollback / Undo:
    Reverts the timetable to the snapshot taken immediately before the last auto-generation.
    """
    require_admin(current_user)
    school_id = get_school_id(current_user, x_school_id)
    if not school_id:
        raise HTTPException(status_code=400, detail="Active school context required")

    q = db.query(TimetableSnapshot).filter(TimetableSnapshot.school_id == school_id)
    if semester_id and isinstance(semester_id, int):
        q = q.filter((TimetableSnapshot.semester_id == semester_id) | (TimetableSnapshot.semester_id.is_(None)))
    latest = q.order_by(TimetableSnapshot.id.desc()).first()

    if not latest:
        raise HTTPException(status_code=404, detail="No previous timetable snapshot found to revert to.")

    # 1. Delete current timetable slots for this school
    class_ids = [c[0] for c in db.query(ClassSection.id).filter(
        (ClassSection.school_id == school_id) | (ClassSection.school_id.is_(None))
    ).all()]

    if class_ids:
        del_q = db.query(Timetable).filter(Timetable.class_section_id.in_(class_ids))
        if semester_id:
            del_q = del_q.filter(Timetable.semester_id == semester_id)
        del_q.delete(synchronize_session=False)

    # 2. Restore slots from snapshot
    restored_items = json.loads(latest.snapshot_data)
    new_slots = [
        Timetable(
            class_section_id=item["class_section_id"],
            subject_id=item["subject_id"],
            teacher_id=item.get("teacher_id"),
            semester_id=item.get("semester_id"),
            day_of_week=item["day_of_week"],
            period_number=item["period_number"],
            start_time=item.get("start_time"),
            end_time=item.get("end_time"),
            room=item.get("room"),
        )
        for item in restored_items
    ]
    if new_slots:
        db.add_all(new_slots)

    db.delete(latest)
    db.commit()

    return {
        "status": "SUCCESS",
        "message": f"Successfully reverted to previous timetable ({len(new_slots)} slots restored).",
        "restored_slots": len(new_slots)
    }


@router.post("/discard")
def discard_draft_timetable(
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id"),
):
    """
    1-Click Discard Draft:
    Deletes the drafted timetable slots and clears the snapshot, resetting to a clean slate.
    """
    require_admin(current_user)
    school_id = get_school_id(current_user, x_school_id)
    if not school_id:
        raise HTTPException(status_code=400, detail="Active school context required")

    class_ids = [c[0] for c in db.query(ClassSection.id).filter(
        (ClassSection.school_id == school_id) | (ClassSection.school_id.is_(None))
    ).all()]

    deleted_count = 0
    if class_ids:
        del_q = db.query(Timetable).filter(Timetable.class_section_id.in_(class_ids))
        if semester_id:
            del_q = del_q.filter(Timetable.semester_id == semester_id)
        deleted_count = del_q.delete(synchronize_session=False)

    # Delete the snapshot as well
    q = db.query(TimetableSnapshot).filter(TimetableSnapshot.school_id == school_id)
    if semester_id and isinstance(semester_id, int):
        q = q.filter((TimetableSnapshot.semester_id == semester_id) | (TimetableSnapshot.semester_id.is_(None)))
    latest = q.order_by(TimetableSnapshot.id.desc()).first()
    if latest:
        db.delete(latest)

    db.commit()

    return {
        "status": "SUCCESS",
        "message": f"Successfully discarded draft ({deleted_count} slots cleared back to blank).",
        "cleared_slots": deleted_count
    }


@router.delete("/clear")
def clear_timetable(
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id"),
):
    """
    Master Clear Timetable:
    Wipes all timetable slots for the school/semester back to 0.
    """
    require_admin(current_user)
    school_id = get_school_id(current_user, x_school_id)
    if not school_id:
        raise HTTPException(status_code=400, detail="Active school context required")

    class_ids = [c[0] for c in db.query(ClassSection.id).filter(
        (ClassSection.school_id == school_id) | (ClassSection.school_id.is_(None))
    ).all()]

    deleted_count = 0
    if class_ids:
        del_q = db.query(Timetable).filter(Timetable.class_section_id.in_(class_ids))
        if semester_id:
            del_q = del_q.filter(Timetable.semester_id == semester_id)
        deleted_count = del_q.delete(synchronize_session=False)

    # Also clean up snapshots for this school/semester
    q = db.query(TimetableSnapshot).filter(TimetableSnapshot.school_id == school_id)
    if semester_id and isinstance(semester_id, int):
        q = q.filter((TimetableSnapshot.semester_id == semester_id) | (TimetableSnapshot.semester_id.is_(None)))
    q.delete(synchronize_session=False)

    db.commit()

    return {
        "status": "SUCCESS",
        "message": f"Successfully cleared all {deleted_count} timetable slots.",
        "deleted_count": deleted_count
    }


@router.post("/auto-generate", status_code=200)
def auto_generate_timetable(
    payload: AutoGenerateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id"),
):
    """
    1-Click Autonomous Constraint Solver:
    Solves and builds the master conflict-free schedule in < 1.5 seconds.
    """
    require_admin(current_user)
    school_id = get_school_id(current_user, x_school_id)
    if not school_id:
        raise HTTPException(status_code=400, detail="Active school context required")

    school = db.query(School).filter(School.id == school_id).first()
    school_mode = getattr(school, "school_mode", "SHS_ONLY") or "SHS_ONLY"
    ownership = getattr(school, "ownership_type", "PRIVATE") or "PRIVATE"

    profile = "PUBLIC_BASIC" if (school_mode == "BASIC_ONLY" and ownership.upper() == "PUBLIC") else (
        "PRIVATE_BASIC" if school_mode == "BASIC_ONLY" else "SHS"
    )

    config = db.query(TimetableConfig).filter(TimetableConfig.school_id == school_id).first()
    break_sched = None
    if config and config.break_schedule:
        try:
            break_sched = json.loads(config.break_schedule)
        except Exception:
            break_sched = None

    periods_per_day = payload.periods_per_day or (config.periods_per_day if config else 8)
    friday_periods = payload.friday_periods or (config.friday_periods if config else 6)
    start_time = config.start_time if config and config.start_time else "08:00"
    period_duration = config.period_duration_minutes if config and config.period_duration_minutes else 45

    saved_fac = {}
    if config and config.facility_counts:
        try:
            saved_fac = json.loads(config.facility_counts)
        except Exception:
            saved_fac = {}

    effective_facility_counts = payload.facility_counts if payload.facility_counts is not None else saved_fac
    if payload.facility_counts is not None:
        if not config:
            config = TimetableConfig(school_id=school_id)
            db.add(config)
        config.facility_counts = json.dumps(payload.facility_counts)
        db.commit()

    solver = TimetableSolver(
        db=db,
        school_id=school_id,
        semester_id=payload.semester_id,
        school_profile=profile,
        periods_per_day=periods_per_day,
        friday_periods=friday_periods,
        start_time=start_time,
        period_duration=period_duration,
        break_schedule=break_sched,
        custom_quotas=payload.custom_quotas or {},
        facility_counts=effective_facility_counts
    )

    # ARCH-6 FIX: Acquire generation lock — only one school generates at a time.
    # Non-blocking acquire with 0 timeout returns False if lock is already held.
    if not _GENERATE_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="Timetable generation is already running. Please wait and try again."
        )
    try:
        result = solver.solve()
    finally:
        _GENERATE_LOCK.release()
    return result


@router.get("/teacher-workloads")
def get_teacher_workloads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id"),
):
    """Admin: view all teachers' assigned period counts vs their legal workload caps."""
    require_admin(current_user)
    school_id = get_school_id(current_user, x_school_id)

    if school_id is not None:
        teachers = db.query(User).filter(User.school_id == school_id).all()
    else:
        teachers = db.query(User).filter(User.school_id.is_(None)).all()

    workloads = []
    for t in teachers:
        roles = [r.name.lower() for r in t.roles] if t.roles else []

        # Superadmin is a global multi-tenant platform user and never part of school staff/timetable
        if "super_admin" in roles or getattr(t, "is_superadmin", False):
            continue

        if any(r in roles for r in ["teacher", "admin", "school_administrator", "secretary", "school_secretary", "headmaster", "bursar", "accountant", "clerk"]) or t.responsibility_role:
            role = getattr(t, "responsibility_role", None)
            if not role or role == "REGULAR_TEACHER":
                if "school_administrator" in roles or "schooladmin" in roles:
                    role = "SCHOOL_ADMINISTRATOR"
                elif "secretary" in roles or "school_secretary" in roles or "clerk" in roles:
                    role = "SECRETARY"
                elif "headmaster" in roles or "principal" in roles:
                    role = "HEADMASTER"
                elif "bursar" in roles or "accountant" in roles:
                    role = "BURSAR"
                elif "assistant_head_admin" in roles:
                    role = "ASSISTANT_HEAD_ADMIN"
                elif "assistant_head_academic" in roles:
                    role = "ASSISTANT_HEAD_ACADEMIC"
                elif "assistant_head_domestic" in roles:
                    role = "ASSISTANT_HEAD_DOMESTIC"
                elif "assistant_head" in roles:
                    role = "ASSISTANT_HEAD"
                elif "admin" in roles:
                    role = "ADMIN"
                else:
                    role = "REGULAR_TEACHER"

            role_limit = ROLE_WORKLOAD_LIMITS.get(role, ROLE_WORKLOAD_LIMITS["REGULAR_TEACHER"])
            
            exempt_roles = {
                "SCHOOL_ADMINISTRATOR", "ADMIN", "SECRETARY", "SCHOOL_SECRETARY",
                "HEADMASTER", "BURSAR", "ASSISTANT_HEAD_ADMIN",
                "ASSISTANT_HEAD_ACADEMIC", "ASSISTANT_HEAD_DOMESTIC", "ASSISTANT_HEAD"
            }
            is_admin_or_office_role = any(r in roles for r in ["admin", "school_administrator", "secretary", "school_secretary", "bursar", "accountant", "headmaster", "clerk"])

            is_exempt = getattr(t, "is_teaching_exempt", False) or is_admin_or_office_role or role in exempt_roles
            max_cap = getattr(t, "max_weekly_periods", 0) if is_exempt else (getattr(t, "max_weekly_periods", role_limit["default_cap"]) or role_limit["default_cap"])

            assigned_count = db.query(Timetable).filter(Timetable.teacher_id == t.id).count()

            if is_exempt:
                compliance_status = "EXEMPT"
            elif assigned_count > max_cap:
                compliance_status = "OVERLOADED"
            elif assigned_count >= 18:
                compliance_status = "OPTIMAL"
            else:
                compliance_status = "UNDERLOADED"

            workloads.append({
                "teacher_id": t.id,
                "teacher_name": t.username,
                "staff_id": getattr(t, "staff_id", None),
                "responsibility_role": role,
                "role_title": role_limit["title"],
                "department_id": t.department_id,
                "department_name": t.department.name if t.department else "General",
                "primary_subject_id": getattr(t, "primary_subject_id", None),
                "primary_subject_name": getattr(t, "primary_subject_name", None),
                "qualified_subject_names": getattr(t, "qualified_subject_names", []),
                "assigned_periods": assigned_count,
                "max_cap": max_cap,
                "is_exempt": is_exempt,
                "compliance_status": compliance_status,
                "utilization_percent": round((assigned_count / max(1, max_cap)) * 100, 1) if not is_exempt else 0
            })

    return workloads


class RolloverAssignmentsSchema(BaseModel):
    source_semester_id: Optional[int] = None
    target_semester_id: Optional[int] = None


@router.post("/rollover-assignments")
def rollover_teacher_assignments(
    payload: RolloverAssignmentsSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id"),
):
    """
    1-Click Academic Delivery Rollover:
    Copies all teacher-to-class subject assignments from a source semester to a target semester.
    Guarantees staff specializations and class allocations carry over seamlessly with 0 keystrokes.
    """
    require_admin(current_user)
    school_id = get_school_id(current_user, x_school_id)

    target_sem_id = payload.target_semester_id
    if not target_sem_id:
        cur_sem = db.query(Semester).filter(Semester.is_current == True).first()
        if not cur_sem:
            raise HTTPException(status_code=400, detail="No active semester found to rollover assignments into.")
        target_sem_id = cur_sem.id

    source_sem_id = payload.source_semester_id
    if not source_sem_id:
        prev_sem = db.query(Semester).filter(Semester.id != target_sem_id).order_by(Semester.id.desc()).first()
        if not prev_sem:
            raise HTTPException(status_code=400, detail="No previous semester found to rollover assignments from.")
        source_sem_id = prev_sem.id

    if source_sem_id == target_sem_id:
        raise HTTPException(status_code=400, detail="Source and target semesters must be different.")

    source_assignments = db.query(TeacherAssignment).options(
        joinedload(TeacherAssignment.class_section)  # BUG 12 FIX: eager-load to avoid N+1
    ).filter(
        TeacherAssignment.semester_id == source_sem_id
    ).all()

    if not source_assignments:
        return {
            "status": "SUCCESS",
            "copied_count": 0,
            "message": f"No assignments found in source semester (ID: {source_sem_id}) to rollover."
        }

    existing_target = set(
        db.query(
            TeacherAssignment.class_section_id,
            TeacherAssignment.subject_id,
            TeacherAssignment.teacher_id
        ).filter(
            TeacherAssignment.semester_id == target_sem_id
        ).all()
    )

    copied = 0
    for sa in source_assignments:
        if school_id and sa.class_section and sa.class_section.school_id != school_id:
            continue
        key = (sa.class_section_id, sa.subject_id, sa.teacher_id)
        if key not in existing_target:
            new_ta = TeacherAssignment(
                class_section_id=sa.class_section_id,
                subject_id=sa.subject_id,
                teacher_id=sa.teacher_id,
                semester_id=target_sem_id
            )
            db.add(new_ta)
            existing_target.add(key)
            copied += 1

    db.commit()
    target_sem_obj = db.query(Semester).filter(Semester.id == target_sem_id).first()
    target_name = target_sem_obj.name if target_sem_obj else f"Semester {target_sem_id}"

    return {
        "status": "SUCCESS",
        "copied_count": copied,
        "source_semester_id": source_sem_id,
        "target_semester_id": target_sem_id,
        "message": f"Successfully rolled over {copied} teacher assignments into {target_name}."
    }


@router.post("/handover")
def execute_teacher_handover(
    payload: HandoverSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    1-Click Staff Handover:
    Surgically transfers all teaching slots from an outgoing teacher to an incoming teacher,
    automatically resolving any colliding slots without disturbing other classes.
    """
    require_admin(current_user)
    school_id = get_school_id(current_user)
    if not school_id:
        raise HTTPException(status_code=400, detail="Active school context required")

    res = smart_surgical_swap(
        db=db,
        school_id=school_id,
        outgoing_teacher_id=payload.outgoing_teacher_id,
        incoming_teacher_id=payload.incoming_teacher_id
    )
    return res


@router.get("/campus-radar")
def get_campus_radar(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id"),
):
    """
    📡 Live Campus Radar ("Now Teaching"):
    Returns the currently active period, room occupancy map, and currently free staff.
    """
    school_id = get_school_id(current_user, x_school_id)
    now = datetime.now()
    now_day = now.weekday()  # 0=Mon ... 6=Sun

    # BUG 2 FIX: Determine current period from TimetableConfig (not hardcoded 08:00 times).
    # Falls back to standard GES SHS period map if config is not set.
    _tt_cfg = db.query(TimetableConfig).filter(TimetableConfig.school_id == school_id).first()
    _start_h, _start_m = 8, 0
    _dur = 45
    if _tt_cfg:
        if _tt_cfg.start_time:
            try:
                _parts = str(_tt_cfg.start_time).split(":")
                _start_h, _start_m = int(_parts[0]), int(_parts[1])
            except Exception:
                pass
        if _tt_cfg.period_duration_minutes:
            _dur = _tt_cfg.period_duration_minutes

    # Standard GES SHS break structure (minutes from school start):
    # P1, P2, [break 20min], P3, P4, [break 40min], P5, P6, P7, P8
    _BREAK_AFTER = {2: 20, 4: 40}  # after period N, break of X minutes
    _now_minutes = (now.hour * 60 + now.minute)
    _cursor = _start_h * 60 + _start_m
    current_period = None
    for _pnum in range(1, 10):
        _pend = _cursor + _dur
        if _cursor <= _now_minutes < _pend:
            current_period = _pnum
            break
        _cursor = _pend
        _brk = _BREAK_AFTER.get(_pnum, 0)
        _cursor += _brk
        if _cursor > _now_minutes and current_period is None:
            # We are in a break between periods
            current_period = _pnum  # Show last active period during break
            break
    if current_period is None:
        current_period = 1  # Before school starts or after it ends

    # Query all slots for today & current period
    slot_filter = [
        Timetable.day_of_week == (now_day if now_day <= 4 else 0),
        Timetable.period_number == current_period
    ]
    if school_id is not None:
        slot_filter.append(ClassSection.school_id == school_id)

    active_slots = db.query(Timetable).options(
        joinedload(Timetable.class_section),
        joinedload(Timetable.subject),
        joinedload(Timetable.teacher)
    ).join(Timetable.class_section).filter(*slot_filter).all()

    busy_teachers = {s.teacher_id for s in active_slots if s.teacher_id}

    # Find free teachers right now
    if school_id is not None:
        all_teachers = db.query(User).filter(User.school_id == school_id).all()
    else:
        all_teachers = db.query(User).filter(User.school_id.is_(None)).all()
    free_teachers = []
    for t in all_teachers:
        roles = [r.name for r in t.roles] if t.roles else []
        if ("teacher" in roles) and (t.id not in busy_teachers):
            free_teachers.append({
                "id": t.id,
                "username": t.username,
                "role": getattr(t, "responsibility_role", "REGULAR_TEACHER")
            })

    occupied_rooms = []
    occupied_labs = []
    for s in active_slots:
        entry = {
            "class_name": s.class_section.name if s.class_section else f"Class #{s.class_section_id}",
            "subject_name": s.subject.name if s.subject else "Subject",
            "teacher_name": s.teacher.username if s.teacher else "Vacant",
            "room": s.room or "Standard Classroom"
        }
        if s.room and any(kw in s.room.lower() for kw in ["lab", "studio", "kitchen", "workshop"]):
            occupied_labs.append(entry)
        else:
            occupied_rooms.append(entry)

    return {
        "current_day": DAYS[now_day] if now_day <= 4 else "Weekend (Showing Monday)",
        "current_period": current_period,
        "is_school_hours": 8 <= current_hour <= 16 and now_day <= 4,
        "active_classes_count": len(active_slots),
        "occupied_rooms": occupied_rooms,
        "occupied_labs": occupied_labs,
        "free_teachers": free_teachers,
        "free_teachers_count": len(free_teachers)
    }


@router.post("/relief/dispatch")
def dispatch_relief_teacher(
    payload: ReliefDispatchSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign an eligible free relief teacher to cover an absent teacher's slot."""
    require_admin(current_user)
    school_id = get_school_id(current_user)
    if not school_id:
        raise HTTPException(status_code=400, detail="Active school context required")

    slot = db.query(Timetable).filter(Timetable.id == payload.timetable_slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Timetable slot not found")

    log = TimetableReliefLog(
        school_id=school_id,
        absent_teacher_id=payload.absent_teacher_id,
        reliever_teacher_id=payload.reliever_teacher_id,
        timetable_slot_id=payload.timetable_slot_id,
        date=payload.date,
        reason=payload.reason,
        status="CONFIRMED"
    )
    db.add(log)
    db.commit()
    return {"status": "SUCCESS", "message": "Relief teacher assigned successfully."}


@router.post("/syllabus-log")
def log_syllabus_delivery(
    payload: SyllabusLogSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record class attendance & topic taught during a timetable period."""
    school_id = get_school_id(current_user)
    if not school_id:
        raise HTTPException(status_code=400, detail="Active school context required")

    log = TimetableSyllabusLog(
        school_id=school_id,
        timetable_slot_id=payload.timetable_slot_id,
        class_section_id=payload.class_section_id,
        subject_id=payload.subject_id,
        teacher_id=current_user.id,
        topic_taught=payload.topic_taught,
        subtopic=payload.subtopic,
        remarks=payload.remarks
    )
    db.add(log)
    db.commit()
    return {"status": "SUCCESS", "message": "Syllabus delivery recorded successfully."}


@router.get("/calendar-sync/{user_id}.ics")
def export_calendar_ics(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Generates standard iCalendar (.ics) feed for smartphone notifications 10 mins before class."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    slots = db.query(Timetable).options(
        joinedload(Timetable.class_section),
        joinedload(Timetable.subject)
    ).filter(Timetable.teacher_id == user_id).all()

    ics_content = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//EduManage360//Academic Timetable//EN\r\nCALSCALE:GREGORIAN\r\n"

    days_abbr = ["MO", "TU", "WE", "TH", "FR"]
    for s in slots:
        sub_name = s.subject.name if s.subject else "Class Lesson"
        cls_name = s.class_section.name if s.class_section else "Class"
        room = s.room or "Classroom"
        day_abbr = days_abbr[s.day_of_week] if 0 <= s.day_of_week <= 4 else "MO"

        # BUG 8 FIX: Use actual slot start_time/end_time from DB instead of
        # hardcoded "8 + period_number" arithmetic that assumed 1-hr periods.
        if s.start_time and s.end_time:
            try:
                _st = str(s.start_time).split(":")
                _et = str(s.end_time).split(":")
                start_h, start_m = int(_st[0]), int(_st[1])
                end_h, end_m = int(_et[0]), int(_et[1])
            except Exception:
                start_h, start_m = 8 + (s.period_number - 1), 0
                end_h, end_m = 8 + s.period_number, 0
        else:
            # Fallback: approximate using period number with 45-min slots
            _base = 8 * 60 + (s.period_number - 1) * 45
            start_h, start_m = _base // 60, _base % 60
            end_h, end_m = (_base + 45) // 60, (_base + 45) % 60

        ics_content += (
            f"BEGIN:VEVENT\r\n"
            f"SUMMARY:{sub_name} - {cls_name}\r\n"
            f"DESCRIPTION:Period {s.period_number} — {cls_name} in {room}\r\n"
            f"LOCATION:{room}\r\n"
            f"RRULE:FREQ=WEEKLY;BYDAY={day_abbr}\r\n"
            f"DTSTART:20260901T{start_h:02d}{start_m:02d}00\r\n"
            f"DTEND:20260901T{end_h:02d}{end_m:02d}00\r\n"
            f"BEGIN:VALARM\r\nTRIGGER:-PT10M\r\nACTION:DISPLAY\r\n"
            f"DESCRIPTION:Reminder: {sub_name} in 10 minutes\r\n"
            f"END:VALARM\r\nEND:VEVENT\r\n"
        )

    ics_content += "END:VCALENDAR\r\n"

    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="Timetable_{user.username}.ics"'}
    )


# ── Standard Timetable Retrieval & CRUD Endpoints ─────────────────────────────

@router.get("/class/{class_section_id}")
def get_class_timetable(
    class_section_id: int,
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the full weekly timetable for a class section."""
    school_id = get_school_id(current_user)
    cs = db.query(ClassSection).options(joinedload(ClassSection.program)).filter(ClassSection.id == class_section_id).first()
    if not cs or not _check_class_school(cs, school_id):
        raise HTTPException(status_code=404, detail="Class section not found")

    query = db.query(Timetable).options(
        joinedload(Timetable.class_section),
        joinedload(Timetable.subject),
        joinedload(Timetable.teacher)
    ).filter(Timetable.class_section_id == class_section_id)
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
    query = db.query(Timetable).options(
        joinedload(Timetable.class_section),
        joinedload(Timetable.subject),
        joinedload(Timetable.teacher)
    ).filter(Timetable.teacher_id == teacher_id)
    if semester_id:
        query = query.filter(Timetable.semester_id == semester_id)
    slots = query.order_by(Timetable.day_of_week, Timetable.period_number).all()
    return [_enrich(s) for s in slots]


@router.get("/conflicts")
def check_conflicts(
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: find all teacher and room/lab double-booking conflicts."""
    require_admin(current_user)
    school_id = get_school_id(current_user)

    query = db.query(Timetable).options(
        joinedload(Timetable.class_section),
        joinedload(Timetable.subject),
        joinedload(Timetable.teacher)
    ).join(Timetable.class_section).outerjoin(ClassSection.program)
    if school_id is not None:
        if hasattr(ClassSection, "school_id"):
            query = query.filter((ClassSection.school_id == school_id) | (Program.school_id == school_id))
        else:
            query = query.filter(Program.school_id == school_id)

    # BUG 11 FIX: Filter by semester to prevent phantom cross-semester conflicts.
    # Auto-detect current active semester when not explicitly provided.
    if not semester_id:
        _active = db.query(Semester).filter(Semester.is_current == True).first()
        if _active:
            semester_id = _active.id
    if semester_id:
        query = query.filter(Timetable.semester_id == semester_id)

    all_slots = query.all()

    seen_teacher = {}
    conflicts = []
    for slot in all_slots:
        if slot.teacher_id:
            key = (slot.teacher_id, slot.day_of_week, slot.period_number)
            if key in seen_teacher:
                conflicts.append({
                    "type": "teacher",
                    "teacher_id": slot.teacher_id,
                    "teacher_name": slot.teacher.username if slot.teacher else None,
                    "day": DAYS[slot.day_of_week],
                    "period": slot.period_number,
                    "slot_1": _enrich(seen_teacher[key]),
                    "slot_2": _enrich(slot),
                })
            else:
                seen_teacher[key] = slot

    seen_room = {}
    for slot in all_slots:
        if slot.room and slot.room.strip():
            key = (slot.room.strip().lower(), slot.day_of_week, slot.period_number)
            if key in seen_room:
                conflicts.append({
                    "type": "room",
                    "room": slot.room,
                    "day": DAYS[slot.day_of_week],
                    "period": slot.period_number,
                    "slot_1": _enrich(seen_room[key]),
                    "slot_2": _enrich(slot),
                })
            else:
                seen_room[key] = slot

    return conflicts


@router.get("/")
def list_all_slots(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: list all timetable entries."""
    require_admin(current_user)
    school_id = get_school_id(current_user)
    query = db.query(Timetable).options(
        joinedload(Timetable.class_section),
        joinedload(Timetable.subject),
        joinedload(Timetable.teacher)
    ).join(Timetable.class_section)
    if school_id is not None:
        query = query.filter((ClassSection.school_id == school_id) | (ClassSection.school_id.is_(None)))
    slots = query.order_by(Timetable.class_section_id, Timetable.day_of_week, Timetable.period_number).all()
    return [_enrich(s) for s in slots]


@router.post("/", status_code=201)
def create_slot(
    payload: SlotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: manually create a timetable slot with double-booking prevention."""
    require_admin(current_user)

    cs = db.query(ClassSection).filter(ClassSection.id == payload.class_section_id).first()
    if not cs:
        raise HTTPException(status_code=404, detail="Class section not found")
    school_id = get_school_id(current_user)
    if not _check_class_school(cs, school_id):
        raise HTTPException(status_code=404, detail="Class section not found")

    if payload.day_of_week < 0 or payload.day_of_week > 4:
        raise HTTPException(status_code=400, detail="day_of_week must be 0 (Mon) to 4 (Fri)")
    if payload.period_number < 1:
        raise HTTPException(status_code=400, detail="period_number must be >= 1")

    # Check class collision
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

    # Check teacher collision
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

    # Check room collision
    if payload.room and payload.room.strip():
        existing_room = db.query(Timetable).filter(
            Timetable.room == payload.room.strip(),
            Timetable.day_of_week == payload.day_of_week,
            Timetable.period_number == payload.period_number,
        ).first()
        if existing_room:
            cls_name = existing_room.class_section.name if existing_room.class_section else f"Class #{existing_room.class_section_id}"
            raise HTTPException(
                status_code=409,
                detail=f"Room/Lab '{payload.room.strip()}' is already allocated to {cls_name} on {DAYS[payload.day_of_week]} Period {payload.period_number}"
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
    school_id = get_school_id(current_user)
    if not _check_class_school(slot.class_section, school_id):
        raise HTTPException(status_code=404, detail="Timetable slot not found")

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

    new_room = payload.room.strip() if payload.room is not None and payload.room.strip() else (slot.room.strip() if slot.room else None)
    if new_room and new_room != (slot.room or "").strip():
        room_conflict = db.query(Timetable).filter(
            Timetable.room == new_room,
            Timetable.day_of_week == slot.day_of_week,
            Timetable.period_number == slot.period_number,
            Timetable.id != slot_id,
        ).first()
        if room_conflict:
            cls_name = room_conflict.class_section.name if room_conflict.class_section else f"Class #{room_conflict.class_section_id}"
            raise HTTPException(status_code=409, detail=f"Room/Lab '{new_room}' is already allocated to {cls_name} in this period")

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
    school_id = get_school_id(current_user)
    if not _check_class_school(slot.class_section, school_id):
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
    cs = db.query(ClassSection).filter(ClassSection.id == class_section_id).first()
    if not cs:
        raise HTTPException(status_code=404, detail="Class section not found")
    school_id = get_school_id(current_user)
    if not _check_class_school(cs, school_id):
        raise HTTPException(status_code=404, detail="Class section not found")
    db.query(Timetable).filter(Timetable.class_section_id == class_section_id).delete()
    db.commit()


# ── PDF Dockets ───────────────────────────────────────────────────────────────

@router.get("/class/{class_section_id}/pdf")
def get_class_timetable_pdf(
    class_section_id: int,
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates and streams an official A4 Landscape Class Weekly Timetable PDF."""
    school_id = get_school_id(current_user)
    cs = db.query(ClassSection).filter(ClassSection.id == class_section_id).first()
    if not cs or not _check_class_school(cs, school_id):
        raise HTTPException(status_code=404, detail="Class section not found")

    # BUG 10 FIX: Scope PDF to one semester. Auto-detect current if none provided.
    if not semester_id:
        _active_sem = db.query(Semester).filter(Semester.is_current == True).first()
        semester_id = _active_sem.id if _active_sem else None
    _pdf_q = [Timetable.class_section_id == class_section_id]
    if semester_id:
        _pdf_q.append(Timetable.semester_id == semester_id)
    slots = db.query(Timetable).filter(*_pdf_q).all()
    slot_map = {(s.day_of_week, s.period_number): s for s in slots}

    school_name_s = db.query(Setting).filter(Setting.key == "school_name").first()
    school_name = school_name_s.value if school_name_s and school_name_s.value else "SENIOR HIGH SCHOOL"
    now_str = datetime.now().strftime("%d %B %Y")

    # Build period rows dynamically from actual slot start/end times stored in DB.
    # Falls back to GES SHS standard times. UX-6 FIX: Period 8 now included.
    _slot_times: Dict[int, str] = {}
    for _s in slots:
        if _s.start_time and _s.end_time and _s.period_number not in _slot_times:
            _slot_times[_s.period_number] = f"{_s.start_time} - {_s.end_time}"
    _std_times = {
        1: "08:00 - 08:45", 2: "08:45 - 09:30", 3: "09:50 - 10:35",
        4: "10:35 - 11:20", 5: "12:00 - 12:45", 6: "12:45 - 13:30",
        7: "13:30 - 14:15", 8: "14:15 - 15:00",
    }
    periods_config = [
        {"period": 1, "time": _slot_times.get(1, _std_times[1])},
        {"period": 2, "time": _slot_times.get(2, _std_times[2])},
        {"is_break": True, "title": "SNACK &amp; BREAKFAST BREAK"},
        {"period": 3, "time": _slot_times.get(3, _std_times[3])},
        {"period": 4, "time": _slot_times.get(4, _std_times[4])},
        {"is_break": True, "title": "MID-DAY LUNCH BREAK"},
        {"period": 5, "time": _slot_times.get(5, _std_times[5])},
        {"period": 6, "time": _slot_times.get(6, _std_times[6])},
        {"period": 7, "time": _slot_times.get(7, _std_times[7])},
        {"period": 8, "time": _slot_times.get(8, _std_times[8])},  # UX-6 FIX: was missing
    ]

    rows_html = ""
    for item in periods_config:
        if item.get("is_break"):
            rows_html += f"""
            <tr style="background:#f1f5f9; text-align:center; font-weight:bold; color:#475569; font-size:7.5px;">
                <td colspan="6" style="padding:4px; border:1px solid #94a3b8; letter-spacing:1px;">&mdash; {item['title']} &mdash;</td>
            </tr>
            """
        else:
            p_num = item["period"]
            p_time = item["time"]
            cols_html = f'<td style="text-align:center; font-weight:bold; background:#f8fafc; border:1px solid #94a3b8; font-size:8px;">Period {p_num}<br/><span style="font-size:7px; color:#64748b; font-weight:normal;">{p_time}</span></td>'

            for day_idx in range(5):
                slot = slot_map.get((day_idx, p_num))
                if slot:
                    sub_name = slot.subject.name if slot.subject else "Subject"
                    t_name = slot.teacher.username if slot.teacher else ""
                    room_str = f" [{slot.room}]" if slot.room else ""
                    is_core = slot.subject.is_core if slot.subject else True
                    badge_color = "#0369a1" if is_core else "#059669"

                    cols_html += f"""
                    <td style="border:1px solid #94a3b8; padding:4px 6px; vertical-align:top; background:rgba(255,255,255,0.7);">
                        <div style="font-weight:bold; font-size:8px; color:{badge_color};">{sub_name}</div>
                        <div style="font-size:7px; color:#475569; margin-top:2px;">{t_name}{room_str}</div>
                    </td>
                    """
                else:
                    cols_html += '<td style="border:1px solid #94a3b8; padding:4px; text-align:center; font-size:7px; color:#cbd5e1;">&mdash;</td>'

            rows_html += f"<tr>{cols_html}</tr>"

    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: a4 landscape; margin: 0.8cm; }}
            body {{ font-family: Helvetica, Arial, sans-serif; font-size: 8px; color: #0f172a; }}
            .header-table {{ width: 100%; border-bottom: 2px solid #0f172a; padding-bottom: 6px; margin-bottom: 8px; }}
            .grid-table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
            .grid-table th, .grid-table td {{ border: 1px solid #94a3b8; }}
            .grid-table th {{ background: #0f172a; color: #ffffff; font-weight: bold; text-align: center; padding: 6px; font-size: 8.5px; }}
        </style>
    </head>
    <body>
        <table class="header-table">
            <tr>
                <td style="width:70%;">
                    <div style="font-size:7.5px; font-weight:bold; color:#475569; letter-spacing:1px; text-transform:uppercase;">GHANA EDUCATION SERVICE &bull; ACADEMIC TIMETABLE BOARD</div>
                    <div style="font-size:14px; font-weight:900; color:#0f172a; text-transform:uppercase; margin-top:2px;">{school_name}</div>
                    <div style="font-size:10px; font-weight:bold; color:#0369a1; margin-top:2px; text-transform:uppercase;">OFFICIAL CLASS WEEKLY TIMETABLE &bull; {cs.name}</div>
                </td>
                <td style="width:30%; text-align:right; vertical-align:top;">
                    <div style="font-size:9.5px; font-weight:bold; color:#0f172a;">CLASS: {cs.name}</div>
                    <div style="font-size:7.5px; color:#64748b;">EFFECTIVE: 2025/2026 ACADEMIC SESSION</div>
                    <div style="font-size:7.5px; color:#64748b;">DATE: {now_str}</div>
                </td>
            </tr>
        </table>

        <table class="grid-table">
            <thead>
                <tr>
                    <th style="width:85px;">Period / Time</th>
                    <th>Monday</th>
                    <th>Tuesday</th>
                    <th>Wednesday</th>
                    <th>Thursday</th>
                    <th>Friday</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>

        <table style="width:100%; margin-top:16px; border:none; font-size:8px;">
            <tr>
                <td style="width:33%; text-align:center;">
                    <div style="border-bottom:1px solid #000; width:130px; margin:0 auto 4px;"></div>
                    <strong>Form Master / Mistress</strong>
                    <div style="font-size:7px; color:#64748b;">Signature &amp; Date</div>
                </td>
                <td style="width:33%; text-align:center;">
                    <div style="border-bottom:1px solid #000; width:130px; margin:0 auto 4px;"></div>
                    <strong>Head of Academic Affairs</strong>
                    <div style="font-size:7px; color:#64748b;">Signature &amp; Date</div>
                </td>
                <td style="width:34%; text-align:center;">
                    <div style="border-bottom:1px solid #000; width:130px; margin:0 auto 4px;"></div>
                    <strong>Headmaster / Principal</strong>
                    <div style="font-size:7px; color:#64748b;">Official Approval &amp; Stamp</div>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)
    if pisa_status.err:
        raise HTTPException(status_code=500, detail="Failed to compile class timetable PDF")

    clean_cls_name = (cs.name or f"Class_{class_section_id}").replace(" ", "_")
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Timetable_{clean_cls_name}.pdf"'}
    )


@router.get("/teacher/{teacher_id}/pdf")
def get_teacher_timetable_pdf(
    teacher_id: int,
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates and streams an official A4 Landscape Teacher Schedule Docket PDF."""
    teacher = db.query(User).filter(User.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    # BUG 10 FIX: Scope teacher PDF to one semester — auto-detect current if none provided.
    if not semester_id:
        _active_sem = db.query(Semester).filter(Semester.is_current == True).first()
        semester_id = _active_sem.id if _active_sem else None
    _t_pdf_q = [Timetable.teacher_id == teacher_id]
    if semester_id:
        _t_pdf_q.append(Timetable.semester_id == semester_id)
    slots = db.query(Timetable).filter(*_t_pdf_q).all()
    slot_map = {(s.day_of_week, s.period_number): s for s in slots}

    school_name_s = db.query(Setting).filter(Setting.key == "school_name").first()
    school_name = school_name_s.value if school_name_s and school_name_s.value else "SENIOR HIGH SCHOOL"
    now_str = datetime.now().strftime("%d %B %Y")

    # BUG 3 + UX-6 FIX: Dynamic period times from actual DB slot data; Period 8 included.
    _t_slot_times: Dict[int, str] = {}
    for _s in slots:
        if _s.start_time and _s.end_time and _s.period_number not in _t_slot_times:
            _t_slot_times[_s.period_number] = f"{_s.start_time} - {_s.end_time}"
    _t_std_times = {
        1: "08:00 - 08:45", 2: "08:45 - 09:30", 3: "09:50 - 10:35",
        4: "10:35 - 11:20", 5: "12:00 - 12:45", 6: "12:45 - 13:30",
        7: "13:30 - 14:15", 8: "14:15 - 15:00",
    }
    periods_config = [
        {"period": 1, "time": _t_slot_times.get(1, _t_std_times[1])},
        {"period": 2, "time": _t_slot_times.get(2, _t_std_times[2])},
        {"is_break": True, "title": "SNACK &amp; BREAKFAST BREAK"},
        {"period": 3, "time": _t_slot_times.get(3, _t_std_times[3])},
        {"period": 4, "time": _t_slot_times.get(4, _t_std_times[4])},
        {"is_break": True, "title": "MID-DAY LUNCH BREAK"},
        {"period": 5, "time": _t_slot_times.get(5, _t_std_times[5])},
        {"period": 6, "time": _t_slot_times.get(6, _t_std_times[6])},
        {"period": 7, "time": _t_slot_times.get(7, _t_std_times[7])},
        {"period": 8, "time": _t_slot_times.get(8, _t_std_times[8])},  # UX-6 FIX: was missing
    ]

    rows_html = ""
    for item in periods_config:
        if item.get("is_break"):
            rows_html += f"""
            <tr style="background:#f1f5f9; text-align:center; font-weight:bold; color:#475569; font-size:7.5px;">
                <td colspan="6" style="padding:4px; border:1px solid #94a3b8; letter-spacing:1px;">&mdash; {item['title']} &mdash;</td>
            </tr>
            """
        else:
            p_num = item["period"]
            p_time = item["time"]
            cols_html = f'<td style="text-align:center; font-weight:bold; background:#f8fafc; border:1px solid #94a3b8; font-size:8px;">Period {p_num}<br/><span style="font-size:7px; color:#64748b; font-weight:normal;">{p_time}</span></td>'

            for day_idx in range(5):
                slot = slot_map.get((day_idx, p_num))
                if slot:
                    sub_name = slot.subject.name if slot.subject else "Subject"
                    cls_name = slot.class_section.name if slot.class_section else ""
                    room_str = f" [{slot.room}]" if slot.room else ""

                    cols_html += f"""
                    <td style="border:1px solid #94a3b8; padding:4px 6px; vertical-align:top; background:rgba(255,255,255,0.7);">
                        <div style="font-weight:bold; font-size:8px; color:#0369a1;">{sub_name}</div>
                        <div style="font-size:7px; color:#059669; font-weight:bold; margin-top:2px;">{cls_name}{room_str}</div>
                    </td>
                    """
                else:
                    cols_html += '<td style="border:1px solid #94a3b8; padding:4px; text-align:center; font-size:7px; color:#cbd5e1;">&mdash;</td>'

            rows_html += f"<tr>{cols_html}</tr>"

    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: a4 landscape; margin: 0.8cm; }}
            body {{ font-family: Helvetica, Arial, sans-serif; font-size: 8px; color: #0f172a; }}
            .header-table {{ width: 100%; border-bottom: 2px solid #0f172a; padding-bottom: 6px; margin-bottom: 8px; }}
            .grid-table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
            .grid-table th, .grid-table td {{ border: 1px solid #94a3b8; }}
            .grid-table th {{ background: #0369a1; color: #ffffff; font-weight: bold; text-align: center; padding: 6px; font-size: 8.5px; }}
        </style>
    </head>
    <body>
        <table class="header-table">
            <tr>
                <td style="width:70%;">
                    <div style="font-size:7.5px; font-weight:bold; color:#475569; letter-spacing:1px; text-transform:uppercase;">GHANA EDUCATION SERVICE &bull; ACADEMIC TIMETABLE BOARD</div>
                    <div style="font-size:14px; font-weight:900; color:#0f172a; text-transform:uppercase; margin-top:2px;">{school_name}</div>
                    <div style="font-size:10px; font-weight:bold; color:#0369a1; margin-top:2px; text-transform:uppercase;">INSTRUCTOR TEACHING SCHEDULE &bull; {teacher.username.upper()}</div>
                </td>
                <td style="width:30%; text-align:right; vertical-align:top;">
                    <div style="font-size:9.5px; font-weight:bold; color:#0f172a;">TEACHER: {teacher.username}</div>
                    <div style="font-size:7.5px; color:#059669; font-weight:bold;">TOTAL WORKLOAD: {len(slots)} PERIODS / WEEK</div>
                    <div style="font-size:7.5px; color:#64748b;">DATE: {now_str}</div>
                </td>
            </tr>
        </table>

        <table class="grid-table">
            <thead>
                <tr>
                    <th style="width:85px;">Period / Time</th>
                    <th>Monday</th>
                    <th>Tuesday</th>
                    <th>Wednesday</th>
                    <th>Thursday</th>
                    <th>Friday</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>

        <table style="width:100%; margin-top:16px; border:none; font-size:8px;">
            <tr>
                <td style="width:50%; text-align:center;">
                    <div style="border-bottom:1px solid #000; width:140px; margin:0 auto 4px;"></div>
                    <strong>Teacher / Instructor</strong>
                    <div style="font-size:7px; color:#64748b;">Signature &amp; Date</div>
                </td>
                <td style="width:50%; text-align:center;">
                    <div style="border-bottom:1px solid #000; width:140px; margin:0 auto 4px;"></div>
                    <strong>Head of Department / Academic Head</strong>
                    <div style="font-size:7px; color:#64748b;">Official Confirmation</div>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)
    if pisa_status.err:
        raise HTTPException(status_code=500, detail="Failed to compile teacher schedule PDF")

    clean_tname = teacher.username.replace(" ", "_")
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Teacher_Schedule_{clean_tname}.pdf"'}
    )
