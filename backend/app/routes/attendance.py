import io
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel
from xhtml2pdf import pisa

from ..database import get_db
from ..models import (
    Attendance, Notification, Student, MessageLog, User, Subject, TeacherAssignment, ClassSection,
    Setting, School
)
from ..schemas import AttendanceCreate
from ..dependencies import get_current_user, get_school_id, get_user_assigned_scope, get_form_master_class_ids, ATTENDANCE_ADMIN_ROLES
from ..services.communication_service import CommunicationService

router = APIRouter()


class ScanCheckinPayload(BaseModel):
    student_code: str
    scan_type: str = "Morning Roll Call"
    timestamp: Optional[str] = None


class TruancyAlertDispatchPayload(BaseModel):
    date_str: Optional[str] = None
    class_section_id: Optional[int] = None


# ── Helpers ────────────────────────────────────────────────────────────────────


def _parse_date(date_str: str) -> date:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return datetime.now().date()


def _handle_absence_alert(db: Session, student_id: int, target_date: date, status: str, current_user: Optional[User] = None):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return

    date_str = target_date.strftime("%Y-%m-%d")
    msg_pattern = f"%on {date_str}%"

    existing_msg = (
        db.query(MessageLog)
        .filter(
            MessageLog.student_id == student_id,
            MessageLog.message_type == "ABSENCE_ALERT",
            MessageLog.message_body.like(msg_pattern)
        )
        .first()
    )

    if status.lower() == "absent":
        if student.phone and len(student.phone.strip()) >= 7:
            guardian_name = student.guardian_name or (student.parent.username if student.parent else "Parent/Guardian")
            msg_body = f"Dear {guardian_name}, please be informed that your child {student.full_name} was marked ABSENT from school on {date_str}."
            sender_id = current_user.id if current_user else None

            if not existing_msg:
                new_msg = MessageLog(
                    sender_id=sender_id,
                    student_id=student.id,
                    recipient_name=guardian_name,
                    recipient_phone=student.phone,
                    channel="SMS",
                    message_type="ABSENCE_ALERT",
                    message_body=msg_body,
                    status="PENDING"
                )
                db.add(new_msg)
            elif existing_msg.status == "PENDING":
                existing_msg.recipient_name = guardian_name
                existing_msg.recipient_phone = student.phone
                existing_msg.message_body = msg_body
                if sender_id:
                    existing_msg.sender_id = sender_id
    else:
        # Status changed away from Absent -> remove pending alert draft if present
        if existing_msg and existing_msg.status == "PENDING":
            db.delete(existing_msg)


# ── Existing Endpoints ─────────────────────────────────────────────────────────

