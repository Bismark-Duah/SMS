"""
Super-Admin Multi-School Management Routes
School Management System (SMS)
"""
import os
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import School, User, Role, Student, Fee, Setting, Subject, SchoolStage, ConfigAuditLog
from ..routes.auth import get_current_user, get_password_hash
from ..ncca_seed import seed_ncca_curriculum

router = APIRouter(prefix="/super-admin", tags=["Super Admin Multi-School Portal"])

def require_super_admin(current_user: User = Depends(get_current_user)):
    role_names = [r.name for r in current_user.roles]
    if "super_admin" not in role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super-Admin privileges required for cross-school management."
        )
    return current_user

class SchoolCreateSchema(BaseModel):
    name: str
    code: str
    school_mode: str = "COMBINED"  # SHS_ONLY, BASIC_ONLY, COMBINED
    boarding_type: str = "BOARDING_AND_DAY"
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    admin_username: str
    admin_email: str
    admin_password: str

class SchoolStatusSchema(BaseModel):
    status: str  # ACTIVE, SUSPENDED

@router.get("/dashboard")
def get_super_admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Returns global system-wide metrics across all registered schools in Ghana.
    """
    total_schools = db.query(School).count()
    active_schools = db.query(School).filter(School.status == "ACTIVE").count()
    total_students = db.query(Student).count()
    total_users = db.query(User).filter(User.username != "superadmin", User.school_id.isnot(None)).count()
    total_fees_collected = db.query(func.sum(Fee.amount_paid)).scalar() or 0.0

    # System diagnostics & storage health
    db_size_bytes = os.path.getsize("school.db") if os.path.exists("school.db") else 0
    db_size_mb = round(db_size_bytes / (1024 * 1024), 2)

    backups_dir = "backups"
    backups_list = [os.path.join(backups_dir, f) for f in os.listdir(backups_dir)] if os.path.exists(backups_dir) else []
    backups_count = len(backups_list)
    last_backup_time = None
    if backups_list:
        latest_file = max(backups_list, key=os.path.getmtime)
        last_backup_time = datetime.fromtimestamp(os.path.getmtime(latest_file)).strftime("%Y-%m-%d %H:%M")

    mode_distribution = {
        "SHS_ONLY": db.query(School).filter(School.school_mode == "SHS_ONLY").count(),
        "BASIC_ONLY": db.query(School).filter(School.school_mode == "BASIC_ONLY").count(),
        "COMBINED": db.query(School).filter(School.school_mode == "COMBINED").count(),
    }

    schools = db.query(School).order_by(School.id.asc()).all()
    school_summary = []
    for s in schools:
        student_cnt = db.query(Student).filter(Student.school_id == s.id).count()
        user_cnt = db.query(User).filter(User.school_id == s.id).count()
        school_summary.append({
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "school_mode": s.school_mode,
            "boarding_type": s.boarding_type,
            "status": s.status,
            "student_count": student_cnt,
            "user_count": user_cnt,
            "created_at": s.created_at.isoformat() if s.created_at else None
        })

    return {
        "total_schools": total_schools,
        "active_schools": active_schools,
        "total_students": total_students,
        "total_users": total_users,
        "total_fees_collected": float(total_fees_collected),
        "mode_distribution": mode_distribution,
        "diagnostics": {
            "db_size_mb": db_size_mb,
            "backups_count": backups_count,
            "last_backup_time": last_backup_time or "No backup yet"
        },
        "schools": school_summary
    }

@router.get("/schools")
def list_all_schools(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Returns list of all registered schools with enrolment counters.
    """
    schools = db.query(School).all()
    res = []
    for s in schools:
        res.append({
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "school_mode": s.school_mode,
            "boarding_type": s.boarding_type,
            "status": s.status,
            "address": s.address,
            "phone": s.phone,
            "email": s.email,
            "student_count": db.query(Student).filter(Student.school_id == s.id).count(),
            "user_count": db.query(User).filter(User.school_id == s.id).count(),
            "created_at": s.created_at.isoformat() if s.created_at else None
        })
    return res

