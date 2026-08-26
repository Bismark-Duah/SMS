from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Subject, Setting, User, School, Score, Attendance, 
    TeacherAssignment, Timetable, ClassSubjectScoreStatus, TextbookAllocation
)
from ..schemas import SubjectCreate
from ..dependencies import get_current_user, get_school_id

router = APIRouter()


@router.get("/")
def list_subjects(
    school_level: Optional[str] = None,
    exclude_basic: Optional[bool] = False,
    include_inactive: Optional[bool] = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id"),
):
    school_id = get_school_id(current_user, x_school_id)
    query = db.query(Subject)

    if not include_inactive:
        query = query.filter((Subject.is_active == True) | (Subject.is_active.is_(None)))

    # Check active school_mode and active subscribed subjects for the school
    school_mode = None
    has_active_subjects = False
    if school_id is not None:
        sch = db.query(School).filter(School.id == school_id).first()
        if sch:
            if sch.school_mode:
                school_mode = sch.school_mode
            if sch.active_subjects:
                has_active_subjects = True
                active_sub_ids = [s.id for s in sch.active_subjects]
                query = query.filter((Subject.id.in_(active_sub_ids)) | (Subject.school_id == school_id))

    if not has_active_subjects:
        if school_id is not None and hasattr(Subject, "school_id"):
            query = query.filter((Subject.school_id == school_id) | (Subject.school_id.is_(None)) | (Subject.school_id == 1))

    if not school_mode:
        mode_setting = db.query(Setting).filter(Setting.key == "school_mode").first()
        school_mode = mode_setting.value if mode_setting else "COMBINED"

    if school_level:
        query = query.filter(Subject.school_level == school_level)
    elif not has_active_subjects:
        if school_mode == "SHS_ONLY" or exclude_basic:
            query = query.filter(Subject.school_level.in_(["SHS", "STEM"]))
        elif school_mode == "BASIC_ONLY":
            query = query.filter(Subject.school_level == "Basic")

    # ── Role-based scoping ─────────────────────────────────────────────────────
    from ..dependencies import get_user_assigned_scope
    from ..models import Department
    scope = get_user_assigned_scope(current_user, db)
    if not scope["is_admin"]:
        if scope["department_ids"]:
            # User is HOD of a department — show all subjects in their department
            dept_subject_ids = set()
            depts = db.query(Department).filter(Department.id.in_(scope["department_ids"])).all()
            for dept in depts:
                for s in dept.subjects:
                    dept_subject_ids.add(s.id)
            # Also include their personal teaching assignments
            if scope["subject_ids"]:
                dept_subject_ids.update(scope["subject_ids"])
            if dept_subject_ids:
                query = query.filter(Subject.id.in_(dept_subject_ids))
            else:
                return []
        elif scope["subject_ids"]:
            # Regular teachers: only their assigned subjects
            query = query.filter(Subject.id.in_(scope["subject_ids"]))
        else:
            return []

    return query.all()


@router.get("/my-assignments")
def get_my_subjects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from ..dependencies import get_user_assigned_scope
    scope = get_user_assigned_scope(current_user, db)
    if scope["is_admin"]:
        return list_subjects(db=db, current_user=current_user)
    if not scope["subject_ids"]:
        return []
    return db.query(Subject).filter(
        Subject.id.in_(scope["subject_ids"]),
        (Subject.is_active == True) | (Subject.is_active.is_(None))
    ).all()


@router.get("/{subject_id}")
def get_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id"),
):
    school_id = get_school_id(current_user, x_school_id)
    query = db.query(Subject).filter(Subject.id == subject_id)
    if school_id is not None and hasattr(Subject, "school_id"):
        query = query.filter((Subject.school_id == school_id) | (Subject.school_id.is_(None)))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Subject not found")
    return item


def _check_admin(current_user: User):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not hasattr(current_user, 'roles'):
        return
    role_names = [r.name.lower() for r in current_user.roles] if hasattr(current_user, 'roles') and current_user.roles else []
    admin_roles = {
        "admin", "super_admin", "headmaster", "headmistress",
        "assistant_headmaster_academic", "assistant_head_academic",
        "assistant_headmaster_admin", "assistant_head_admin"
    }
    if not any(r in admin_roles for r in role_names):
        raise HTTPException(status_code=403, detail="Only administrators can manage subjects")


