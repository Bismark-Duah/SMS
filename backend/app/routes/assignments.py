from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Tuple, Any

from ..database import get_db
from ..models import TeacherAssignment, User, Subject, Semester, ClassSection, House, Role, Setting, SchoolStage, Department
from ..schemas import TeacherAssignmentCreate, TeacherAssignmentDetail, TeacherPrivilegeCreate, TeacherPrivilegeDetail
from ..dependencies import get_current_user, get_school_id

router = APIRouter()

def _get_school_mode(db: Session, school_id: Optional[int] = None) -> str:
    if school_id:
        from ..models import School
        sch = db.query(School).filter(School.id == school_id).first()
        if sch and sch.school_mode:
            return sch.school_mode
    setting = db.query(Setting).filter(Setting.key == "school_mode").first()
    return setting.value if setting and setting.value else "COMBINED"

def _check_admin(current_user: User, allow_view: bool = False):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not hasattr(current_user, 'roles'):
        return
    role_names = [r.name.lower() for r in current_user.roles] if hasattr(current_user, 'roles') and current_user.roles else []
    if allow_view:
        if "student" in role_names or "parent" in role_names:
            if not any(r in role_names for r in ["admin", "super_admin", "headmaster", "teacher", "form_master", "house_master", "hod"]):
                raise HTTPException(status_code=403, detail="Not authorized to view teacher assignments")
        return
    allowed_roles = {
        "admin", "super_admin", "headmaster", "headmistress",
        "assistant_headmaster_academic", "assistant_head_academic",
        "assistant_headmaster_admin", "assistant_head_admin",
        "hod"
    }
    if not any(r in allowed_roles for r in role_names):
        raise HTTPException(status_code=403, detail="Only administrators or HODs can manage teacher assignments")

@router.get("/", response_model=List[TeacherAssignmentDetail])
def list_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    school_id: Optional[int] = Depends(get_school_id),
):
    _check_admin(current_user, allow_view=True)
    
    mode = _get_school_mode(db, school_id)
    query = db.query(TeacherAssignment)
    if school_id is not None:
        query = query.join(TeacherAssignment.teacher).filter(User.school_id == school_id)
        
    from ..dependencies import get_user_assigned_scope
    scope = get_user_assigned_scope(current_user, db)
    if not scope["is_admin"] and scope["department_ids"]:
        dept_objs = db.query(Department).filter(Department.id.in_(scope["department_ids"])).all()
        allowed_sub_ids = set()
        for d in dept_objs:
            for s in d.subjects:
                allowed_sub_ids.add(s.id)
        if allowed_sub_ids:
            query = query.filter(TeacherAssignment.subject_id.in_(allowed_sub_ids))
        else:
            return []

    if mode == "BASIC_ONLY":
        query = query.outerjoin(TeacherAssignment.class_section).outerjoin(ClassSection.stage).filter(
            (SchoolStage.school_type == "Basic") | (ClassSection.stage_id == None) | (TeacherAssignment.class_section_id == None)
        )
    elif mode == "SHS_ONLY":
        query = query.outerjoin(TeacherAssignment.class_section).outerjoin(ClassSection.stage).filter(
            (SchoolStage.school_type == "SHS") | (ClassSection.stage_id == None) | (TeacherAssignment.class_section_id == None)
        )
    assignments = query.all()
    results = []
    for a in assignments:
        semester_label = f"{a.semester.name} ({a.semester.academic_year.label})" if a.semester and a.semester.academic_year else (a.semester.name if a.semester else "N/A")
        results.append({
            "id": a.id,
            "teacher_id": a.teacher_id,
            "teacher_name": a.teacher.username if a.teacher else f"User {a.teacher_id}",
            "subject_id": a.subject_id,
            "subject_name": a.subject.name if a.subject else f"Subject {a.subject_id}",
            "class_section_id": a.class_section_id,
            "class_section_name": a.class_section.name if a.class_section else f"Class {a.class_section_id}",
            "semester_id": a.semester_id,
            "semester_name": semester_label
        })
    return results

