from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db
from ..models import TeacherAssignment, User, Subject, Semester, ClassSection, House, Role, Setting, SchoolStage, Department
from ..schemas import TeacherAssignmentCreate, TeacherAssignmentDetail, TeacherPrivilegeCreate, TeacherPrivilegeDetail
from ..dependencies import get_current_user, get_school_id

router = APIRouter()

def _get_school_mode(db: Session) -> str:
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
def list_assignments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _check_admin(current_user, allow_view=True)
    school_id = get_school_id(current_user)
    
    mode = _get_school_mode(db)
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
def create_assignment(payload: TeacherAssignmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _check_admin(current_user)
    school_id = get_school_id(current_user)
    
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

    if not db.query(ClassSection).filter(ClassSection.id == payload.class_section_id).first():
        raise HTTPException(status_code=404, detail="Class section not found")
    if not db.query(Semester).filter(Semester.id == payload.semester_id).first():
        raise HTTPException(status_code=404, detail="Semester not found")
        
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
def list_privileges(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _check_admin(current_user, allow_view=True)
    school_id = get_school_id(current_user)
    
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
        house_query = house_query.filter((House.school_id == school_id) | (House.school_id == 1) | (House.school_id.is_(None)))
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
def create_privilege(payload: TeacherPrivilegeCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