@router.get("/student/{student_id}")
def get_student_attendance(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all attendance records for a specific student (for heatmap)."""
    school_id = get_school_id(current_user)
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student or (school_id is not None and student.school_id != school_id):
        raise HTTPException(status_code=404, detail="Student not found.")

    records = (
        db.query(Attendance)
        .filter(Attendance.student_id == student_id)
        .order_by(Attendance.date.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "date": str(r.date)[:10],
            "status": r.status,
        }
        for r in records
    ]


@router.get("/")
def list_attendance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(Attendance).join(Attendance.student)
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)

    scope = get_user_assigned_scope(current_user, db)
    if not scope["is_admin"]:
        if scope["class_ids"]:
            query = query.filter(Student.class_section_id.in_(scope["class_ids"]))
        else:
            return []

    return query.all()


@router.post("/")
def create_attendance(
    payload: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user:
        form_class_ids = get_form_master_class_ids(current_user, db)
        if form_class_ids is not None:  # None means admin — no restriction
            student = db.query(Student).filter(Student.id == payload.student_id).first()
            if not student or student.class_section_id not in form_class_ids:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to mark daily attendance. Only the Form Master or an Administrator can mark the class register."
                )

    parsed_date = _parse_date(payload.date)

    # Upsert: if a record already exists for this student+date, overwrite it
    existing = (
        db.query(Attendance)
        .filter(Attendance.student_id == payload.student_id, Attendance.date == parsed_date)
        .first()
    )
    if existing:
        existing.status = payload.status
        _handle_absence_alert(db, payload.student_id, parsed_date, payload.status, current_user)
        db.commit()
        db.refresh(existing)
        return existing

    record = Attendance(student_id=payload.student_id, date=parsed_date, status=payload.status)
    db.add(record)

    if payload.status.lower() == "absent":
        notif = Notification(
            student_id=payload.student_id,
            message=f"Student was marked Absent on {parsed_date.strftime('%Y-%m-%d')}.",
            type="Attendance",
        )
        db.add(notif)

    _handle_absence_alert(db, payload.student_id, parsed_date, payload.status, current_user)

    db.commit()
    db.refresh(record)
    return record


# ── New Endpoints ──────────────────────────────────────────────────────────────

@router.post("/bulk")
def bulk_create_attendance(
    records: List[AttendanceCreate],
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Bulk-mark daily attendance for a list of students (Form Master / Admin only).
    If a record already exists for student+date, it is overwritten (upsert).
    """
    if current_user and records:
        form_class_ids = get_form_master_class_ids(current_user, db)
        if form_class_ids is not None:  # None means admin — no restriction
            first_student = db.query(Student).filter(Student.id == records[0].student_id).first()
            if not first_student or first_student.class_section_id not in form_class_ids:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to mark daily attendance. Only the Form Master or an Administrator can mark the class register."
                )

    saved = []
    for payload in records:
        parsed_date = _parse_date(payload.date)

        existing = (
            db.query(Attendance)
            .filter(Attendance.student_id == payload.student_id, Attendance.date == parsed_date)
            .first()
        )
        if existing:
            existing.status = payload.status
            _handle_absence_alert(db, payload.student_id, parsed_date, payload.status, current_user)
            saved.append(existing)
        else:
            record = Attendance(student_id=payload.student_id, date=parsed_date, status=payload.status)
            db.add(record)
            saved.append(record)

            if payload.status.lower() == "absent":
                db.add(
                    Notification(
                        student_id=payload.student_id,
                        message=f"Student was marked Absent on {parsed_date.strftime('%Y-%m-%d')}.",
                        type="Attendance",
                    )
                )

            _handle_absence_alert(db, payload.student_id, parsed_date, payload.status, current_user)

    db.commit()
    return {"saved": len(saved), "message": "Bulk attendance saved successfully."}