@router.post("/", response_model=TeacherAssignmentDetail)
def create_assignment(
    payload: TeacherAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    school_id: Optional[int] = Depends(get_school_id),
):
    _check_admin(current_user)
    
    teacher_query = db.query(User).filter(User.id == payload.teacher_id)
    if school_id is not None:
        teacher_query = teacher_query.filter(User.school_id == school_id)
    teacher = teacher_query.first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
        
    is_teacher = any(r.name == "teacher" for r in teacher.roles)
    if not is_teacher:
        raise HTTPException(status_code=400, detail="Assigned user must have the 'teacher' role")
        
    if not db.query(Subject).filter(Subject.id == payload.subject_id).first():
        raise HTTPException(status_code=404, detail="Subject not found")

    from ..dependencies import get_user_assigned_scope
    scope = get_user_assigned_scope(current_user, db)
    if not scope["is_admin"] and scope["department_ids"]:
        dept_objs = db.query(Department).filter(Department.id.in_(scope["department_ids"])).all()
        allowed_sub_ids = set()
        for d in dept_objs:
            for s in d.subjects:
                allowed_sub_ids.add(s.id)
        if payload.subject_id not in allowed_sub_ids:
            raise HTTPException(status_code=403, detail="HODs can only assign subjects belonging to their department")

    class_sec = db.query(ClassSection).filter(ClassSection.id == payload.class_section_id).first()
    if not class_sec:
        raise HTTPException(status_code=404, detail="Class section not found")

    # GES Secondary Education Policy Guard: In SHS, Headmasters/Headmistresses do NOT teach
    mode = _get_school_mode(db, school_id)
    teacher_roles = [r.name.lower() for r in teacher.roles] if teacher.roles else []
    is_head = any(r in ["headmaster", "headmistress", "principal"] for r in teacher_roles) or getattr(teacher, "responsibility_role", None) == "HEADMASTER"
    is_shs = (class_sec.stage and getattr(class_sec.stage, "school_type", "").upper() == "SHS") or mode in ["SHS_ONLY", "SHS"]
    if is_head and is_shs:
        raise HTTPException(
            status_code=400,
            detail="In Senior High Schools (SHS), Headmasters and Headmistresses are 100% duty-exempt from teaching and cannot be assigned class subjects."
        )

    duplicate = db.query(TeacherAssignment).filter(
        TeacherAssignment.teacher_id == payload.teacher_id,
        TeacherAssignment.subject_id == payload.subject_id,
        TeacherAssignment.class_section_id == payload.class_section_id,
        TeacherAssignment.semester_id == payload.semester_id
    ).first()
    
    if duplicate:
        raise HTTPException(status_code=400, detail="This assignment already exists")
        
    db_assignment = TeacherAssignment(
        teacher_id=payload.teacher_id,
        subject_id=payload.subject_id,
        class_section_id=payload.class_section_id,
        semester_id=payload.semester_id
    )
    db.add(db_assignment)
    db.commit()
    db.refresh(db_assignment)
    
    semester_label = f"{db_assignment.semester.name} ({db_assignment.semester.academic_year.label})" if db_assignment.semester and db_assignment.semester.academic_year else (db_assignment.semester.name if db_assignment.semester else "N/A")
    return {
        "id": db_assignment.id,
        "teacher_id": db_assignment.teacher_id,
        "teacher_name": db_assignment.teacher.username,
        "subject_id": db_assignment.subject_id,
        "subject_name": db_assignment.subject.name,
        "class_section_id": db_assignment.class_section_id,
        "class_section_name": db_assignment.class_section.name,
        "semester_id": db_assignment.semester_id,
        "semester_name": semester_label
    }

