from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import Department, Subject, User
from ..schemas import DepartmentCreate, DepartmentResponse
from ..dependencies import get_current_user, get_school_id

router = APIRouter()

def _check_admin(current_user: User):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    role_names = [r.name for r in current_user.roles]
    if "admin" not in role_names and "super_admin" not in role_names:
        raise HTTPException(status_code=403, detail="Only administrators can manage departments")

@router.get("/", response_model=List[DepartmentResponse])
def list_departments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from ..dependencies import get_user_assigned_scope
    school_id = get_school_id(current_user)
    query = db.query(Department)
    if school_id is not None:
        query = query.filter(Department.school_id == school_id)

    # ── Role-based scoping ─────────────────────────────────────────────────────
    scope = get_user_assigned_scope(current_user, db)
    if not scope["is_admin"]:
        if scope["department_ids"]:
            # User is HOD of one or more departments — show only those
            query = query.filter(Department.id.in_(scope["department_ids"]))
        else:
            # No department assignment — no access
            return []

    school_mode = None
    if school_id is not None:
        from ..models import School, Setting
        sch = db.query(School).filter(School.id == school_id).first()
        if sch and sch.school_mode:
            school_mode = sch.school_mode
    if not school_mode:
        from ..models import Setting
        mode_setting = db.query(Setting).filter(Setting.key == "school_mode").first()
        school_mode = mode_setting.value if mode_setting else "COMBINED"

    if school_mode == "BASIC_ONLY":
        return []

    departments = query.all()
    results = []
    for d in departments:
        hod_name = d.hod.username if d.hod else None
        
        filtered_subjects = d.subjects
        if school_mode == "SHS_ONLY":
            filtered_subjects = [s for s in d.subjects if s.school_level in ["SHS", "STEM"]]
        elif school_mode == "BASIC_ONLY":
            filtered_subjects = [s for s in d.subjects if s.school_level == "Basic"]

        subject_ids = [s.id for s in filtered_subjects]
        subject_names = [s.name for s in filtered_subjects]
        
        # Collect department teachers from department_id and TeacherAssignments
        from ..models import TeacherAssignment
        dept_sub_ids = set(subject_ids)
        assigned_teachers = db.query(User).join(TeacherAssignment, TeacherAssignment.teacher_id == User.id)\
            .filter(TeacherAssignment.subject_id.in_(dept_sub_ids)).all() if dept_sub_ids else []
        
        direct_teachers = db.query(User).filter(User.department_id == d.id).all()
        
        all_dept_teachers_dict = {t.id: t for t in (direct_teachers + assigned_teachers)}
        dept_teachers = list(all_dept_teachers_dict.values())
        
        teacher_names = [getattr(t, 'full_name', None) or t.username for t in dept_teachers]
        teachers = []
        for t in dept_teachers:
            t_name = getattr(t, 'full_name', None) or t.username
            # Calculate teacher workload inside this department
            t_assignments = db.query(TeacherAssignment).filter(
                TeacherAssignment.teacher_id == t.id,
                TeacherAssignment.subject_id.in_(dept_sub_ids)
            ).all() if dept_sub_ids else []
            
            t_sub_names = list({a.subject.name for a in t_assignments if a.subject})
            t_cls_names = list({a.class_section.name for a in t_assignments if a.class_section})
            cls_count = len(t_cls_names)
            sub_count = len(t_sub_names)
            
            workload_status = "UNASSIGNED"
            if cls_count >= 6:
                workload_status = "HEAVY"
            elif cls_count >= 3:
                workload_status = "BALANCED"
            elif cls_count >= 1:
                workload_status = "LIGHT"

            teachers.append({
                "id": t.id,
                "username": t.username,
                "full_name": t_name,
                "email": t.email or "",
                "assigned_subjects": t_sub_names,
                "assigned_classes": t_cls_names,
                "class_count": cls_count,
                "subject_count": sub_count,
                "workload_status": workload_status
            })
        
        results.append(
            DepartmentResponse(
                id=d.id,
                name=d.name,
                code=d.code,
                hod_id=d.hod_id,
                hod_name=hod_name,
                subject_ids=subject_ids,
                subject_names=subject_names,
                teacher_count=len(dept_teachers),
                teacher_names=teacher_names,
                teachers=teachers
            )
        )
    return results