@router.get("/class/{class_id}")
def get_class_attendance(
    class_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all attendance records for a class section, joined with student names.
    Optional filters: date_from, date_to (YYYY-MM-DD), status.
    """
    school_id = get_school_id(current_user)
    query = (
        db.query(Attendance)
        .join(Student, Attendance.student_id == Student.id)
        .filter(Student.class_section_id == class_id)
    )
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)

    if date_from:
        query = query.filter(Attendance.date >= _parse_date(date_from))
    if date_to:
        query = query.filter(Attendance.date <= _parse_date(date_to))
    if status:
        query = query.filter(Attendance.status == status)

    records = query.order_by(Attendance.date.desc()).all()

    return [
        {
            "id": r.id,
            "student_id": r.student_id,
            "student_name": r.student.full_name if r.student else f"Student {r.student_id}",
            "student_code": r.student.student_code if r.student else "",
            "date": str(r.date)[:10],
            "status": r.status,
        }
        for r in records
    ]


@router.delete("/{record_id}")
def delete_attendance(record_id: int, db: Session = Depends(get_db)):
    """Delete a single attendance record by ID."""
    record = db.query(Attendance).filter(Attendance.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found.")
    db.delete(record)
    db.commit()
    return {"message": "Attendance record deleted."}


@router.get("/my-subject-assignments")
def get_my_subject_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the list of class-section + subject pairs assigned to the current teacher.
    Used to populate the Period Absence Log panel dropdowns.
    """
    school_id = get_school_id(current_user)
    role_names = [r.name.lower() for r in current_user.roles] if hasattr(current_user, "roles") and current_user.roles else []

    # Admins get all classes
    if any(r in ATTENDANCE_ADMIN_ROLES for r in role_names):
        sections = db.query(ClassSection)
        if school_id:
            sections = sections.filter(ClassSection.school_id == school_id)
        return [
            {"class_section_id": s.id, "class_name": s.name, "subject_id": None, "subject_name": "All Subjects"}
            for s in sections.all()
        ]

    assignments = (
        db.query(TeacherAssignment)
        .filter(TeacherAssignment.teacher_id == current_user.id)
        .all()
    )
    return [
        {
            "class_section_id": a.class_section_id,
            "class_name": a.class_section.name if a.class_section else f"Class {a.class_section_id}",
            "subject_id": a.subject_id,
            "subject_name": a.subject.name if a.subject else f"Subject {a.subject_id}",
        }
        for a in assignments
    ]


class PeriodAbsencePayload(object):
    pass

from pydantic import BaseModel

class PeriodAbsencePayload(BaseModel):
    class_section_id: int
    subject_id: int
    date: str
    period_label: Optional[str] = None  # e.g. "Period 3 – 11:30 AM"
    absent_student_ids: List[int]


@router.post("/period-absence")
def log_period_absence(
    payload: PeriodAbsencePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Subject Teachers log students absent from their specific lesson/period.
    Only students who were ABSENT are submitted — all others are assumed present.
    Records are saved with attendance_type='period'.
    Automatically notifies the Form Master of the class section.
    """
    # Verify teacher is assigned to this class+subject
    role_names = [r.name.lower() for r in current_user.roles] if hasattr(current_user, "roles") and current_user.roles else []
    is_admin = any(r in ATTENDANCE_ADMIN_ROLES for r in role_names)

    if not is_admin:
        assignment = db.query(TeacherAssignment).filter(
            TeacherAssignment.teacher_id == current_user.id,
            TeacherAssignment.class_section_id == payload.class_section_id,
            TeacherAssignment.subject_id == payload.subject_id,
        ).first()
        if not assignment:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to log period absences for this class/subject combination."
            )

    parsed_date = _parse_date(payload.date)
    subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    class_section = db.query(ClassSection).filter(ClassSection.id == payload.class_section_id).first()

    saved_count = 0
    for student_id in payload.absent_student_ids:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            continue

        # Upsert period record for this student+date+subject
        existing = db.query(Attendance).filter(
            Attendance.student_id == student_id,
            Attendance.date == parsed_date,
            Attendance.attendance_type == "period",
            Attendance.subject_id == payload.subject_id,
        ).first()

        if existing:
            existing.status = "Absent"
            existing.period_label = payload.period_label
            existing.logged_by_id = current_user.id
        else:
            record = Attendance(
                student_id=student_id,
                date=parsed_date,
                status="Absent",
                attendance_type="period",
                subject_id=payload.subject_id,
                period_label=payload.period_label,
                logged_by_id=current_user.id,
            )
            db.add(record)
        saved_count += 1

    # Notify Form Master of the class
    if class_section and class_section.form_master_id and saved_count > 0:
        subject_name = subject.name if subject else f"Subject {payload.subject_id}"
        class_name = class_section.name
        teacher_name = current_user.username
        period_info = f" during {payload.period_label}" if payload.period_label else ""
        notif_msg = (
            f"⚠️ Period Absence Alert: {saved_count} student(s) were absent from "
            f"{subject_name} class in {class_name}{period_info} on {str(parsed_date)}. "
            f"Logged by {teacher_name}."
        )
        # Find a student in this class to attach the notification to (use first absentee)
        if payload.absent_student_ids:
            notif = Notification(
                student_id=payload.absent_student_ids[0],
                message=notif_msg,
                type="Period Absence",
            )
            db.add(notif)

    db.commit()
    return {
        "saved": saved_count,
        "message": f"Period absence log saved. {saved_count} student(s) marked absent."
    }


from ..models import Attendance, Notification, Student, Setting, SchoolStage, ClassSection

def _get_school_mode(db: Session) -> str:
    setting = db.query(Setting).filter(Setting.key == "school_mode").first()
    return setting.value if setting and setting.value else "COMBINED"

@router.get("/today-stats")
def get_today_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns today's attendance breakdown: present, absent, late, total, percentage.
    """
    today = datetime.now().date()
    mode = _get_school_mode(db)
    school_id = get_school_id(current_user)
    
    student_query = db.query(Student).filter(Student.is_active == True)
    attendance_query = db.query(Attendance).filter(Attendance.date == today)

    if school_id is not None:
        student_query = student_query.filter(Student.school_id == school_id)
        attendance_query = attendance_query.join(Attendance.student).filter(Student.school_id == school_id)

    if mode == "BASIC_ONLY":
        student_query = student_query.join(Student.class_section).join(ClassSection.stage).filter(SchoolStage.school_type == "Basic")
        attendance_query = attendance_query.join(Attendance.student).join(Student.class_section).join(ClassSection.stage).filter(SchoolStage.school_type == "Basic")
    elif mode == "SHS_ONLY":
        student_query = student_query.join(Student.class_section).join(ClassSection.stage).filter(SchoolStage.school_type == "SHS")
        attendance_query = attendance_query.join(Attendance.student).join(Student.class_section).join(ClassSection.stage).filter(SchoolStage.school_type == "SHS")

    total_students = student_query.count()
    records = attendance_query.all()
    total_marked = len(records)
    present = sum(1 for r in records if r.status == "Present")
    absent = sum(1 for r in records if r.status == "Absent")
    late = sum(1 for r in records if r.status == "Late")
    excused = sum(1 for r in records if r.status == "Excused")

    percentage = round((present / total_marked) * 100, 1) if total_marked > 0 else 0.0

    return {
        "date": str(today),
        "total_students": total_students,
        "total_marked": total_marked,
        "present": present,
        "absent": absent,
        "late": late,
        "excused": excused,
        "attendance_percentage": percentage,
    }


@router.get("/analytics")
def get_attendance_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns attendance statistics per student — now includes student name.
    """
    from sqlalchemy import func, Integer

    school_id = get_school_id(current_user)
    query = (
        db.query(
            Attendance.student_id,
            func.count(Attendance.id).label("total_days"),
            func.sum(func.cast(Attendance.status == "Present", Integer)).label("present_days"),
        )
        .join(Attendance.student)
    )
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)

    stats = query.group_by(Attendance.student_id).all()

    results = []
    for s in stats:
        total = s.total_days or 1
        present = s.present_days or 0
        percentage = (present / total) * 100
        student = db.query(Student).filter(Student.id == s.student_id).first()
        results.append(
            {
                "student_id": s.student_id,
                "student_name": student.full_name if student else f"Student {s.student_id}",
                "total_days": total,
                "present_days": present,
                "percentage": round(percentage, 2),
            }
        )

    return results


@router.get("/reconciliation-audit")
def get_reconciliation_audit(
    date_str: Optional[str] = Query(None),
    house_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reconciles Morning Classroom Attendance vs Evening House Roll Call vs Exeat Records.
    Flags Day Truancy, Night Absences, and Unapproved Exeat Discrepancies.
    """
    from ..models import ExeatRecord, House, ClassSection
    
    target_date = _parse_date(date_str) if date_str else datetime.now().date()
    school_id = get_school_id(current_user)

    # Fetch active boarders
    query = db.query(Student).filter(Student.is_active == True)
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)
    if house_id:
        query = query.filter(Student.house_id == house_id)
    else:
        query = query.filter(
            (Student.house_id.isnot(None)) |
            (Student.residential_status.ilike("%boarding%"))
        )

    boarders = query.all()

    # Active exeats covering date
    active_exeats = db.query(ExeatRecord).filter(
        ExeatRecord.status.in_(["Departed", "Away", "APPROVED"])
    ).all()
    exeat_student_ids = {e.student_id for e in active_exeats}

    discrepancies = []
    day_truancy_count = 0
    night_absence_count = 0
    unexcused_house_absence_count = 0
    reconciled_clean_count = 0

    for s in boarders:
        records = db.query(Attendance).filter(
            Attendance.student_id == s.id,
            Attendance.date == target_date
        ).all()

        class_rec = None
        house_rec = None
        for r in records:
            if r.remarks and "[House Roll]" in r.remarks:
                house_rec = r
            else:
                class_rec = r

        c_status = class_rec.status if class_rec else "NOT_MARKED"
        h_remarks = house_rec.remarks if house_rec else ""
        h_status = "NOT_MARKED"
        if house_rec:
            if "Present in Dorm" in h_remarks or house_rec.status == "Present":
                h_status = "Present in Dorm"
            elif "Away on Exeat" in h_remarks:
                h_status = "Away on Exeat"
            elif "Sickbay" in h_remarks:
                h_status = "Sickbay"
            elif "Absent" in h_remarks or house_rec.status == "Absent":
                h_status = "Absent / Unaccounted"

        has_exeat = s.id in exeat_student_ids

        disc_type = "OK"
        disc_label = "Reconciled"

        # Rule 1: Day Truancy (Present in Dorm at night, but Absent in Class in morning)
        if h_status == "Present in Dorm" and c_status == "Absent" and not has_exeat:
            disc_type = "DAY_TRUANCY"
            disc_label = "🚨 DAY TRUANCY (Present at Night, Skipped Class Morning)"
            day_truancy_count += 1

        # Rule 2: Night Absence (Present in Class in morning, but Absent in Dorm at night without exeat)
        elif c_status in ["Present", "Late"] and h_status == "Absent / Unaccounted" and not has_exeat:
            disc_type = "NIGHT_ABSENCE"
            disc_label = "🚨 NIGHT ABSENCE (Present Morning, Missing from Dorm Night)"
            night_absence_count += 1

        # Rule 3: Unapproved House Absence
        elif h_status == "Absent / Unaccounted" and not has_exeat:
            disc_type = "UNEXCUSED_HOUSE_ABSENCE"
            disc_label = "✈️ UNAPPROVED ABSENCE (Missing from Dorm, No Exeat File)"
            unexcused_house_absence_count += 1
        else:
            reconciled_clean_count += 1

        if disc_type != "OK":
            house_obj = db.query(House).filter(House.id == s.house_id).first() if s.house_id else None
            class_obj = db.query(ClassSection).filter(ClassSection.id == s.class_section_id).first() if s.class_section_id else None

            discrepancies.append({
                "student_id": s.id,
                "student_code": s.student_code or str(s.id),
                "student_name": s.full_name,
                "house_name": house_obj.name if house_obj else "Unassigned",
                "class_name": class_obj.name if class_obj else "Unassigned",
                "class_status": c_status,
                "house_status": h_status,
                "has_active_exeat": has_exeat,
                "discrepancy_type": disc_type,
                "discrepancy_label": disc_label
            })

    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "total_audited": len(boarders),
        "day_truancy_count": day_truancy_count,
        "night_absence_count": night_absence_count,
        "unexcused_house_absence_count": unexcused_house_absence_count,
        "reconciled_clean_count": reconciled_clean_count,
        "discrepancies": discrepancies
    }