@router.post("/")
def create_subject(
    payload: SubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_admin(current_user)
    school_id = get_school_id(current_user)
    data = payload.dict()
    if school_id is not None and hasattr(Subject, "school_id"):
        data["school_id"] = school_id
    if "is_active" not in data or data["is_active"] is None:
        data["is_active"] = True
    db_subject = Subject(**data)
    db.add(db_subject)
    db.commit()
    db.refresh(db_subject)
    return db_subject


@router.post("/{subject_id}/toggle-status")
def toggle_subject_status(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enterprise Soft-Delete / Archiving Toggle.
    Allows administrators to safely archive/discontinue a subject so it does not appear
    in new term entry forms, while preserving all historical scores and transcripts.
    """
    _check_admin(current_user)
    school_id = get_school_id(current_user)
    query = db.query(Subject).filter(Subject.id == subject_id)
    if school_id is not None and hasattr(Subject, "school_id"):
        query = query.filter((Subject.school_id == school_id) | (Subject.school_id.is_(None)))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Subject not found")

    current_status = getattr(item, "is_active", True)
    item.is_active = not (current_status if current_status is not None else True)
    db.commit()
    db.refresh(item)
    status_label = "Active" if item.is_active else "Archived (Discontinued)"
    return {
        "status": "success",
        "id": item.id,
        "is_active": item.is_active,
        "message": f"Subject '{item.name}' is now {status_label}."
    }


@router.delete("/{subject_id}")
def delete_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enterprise Protected Delete.
    Hard deletion is ONLY allowed if 0 historical student grades and records depend on it.
    If historical records exist, hard deletion is blocked to prevent data corruption.
    """
    _check_admin(current_user)
    school_id = get_school_id(current_user)
    query = db.query(Subject).filter(Subject.id == subject_id)
    if school_id is not None and hasattr(Subject, "school_id"):
        query = query.filter((Subject.school_id == school_id) | (Subject.school_id.is_(None)))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Subject not found")

    # ── 1. Check for critical dependent records ───────────────────────────────
    score_count = db.query(Score).filter(Score.subject_id == subject_id).count()
    attendance_count = db.query(Attendance).filter(Attendance.subject_id == subject_id).count()
    textbook_count = db.query(TextbookAllocation).filter(TextbookAllocation.subject_id == subject_id).count()
    score_status_count = db.query(ClassSubjectScoreStatus).filter(ClassSubjectScoreStatus.subject_id == subject_id).count()

    total_critical_dependencies = score_count + attendance_count + textbook_count + score_status_count

    if total_critical_dependencies > 0:
        details = []
        if score_count:
            details.append(f"{score_count} student exam/class score(s)")
        if attendance_count:
            details.append(f"{attendance_count} period attendance record(s)")
        if textbook_count:
            details.append(f"{textbook_count} textbook allocation(s)")
        if score_status_count:
            details.append(f"{score_status_count} term score sheet approval(s)")

        dependencies_text = ", ".join(details)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot permanently delete '{item.name}' because historical records depend on it: "
                f"{dependencies_text}. To prevent data corruption on past report cards and transcripts, "
                f"please 'Archive / Deactivate' this subject instead."
            )
        )

    # ── 2. Safe cleanup of empty non-critical assignments/timetables ──────────
    db.query(Timetable).filter(Timetable.subject_id == subject_id).delete(synchronize_session=False)
    db.query(TeacherAssignment).filter(TeacherAssignment.subject_id == subject_id).delete(synchronize_session=False)

    item.class_sections.clear()
    item.programs.clear()

    db.delete(item)
    db.commit()
    return {"status": "success", "message": f"Subject '{item.name}' was permanently deleted."}


@router.put("/{subject_id}")
def update_subject(
    subject_id: int,
    payload: SubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_admin(current_user)
    school_id = get_school_id(current_user)
    query = db.query(Subject).filter(Subject.id == subject_id)
    if school_id is not None and hasattr(Subject, "school_id"):
        query = query.filter((Subject.school_id == school_id) | (Subject.school_id.is_(None)))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Subject not found")

    item.name = payload.name
    item.code = payload.code
    item.is_core = payload.is_core
    if payload.is_active is not None:
        item.is_active = payload.is_active
    if payload.category is not None:
        item.category = payload.category
    if payload.group_code is not None:
        item.group_code = payload.group_code
    if payload.assessment_type is not None:
        item.assessment_type = payload.assessment_type
    if payload.school_level is not None:
        item.school_level = payload.school_level

    db.commit()
    db.refresh(item)
    return item
