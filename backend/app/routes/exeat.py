from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List, Optional
from datetime import datetime

from ..database import get_db
from ..models import ExeatRecord, Student, House, Dormitory, User, Role, Setting
from ..schemas import ExeatCreate, ExeatUpdate, ExeatResponse, ExeatStats
from ..dependencies import get_current_user, get_school_id

router = APIRouter()

def _check_overdue_exeats(db: Session):
    """Automatically update status of departed exeats past expected return to Overdue."""
    now = datetime.now()
    overdue_exeats = db.query(ExeatRecord).filter(
        ExeatRecord.status == "Departed",
        ExeatRecord.expected_return < now
    ).all()
    for ex in overdue_exeats:
        ex.status = "Overdue"
    if overdue_exeats:
        db.commit()

def _get_user_jurisdiction(db: Session, user: User):
    """
    Returns user role classification and list of house_ids/student_genders they can manage.
    """
    roles = [r.name.lower() for r in user.roles]
    username_lower = user.username.lower()
    
    # Check master admin roles
    is_master_admin = any(r in roles for r in ["admin", "headmaster", "assistant_head_domestic", "assistant head domestic"]) or \
                      "domestic" in username_lower or "admin" in username_lower

    # Check Senior House Master (Boys) and Senior House Mistress (Girls)
    is_shm_boys = any(r in roles for r in ["senior_house_master", "senior house master", "shm_boys"]) or \
                 "senior house master" in username_lower or "shm" in username_lower
    is_shm_girls = any(r in roles for r in ["senior_house_mistress", "senior house mistress", "shm_girls"]) or \
                  "senior house mistress" in username_lower or "shmistress" in username_lower

    # Find specific houses where this user is assigned
    houses = db.query(House).filter(
        or_(
            House.house_master_id == user.id,
            House.assistant_house_master_id == user.id,
            House.senior_in_charge_id == user.id,
            House.house_master_girls_id == user.id,
            House.assistant_house_master_girls_id == user.id,
            House.senior_in_charge_girls_id == user.id
        )
    ).all()
    allowed_house_ids = [h.id for h in houses]

    # Find specific dormitories where this user is assigned
    dorms = db.query(Dormitory).filter(Dormitory.housemaster_id == user.id).all()
    allowed_dorm_ids = [d.id for d in dorms]

    primary_role_label = "Staff"
    if is_master_admin:
        primary_role_label = "Administrator / Domestic Head"
    elif is_shm_boys:
        primary_role_label = "Senior House Master (Boys)"
    elif is_shm_girls:
        primary_role_label = "Senior House Mistress (Girls)"
    elif allowed_house_ids:
        house_obj = houses[0]
        primary_role_label = f"House Master - {house_obj.name}"

    return {
        "is_master_admin": is_master_admin,
        "is_shm_boys": is_shm_boys,
        "is_shm_girls": is_shm_girls,
        "allowed_house_ids": allowed_house_ids,
        "allowed_dorm_ids": allowed_dorm_ids,
        "primary_role_label": primary_role_label
    }

def _can_user_access_student(db: Session, user: User, student: Student) -> bool:
    """Validate if logged in user has authority over the given student's exeat."""
    jurisdiction = _get_user_jurisdiction(db, user)
    
    if jurisdiction["is_master_admin"]:
        return True
    
    # Parent can access own children
    if student.parent_id == user.id:
        return True

    # Check student gender / house gender for Senior House Masters
    student_gender = (student.gender or "").lower()
    
    if jurisdiction["is_shm_boys"]:
        if student_gender in ["male", "m", "boy"]:
            return True
        if student.house and (student.house.gender or "").lower() in ["male", "boys"]:
            return True

    if jurisdiction["is_shm_girls"]:
        if student_gender in ["female", "f", "girl"]:
            return True
        if student.house and (student.house.gender or "").lower() in ["female", "girls"]:
            return True

    # Check specific house assignment
    if student.house_id and student.house_id in jurisdiction["allowed_house_ids"]:
        return True

    # Check specific dormitory assignment
    if student.dormitory_id and student.dormitory_id in jurisdiction["allowed_dorm_ids"]:
        return True

    return False


