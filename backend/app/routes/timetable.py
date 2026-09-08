import io
import json
from datetime import datetime, time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from xhtml2pdf import pisa

from ..database import get_db
from ..models import (
    Timetable, ClassSection, Subject, User, Semester, Program, School, Setting,
    TimetableConfig, TimetableReliefLog, TimetableSyllabusLog
)
from ..dependencies import get_current_user, get_school_id
from ..services.timetable_generator import TimetableSolver, smart_surgical_swap
from ..services.curriculum_presets import (
    DEFAULT_BREAK_SCHEDULES, DEFAULT_SUBJECT_CONFIGS, ROLE_WORKLOAD_LIMITS
)

router = APIRouter()

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def require_admin(current_user: User):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    roles = [r.name for r in current_user.roles] if current_user.roles else []
    if "admin" not in roles and "super_admin" not in roles:
        raise HTTPException(status_code=403, detail="Admin access required")


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


class PreferencesUpdateSchema(BaseModel):
    start_time: Optional[str] = "08:00"
    period_duration_minutes: Optional[int] = 45
    periods_per_day: Optional[int] = 8
    friday_periods: Optional[int] = 6
    break_schedule: Optional[List[Dict[str, Any]]] = None


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
        "role_workload_limits": ROLE_WORKLOAD_LIMITS
    }


@router.put("/preferences")
def update_timetable_preferences(
    payload: PreferencesUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: update school-specific daily hours, period counts, and break/chapel intervals."""
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

    db.commit()
    db.refresh(config)
    return {"status": "SUCCESS", "message": "Timetable preferences saved successfully."}


@router.post("/auto-generate", status_code=200)
def auto_generate_timetable(
    payload: AutoGenerateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    1-Click Autonomous Constraint Solver:
    Solves and builds the master conflict-free schedule in < 1.5 seconds.
    """
    require_admin(current_user)
    school_id = get_school_id(current_user)
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

    solver = TimetableSolver(
        db=db,
        school_id=school_id,
        semester_id=payload.semester_id,
        school_profile=profile,
        periods_per_day=periods_per_day,
        friday_periods=friday_periods,
        break_schedule=break_sched,
        custom_quotas=payload.custom_quotas or {}
    )

    result = solver.solve()
    return result


@router.get("/teacher-workloads")
def get_teacher_workloads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: view all teachers' assigned period counts vs their legal workload caps."""
    require_admin(current_user)
    school_id = get_school_id(current_user)

    teachers = db.query(User).filter(
        (User.school_id == school_id) | (User.school_id.is_(None))
    ).all()

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

            workloads.append({
                "teacher_id": t.id,
                "teacher_name": t.username,
                "responsibility_role": role,
                "role_title": role_limit["title"],
                "assigned_periods": assigned_count,
                "max_cap": max_cap,
                "is_exempt": is_exempt,
                "utilization_percent": round((assigned_count / max(1, max_cap)) * 100, 1) if not is_exempt else 0
            })

    return workloads


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
):
    """
    📡 Live Campus Radar ("Now Teaching"):
    Returns the currently active period, room occupancy map, and currently free staff.
    """
    school_id = get_school_id(current_user)
    now = datetime.now()
    now_day = now.weekday()  # 0=Mon ... 6=Sun

    # Determine current period from time
    current_hour = now.hour
    current_min = now.minute

    # Simple standard period mapping:
    # 08:00 - 08:45 -> P1, 08:45 - 09:30 -> P2, 09:50 - 10:35 -> P3, 10:35 - 11:20 -> P4,
    # 12:00 - 12:45 -> P5, 12:45 - 01:30 -> P6, 01:30 - 02:15 -> P7, 02:15 - 03:00 -> P8
    current_period = 1
    if current_hour == 8 and current_min < 45:
        current_period = 1
    elif (current_hour == 8 and current_min >= 45) or (current_hour == 9 and current_min < 30):
        current_period = 2
    elif current_hour == 9 and current_min >= 50 or (current_hour == 10 and current_min < 35):
        current_period = 3
    elif (current_hour == 10 and current_min >= 35) or (current_hour == 11 and current_min < 20):
        current_period = 4
    elif current_hour == 12 and current_min < 45:
        current_period = 5
    elif (current_hour == 12 and current_min >= 45) or (current_hour == 13 and current_min < 30):
        current_period = 6
    elif (current_hour == 13 and current_min >= 30) or (current_hour == 14 and current_min < 15):
        current_period = 7
    elif (current_hour == 14 and current_min >= 15) or current_hour >= 15:
        current_period = 8

    # Query all slots for today & current period
    active_slots = db.query(Timetable).options(
        joinedload(Timetable.class_section),
        joinedload(Timetable.subject),
        joinedload(Timetable.teacher)
    ).join(Timetable.class_section).filter(
        (ClassSection.school_id == school_id) | (ClassSection.school_id.is_(None)),
        Timetable.day_of_week == (now_day if now_day <= 4 else 0),
        Timetable.period_number == current_period
    ).all()

    busy_teachers = {s.teacher_id for s in active_slots if s.teacher_id}

    # Find free teachers right now
    all_teachers = db.query(User).filter(
        (User.school_id == school_id) | (User.school_id.is_(None))
    ).all()
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

        start_h = 8 + (s.period_number - 1)
        end_h = 8 + s.period_number

        ics_content += f"BEGIN:VEVENT\r\nSUMMARY:{sub_name} - {cls_name}\r\nDESCRIPTION:Teaching period {s.period_number} for {cls_name} in {room}\r\nLOCATION:{room}\r\nRRULE:FREQ=WEEKLY;BYDAY={day_abbr}\r\nDTSTART:20260901T{start_h:02d}0000\r\nDTEND:20260901T{end_h:02d}0000\r\nBEGIN:VALARM\r\nTRIGGER:-PT10M\r\nACTION:DISPLAY\r\nDESCRIPTION:Reminder: {sub_name} in 10 minutes\r\nEND:VALARM\r\nEND:VEVENT\r\n"

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


