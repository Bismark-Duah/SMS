from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Subject, Setting, User, School
from ..schemas import SubjectCreate
from ..dependencies import get_current_user, get_school_id

router = APIRouter()


@router.get("/")
def list_subjects(
    school_level: Optional[str] = None,
    exclude_basic: Optional[bool] = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id"),
):
    school_id = get_school_id(current_user, x_school_id)
    query = db.query(Subject)
    if school_id is not None and hasattr(Subject, "school_id"):
        query = query.filter((Subject.school_id == school_id) | (Subject.school_id.is_(None)))
    
    # Check active school_mode for the school or system default
    school_mode = None
    if school_id is not None:
        sch = db.query(School).filter(School.id == school_id).first()
        if sch and sch.school_mode:
            school_mode = sch.school_mode
    if not school_mode:
        mode_setting = db.query(Setting).filter(Setting.key == "school_mode").first()
        school_mode = mode_setting.value if mode_setting else "COMBINED"

    if school_level:
        query = query.filter(Subject.school_level == school_level)
    elif school_mode == "SHS_ONLY" or exclude_basic:
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
    return db.query(Subject).filter(Subject.id.in_(scope["subject_ids"])).all()



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
    db_subject = Subject(**data)
    db.add(db_subject)
    db.commit()
    db.refresh(db_subject)
    return db_subject


@router.delete("/{subject_id}")
def delete_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_admin(current_user)
    school_id = get_school_id(current_user)
    query = db.query(Subject).filter(Subject.id == subject_id)
    if school_id is not None:
        query = query.filter(Subject.school_id == school_id)
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Subject not found")
    db.delete(item)
    db.commit()
    return {"message": "Subject deleted"}


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
    if school_id is not None:
        query = query.filter(Subject.school_id == school_id)
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Subject not found")

    item.name = payload.name
    item.code = payload.code
    item.is_core = payload.is_core
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