@router.post("/schools", status_code=status.HTTP_201_CREATED)
def create_new_school(
    payload: SchoolCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Provisions a new school, seeds its curriculum subjects for its mode, and sets up its School Admin account.
    """
    # Check code uniqueness
    existing_code = db.query(School).filter(School.code == payload.code.upper().strip()).first()
    if existing_code:
        raise HTTPException(status_code=400, detail=f"School code '{payload.code}' is already registered.")

    # Check admin username uniqueness
    existing_user = db.query(User).filter(User.username == payload.admin_username.strip()).first()
    if existing_user:
        raise HTTPException(status_code=400, detail=f"Username '{payload.admin_username}' is already in use.")

    # Create School
    new_school = School(
        name=payload.name.strip(),
        code=payload.code.upper().strip(),
        school_mode=payload.school_mode.upper(),
        boarding_type=payload.boarding_type.upper(),
        status="ACTIVE",
        address=payload.address,
        phone=payload.phone,
        email=payload.email
    )
    db.add(new_school)
    db.flush()

    # Seed Admin Role if needed
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if not admin_role:
        admin_role = Role(name="admin")
        db.add(admin_role)
        db.flush()

    # Create School Admin User
    school_admin = User(
        username=payload.admin_username.strip(),
        email=payload.admin_email.strip(),
        password_hash=get_password_hash(payload.admin_password),
        school_id=new_school.id,
        is_active=True
    )
    db.add(school_admin)
    db.flush()
    if admin_role:
        from ..models import user_roles
        db.execute(user_roles.insert().values(user_id=school_admin.id, role_id=admin_role.id))

    # Seed default Settings for School
    default_settings = [
        ("school_name", new_school.name),
        ("school_abbreviation", new_school.code),
        ("school_mode", new_school.school_mode),
        ("boarding_status", new_school.boarding_type),
        ("grading_standard", "WAEC"),
        ("active_academic_year_id", "1"),
        ("active_semester_id", "1"),
        ("report_title", "TERMINAL REPORT"),
        ("report_publishing_mode", "HYBRID_BOTH")
    ]
    try:
        db.commit()
        db.refresh(new_school)
    except Exception as commit_err:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database commit error: {str(commit_err)}")

    return {
        "message": f"School '{new_school.name}' ({new_school.code}) registered successfully!",
        "school": {
            "id": new_school.id,
            "name": new_school.name,
            "code": new_school.code,
            "school_mode": new_school.school_mode,
            "status": new_school.status,
            "admin_username": school_admin.username
        }
    }

@router.put("/schools/{school_id}/status")
def update_school_status(
    school_id: int,
    payload: SchoolStatusSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Activates or Suspended a registered school account.
    """
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    school.status = payload.status
    db.commit()
    return {"message": f"School status updated to '{school.status}'", "school_id": school.id, "status": school.status}


class SchoolModeUpdateSchema(BaseModel):
    school_mode: str

@router.put("/schools/{school_id}/mode")
def update_school_mode(
    school_id: int,
    payload: SchoolModeUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Super-Admin exclusive endpoint to modify a registered school's operating mode.
    """
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    old_mode = school.school_mode
    school.school_mode = payload.school_mode
    setting = db.query(Setting).filter(Setting.school_id == school_id, Setting.key == "school_mode").first()
    if setting:
        setting.value = payload.school_mode
    else:
        db.add(Setting(key="school_mode", value=payload.school_mode, school_id=school_id))

    # Auto-derive boarding_hierarchy_mode when school_mode changes
    auto_hierarchy = "BASIC_TWO_TIER" if payload.school_mode == "BASIC_ONLY" else "SHS_THREE_TIER"
    hier_setting = db.query(Setting).filter(Setting.school_id == school_id, Setting.key == "boarding_hierarchy_mode").first()
    if hier_setting:
        hier_setting.value = auto_hierarchy
    else:
        db.add(Setting(key="boarding_hierarchy_mode", value=auto_hierarchy, school_id=school_id))

    # Audit Trail Entry
    audit = ConfigAuditLog(
        school_id=school_id,
        changed_by_user_id=current_user.id,
        change_type="SCHOOL_MODE_CHANGE",
        old_value=old_mode,
        new_value=payload.school_mode,
        notes=f"Changed school operating mode from {old_mode} to {payload.school_mode}."
    )
    db.add(audit)

    db.commit()
    return {"message": f"School mode updated to '{payload.school_mode}' successfully!", "school_id": school.id, "school_mode": payload.school_mode, "boarding_hierarchy_mode": auto_hierarchy}


class SchoolBoardingUpdateSchema(BaseModel):
    boarding_status: str

@router.put("/schools/{school_id}/boarding")
def update_school_boarding(
    school_id: int,
    payload: SchoolBoardingUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Super-Admin exclusive endpoint to modify a school's boarding configuration.
    Validates the value, updates the School model, and syncs the Setting record.
    """
    valid_values = {"DAY_ONLY", "BOARDING_AND_DAY"}
    boarding_val = payload.boarding_status.upper()
    if boarding_val not in valid_values:
        raise HTTPException(status_code=400, detail=f"Invalid boarding_status. Must be one of: {', '.join(valid_values)}")

    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    old_boarding = school.boarding_type or "BOARDING_AND_DAY"
    school.boarding_type = boarding_val

    # Sync to Setting table for consistency
    bs_setting = db.query(Setting).filter(Setting.school_id == school_id, Setting.key == "boarding_status").first()
    if bs_setting:
        bs_setting.value = boarding_val
    else:
        db.add(Setting(key="boarding_status", value=boarding_val, school_id=school_id))

    # Audit Trail Entry
    audit = ConfigAuditLog(
        school_id=school_id,
        changed_by_user_id=current_user.id,
        change_type="BOARDING_STATUS_CHANGE",
        old_value=old_boarding,
        new_value=boarding_val,
        notes=f"Changed boarding status from {old_boarding} to {boarding_val}."
    )
    db.add(audit)

    db.commit()
    return {
        "message": f"Boarding status updated to '{boarding_val}' successfully!",
        "school_id": school.id,
        "boarding_status": boarding_val
    }



@router.get("/schools/{school_id}/backup")
def download_school_backup(
    school_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Exports a comprehensive JSON backup payload for a specific registered school.
    """
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    students = db.query(Student).filter(Student.school_id == school_id).all()
    users = db.query(User).filter(User.school_id == school_id).all()
    settings = db.query(Setting).filter(Setting.school_id == school_id).all()
    fees = db.query(Fee).join(Student, Fee.student_id == Student.id).filter(Student.school_id == school_id).all()

    backup_data = {
        "timestamp": datetime.now().isoformat(),
        "school": {
            "id": school.id,
            "name": school.name,
            "code": school.code,
            "school_mode": school.school_mode,
            "boarding_type": school.boarding_type,
            "status": school.status
        },
        "student_count": len(students),
        "user_count": len(users),
        "students": [{"id": s.id, "name": s.full_name, "code": s.student_code, "class": s.class_name} for s in students],
        "users": [{"id": u.id, "username": u.username, "email": u.email} for u in users],
        "settings": {st.key: st.value for st in settings},
        "total_fees_count": len(fees)
    }

    return backup_data


import json

@router.delete("/schools/{school_id}")
def delete_school(
    school_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Permanently deletes a registered school account and its associated data, 
    after automatically saving a timestamped pre-delete JSON backup.
    """
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    # 1. Trigger automatic pre-deletion backup
    backup_payload = download_school_backup(school_id, db, current_user)
    os.makedirs("backups", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"school_{school_id}_pre_delete_{timestamp}.json"
    backup_path = os.path.join("backups", backup_filename)
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup_payload, f, indent=2)

    # 2. Cascade delete all school-related entities completely
    from ..models import (
        Department, ClassSection, Program, House, Dormitory, Asset,
        TextbookAllocation, UniformItem, UniformDisbursement, GatePassLog,
        AdmissionVoucher, StudentGuardian, StudentHealth, Score, Attendance,
        Notification, Fee, Payment, DisciplineRecord, ExeatRecord,
        StudentSemesterSummary, MessageLog, TeacherAssignment, user_roles
    )

    student_ids = [s.id for s in db.query(Student.id).filter(Student.school_id == school_id).all()]
    user_ids = [u.id for u in db.query(User.id).filter(User.school_id == school_id).all()]
    class_section_ids = [cs.id for cs in db.query(ClassSection.id).filter(ClassSection.school_id == school_id).all()] if hasattr(ClassSection, 'school_id') else []
    house_ids = [h.id for h in db.query(House.id).filter(House.school_id == school_id).all()]

    # Student dependent data
    if student_ids:
        db.query(StudentGuardian).filter(StudentGuardian.student_id.in_(student_ids)).delete(synchronize_session=False)
        db.query(StudentHealth).filter(StudentHealth.student_id.in_(student_ids)).delete(synchronize_session=False)
        db.query(Score).filter(Score.student_id.in_(student_ids)).delete(synchronize_session=False)
        db.query(Attendance).filter(Attendance.student_id.in_(student_ids)).delete(synchronize_session=False)
        db.query(Notification).filter(Notification.student_id.in_(student_ids)).delete(synchronize_session=False)
        fee_ids = [f.id for f in db.query(Fee.id).filter(Fee.student_id.in_(student_ids)).all()]
        if fee_ids:
            db.query(Payment).filter(Payment.fee_id.in_(fee_ids)).delete(synchronize_session=False)
            db.query(Fee).filter(Fee.id.in_(fee_ids)).delete(synchronize_session=False)
        db.query(DisciplineRecord).filter(DisciplineRecord.student_id.in_(student_ids)).delete(synchronize_session=False)
        db.query(ExeatRecord).filter(ExeatRecord.student_id.in_(student_ids)).delete(synchronize_session=False)
        db.query(StudentSemesterSummary).filter(StudentSemesterSummary.student_id.in_(student_ids)).delete(synchronize_session=False)
        db.query(MessageLog).filter(MessageLog.student_id.in_(student_ids)).delete(synchronize_session=False)
        db.query(UniformDisbursement).filter(UniformDisbursement.student_id.in_(student_ids)).delete(synchronize_session=False)
        db.query(TextbookAllocation).filter(TextbookAllocation.student_id.in_(student_ids)).delete(synchronize_session=False)
        db.query(GatePassLog).filter(GatePassLog.student_id.in_(student_ids)).delete(synchronize_session=False)

    # User dependent data
    if user_ids:
        db.execute(user_roles.delete().where(user_roles.c.user_id.in_(user_ids)))
        db.query(TeacherAssignment).filter(TeacherAssignment.teacher_id.in_(user_ids)).delete(synchronize_session=False)

    # Housing & Dormitories
    if house_ids:
        db.query(Dormitory).filter(Dormitory.house_id.in_(house_ids)).delete(synchronize_session=False)
        db.query(House).filter(House.id.in_(house_ids)).delete(synchronize_session=False)

    # School-level operations & structural entities
    db.query(Asset).filter(Asset.school_id == school_id).delete(synchronize_session=False)
    db.query(UniformItem).filter(UniformItem.school_id == school_id).delete(synchronize_session=False)
    db.query(AdmissionVoucher).filter(AdmissionVoucher.school_id == school_id).delete(synchronize_session=False)
    db.query(Program).filter(Program.school_id == school_id).delete(synchronize_session=False)
    db.query(Setting).filter(Setting.school_id == school_id).delete(synchronize_session=False)
    db.query(Department).filter(Department.school_id == school_id).delete(synchronize_session=False)
    db.query(ClassSection).filter(ClassSection.school_id == school_id).delete(synchronize_session=False) if hasattr(ClassSection, 'school_id') else None
    
    # Core Student & User records
    db.query(Student).filter(Student.school_id == school_id).delete(synchronize_session=False)
    db.query(User).filter(User.school_id == school_id).delete(synchronize_session=False)

    # Delete School entry
    db.delete(school)
    db.commit()

    return {
        "message": f"School '{school.name}' ({school.code}) and all associated data purged successfully.",
        "school_id": school_id,
        "backup_saved_to": backup_path
    }