# ── PDF Dockets ───────────────────────────────────────────────────────────────

@router.get("/class/{class_section_id}/pdf")
def get_class_timetable_pdf(
    class_section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates and streams an official A4 Landscape Class Weekly Timetable PDF."""
    school_id = get_school_id(current_user)
    cs = db.query(ClassSection).filter(ClassSection.id == class_section_id).first()
    if not cs or not _check_class_school(cs, school_id):
        raise HTTPException(status_code=404, detail="Class section not found")

    slots = db.query(Timetable).filter(Timetable.class_section_id == class_section_id).all()
    slot_map = {(s.day_of_week, s.period_number): s for s in slots}

    school_name_s = db.query(Setting).filter(Setting.key == "school_name").first()
    school_name = school_name_s.value if school_name_s and school_name_s.value else "SENIOR HIGH SCHOOL"
    now_str = datetime.now().strftime("%d %B %Y")

    periods_config = [
        {"period": 1, "time": "08:00 - 08:45"},
        {"period": 2, "time": "08:45 - 09:30"},
        {"is_break": True, "title": "SNACK &amp; BREAKFAST BREAK (09:30 - 09:50)"},
        {"period": 3, "time": "09:50 - 10:35"},
        {"period": 4, "time": "10:35 - 11:20"},
        {"is_break": True, "title": "MID-DAY LUNCH BREAK (11:20 - 12:00)"},
        {"period": 5, "time": "12:00 - 12:45"},
        {"period": 6, "time": "12:45 - 01:30"},
        {"period": 7, "time": "01:30 - 02:15"},
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates and streams an official A4 Landscape Teacher Schedule Docket PDF."""
    teacher = db.query(User).filter(User.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    slots = db.query(Timetable).filter(Timetable.teacher_id == teacher_id).all()
    slot_map = {(s.day_of_week, s.period_number): s for s in slots}

    school_name_s = db.query(Setting).filter(Setting.key == "school_name").first()
    school_name = school_name_s.value if school_name_s and school_name_s.value else "SENIOR HIGH SCHOOL"
    now_str = datetime.now().strftime("%d %B %Y")

    periods_config = [
        {"period": 1, "time": "08:00 - 08:45"},
        {"period": 2, "time": "08:45 - 09:30"},
        {"is_break": True, "title": "SNACK &amp; BREAKFAST BREAK (09:30 - 09:50)"},
        {"period": 3, "time": "09:50 - 10:35"},
        {"period": 4, "time": "10:35 - 11:20"},
        {"is_break": True, "title": "MID-DAY LUNCH BREAK (11:20 - 12:00)"},
        {"period": 5, "time": "12:00 - 12:45"},
        {"period": 6, "time": "12:45 - 01:30"},
        {"period": 7, "time": "01:30 - 02:15"},
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