from ..models import Department, Subject, User, Role

def _ensure_hod_role(db: Session, user_id: int):
    if not user_id:
        return
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        role = db.query(Role).filter(Role.name == "hod").first()
        if not role:
            role = Role(name="hod")
            db.add(role)
            db.flush()
        if role not in user.roles:
            user.roles.append(role)

@router.post("/", response_model=DepartmentResponse)
def create_department(
    payload: DepartmentCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    _check_admin(current_user)

    # Check unique constraints
    if db.query(Department).filter(Department.name == payload.name).first():
        raise HTTPException(status_code=400, detail="Department name already exists")
    if db.query(Department).filter(Department.code == payload.code).first():
        raise HTTPException(status_code=400, detail="Department code already exists")

    # Verify HOD exists and is teacher/admin
    if payload.hod_id:
        hod = db.query(User).filter(User.id == payload.hod_id).first()
        if not hod:
            raise HTTPException(status_code=404, detail="HOD user not found")

    # Load subjects
    subjects = []
    if payload.subject_ids:
        subjects = db.query(Subject).filter(Subject.id.in_(payload.subject_ids)).all()

    school_id = get_school_id(current_user)
    db_dept = Department(
        name=payload.name,
        code=payload.code,
        hod_id=payload.hod_id,
        subjects=subjects,
        school_id=school_id,
    )
    db.add(db_dept)
    if payload.hod_id:
        _ensure_hod_role(db, payload.hod_id)

    db.commit()
    db.refresh(db_dept)

    hod_name = db_dept.hod.username if db_dept.hod else None
    return DepartmentResponse(
        id=db_dept.id,
        name=db_dept.name,
        code=db_dept.code,
        hod_id=db_dept.hod_id,
        hod_name=hod_name,
        subject_ids=[s.id for s in db_dept.subjects],
        subject_names=[s.name for s in db_dept.subjects]
    )

@router.put("/{id}", response_model=DepartmentResponse)
def update_department(
    id: int,
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_admin(current_user)
    school_id = get_school_id(current_user)
    query = db.query(Department).filter(Department.id == id)
    if school_id is not None:
        query = query.filter(Department.school_id == school_id)
    db_dept = query.first()
    if not db_dept:
        raise HTTPException(status_code=404, detail="Department not found")

    # Check unique constraints
    dup_name = db.query(Department).filter(Department.name == payload.name, Department.id != id).first()
    if dup_name:
        raise HTTPException(status_code=400, detail="Department name already exists")
    dup_code = db.query(Department).filter(Department.code == payload.code, Department.id != id).first()
    if dup_code:
        raise HTTPException(status_code=400, detail="Department code already exists")

    # Verify HOD
    if payload.hod_id:
        hod = db.query(User).filter(User.id == payload.hod_id).first()
        if not hod:
            raise HTTPException(status_code=404, detail="HOD user not found")

    # Load subjects
    subjects = []
    if payload.subject_ids:
        subjects = db.query(Subject).filter(Subject.id.in_(payload.subject_ids)).all()

    db_dept.name = payload.name
    db_dept.code = payload.code
    db_dept.hod_id = payload.hod_id
    db_dept.subjects = subjects

    if payload.hod_id:
        _ensure_hod_role(db, payload.hod_id)

    db.commit()
    db.refresh(db_dept)

    hod_name = db_dept.hod.username if db_dept.hod else None
    return DepartmentResponse(
        id=db_dept.id,
        name=db_dept.name,
        code=db_dept.code,
        hod_id=db_dept.hod_id,
        hod_name=hod_name,
        subject_ids=[s.id for s in db_dept.subjects],
        subject_names=[s.name for s in db_dept.subjects]
    )

@router.delete("/{id}")
def delete_department(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_admin(current_user)

    db_dept = db.query(Department).filter(Department.id == id).first()
    if not db_dept:
        raise HTTPException(status_code=404, detail="Department not found")

    db.delete(db_dept)
    db.commit()
    return {"message": "Department deleted successfully"}