@router.post("/scan-checkin")
def scan_checkin_student(
    payload: ScanCheckinPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Rapid Barcode / QR Scanner Check-in Endpoint.
    Instantly verifies student identity, calculates lateness vs cutoff time,
    updates attendance ledger, and returns audio-visual cue metrics.
    """
    school_id = get_school_id(current_user)
    raw_code = payload.student_code.strip()
    if not raw_code:
        raise HTTPException(status_code=400, detail="Student code cannot be empty")

    query = db.query(Student).filter(
        or_(
            Student.student_code == raw_code,
            Student.student_code == raw_code.upper(),
            Student.bece_index_number == raw_code,
            Student.enrolment_code == raw_code
        )
    )
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)

    student = query.first()
    if not student:
        raise HTTPException(status_code=404, detail=f"No student found with ID/Barcode '{raw_code}'")

    now = datetime.now()
    today = now.date()
    time_str = now.strftime("%I:%M %p")
    today_str = today.strftime("%Y-%m-%d")

    # Read cutoff time from setting or default to 08:00
    cutoff_setting = db.query(Setting).filter(Setting.key == "morning_attendance_cutoff").first()
    cutoff_str = cutoff_setting.value if cutoff_setting and cutoff_setting.value else "08:00"

    status = "Present"
    try:
        c_parts = cutoff_str.split(":")
        cutoff_dt = now.replace(hour=int(c_parts[0]), minute=int(c_parts[1]), second=0, microsecond=0)
        if now > cutoff_dt and "Morning" in payload.scan_type:
            status = "Late"
    except Exception:
        pass

    # Check if attendance record exists for today
    att = db.query(Attendance).filter(
        Attendance.student_id == student.id,
        Attendance.date == today
    ).first()

    is_duplicate = False
    if att:
        if att.status in ["Present", "Late"]:
            is_duplicate = True
        att.status = status
        att.period_label = f"Scanned at {time_str} [{payload.scan_type}]"
    else:
        att = Attendance(
            student_id=student.id,
            date=today,
            status=status,
            attendance_type="daily",
            period_label=f"Scanned at {time_str} [{payload.scan_type}]"
        )
        db.add(att)

    db.commit()

    audio_cue = "already_scanned" if is_duplicate else ("late" if status == "Late" else "success")
    class_name = student.class_section.name if student.class_section else "Unassigned"
    house_name = student.house.name if student.house else "Day Student"

    return {
        "success": True,
        "is_duplicate": is_duplicate,
        "audio_cue": audio_cue,
        "student_id": student.id,
        "student_code": student.student_code,
        "full_name": student.full_name,
        "class_name": class_name,
        "house_name": house_name,
        "residential_status": student.residential_status or "Day",
        "status": status,
        "scan_type": payload.scan_type,
        "timestamp_str": time_str,
        "date_str": today_str,
        "message": f"{student.full_name} ({student.student_code}) verified as {status.upper()} [{payload.scan_type} at {time_str}]"
    }


@router.post("/dispatch-truancy-alerts")
def dispatch_truancy_alerts(
    payload: TruancyAlertDispatchPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Scans unexcused absences for a target date and dispatches personalized Hubtel SMS alerts to parents.
    """
    school_id = get_school_id(current_user)
    target_date = _parse_date(payload.date_str) if payload.date_str else datetime.now().date()

    query = db.query(Attendance).join(Student).filter(
        Attendance.date == target_date,
        Attendance.status == "Absent"
    )
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)
    if payload.class_section_id:
        query = query.filter(Student.class_section_id == payload.class_section_id)

    absent_records = query.all()
    dispatched_count = 0
    date_formatted = target_date.strftime("%d %b %Y")

    for att in absent_records:
        st = att.student
        if not st or not st.phone:
            continue

        guardian_name = st.guardian_name or (st.parent.username if st.parent else "Parent/Guardian")
        msg = f"Attendance Alert: Dear {guardian_name}, your ward {st.full_name} was marked ABSENT from school on {date_formatted}. Please contact school administration if this is an error."

        CommunicationService.send_sms(
            db=db,
            to_phone=st.phone,
            message=msg,
            student_id=st.id,
            recipient_name=guardian_name,
            message_type="ABSENCE_ALERT"
        )
        dispatched_count += 1

    return {
        "success": True,
        "date": target_date.strftime("%Y-%m-%d"),
        "dispatched_count": dispatched_count,
        "message": f"Successfully queued/dispatched {dispatched_count} absence SMS notification(s)."
    }