@router.put("/{assignment_id}", response_model=TeacherAssignmentDetail)
def update_assignment(
    assignment_id: int,
    payload: TeacherAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_admin(current_user)
    
    assignment = db.query(TeacherAssignment).filter(TeacherAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    from ..dependencies import get_user_assigned_scope
    scope = get_user_assigned_scope(current_user, db)
    if not scope["is_admin"] and scope["department_ids"]:
        dept_objs = db.query(Department).filter(Department.id.in_(scope["department_ids"])).all()
        allowed_sub_ids = set()
        for d in dept_objs:
            for s in d.subjects:
                allowed_sub_ids.add(s.id)
        if assignment.subject_id not in allowed_sub_ids or payload.subject_id not in allowed_sub_ids:
            raise HTTPException(status_code=403, detail="HODs can only manage assignments for subjects in their department")

    teacher = db.query(User).filter(User.id == payload.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    class_sec = db.query(ClassSection).filter(ClassSection.id == payload.class_section_id).first()
    if not class_sec:
        raise HTTPException(status_code=404, detail="Class section not found")

    # GES Secondary Education Policy Guard: In SHS, Headmasters/Headmistresses do NOT teach
    mode = _get_school_mode(db, current_user.school_id if hasattr(current_user, "school_id") else None)
    teacher_roles = [r.name.lower() for r in teacher.roles] if teacher.roles else []
    is_head = any(r in ["headmaster", "headmistress", "principal"] for r in teacher_roles) or getattr(teacher, "responsibility_role", None) == "HEADMASTER"
    is_shs = (class_sec.stage and getattr(class_sec.stage, "school_type", "").upper() == "SHS") or mode in ["SHS_ONLY", "SHS"]
    if is_head and is_shs:
        raise HTTPException(
            status_code=400,
            detail="In Senior High Schools (SHS), Headmasters and Headmistresses are 100% duty-exempt from teaching and cannot be assigned class subjects."
        )

    dup = db.query(TeacherAssignment).filter(
        TeacherAssignment.teacher_id == payload.teacher_id,
        TeacherAssignment.subject_id == payload.subject_id,
        TeacherAssignment.class_section_id == payload.class_section_id,
        TeacherAssignment.semester_id == payload.semester_id,
        TeacherAssignment.id != assignment_id
    ).first()
    if dup:
        raise HTTPException(status_code=400, detail="An identical teaching assignment already exists for this teacher, class, and term.")

    assignment.teacher_id = payload.teacher_id
    assignment.class_section_id = payload.class_section_id
    assignment.subject_id = payload.subject_id
    assignment.semester_id = payload.semester_id

    db.commit()
    db.refresh(assignment)

    semester_label = assignment.semester.name if assignment.semester else "General"
    return {
        "id": assignment.id,
        "teacher_id": assignment.teacher_id,
        "teacher_name": getattr(assignment.teacher, 'full_name', None) or getattr(assignment.teacher, 'username', 'Unknown'),
        "subject_id": assignment.subject_id,
        "subject_name": assignment.subject.name if assignment.subject else "N/A",
        "class_section_id": assignment.class_section_id,
        "class_section_name": assignment.class_section.name if assignment.class_section else "N/A",
        "semester_id": assignment.semester_id,
        "semester_name": semester_label
    }

@router.delete("/{assignment_id}")
def delete_assignment(assignment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _check_admin(current_user)
    
    assignment = db.query(TeacherAssignment).filter(TeacherAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    from ..dependencies import get_user_assigned_scope
    scope = get_user_assigned_scope(current_user, db)
    if not scope["is_admin"] and scope["department_ids"]:
        dept_objs = db.query(Department).filter(Department.id.in_(scope["department_ids"])).all()
        allowed_sub_ids = set()
        for d in dept_objs:
            for s in d.subjects:
                allowed_sub_ids.add(s.id)
        if assignment.subject_id not in allowed_sub_ids:
            raise HTTPException(status_code=403, detail="HODs can only delete assignments for subjects in their department")

    db.delete(assignment)
    db.commit()
    return {"status": "success", "message": "Assignment removed"}

@router.get("/privileges", response_model=List[TeacherPrivilegeDetail])
def list_privileges(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    school_id: Optional[int] = Depends(get_school_id),
):
    _check_admin(current_user, allow_view=True)
    
    results = []

    def _get_name(u):
        if not u:
            return "Staff Member"
        return getattr(u, 'full_name', None) or getattr(u, 'username', None) or f"User {u.id}"

    # 1. Form Masters / Form Mistresses
    sec_query = db.query(ClassSection).filter(ClassSection.form_master_id != None)
    if school_id is not None and hasattr(ClassSection, "school_id"):
        sec_query = sec_query.filter(ClassSection.school_id == school_id)
    sections = sec_query.all()
    for s in sections:
        if s.form_master:
            results.append(TeacherPrivilegeDetail(
                id=f"form_master-{s.id}",
                teacher_id=s.form_master_id,
                teacher_name=_get_name(s.form_master),
                privilege_type="Form Master / Mistress",
                target_id=s.id,
                target_name=s.name
            ))

    # 2. Senior House Masters / Mistresses
    senior_roles = db.query(Role).filter(Role.name.in_(["senior_housemaster", "senior_housemistress", "senior_house_master", "senior_house_mistress"])).all()
    for role in senior_roles:
        for u in role.users:
            if school_id is not None and hasattr(u, "school_id") and u.school_id and u.school_id != school_id:
                continue
            results.append(TeacherPrivilegeDetail(
                id=f"senior_house_master-{u.id}",
                teacher_id=u.id,
                teacher_name=_get_name(u),
                privilege_type="Senior House Master / Mistress",
                target_id=None,
                target_name="Global (School-wide)"
            ))

    # 3. House Masters / Mistresses & Assistants
    house_query = db.query(House)
    if school_id is not None and hasattr(House, "school_id"):
        house_query = house_query.filter((House.school_id == school_id) | (House.school_id.is_(None)))
    houses = house_query.all()

    for h in houses:
        if h.house_master:
            results.append(TeacherPrivilegeDetail(
                id=f"house_master-{h.id}",
                teacher_id=h.house_master_id,
                teacher_name=_get_name(h.house_master),
                privilege_type="House Master (Boys/Co-ed)",
                target_id=h.id,
                target_name=h.name
            ))
        if h.assistant_house_master:
            results.append(TeacherPrivilegeDetail(
                id=f"assistant_house_master-{h.id}",
                teacher_id=h.assistant_house_master_id,
                teacher_name=_get_name(h.assistant_house_master),
                privilege_type="Assistant House Master",
                target_id=h.id,
                target_name=h.name
            ))
        if h.house_master_girls:
            results.append(TeacherPrivilegeDetail(
                id=f"house_master_girls-{h.id}",
                teacher_id=h.house_master_girls_id,
                teacher_name=_get_name(h.house_master_girls),
                privilege_type="House Mistress (Girls)",
                target_id=h.id,
                target_name=h.name
            ))
        if h.assistant_house_master_girls:
            results.append(TeacherPrivilegeDetail(
                id=f"assistant_house_master_girls-{h.id}",
                teacher_id=h.assistant_house_master_girls_id,
                teacher_name=_get_name(h.assistant_house_master_girls),
                privilege_type="Assistant House Mistress",
                target_id=h.id,
                target_name=h.name
            ))

    # 4. Heads of Department (HOD)
    dept_query = db.query(Department).filter(Department.hod_id != None)
    if school_id is not None and hasattr(Department, "school_id"):
        dept_query = dept_query.filter((Department.school_id == school_id) | (Department.school_id.is_(None)))
    departments = dept_query.all()

    for d in departments:
        hod_user = d.hod or db.query(User).filter(User.id == d.hod_id).first()
        if hod_user:
            results.append(TeacherPrivilegeDetail(
                id=f"hod-{d.id}",
                teacher_id=d.hod_id,
                teacher_name=_get_name(hod_user),
                privilege_type="Head of Department (HOD)",
                target_id=d.id,
                target_name=f"{d.name} ({d.code})"
            ))

    # 5. Assistant Headmasters & Executive Leadership Roles
    exec_roles_map = {
        "hod": "Head of Department (HOD)",
        "assistant_headmaster_domestic": "Assistant Headmaster / Mistress (Domestic)",
        "assistant_headmaster_academic": "Assistant Headmaster / Mistress (Academic)",
        "assistant_headmaster_admin": "Assistant Headmaster / Mistress (Admin)",
        "assistant_head_domestic": "Assistant Headmaster / Mistress (Domestic)",
        "assistant_head_academic": "Assistant Headmaster / Mistress (Academic)",
        "assistant_head_admin": "Assistant Headmaster / Mistress (Admin)",
        "headmaster": "Headmaster / Principal",
        "headmistress": "Headmistress / Principal",
        "bursar": "School Accountant / Bursar",
    }
    exec_roles = db.query(Role).filter(Role.name.in_(list(exec_roles_map.keys()))).all()
    added_user_priv_types = set()
    for r in exec_roles:
        display_title = exec_roles_map.get(r.name, r.name.replace("_", " ").title())
        for u in r.users:
            if school_id is not None and hasattr(u, "school_id") and u.school_id and u.school_id != school_id:
                continue
            key = (u.id, display_title)
            if key not in added_user_priv_types:
                added_user_priv_types.add(key)
                results.append(TeacherPrivilegeDetail(
                    id=f"executive_role-{u.id}-{r.id}",
                    teacher_id=u.id,
                    teacher_name=_get_name(u),
                    privilege_type=display_title,
                    target_id=None,
                    target_name="Global (School-wide)"
                ))

    return results

def _helper_add_role(db: Session, user: User, role_name: str):
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name)
        db.add(role)
        db.flush()
    if role not in user.roles:
        user.roles.append(role)

def _helper_remove_role_if_unused(db: Session, user: User, role_name: str, checking_func):
    if not checking_func():
        role = db.query(Role).filter(Role.name == role_name).first()
        if role and role in user.roles:
            user.roles.remove(role)

@router.post("/privilege", response_model=TeacherPrivilegeDetail)
def create_privilege(
    payload: TeacherPrivilegeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    school_id: Optional[int] = Depends(get_school_id),
):
    _check_admin(current_user)
    
    teacher = db.query(User).filter(User.id == payload.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    is_female = teacher.gender is not None and teacher.gender.lower() in ["female", "f"]
    
    target_name = None
    priv_id = ""

    if payload.privilege_type == "form_master":
        if not payload.target_id:
            raise HTTPException(status_code=400, detail="Class Section ID is required for Form Master assignment")
        section = db.query(ClassSection).filter(ClassSection.id == payload.target_id).first()
        if not section:
            raise HTTPException(status_code=404, detail="Class Section not found")
        
        section.form_master_id = teacher.id
        db.flush()
        target_name = section.name
        priv_id = f"form_master-{section.id}"
        
        role_name = "form_mistress" if is_female else "form_master"
        _helper_add_role(db, teacher, role_name)

    elif payload.privilege_type == "senior_house_master":
        role_name = "senior_housemistress" if is_female else "senior_housemaster"
        _helper_add_role(db, teacher, role_name)
        target_name = "Global (School-wide)"
        priv_id = f"senior_house_master-{teacher.id}"

    elif payload.privilege_type == "house_master":
        if not payload.target_id:
            raise HTTPException(status_code=400, detail="House ID is required for House Master assignment")
        house = db.query(House).filter(House.id == payload.target_id).first()
        if not house:
            raise HTTPException(status_code=404, detail="House not found")
        
        if house.gender == "Both" and is_female:
            house.house_master_girls_id = teacher.id
        else:
            house.house_master_id = teacher.id
        db.flush()
        target_name = house.name
        priv_id = f"house_master-{house.id}"
        
        role_name = "house_mistress" if is_female else "house_master"
        _helper_add_role(db, teacher, role_name)

    elif payload.privilege_type == "assistant_house_master":
        if not payload.target_id:
            raise HTTPException(status_code=400, detail="House ID is required for Assistant House Master assignment")
        house = db.query(House).filter(House.id == payload.target_id).first()
        if not house:
            raise HTTPException(status_code=404, detail="House not found")
        
        if house.gender == "Both" and is_female:
            house.assistant_house_master_girls_id = teacher.id
        else:
            house.assistant_house_master_id = teacher.id
        db.flush()
        target_name = house.name
        priv_id = f"assistant_house_master-{house.id}"
        
        role_name = "assistant_house_mistress" if is_female else "assistant_house_master"
        _helper_add_role(db, teacher, role_name)

    elif payload.privilege_type == "hod":
        if not payload.target_id:
            raise HTTPException(status_code=400, detail="Department ID is required for HOD assignment")
        dept = db.query(Department).filter(Department.id == payload.target_id).first()
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found")
        
        dept.hod_id = teacher.id
        db.flush()
        target_name = f"{dept.name} ({dept.code})"
        priv_id = f"hod-{dept.id}"
        _helper_add_role(db, teacher, "hod")

    elif payload.privilege_type in ["assistant_headmaster_academic", "assistant_headmaster_domestic", "assistant_headmaster_admin"]:
        _helper_add_role(db, teacher, payload.privilege_type)
        target_name = "Global (School-wide)"
        priv_id = f"{payload.privilege_type}-{teacher.id}"
        
    else:
        raise HTTPException(status_code=400, detail="Invalid privilege type")

    db.commit()
    
    return TeacherPrivilegeDetail(
        id=priv_id,
        teacher_id=teacher.id,
        teacher_name=teacher.username,
        privilege_type=payload.privilege_type,
        target_id=payload.target_id,
        target_name=target_name
    )

@router.delete("/privilege/{priv_type}")
def delete_privilege(
    priv_type: str, 
    target_id: Optional[int] = None, 
    teacher_id: Optional[int] = None,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    _check_admin(current_user)
    
    teacher = None
    
    if priv_type == "form_master":
        if not target_id:
            raise HTTPException(status_code=400, detail="target_id is required")
        section = db.query(ClassSection).filter(ClassSection.id == target_id).first()
        if section:
            teacher = db.query(User).filter(User.id == section.form_master_id).first()
            section.form_master_id = None
            db.flush()
            if teacher:
                is_female = teacher.gender is not None and teacher.gender.lower() in ["female", "f"]
                role_name = "form_mistress" if is_female else "form_master"
                
                def is_still_fm():
                    return db.query(ClassSection).filter(ClassSection.form_master_id == teacher.id).first() is not None
                
                _helper_remove_role_if_unused(db, teacher, role_name, is_still_fm)

    elif priv_type == "senior_house_master":
        if not teacher_id:
            raise HTTPException(status_code=400, detail="teacher_id is required")
        teacher = db.query(User).filter(User.id == teacher_id).first()
        if teacher:
            is_female = teacher.gender is not None and teacher.gender.lower() in ["female", "f"]
            role_name = "senior_housemistress" if is_female else "senior_housemaster"
            _helper_remove_role_if_unused(db, teacher, role_name, lambda: False)

    elif priv_type == "house_master":
        if not target_id:
            raise HTTPException(status_code=400, detail="target_id is required")
        house = db.query(House).filter(House.id == target_id).first()
        if house:
            if teacher_id:
                teacher = db.query(User).filter(User.id == teacher_id).first()
                if house.house_master_id == teacher_id:
                    house.house_master_id = None
                elif house.house_master_girls_id == teacher_id:
                    house.house_master_girls_id = None
            else:
                teacher = db.query(User).filter(User.id == house.house_master_id).first()
                if teacher:
                    house.house_master_id = None
                else:
                    teacher = db.query(User).filter(User.id == house.house_master_girls_id).first()
                    house.house_master_girls_id = None
            db.flush()
            if teacher:
                is_female = teacher.gender is not None and teacher.gender.lower() in ["female", "f"]
                role_name = "house_mistress" if is_female else "house_master"
                
                def is_still_hm():
                    return db.query(House).filter(
                        (House.house_master_id == teacher.id) | 
                        (House.house_master_girls_id == teacher.id)
                    ).first() is not None
                
                _helper_remove_role_if_unused(db, teacher, role_name, is_still_hm)

    elif priv_type == "assistant_house_master":
        if not target_id:
            raise HTTPException(status_code=400, detail="target_id is required")
        house = db.query(House).filter(House.id == target_id).first()
        if house:
            if teacher_id:
                teacher = db.query(User).filter(User.id == teacher_id).first()
                if house.assistant_house_master_id == teacher_id:
                    house.assistant_house_master_id = None
                elif house.assistant_house_master_girls_id == teacher_id:
                    house.assistant_house_master_girls_id = None
            else:
                teacher = db.query(User).filter(User.id == house.assistant_house_master_id).first()
                if teacher:
                    house.assistant_house_master_id = None
                else:
                    teacher = db.query(User).filter(User.id == house.assistant_house_master_girls_id).first()
                    house.assistant_house_master_girls_id = None
            db.flush()
            if teacher:
                is_female = teacher.gender is not None and teacher.gender.lower() in ["female", "f"]
                role_name = "assistant_house_mistress" if is_female else "assistant_house_master"
                
                def is_still_ahm():
                    return db.query(House).filter(
                        (House.assistant_house_master_id == teacher.id) | 
                        (House.assistant_house_master_girls_id == teacher.id)
                    ).first() is not None
                
                _helper_remove_role_if_unused(db, teacher, role_name, is_still_ahm)

    elif priv_type == "hod" or priv_type.startswith("hod-") or "head of department" in priv_type.lower() or "hod" in priv_type.lower():
        if target_id:
            dept = db.query(Department).filter(Department.id == target_id).first()
            if dept:
                teacher = db.query(User).filter(User.id == dept.hod_id).first()
                dept.hod_id = None
                db.flush()
        elif teacher_id:
            teacher = db.query(User).filter(User.id == teacher_id).first()
            depts = db.query(Department).filter(Department.hod_id == teacher_id).all()
            for dept in depts:
                dept.hod_id = None
            db.flush()

        if teacher:
            def is_still_hod():
                return db.query(Department).filter(Department.hod_id == teacher.id).first() is not None
            _helper_remove_role_if_unused(db, teacher, "hod", is_still_hod)

    elif "assistant head" in priv_type.lower() or "assistant_head" in priv_type.lower() or priv_type in ["assistant_headmaster_academic", "assistant_headmaster_domestic", "assistant_headmaster_admin"]:
        t_id = teacher_id or target_id
        if t_id:
            teacher = db.query(User).filter(User.id == t_id).first()
            if teacher:
                # find matching assistant head role
                role_names = [r.name for r in teacher.roles if "assistant_head" in r.name or "assistant head" in r.name]
                for rn in role_names:
                    _helper_remove_role_if_unused(db, teacher, rn, lambda: False)
                if not role_names:
                    _helper_remove_role_if_unused(db, teacher, priv_type, lambda: False)
                
    else:
        raise HTTPException(status_code=400, detail="Invalid privilege type")

    db.commit()
    return {"status": "success", "message": "Privilege removed"}


from pydantic import BaseModel

class AssignPrimaryClassRequest(BaseModel):
    teacher_id: int
    class_section_id: int
    semester_id: int

class BatchJHSMatrixRequest(BaseModel):
    teacher_id: int
    subject_ids: List[int]
    class_section_ids: List[int]
    semester_id: int


@router.post("/assign-primary-class")
def assign_primary_class_teacher(
    payload: AssignPrimaryClassRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    1-Click Class Teacher Allocation for Ghanaian Basic Schools:
    Binds the assigned teacher to ALL active subjects of the class section
    and designates them as the official Class Teacher (form_master_id).
    """
    _check_admin(current_user)
    school_id = getattr(current_user, 'school_id', None)
    is_super = any(r.name in ["super_admin", "admin"] for r in current_user.roles) if hasattr(current_user, 'roles') else False

    sec_q = db.query(ClassSection).filter(ClassSection.id == payload.class_section_id)
    if not is_super and school_id is not None and hasattr(ClassSection, "school_id"):
        sec_q = sec_q.filter(ClassSection.school_id == school_id)
    class_sec = sec_q.first()
    if not class_sec:
        raise HTTPException(status_code=404, detail="Class section not found")

    teacher_q = db.query(User).filter(User.id == payload.teacher_id)
    if not is_super and class_sec.school_id is not None:
        teacher_q = teacher_q.filter((User.school_id == class_sec.school_id) | (User.school_id == None))
    elif not is_super and school_id is not None:
        teacher_q = teacher_q.filter((User.school_id == school_id) | (User.school_id == None))
    teacher = teacher_q.first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    is_teacher = any(r.name == "teacher" for r in teacher.roles)
    if not is_teacher:
        raise HTTPException(status_code=400, detail="Assigned user must have the 'teacher' role")

    sem = db.query(Semester).filter(Semester.id == payload.semester_id).first()
    if not sem:
        raise HTTPException(status_code=404, detail="Semester not found")

    # Set as official Class Teacher (form_master_id)
    class_sec.form_master_id = teacher.id

    # Retrieve all active subjects for this class section (or all basic subjects)
    assigned_subjects = list(class_sec.subjects) if class_sec.subjects else []
    if not assigned_subjects:
        assigned_subjects = db.query(Subject).filter(
            (Subject.school_level.ilike("Basic%")) | (Subject.school_level == None)
        ).all()
        class_sec.subjects = assigned_subjects

    created_count = 0
    updated_count = 0
    for sub in assigned_subjects:
        existing = db.query(TeacherAssignment).filter(
            TeacherAssignment.class_section_id == class_sec.id,
            TeacherAssignment.subject_id == sub.id,
            TeacherAssignment.semester_id == sem.id
        ).first()

        if existing:
            existing.teacher_id = teacher.id
            updated_count += 1
        else:
            new_asgn = TeacherAssignment(
                teacher_id=teacher.id,
                class_section_id=class_sec.id,
                subject_id=sub.id,
                semester_id=sem.id
            )
            db.add(new_asgn)
            created_count += 1

    # Ensure form_master role is assigned to the teacher
    fm_role = db.query(Role).filter(Role.name == "form_master").first()
    if fm_role and fm_role not in teacher.roles:
        teacher.roles.append(fm_role)

    db.commit()
    return {
        "status": "success",
        "message": f"Successfully assigned {getattr(teacher, 'full_name', None) or teacher.username} as Class Teacher for {class_sec.name} across all {len(assigned_subjects)} subjects.",
        "class_id": class_sec.id,
        "class_name": class_sec.name,
        "teacher_id": teacher.id,
        "teacher_name": getattr(teacher, 'full_name', None) or teacher.username,
        "subjects_assigned_count": len(assigned_subjects),
        "subjects": [s.name for s in assigned_subjects]
    }


@router.post("/batch-jhs-matrix")
def batch_jhs_matrix_assignment(
    payload: BatchJHSMatrixRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Multi-Subject & Multi-Class Workload Matrix Allocator for Junior High Schools:
    Assigns a teacher to multiple subjects across multiple JHS streams in one request.
    """
    _check_admin(current_user)
    school_id = getattr(current_user, 'school_id', None)
    is_super = any(r.name in ["super_admin", "admin"] for r in current_user.roles) if hasattr(current_user, 'roles') else False

    teacher_q = db.query(User).filter(User.id == payload.teacher_id)
    if not is_super and school_id is not None:
        teacher_q = teacher_q.filter(User.school_id == school_id)
    teacher = teacher_q.first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    is_teacher = any(r.name == "teacher" for r in teacher.roles)
    if not is_teacher:
        raise HTTPException(status_code=400, detail="Assigned user must have the 'teacher' role")

    sem = db.query(Semester).filter(Semester.id == payload.semester_id).first()
    if not sem:
        raise HTTPException(status_code=404, detail="Semester not found")

    assigned_count = 0
    for cls_id in payload.class_section_ids:
        # verify class exists
        cls_q = db.query(ClassSection).filter(ClassSection.id == cls_id)
        if not is_super and school_id is not None and hasattr(ClassSection, "school_id"):
            cls_q = cls_q.filter(ClassSection.school_id == school_id)
        cls_sec = cls_q.first()
        if not cls_sec:
            continue

        for sub_id in payload.subject_ids:
            sub_obj = db.query(Subject).filter(Subject.id == sub_id).first()
            if not sub_obj:
                continue

            existing = db.query(TeacherAssignment).filter(
                TeacherAssignment.class_section_id == cls_id,
                TeacherAssignment.subject_id == sub_id,
                TeacherAssignment.semester_id == sem.id
            ).first()

            if existing:
                existing.teacher_id = teacher.id
                assigned_count += 1
            else:
                new_asgn = TeacherAssignment(
                    teacher_id=teacher.id,
                    class_section_id=cls_id,
                    subject_id=sub_id,
                    semester_id=sem.id
                )
                db.add(new_asgn)
                assigned_count += 1

    db.commit()
    t_name = getattr(teacher, 'full_name', None) or teacher.username
    return {
        "status": "success",
        "assigned_count": assigned_count,
        "teacher_name": t_name,
        "message": f"Successfully allocated {assigned_count} teaching assignment(s) for {t_name}."
    }


# ── Staffing Conflicts & Smart Distribution Engine ───────────────────────────
from ..services.curriculum_presets import get_subject_config, ROLE_WORKLOAD_LIMITS
from ..models import class_section_subjects

class BatchConfirmAssignmentItem(BaseModel):
    teacher_id: int
    subject_id: int
    class_section_id: int

class BatchConfirmAssignmentsRequest(BaseModel):
    semester_id: int
    assignments: List[BatchConfirmAssignmentItem]
    replace_subject_ids: Optional[List[int]] = None


@router.get("/audit-staffing-conflicts")
def audit_staffing_conflicts(
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    school_id: Optional[int] = Depends(get_school_id),
):
    """
    Audits active teaching allocations against curriculum weekly periods and teacher capacity caps.
    Detects overloaded teachers and overloaded subjects with available qualified candidate teachers.
    """
    _check_admin(current_user, allow_view=True)

    target_sch_id = school_id or getattr(current_user, "school_id", None)
    if not semester_id:
        cur_sem = db.query(Semester).filter(
            (Semester.school_id == target_sch_id) if target_sch_id else True,
            Semester.is_current == True
        ).first()
        semester_id = cur_sem.id if cur_sem else None

    if not semester_id:
        return {"conflicts": [], "total_conflicts": 0, "semester_id": None}

    # Fetch active teaching assignments
    asgns = db.query(TeacherAssignment).filter(
        TeacherAssignment.semester_id == semester_id
    ).join(TeacherAssignment.teacher).filter(
        (User.school_id == target_sch_id) if target_sch_id else True
    ).all()

    # Preload all active teachers for qualified lookup
    teachers_q = db.query(User).filter(
        (User.school_id == target_sch_id) if target_sch_id else True
    ).all()

    teacher_map = {t.id: t for t in teachers_q}
    
    # Calculate period loads per teacher
    teacher_period_loads: Dict[int, int] = {}
    teacher_classes_by_subj: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}

    for a in asgns:
        s_cfg = get_subject_config(a.subject.name if a.subject else "")
        weekly_p = s_cfg.get("weekly_periods", 4)

        teacher_period_loads[a.teacher_id] = teacher_period_loads.get(a.teacher_id, 0) + weekly_p

        key = (a.teacher_id, a.subject_id)
        if key not in teacher_classes_by_subj:
            teacher_classes_by_subj[key] = []
        teacher_classes_by_subj[key].append({
            "assignment_id": a.id,
            "class_section_id": a.class_section_id,
            "class_section_name": a.class_section.name if a.class_section else f"Class {a.class_section_id}",
            "weekly_periods": weekly_p
        })

    conflicts = []
    # Identify overloaded teacher-subject assignments
    for (t_id, s_id), class_items in teacher_classes_by_subj.items():
        t = teacher_map.get(t_id)
        if not t:
            continue
        
        t_roles = [r.name.lower() for r in t.roles] if t.roles else []
        is_exempt = getattr(t, "is_teaching_exempt", False) or any(r in t_roles for r in ["headmaster", "principal", "admin", "bursar"])
        role_key = getattr(t, "responsibility_role", "REGULAR_TEACHER") or "REGULAR_TEACHER"
        role_limit = ROLE_WORKLOAD_LIMITS.get(role_key, ROLE_WORKLOAD_LIMITS["REGULAR_TEACHER"])
        max_cap = getattr(t, "max_weekly_periods", 0) if is_exempt else (getattr(t, "max_weekly_periods", role_limit["default_cap"]) or role_limit["default_cap"])

        total_load = teacher_period_loads.get(t_id, 0)
        subj_obj = db.query(Subject).filter(Subject.id == s_id).first()
        subj_name = subj_obj.name if subj_obj else "Subject"

        # Conflict trigger: total load exceeds max_cap or single subject load exceeds 24 periods
        subject_load = sum(c["weekly_periods"] for c in class_items)
        if (total_load > max_cap and not is_exempt) or (subject_load > 26 and len(class_items) > 4):
            # Find candidate teachers who are qualified in this subject
            qualified_candidates = []
            for other_t in teachers_q:
                # check if qualified or primary subject matches
                is_qual = (other_t.primary_subject_id == s_id) or (s_id in [qs.id for qs in getattr(other_t, "qualified_subjects", [])])
                # Also include same department teachers if available
                if not is_qual and other_t.department_id and subj_obj:
                    t_dept = db.query(Department).filter(Department.id == other_t.department_id).first()
                    if t_dept and any(s.id == s_id for s in t_dept.subjects):
                        is_qual = True
                
                other_t_roles = [r.name.lower() for r in other_t.roles] if other_t.roles else []
                is_other_head = any(r in ["headmaster", "principal"] for r in other_t_roles) or getattr(other_t, "responsibility_role", None) == "HEADMASTER"
                if is_qual and not is_other_head:
                    other_load = teacher_period_loads.get(other_t.id, 0)
                    other_cap = getattr(other_t, "max_weekly_periods", 26) or 26
                    qualified_candidates.append({
                        "teacher_id": other_t.id,
                        "teacher_name": getattr(other_t, "full_name", None) or other_t.username,
                        "current_periods": other_load,
                        "max_cap": other_cap,
                        "available_capacity": max(0, other_cap - other_load)
                    })

            conflicts.append({
                "subject_id": s_id,
                "subject_name": subj_name,
                "overloaded_teacher_id": t_id,
                "overloaded_teacher_name": getattr(t, "full_name", None) or t.username,
                "current_teacher_load": total_load,
                "subject_periods": subject_load,
                "max_cap": max_cap,
                "overload_periods": max(0, total_load - max_cap) if not is_exempt else 0,
                "assigned_classes": class_items,
                "qualified_teachers": qualified_candidates,
                "recommendation": f"Redistribute {len(class_items)} classes of {subj_name} across {len(qualified_candidates)} available qualified teacher(s)."
            })

    return {
        "status": "success",
        "semester_id": semester_id,
        "total_conflicts": len(conflicts),
        "conflicts": conflicts
    }


@router.get("/smart-distribute-subject")
def smart_distribute_subject(
    subject_id: int,
    semester_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    school_id: Optional[int] = Depends(get_school_id),
):
    """
    Calculates a balanced class distribution proposal for an overloaded subject.
    Splits classes among qualified teachers respecting weekly workload limits.
    """
    _check_admin(current_user, allow_view=True)
    target_sch_id = school_id or getattr(current_user, "school_id", None)

    subj = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")

    s_cfg = get_subject_config(subj.name)
    weekly_p = s_cfg.get("weekly_periods", 4)

    # All classes currently needing this subject in this school
    # (either currently assigned in this semester, or bound via class_section_subjects)
    assigned_sections = db.query(ClassSection).join(
        TeacherAssignment,
        ClassSection.id == TeacherAssignment.class_section_id
    ).filter(
        TeacherAssignment.subject_id == subject_id,
        TeacherAssignment.semester_id == semester_id,
        (ClassSection.school_id == target_sch_id) if target_sch_id else True
    ).distinct().all()

    if not assigned_sections:
        # Fallback to academic structure links
        assigned_sections = db.query(ClassSection).join(
            class_section_subjects,
            ClassSection.id == class_section_subjects.c.class_section_id
        ).filter(
            class_section_subjects.c.subject_id == subject_id,
            (ClassSection.school_id == target_sch_id) if target_sch_id else True
        ).all()

    all_teachers = db.query(User).filter(
        (User.school_id == target_sch_id) if target_sch_id else True
    ).all()

    # Find qualified teachers
    qualified = []
    for t in all_teachers:
        t_roles = [r.name.lower() for r in t.roles] if t.roles else []
        is_head = any(r in ["headmaster", "principal"] for r in t_roles) or getattr(t, "responsibility_role", None) == "HEADMASTER"
        if is_head:
            continue
        
        is_qual = (t.primary_subject_id == subject_id) or (subject_id in [qs.id for qs in getattr(t, "qualified_subjects", [])])
        if not is_qual and t.department_id:
            t_dept = db.query(Department).filter(Department.id == t.department_id).first()
            if t_dept and any(s.id == subject_id for s in t_dept.subjects):
                is_qual = True
        
        if is_qual:
            cap = getattr(t, "max_weekly_periods", 26) or 26
            # Current load excluding this subject
            other_load = 0
            other_asgns = db.query(TeacherAssignment).filter(
                TeacherAssignment.teacher_id == t.id,
                TeacherAssignment.semester_id == semester_id,
                TeacherAssignment.subject_id != subject_id
            ).all()
            for oa in other_asgns:
                other_load += get_subject_config(oa.subject.name if oa.subject else "").get("weekly_periods", 4)

            qualified.append({
                "teacher_id": t.id,
                "teacher_name": getattr(t, "full_name", None) or t.username,
                "max_cap": cap,
                "base_load": other_load,
                "classes": []
            })

    if not qualified:
        # If no specific qualified teachers, pick any teacher currently assigned to this subject
        asgn_teacher_ids = {a.teacher_id for a in db.query(TeacherAssignment).filter(
            TeacherAssignment.subject_id == subject_id,
            TeacherAssignment.semester_id == semester_id
        ).all()}
        for t in all_teachers:
            if t.id in asgn_teacher_ids:
                qualified.append({
                    "teacher_id": t.id,
                    "teacher_name": getattr(t, "full_name", None) or t.username,
                    "max_cap": getattr(t, "max_weekly_periods", 26) or 26,
                    "base_load": 0,
                    "classes": []
                })

    if not qualified:
        raise HTTPException(status_code=400, detail=f"No qualified teachers available to distribute '{subj.name}'. Please create or qualify additional teachers first.")

    # Sort classes by name/level to group logically (e.g., 1S1, 1S2 together)
    sections_sorted = sorted(assigned_sections, key=lambda c: c.name)

    # Distribute classes round-robin or by available capacity
    for idx, sec in enumerate(sections_sorted):
        # Pick teacher with minimum projected load
        target_teacher = min(qualified, key=lambda t: t["base_load"] + (len(t["classes"]) * weekly_p))
        target_teacher["classes"].append({
            "class_section_id": sec.id,
            "class_section_name": sec.name,
            "weekly_periods": weekly_p
        })

    # Prepare response proposal
    proposal = []
    for q in qualified:
        projected_p = q["base_load"] + (len(q["classes"]) * weekly_p)
        proposal.append({
            "teacher_id": q["teacher_id"],
            "teacher_name": q["teacher_name"],
            "assigned_classes": q["classes"],
            "classes_count": len(q["classes"]),
            "subject_periods": len(q["classes"]) * weekly_p,
            "projected_total_periods": projected_p,
            "max_cap": q["max_cap"],
            "status": "OVERLOADED" if projected_p > q["max_cap"] else "OPTIMAL"
        })

    return {
        "status": "success",
        "subject_id": subject_id,
        "subject_name": subj.name,
        "weekly_periods_per_class": weekly_p,
        "total_classes": len(sections_sorted),
        "teachers_count": len(qualified),
        "proposal": proposal
    }


@router.post("/batch-confirm-assignments")
def batch_confirm_assignments(
    payload: BatchConfirmAssignmentsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    school_id: Optional[int] = Depends(get_school_id),
):
    """
    Commits approved teacher-class distributions after Admin inspection & confirmation.
    Safely replaces previous allocations for the specified subjects.
    """
    _check_admin(current_user)
    target_sch_id = school_id or getattr(current_user, "school_id", None)

    sem = db.query(Semester).filter(Semester.id == payload.semester_id).first()
    if not sem:
        raise HTTPException(status_code=404, detail="Semester not found")

    # If replace_subject_ids provided, remove existing assignments for these subjects first
    if payload.replace_subject_ids:
        del_q = db.query(TeacherAssignment).filter(
            TeacherAssignment.semester_id == payload.semester_id,
            TeacherAssignment.subject_id.in_(payload.replace_subject_ids)
        )
        if target_sch_id:
            del_q = del_q.join(TeacherAssignment.class_section).filter(ClassSection.school_id == target_sch_id)
        del_q.delete(synchronize_session=False)

    saved_count = 0
    for item in payload.assignments:
        existing = db.query(TeacherAssignment).filter(
            TeacherAssignment.teacher_id == item.teacher_id,
            TeacherAssignment.subject_id == item.subject_id,
            TeacherAssignment.class_section_id == item.class_section_id,
            TeacherAssignment.semester_id == payload.semester_id
        ).first()

        if existing:
            existing.teacher_id = item.teacher_id
            saved_count += 1
        else:
            new_ta = TeacherAssignment(
                teacher_id=item.teacher_id,
                subject_id=item.subject_id,
                class_section_id=item.class_section_id,
                semester_id=payload.semester_id
            )
            db.add(new_ta)
            saved_count += 1

    db.commit()
    return {
        "status": "success",
        "saved_count": saved_count,
        "message": f"Successfully confirmed and committed {saved_count} teaching allocation(s)."
    }