def _format_exeat_response(ex: ExeatRecord, db: Session) -> ExeatResponse:
    student = ex.student
    student_name = student.full_name if student else "Unknown Student"
    student_code = student.student_code if student else "N/A"
    class_name = student.class_name if student else None
    house_name = student.house.name if (student and student.house) else None
    dorm_name = student.dormitory.name if (student and student.dormitory) else None
    gender = student.gender if student else None

    created_by_name = ex.created_by.username if ex.created_by else "System"
    approved_by_name = ex.approved_by.username if ex.approved_by else None
    gate_out_name = ex.gate_out_by.username if ex.gate_out_by else None
    gate_in_name = ex.gate_in_by.username if ex.gate_in_by else None

    approved_by_role = None
    if ex.approved_by:
        jur = _get_user_jurisdiction(db, ex.approved_by)
        approved_by_role = jur["primary_role_label"]

    return ExeatResponse(
        id=ex.id,
        student_id=ex.student_id,
        student_name=student_name,
        student_code=student_code,
        class_name=class_name,
        house_id=student.house_id if student else None,
        house_name=house_name,
        dormitory_name=dorm_name,
        gender=gender,
        exeat_type=ex.exeat_type,
        reason=ex.reason,
        destination=ex.destination,
        expected_departure=ex.expected_departure,
        expected_return=ex.expected_return,
        actual_departure=ex.actual_departure,
        actual_return=ex.actual_return,
        parent_contact=ex.parent_contact or (student.phone if student else None),
        parent_approved=ex.parent_approved,
        status=ex.status,
        created_by_name=created_by_name,
        approved_by_name=approved_by_name,
        approved_by_role=approved_by_role,
        gate_out_by_name=gate_out_name,
        gate_in_by_name=gate_in_name,
        approval_notes=ex.approval_notes,
        created_at=ex.created_at or datetime.now(),
        updated_at=ex.updated_at or datetime.now()
    )


@router.get("/", response_model=List[ExeatResponse])
def list_exeats(
    status: Optional[str] = None,
    exeat_type: Optional[str] = None,
    house_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_overdue_exeats(db)
    school_id = get_school_id(current_user)
    jur = _get_user_jurisdiction(db, current_user)

    query = db.query(ExeatRecord).join(Student, ExeatRecord.student_id == Student.id)
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)

    if not jur["is_master_admin"]:
        conditions = []
        if current_user.roles and any(r.name == "parent" for r in current_user.roles):
            conditions.append(Student.parent_id == current_user.id)
        
        if jur["is_shm_boys"]:
            conditions.append(or_(Student.gender.ilike("male"), Student.gender.ilike("boy"), Student.gender.ilike("m")))
        elif jur["is_shm_girls"]:
            conditions.append(or_(Student.gender.ilike("female"), Student.gender.ilike("girl"), Student.gender.ilike("f")))
        
        if jur["allowed_house_ids"]:
            conditions.append(Student.house_id.in_(jur["allowed_house_ids"]))
        
        if jur["allowed_dorm_ids"]:
            conditions.append(Student.dormitory_id.in_(jur["allowed_dorm_ids"]))

        if conditions:
            query = query.filter(or_(*conditions))

    if status:
        query = query.filter(ExeatRecord.status.ilike(status))
    
    if exeat_type:
        query = query.filter(ExeatRecord.exeat_type.ilike(exeat_type))

    if house_id:
        query = query.filter(Student.house_id == house_id)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Student.full_name.ilike(search_pattern),
                Student.student_code.ilike(search_pattern),
                ExeatRecord.destination.ilike(search_pattern),
                ExeatRecord.reason.ilike(search_pattern)
            )
        )

    exeats = query.order_by(ExeatRecord.id.desc()).all()
    return [_format_exeat_response(ex, db) for ex in exeats]


@router.get("/stats", response_model=ExeatStats)
def get_exeat_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_overdue_exeats(db)
    school_id = get_school_id(current_user)
    jur = _get_user_jurisdiction(db, current_user)

    query = db.query(ExeatRecord).join(Student, ExeatRecord.student_id == Student.id)
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)

    if not jur["is_master_admin"]:
        conditions = []
        if current_user.roles and any(r.name == "parent" for r in current_user.roles):
            conditions.append(Student.parent_id == current_user.id)
        if jur["is_shm_boys"]:
            conditions.append(or_(Student.gender.ilike("male"), Student.gender.ilike("boy"), Student.gender.ilike("m")))
        elif jur["is_shm_girls"]:
            conditions.append(or_(Student.gender.ilike("female"), Student.gender.ilike("girl"), Student.gender.ilike("f")))
        if jur["allowed_house_ids"]:
            conditions.append(Student.house_id.in_(jur["allowed_house_ids"]))
        if jur["allowed_dorm_ids"]:
            conditions.append(Student.dormitory_id.in_(jur["allowed_dorm_ids"]))
        if conditions:
            query = query.filter(or_(*conditions))

    all_exeats = query.all()

    currently_away = sum(1 for e in all_exeats if e.status in ["Departed", "Overdue"])
    pending_approvals = sum(1 for e in all_exeats if e.status == "Pending")
    overdue_returns = sum(1 for e in all_exeats if e.status == "Overdue")
    total_this_term = len(all_exeats)

    return ExeatStats(
        currently_away=currently_away,
        pending_approvals=pending_approvals,
        overdue_returns=overdue_returns,
        total_this_term=total_this_term
    )