@router.get("/ledger-pdf/{class_section_id}")
def get_attendance_ledger_pdf(
    class_section_id: int,
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generates and returns an official GES Attendance Register PDF Ledger.
    """
    school_id = get_school_id(current_user)
    cs = db.query(ClassSection).filter(ClassSection.id == class_section_id).first()
    if not cs or (school_id is not None and hasattr(cs, "school_id") and cs.school_id and cs.school_id != school_id):
        raise HTTPException(status_code=404, detail="Class section not found")

    now = datetime.now()
    target_month = month or now.month
    target_year = year or now.year

    # Query students in class
    students = db.query(Student).filter(
        Student.class_section_id == cs.id,
        Student.is_active == True
    ).order_by(Student.full_name).all()

    if not students:
        raise HTTPException(status_code=404, detail="No active students found in this class section")

    # Get attendance totals for this month/year
    student_stats = []
    class_present_total = 0
    class_records_total = 0
    chronic_absent_count = 0
    perfect_count = 0

    for idx, st in enumerate(students):
        records = db.query(Attendance).filter(
            Attendance.student_id == st.id,
            func.extract('year', Attendance.date) == target_year,
            func.extract('month', Attendance.date) == target_month
        ).all()

        present_cnt = sum(1 for r in records if r.status in ["Present", "Late"])
        absent_cnt = sum(1 for r in records if r.status == "Absent")
        late_cnt = sum(1 for r in records if r.status == "Late")
        total_days = len(records)

        rate = round((present_cnt / total_days * 100), 1) if total_days > 0 else 100.0
        if rate == 100.0 and total_days > 0:
            perfect_count += 1
        elif rate < 80.0 and total_days > 0:
            chronic_absent_count += 1

        class_present_total += present_cnt
        class_records_total += total_days

        student_stats.append({
            "index": idx + 1,
            "code": st.student_code,
            "name": st.full_name,
            "gender": st.gender or "-",
            "present": present_cnt,
            "absent": absent_cnt,
            "late": late_cnt,
            "total": total_days,
            "rate": rate
        })

    overall_rate = round((class_present_total / class_records_total * 100), 1) if class_records_total > 0 else 100.0

    school_name_setting = db.query(Setting).filter(Setting.key == "school_name").first()
    school_name = school_name_setting.value if school_name_setting and school_name_setting.value else "SENIOR HIGH SCHOOL"
    month_name = datetime(target_year, target_month, 1).strftime("%B %Y")

    # HTML compilation
    rows_html = ""
    for s in student_stats:
        status_color = "#059669" if s["rate"] >= 90 else ("#d97706" if s["rate"] >= 80 else "#dc2626")
        rows_html += f"""
        <tr>
            <td style="text-align:center;">{s['index']}</td>
            <td style="font-family:monospace; font-size:8px;">{s['code']}</td>
            <td style="text-align:left; font-weight:bold;">{s['name']}</td>
            <td style="text-align:center;">{s['gender']}</td>
            <td style="text-align:center; font-weight:bold; color:#059669;">{s['present']}</td>
            <td style="text-align:center; font-weight:bold; color:#dc2626;">{s['absent']}</td>
            <td style="text-align:center; color:#d97706;">{s['late']}</td>
            <td style="text-align:center;">{s['total']}</td>
            <td style="text-align:right; font-weight:bold; color:{status_color};">{s['rate']}%</td>
        </tr>
        """

    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: a4 portrait; margin: 0.8cm; }}
            body {{ font-family: Helvetica, Arial, sans-serif; font-size: 8.5px; color: #0f172a; }}
            .header-table {{ width: 100%; border-bottom: 2px solid #0f172a; padding-bottom: 6px; margin-bottom: 8px; }}
            .matrix-table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
            .matrix-table th, .matrix-table td {{ border: 1px solid #94a3b8; padding: 4px 6px; }}
            .matrix-table th {{ background: #f1f5f9; font-weight: bold; text-align: center; }}
            .kpi-table {{ width: 100%; margin-top: 8px; margin-bottom: 8px; }}
            .kpi-box {{ background: #f8fafc; border: 1px solid #cbd5e1; padding: 6px; text-align: center; }}
        </style>
    </head>
    <body>
        <table class="header-table">
            <tr>
                <td style="width:70%;">
                    <div style="font-size:14px; font-weight:bold; text-transform:uppercase;">{school_name}</div>
                    <div style="font-size:9px; color:#475569;">Official Monthly Attendance Register &amp; Truancy Audit Ledger</div>
                </td>
                <td style="width:30%; text-align:right; vertical-align:top;">
                    <div style="font-size:10px; font-weight:bold; color:#0369a1;">Class: {cs.name}</div>
                    <div style="font-size:8.5px; color:#64748b;">Month: {month_name}</div>
                </td>
            </tr>
        </table>

        <table class="kpi-table">
            <tr>
                <td class="kpi-box" style="width:25%;">
                    <div style="font-size:7.5px; color:#64748b;">Total Students</div>
                    <div style="font-size:12px; font-weight:bold; color:#0f172a;">{len(students)}</div>
                </td>
                <td class="kpi-box" style="width:25%;">
                    <div style="font-size:7.5px; color:#64748b;">Overall Attendance Rate</div>
                    <div style="font-size:12px; font-weight:bold; color:#059669;">{overall_rate}%</div>
                </td>
                <td class="kpi-box" style="width:25%;">
                    <div style="font-size:7.5px; color:#64748b;">100% Perfect Attendance</div>
                    <div style="font-size:12px; font-weight:bold; color:#0284c7;">{perfect_count}</div>
                </td>
                <td class="kpi-box" style="width:25%;">
                    <div style="font-size:7.5px; color:#64748b;">Chronic Absenteeism (&lt;80%)</div>
                    <div style="font-size:12px; font-weight:bold; color:#dc2626;">{chronic_absent_count}</div>
                </td>
            </tr>
        </table>

        <table class="matrix-table">
            <thead>
                <tr>
                    <th style="width:20px;">#</th>
                    <th style="width:65px;">Student ID</th>
                    <th style="text-align:left;">Full Name</th>
                    <th style="width:30px;">Sex</th>
                    <th style="width:45px;">Present</th>
                    <th style="width:45px;">Absent</th>
                    <th style="width:40px;">Late</th>
                    <th style="width:40px;">Total</th>
                    <th style="width:50px; text-align:right;">Rate (%)</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>

        <table style="width:100%; margin-top:20px; border:none; font-size:8.5px;">
            <tr>
                <td style="width:33%; text-align:center;">
                    <div style="border-bottom:1px solid #000; width:130px; margin:0 auto 4px;"></div>
                    <strong>Form Master / Mistress</strong>
                </td>
                <td style="width:33%; text-align:center;">
                    <div style="border-bottom:1px solid #000; width:130px; margin:0 auto 4px;"></div>
                    <strong>Senior Housemaster / Mistress</strong>
                </td>
                <td style="width:34%; text-align:center;">
                    <div style="border-bottom:1px solid #000; width:130px; margin:0 auto 4px;"></div>
                    <strong>Headmaster / Principal</strong>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)
    if pisa_status.err:
        raise HTTPException(status_code=500, detail="Failed to compile attendance ledger PDF")

    clean_cls_name = (cs.name or f"Class_{class_section_id}").replace(" ", "_")
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Attendance_Register_{clean_cls_name}_{target_month}_{target_year}.pdf"'
        }
    )