@router.post("/", response_model=ExeatResponse)
def create_exeat(
    payload: ExeatCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    student = db.query(Student).filter(Student.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if not _can_user_access_student(db, current_user, student):
        raise HTTPException(
            status_code=403,
            detail=f"Access Denied: You do not have permission to issue an exeat for {student.full_name}. You can only manage exeats for students in your assigned house or jurisdiction."
        )

    jur = _get_user_jurisdiction(db, current_user)
    
    # Load boarding hierarchy mode
    setting_hierarchy = db.query(Setting).filter(Setting.key == "boarding_hierarchy_mode").first()
    hierarchy_mode = setting_hierarchy.value if setting_hierarchy else "SHS_THREE_TIER"

    if hierarchy_mode == "BASIC_TWO_TIER":
        initial_status = "Approved" if jur["is_master_admin"] else "Pending"
    else:
        initial_status = "Approved" if (jur["is_master_admin"] or jur["is_shm_boys"] or jur["is_shm_girls"] or jur["allowed_house_ids"]) else "Pending"

    parent_contact = payload.parent_contact or student.phone

    new_exeat = ExeatRecord(
        student_id=student.id,
        exeat_type=payload.exeat_type,
        reason=payload.reason,
        destination=payload.destination,
        expected_departure=payload.expected_departure,
        expected_return=payload.expected_return,
        parent_contact=parent_contact,
        parent_approved=payload.parent_approved,
        status=initial_status,
        created_by_id=current_user.id,
        approved_by_id=current_user.id if initial_status == "Approved" else None,
        approval_notes=payload.approval_notes
    )

    db.add(new_exeat)
    db.commit()
    db.refresh(new_exeat)

    return _format_exeat_response(new_exeat, db)


@router.put("/{exeat_id}/approve", response_model=ExeatResponse)
def approve_exeat(
    exeat_id: int,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ex = db.query(ExeatRecord).filter(ExeatRecord.id == exeat_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Exeat record not found")

    jur = _get_user_jurisdiction(db, current_user)
    
    # Load boarding hierarchy mode
    setting_hierarchy = db.query(Setting).filter(Setting.key == "boarding_hierarchy_mode").first()
    hierarchy_mode = setting_hierarchy.value if setting_hierarchy else "SHS_THREE_TIER"

    if hierarchy_mode == "BASIC_TWO_TIER":
        if not jur["is_master_admin"]:
            raise HTTPException(status_code=403, detail="Access Denied: Only Headmaster/Assistant Head can approve exeat in simple boarding hierarchy mode.")
    else:
        if not _can_user_access_student(db, current_user, ex.student):
            raise HTTPException(
                status_code=403,
                detail="Access Denied: You do not have house permission to approve this exeat."
            )

    ex.status = "Approved"
    ex.approved_by_id = current_user.id
    if notes:
        ex.approval_notes = notes
    db.commit()
    db.refresh(ex)

    return _format_exeat_response(ex, db)


@router.put("/{exeat_id}/reject", response_model=ExeatResponse)
def reject_exeat(
    exeat_id: int,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ex = db.query(ExeatRecord).filter(ExeatRecord.id == exeat_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Exeat record not found")

    if not _can_user_access_student(db, current_user, ex.student):
        raise HTTPException(
            status_code=403,
            detail="Access Denied: You do not have house permission to reject this exeat."
        )

    ex.status = "Rejected"
    ex.approved_by_id = current_user.id
    if notes:
        ex.approval_notes = notes
    db.commit()
    db.refresh(ex)

    return _format_exeat_response(ex, db)


@router.put("/{exeat_id}/sign-out", response_model=ExeatResponse)
def gate_sign_out(
    exeat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ex = db.query(ExeatRecord).filter(ExeatRecord.id == exeat_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Exeat record not found")

    if ex.status not in ["Approved", "Pending"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot sign out student. Exeat status is currently '{ex.status}' (Must be Approved)."
        )

    ex.status = "Departed"
    ex.actual_departure = datetime.now()
    ex.gate_out_by_id = current_user.id
    db.commit()
    db.refresh(ex)

    return _format_exeat_response(ex, db)


@router.put("/{exeat_id}/sign-in", response_model=ExeatResponse)
def gate_sign_in(
    exeat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ex = db.query(ExeatRecord).filter(ExeatRecord.id == exeat_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Exeat record not found")

    if ex.status not in ["Departed", "Overdue"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot sign in student. Student status is '{ex.status}' (Must be Departed or Overdue)."
        )

    ex.status = "Returned"
    ex.actual_return = datetime.now()
    ex.gate_in_by_id = current_user.id
    db.commit()
    db.refresh(ex)

    return _format_exeat_response(ex, db)


@router.get("/{exeat_id}/slip")
def get_exeat_slip(
    exeat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ex = db.query(ExeatRecord).filter(ExeatRecord.id == exeat_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Exeat record not found")

    return _format_exeat_response(ex, db)


# ── Gate Security Scanner & Incident Reporting ──────────────────────────────

@router.post("/gate-verify")
def gate_verify_pass(
    payload: GateVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    code = payload.student_code_or_index.strip().lower()
    school_id = get_school_id(current_user)
    
    stud_query = db.query(Student).filter(
        or_(
            func.lower(Student.student_code) == code,
            func.lower(Student.full_name).contains(code)
        )
    )
    if school_id is not None:
        stud_query = stud_query.filter(Student.school_id == school_id)
    student = stud_query.first()
    
    if not student:
        return {
            "is_valid": False,
            "status": "NOT_FOUND",
            "message": f"🔴 GATE PASS DENIED: No student record found for '{payload.student_code_or_index}'."
        }
        
    # Check exeat record
    exeat = db.query(ExeatRecord).filter(
        ExeatRecord.student_id == student.id,
        ExeatRecord.status.in_(["Approved", "Departed", "Overdue"])
    ).order_by(ExeatRecord.id.desc()).first()
    
    class_name = student.class_section.name if student.class_section else "N/A"
    
    if not exeat:
        return {
            "is_valid": False,
            "student_id": student.id,
            "student_name": student.full_name,
            "student_code": student.student_code,
            "class_name": class_name,
            "status": "NO_EXEAT",
            "message": f"🔴 GATE PASS DENIED: {student.full_name} ({student.student_code}) has no active approved exeat."
        }
        
    is_valid = exeat.status in ["Approved", "Departed"]
    msg_prefix = "🟢 GATE PASS APPROVED & VALID" if exeat.status == "Approved" else ("🟡 STUDENT ALREADY DEPARTED" if exeat.status == "Departed" else "🔴 OVERDUE RETURN DETECTED")
    
    return {
        "is_valid": is_valid,
        "exeat_id": exeat.id,
        "student_id": student.id,
        "student_name": student.full_name,
        "student_code": student.student_code,
        "class_name": class_name,
        "exeat_type": exeat.exeat_type,
        "destination": exeat.destination,
        "expected_departure": exeat.expected_departure.strftime("%Y-%m-%d %H:%M") if exeat.expected_departure else "",
        "expected_return": exeat.expected_return.strftime("%Y-%m-%d %H:%M") if exeat.expected_return else "",
        "status": exeat.status,
        "message": f"{msg_prefix} for {student.full_name}."
    }

@router.post("/security-incident")
def report_security_incident(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    student_id = payload.get("student_id")
    incident_type = payload.get("incident_type", "Curfew / Gate Violation")
    description = payload.get("description", "Student attempted to leave campus without valid exeat slip.")
    
    if not student_id:
        raise HTTPException(status_code=400, detail="student_id is required")
        
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    from ..models import DisciplineRecord
    record = DisciplineRecord(
        student_id=student_id,
        incident_type=incident_type,
        description=f"[Security Officer Gate Alert] {description}",
        action_taken="Escalated to Assistant Head (Domestic)",
        recorded_by=current_user.id,
        parent_notified=True
    )
    db.add(record)
    db.commit()
    return {"status": "success", "message": "Security incident logged and escalated to Assistant Head Domestic."}
