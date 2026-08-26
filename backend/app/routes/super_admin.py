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
from ..models import School, User, Role, Student, Fee, Setting, Subject, SchoolStage, ConfigAuditLog, Program
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
    accredited_program_ids: Optional[List[int]] = None
    active_subject_ids: Optional[List[int]] = None

class SchoolStatusSchema(BaseModel):
    status: str  # ACTIVE, SUSPENDED

class SchoolAccreditationUpdateSchema(BaseModel):
    program_ids: Optional[List[int]] = None
    subject_ids: Optional[List[int]] = None

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
    for k, v in default_settings:
        db.add(Setting(school_id=new_school.id, key=k, value=v))

    # Bind accredited programs and active subjects
    if payload.active_subject_ids:
        active_subs = db.query(Subject).filter(Subject.id.in_(payload.active_subject_ids)).all()
        new_school.active_subjects = active_subs
    else:
        # Default auto-provisioning according to school_mode
        if new_school.school_mode == "SHS_ONLY":
            active_subs = db.query(Subject).filter(
                (Subject.school_level.in_(["SHS", "STEM"]) | (Subject.school_level == None)),
                ~Subject.code.ilike("%-BAS"),
                ~Subject.code.ilike("%-KG")
            ).all()
            new_school.active_subjects = active_subs
        elif new_school.school_mode == "BASIC_ONLY":
            active_subs = db.query(Subject).filter(
                (Subject.school_level.in_(["Basic", "KG"])) | (Subject.code.ilike("%-BAS")) | (Subject.code.ilike("%-KG"))
            ).all()
            new_school.active_subjects = active_subs

    if payload.accredited_program_ids:
        accredited_progs = db.query(Program).filter(Program.id.in_(payload.accredited_program_ids)).all()
        new_school.accredited_programs = accredited_progs

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

@router.get("/schools/{school_id}/accreditation")
def get_school_accreditation(
    school_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Returns the national master catalog categorized by learning area/track,
    along with the school's active subscribed subjects and accredited programs.
    """
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    active_subject_ids = [s.id for s in school.active_subjects]
    accredited_program_ids = [p.id for p in school.accredited_programs]

    all_subjects = db.query(Subject).order_by(Subject.name.asc()).all()
    all_programs = db.query(Program).order_by(Program.name.asc()).all()

    def categorize_subject(sub: Subject) -> str:
        name_lower = sub.name.lower()
        code_upper = (sub.code or "").upper()
        lvl_upper = (sub.school_level or "").upper()

        if lvl_upper in ["BASIC", "KG"] or code_upper.endswith("-BAS") or code_upper.endswith("-KG"):
            return "Basic School Common Core"
        if sub.is_core or sub.category == "Core" or code_upper.endswith("-CORE") or "core" in name_lower or code_upper in ["MATH-SHS", "ENG-SHS", "SOC-SHS", "GSCI-SHS", "PEH-SHS", "ROB-F2", "ICT-CORE"]:
            return "SHS Core Curriculum"
        # Cross-cutting electives shared across multiple programs
        if any(w == name_lower for w in ["elective mathematics", "additional mathematics", "economics", "geography", "chemistry", "biology", "general knowledge in art", "french (elective)", "arabic", "music"]) or code_upper in ["AMATH-SHS", "ECON-SHS", "GEO-SHS", "CHEM-SHS", "BIO-SHS", "GKA-SHS", "FRE-SHS", "ARAB-SHS", "MUS-SHS"]:
            return "🌐 Cross-Cutting / Multi-Track Electives"
        if any(w in name_lower for w in ["robotics", "artificial intelligence", "aviation", "cybersecurity", "engineering", "biomedical", "renewable", "lab-stem"]):
            return "STEM & Applied Technology"
        if any(w in name_lower for w in ["physics", "computer science", "ict (elective)"]):
            return "General Science"
        if any(w in name_lower for w in ["accounting", "business management", "cost", "clerical", "typewriting"]):
            return "Business"
        if any(w in name_lower for w in ["government", "history", "literature", "christian", "islamic"]):
            return "General Arts & Humanities"
        if any(w in name_lower for w in ["art and design", "design and communication", "graphic", "picture", "ceramics", "sculpture", "textiles", "leatherwork", "basketry"]):
            return "Visual Arts"
        if any(w in name_lower for w in ["management in living", "clothing and textiles", "food and nutrition", "catering", "garment", "cosmetology"]):
            return "Home Economics"
        if any(w in name_lower for w in ["agriculture", "animal husbandry", "crop husbandry", "fisheries", "forestry", "horticulture"]):
            return "Agricultural Science"
        if any(w in name_lower for w in ["applied technology", "applied electricity", "electronics", "auto", "refrigeration", "welding", "plumbing", "building", "woodwork", "metalwork", "technical drawing"]):
            return "Technical & TVET"
        return "General Electives"

    grouped_subjects = {}
    for sub in all_subjects:
        cat = categorize_subject(sub)
        if cat not in grouped_subjects:
            grouped_subjects[cat] = []
        is_active = sub.id in active_subject_ids if len(active_subject_ids) > 0 else (
            sub.school_level == school.school_mode or school.school_mode == "COMBINED" or (school.school_mode == "SHS_ONLY" and sub.school_level in ["SHS", "STEM"]) or (school.school_mode == "BASIC_ONLY" and sub.school_level == "Basic")
        )
        grouped_subjects[cat].append({
            "id": sub.id,
            "name": sub.name,
            "code": sub.code,
            "is_core": sub.is_core,
            "category": sub.category,
            "school_level": sub.school_level,
            "is_active_for_school": is_active
        })

    # Track presets mapping
    presets = {
        "science_stem": {
            "name": "🔬 Pure Science & STEM",
            "subject_names": [
                "Core Mathematics", "English Language (SHS)", "Social Studies (SHS)", "General Science (Core)", "PEH (Core)", "Robotics and Coding (Form 2)",
                "Physics", "Chemistry", "Biology", "Additional Mathematics", "Computer Science (Elective)", "ICT (Elective)", "Geography",
                "Engineering Science", "Robotics Engineering", "Artificial Intelligence & Data Science", "Renewable Energy Technology", "STEM Group C Lab Practical"
            ]
        },
        "business": {
            "name": "📊 Business & Finance",
            "subject_names": [
                "Core Mathematics", "English Language (SHS)", "Social Studies (SHS)", "General Science (Core)", "Information and Communication Technology (Core)", "PEH (Core)",
                "Business Management", "Financial Accounting", "Cost Accounting", "Economics", "Additional Mathematics", "Clerical Office Duties", "Typewriting & Keyboarding", "French (Elective)"
            ]
        },
        "general_arts": {
            "name": "📜 General Arts",
            "subject_names": [
                "Core Mathematics", "English Language (SHS)", "Social Studies (SHS)", "General Science (Core)", "Information and Communication Technology (Core)", "PEH (Core)",
                "Government", "History (SHS)", "Literature in English", "Christian Religious Studies", "Islamic Religious Studies", "Economics", "Geography", "French (Elective)", "Arabic", "Music", "Additional Mathematics"
            ]
        },
        "visual_arts": {
            "name": "🎨 Visual Arts",
            "subject_names": [
                "Core Mathematics", "English Language (SHS)", "Social Studies (SHS)", "General Science (Core)", "Information and Communication Technology (Core)", "PEH (Core)",
                "Art and Design Foundation", "Art and Design Studio", "Design and Communication", "General Knowledge in Art", "Graphic Design", "Picture Making", "Ceramics", "Sculpture", "Textiles", "Leatherwork", "Basketry", "Literature in English", "French (Elective)"
            ]
        },
        "home_economics": {
            "name": "🍳 Home Economics",
            "subject_names": [
                "Core Mathematics", "English Language (SHS)", "Social Studies (SHS)", "General Science (Core)", "Information and Communication Technology (Core)", "PEH (Core)",
                "Management in Living", "Clothing and Textiles", "Food and Nutrition", "General Knowledge in Art", "Biology", "Chemistry", "Catering & Hospitality", "Garment Making & Fashion", "Cosmetology & Beauty Therapy", "Economics", "French (Elective)"
            ]
        },
        "technical_tvet": {
            "name": "🛠️ Technical & TVET",
            "subject_names": [
                "Core Mathematics", "English Language (SHS)", "Social Studies (SHS)", "General Science (Core)", "Information and Communication Technology (Core)", "PEH (Core)",
                "Applied Technology", "Technical Drawing", "Applied Electricity", "Electronics", "Auto Mechanics", "Auto Electricals", "Refrigeration & Air Conditioning", "Mechanical Engineering Craft Practice", "Plumbing & Pipe Fitting", "Welding & Fabrication", "Building Construction", "Woodwork", "Metalwork", "Additional Mathematics", "Physics"
            ]
        },
        "agriculture": {
            "name": "🌱 Agricultural Science",
            "subject_names": [
                "Core Mathematics", "English Language (SHS)", "Social Studies (SHS)", "General Science (Core)", "Information and Communication Technology (Core)", "PEH (Core)",
                "General Agriculture", "Animal Husbandry", "Crop Husbandry & Horticulture", "Fisheries", "Forestry", "Horticulture", "Chemistry", "Biology", "Physics", "Geography"
            ]
        },
        "comprehensive_shs": {
            "name": "🌟 Comprehensive All-Track SHS",
            "subject_names": [s.name for s in all_subjects if (s.school_level in ["SHS", "STEM"] or s.school_level is None) and not (s.code or "").endswith("-BAS") and not (s.code or "").endswith("-KG")]
        }
    }

    # Map preset subject_names to subject IDs
    name_to_id = {s.name: s.id for s in all_subjects}
    preset_id_map = {}
    for key, pinfo in presets.items():
        preset_id_map[key] = {
            "name": pinfo["name"],
            "subject_ids": [name_to_id[name] for name in pinfo["subject_names"] if name in name_to_id]
        }

    return {
        "school_id": school.id,
        "school_name": school.name,
        "school_code": school.code,
        "school_mode": school.school_mode,
        "active_subject_ids": active_subject_ids,
        "accredited_program_ids": accredited_program_ids,
        "grouped_catalog": grouped_subjects,
        "presets": preset_id_map,
        "all_programs": [
            {
                "id": p.id,
                "name": p.name,
                "code": p.code,
                "is_accredited_for_school": p.id in accredited_program_ids if len(accredited_program_ids) > 0 else True
            }
            for p in all_programs
        ]
    }

@router.put("/schools/{school_id}/accreditation")
def update_school_accreditation(
    school_id: int,
    payload: SchoolAccreditationUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Updates the active subjects and accredited programs for a school.
    """
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    if payload.subject_ids is not None:
        target_subjects = db.query(Subject).filter(Subject.id.in_(payload.subject_ids)).all() if payload.subject_ids else []
        school.active_subjects = target_subjects

    if payload.program_ids is not None:
        target_programs = db.query(Program).filter(Program.id.in_(payload.program_ids)).all() if payload.program_ids else []
        school.accredited_programs = target_programs

    # Audit log
    audit = ConfigAuditLog(
        school_id=school_id,
        changed_by_user_id=current_user.id,
        change_type="ACCREDITATION_UPDATE",
        old_value="",
        new_value=f"Active Subjects: {len(school.active_subjects)}, Programs: {len(school.accredited_programs)}",
        notes=f"Updated accredited learning areas ({len(school.accredited_programs)} programs) and active subjects ({len(school.active_subjects)} subjects)."
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Accreditation updated: {len(school.active_subjects)} active subjects and {len(school.accredited_programs)} accredited programs.",
        "school_id": school.id,
        "active_subjects_count": len(school.active_subjects),
        "accredited_programs_count": len(school.accredited_programs)
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


class CloudSyncSchema(BaseModel):
    remote_url: str
    username: str = "superadmin"
    password: str
    sync_mode: str = "MIRROR"  # MIRROR or MERGE


@router.get("/export-all-schools")
def export_all_schools(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Exports a comprehensive JSON snapshot of ALL registered schools and their complete
    relational data (students, classes, subjects, staff, fees, attendance, scores).
    """
    from ..models import (
        SchoolStage, Department, Program, House, Dormitory, ClassSection,
        Subject, User, Student, StudentGuardian, StudentHealth, Fee, Payment,
        Attendance, Score, Setting, UniformItem
    )

    schools = db.query(School).all()
    exported_schools = []

    for s in schools:
        stages = db.query(SchoolStage).filter(SchoolStage.school_id == s.id).all()
        departments = db.query(Department).filter(Department.school_id == s.id).all()
        programs = db.query(Program).filter(Program.school_id == s.id).all()
        houses = db.query(House).filter(House.school_id == s.id).all()
        house_ids = [h.id for h in houses]
        dormitories = db.query(Dormitory).filter(Dormitory.house_id.in_(house_ids)).all() if house_ids else []
        classes = db.query(ClassSection).filter(ClassSection.school_id == s.id).all() if hasattr(ClassSection, 'school_id') else db.query(ClassSection).all()
        subjects = db.query(Subject).all()
        users = db.query(User).filter(User.school_id == s.id).all()
        students = db.query(Student).filter(Student.school_id == s.id).all()
        student_ids = [st.id for st in students]

        guardians = db.query(StudentGuardian).filter(StudentGuardian.student_id.in_(student_ids)).all() if student_ids else []
        health_records = db.query(StudentHealth).filter(StudentHealth.student_id.in_(student_ids)).all() if student_ids else []
        fees = db.query(Fee).filter(Fee.student_id.in_(student_ids)).all() if student_ids else []
        fee_ids = [f.id for f in fees]
        payments = db.query(Payment).filter(Payment.fee_id.in_(fee_ids)).all() if fee_ids else []
        attendances = db.query(Attendance).filter(Attendance.student_id.in_(student_ids)).all() if student_ids else []
        scores = db.query(Score).filter(Score.student_id.in_(student_ids)).all() if student_ids else []
        settings = db.query(Setting).filter(Setting.school_id == s.id).all()

        exported_schools.append({
            "school": {
                "name": s.name,
                "code": s.code,
                "school_mode": s.school_mode,
                "boarding_type": s.boarding_type,
                "status": s.status,
                "address": s.address,
                "phone": s.phone,
                "email": s.email,
                "logo_url": s.logo_url
            },
            "stages": [{"stage_type": st.stage_type, "is_active": st.is_active, "label": st.label} for st in stages],
            "departments": [{"name": d.name, "description": d.description} for d in departments],
            "programs": [{"name": p.name, "description": p.description} for p in programs],
            "houses": [{"name": h.name, "gender": h.gender, "house_type": getattr(h, 'house_type', 'BOARDING')} for h in houses],
            "dormitories": [{"name": d.name, "capacity": d.capacity, "house_name": d.house.name if d.house else None} for d in dormitories],
            "classes": [{"name": c.name, "level": c.level, "stage_type": getattr(c, 'stage_type', None)} for c in classes],
            "subjects": [{"name": sub.name, "code": sub.code, "is_core": sub.is_core, "category": sub.category, "school_level": getattr(sub, 'school_level', 'SHS')} for sub in subjects],
            "users": [
                {
                    "username": u.username,
                    "email": u.email,
                    "password_hash": u.password_hash,
                    "gender": u.gender,
                    "is_active": u.is_active,
                    "roles": [r.name for r in u.roles]
                }
                for u in users
            ],
            "students": [
                {
                    "student_code": st.student_code,
                    "full_name": st.full_name,
                    "first_name": st.first_name,
                    "last_name": st.last_name,
                    "other_names": getattr(st, 'other_names', None),
                    "gender": st.gender,
                    "date_of_birth": str(st.date_of_birth) if st.date_of_birth else None,
                    "class_name": st.class_section.name if st.class_section else None,
                    "house_name": st.house.name if st.house else None,
                    "dormitory_name": st.dormitory.name if st.dormitory else None,
                    "residential_status": st.residential_status,
                    "program_name": st.program_name,
                    "bece_index_number": st.bece_index_number,
                    "enrollment_status": getattr(st, 'enrollment_status', 'PLACED'),
                    "is_active": st.is_active
                }
                for st in students
            ],
            "guardians": [
                {
                    "student_code": g.student.student_code if g.student else None,
                    "guardian_name": g.guardian_name,
                    "relationship_type": g.relationship_type,
                    "primary_phone": g.primary_phone,
                    "alternative_phone": g.alternative_phone,
                    "occupation": g.occupation,
                    "residential_address": g.residential_address
                }
                for g in guardians
            ],
            "health_records": [
                {
                    "student_code": hr.student.student_code if hr.student else None,
                    "blood_group": hr.blood_group,
                    "allergies": hr.allergies,
                    "chronic_conditions": hr.chronic_conditions,
                    "emergency_contact": hr.emergency_contact
                }
                for hr in health_records
            ],
            "fees": [
                {
                    "student_code": f.student.student_code if f.student else None,
                    "amount_due": f.amount_due,
                    "amount_paid": f.amount_paid,
                    "term": f.term,
                    "academic_year": f.academic_year
                }
                for f in fees
            ],
            "payments": [
                {
                    "student_code": p.fee.student.student_code if p.fee and p.fee.student else None,
                    "amount": p.amount,
                    "payment_method": p.payment_method,
                    "receipt_number": p.receipt_number,
                    "payment_date": str(p.payment_date) if p.payment_date else None
                }
                for p in payments
            ],
            "attendances": [
                {
                    "student_code": a.student.student_code if a.student else None,
                    "date": str(a.date) if a.date else None,
                    "status": a.status,
                    "term": getattr(a, 'term', None),
                    "academic_year": getattr(a, 'academic_year', None)
                }
                for a in attendances
            ],
            "scores": [
                {
                    "student_code": sc.student.student_code if sc.student else None,
                    "subject_code": sc.subject.code if sc.subject else None,
                    "class_score": sc.class_score,
                    "exam_score": sc.exam_score,
                    "total_score": sc.total_score,
                    "grade": sc.grade,
                    "remarks": sc.remarks,
                    "term": sc.term,
                    "academic_year": sc.academic_year
                }
                for sc in scores
            ],
            "settings": {st.key: st.value for st in settings}
        })

    return {
        "status": "success",
        "exported_at": datetime.now().isoformat(),
        "total_schools": len(exported_schools),
        "schools": exported_schools
    }


@router.post("/sync-from-cloud")
def sync_from_cloud(
    payload: CloudSyncSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    1-Click Master Cloud Sync: Connects to live Render/Cloud instance via API,
    authenticates as Super-Admin, downloads all schools & entities, and synchronizes
    the local offline SQLite database seamlessly.
    """
    import urllib.request
    import urllib.error
    import json
    import ssl

    remote_base = payload.remote_url.strip().rstrip("/")
    if not remote_base.startswith("http://") and not remote_base.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid Remote Cloud URL. Must start with http:// or https://")

    # SSL Context that works reliably across environments
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # 1. Authenticate with Remote Server
    login_url = f"{remote_base}/api/auth/login"
    login_data = json.dumps({
        "username": payload.username,
        "password": payload.password
    }).encode("utf-8")

    req = urllib.request.Request(
        login_url,
        data=login_data,
        headers={"Content-Type": "application/json", "User-Agent": "eduManage360-LocalSync/4.6"}
    )

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
            login_resp = json.loads(resp.read().decode("utf-8"))
            access_token = login_resp.get("access_token")
            if not access_token:
                raise HTTPException(status_code=400, detail="Remote server did not return an access token.")
    except urllib.error.HTTPError as e:
        err_msg = f"Remote authentication failed (HTTP {e.code}). Please verify your Super-Admin password."
        try:
            body = json.loads(e.read().decode("utf-8"))
            if "detail" in body:
                err_msg = f"Remote authentication error: {body['detail']}"
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=err_msg)
    except urllib.error.URLError as e:
        raise HTTPException(status_code=502, detail=f"Cannot reach remote cloud server at {remote_base}: {str(e.reason)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to remote server: {str(e)}")

    # 2. Fetch Complete Master Export from Remote Server
    export_url = f"{remote_base}/api/super-admin/export-all-schools"
    req_export = urllib.request.Request(
        export_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "eduManage360-LocalSync/4.6"
        }
    )

    try:
        with urllib.request.urlopen(req_export, context=ctx, timeout=45) as resp:
            export_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=e.code, detail=f"Failed to retrieve data from remote server (HTTP {e.code})")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading data snapshot: {str(e)}")

    remote_schools = export_data.get("schools", [])

    # 3. Apply Sync into Local SQLite Database
    from ..models import (
        Base, SchoolStage, Department, Program, House, Dormitory, ClassSection,
        Subject, User, Role, Student, StudentGuardian, StudentHealth, Fee, Payment,
        Attendance, Score, Setting, UniformItem
    )

    total_imported_students = 0
    total_imported_users = 0

    try:
        if payload.sync_mode.upper() == "MIRROR":
            # Wipe local tenant tables while retaining roles and superadmin
            for table in reversed(Base.metadata.sorted_tables):
                if table.name in ['roles', 'user_roles']:
                    continue
                if table.name == 'users':
                    db.execute(table.delete().where(table.c.username != 'superadmin'))
                else:
                    db.execute(table.delete())

        # Cache available roles
        roles_by_name = {r.name: r for r in db.query(Role).all()}

        for s_data in remote_schools:
            sc_info = s_data.get("school", {})
            school = School(
                name=sc_info.get("name"),
                code=sc_info.get("code"),
                school_mode=sc_info.get("school_mode", "COMBINED"),
                boarding_type=sc_info.get("boarding_type", "BOARDING_AND_DAY"),
                status=sc_info.get("status", "ACTIVE"),
                address=sc_info.get("address"),
                phone=sc_info.get("phone"),
                email=sc_info.get("email"),
                logo_url=sc_info.get("logo_url")
            )
            db.add(school)
            db.flush()

            # Stages
            for stg in s_data.get("stages", []):
                db.add(SchoolStage(
                    school_id=school.id,
                    stage_type=stg.get("stage_type"),
                    is_active=stg.get("is_active", True),
                    label=stg.get("label")
                ))

            # Departments
            dept_map = {}
            for dept in s_data.get("departments", []):
                d_obj = Department(name=dept["name"], description=dept.get("description"), school_id=school.id)
                db.add(d_obj)
                db.flush()
                dept_map[dept["name"]] = d_obj.id

            # Programs
            for prog in s_data.get("programs", []):
                db.add(Program(name=prog["name"], description=prog.get("description"), school_id=school.id))

            # Houses & Dormitories
            house_map = {}
            for h in s_data.get("houses", []):
                h_obj = House(
                    name=h["name"],
                    gender=h.get("gender", "Mixed"),
                    house_type=h.get("house_type", "BOARDING"),
                    school_id=school.id
                )
                db.add(h_obj)
                db.flush()
                house_map[h["name"]] = h_obj.id

            dorm_map = {}
            for d in s_data.get("dormitories", []):
                h_id = house_map.get(d.get("house_name"))
                if h_id:
                    d_obj = Dormitory(name=d["name"], capacity=d.get("capacity", 30), house_id=h_id)
                    db.add(d_obj)
                    db.flush()
                    dorm_map[d["name"]] = d_obj.id

            # Classes
            class_map = {}
            for c in s_data.get("classes", []):
                c_kwargs = {"name": c["name"], "level": c.get("level", "SHS 1")}
                if hasattr(ClassSection, 'stage_type'):
                    c_kwargs["stage_type"] = c.get("stage_type")
                if hasattr(ClassSection, 'school_id'):
                    c_kwargs["school_id"] = school.id
                c_obj = ClassSection(**c_kwargs)
                db.add(c_obj)
                db.flush()
                class_map[c["name"]] = c_obj.id

            # Subjects
            subject_map = {}
            for sub in s_data.get("subjects", []):
                existing_sub = db.query(Subject).filter(Subject.code == sub.get("code")).first()
                if not existing_sub:
                    sub_kwargs = {
                        "name": sub["name"],
                        "code": sub["code"],
                        "is_core": sub.get("is_core", True),
                        "category": sub.get("category", "Core")
                    }
                    if hasattr(Subject, 'school_level'):
                        sub_kwargs["school_level"] = sub.get("school_level", "SHS")
                    existing_sub = Subject(**sub_kwargs)
                    db.add(existing_sub)
                    db.flush()
                subject_map[sub["code"]] = existing_sub.id

            # Users
            for u in s_data.get("users", []):
                if u["username"] == "superadmin":
                    continue
                user_obj = User(
                    username=u["username"],
                    email=u.get("email"),
                    password_hash=u.get("password_hash"),
                    gender=u.get("gender"),
                    is_active=u.get("is_active", True),
                    school_id=school.id
                )
                for r_name in u.get("roles", []):
                    if r_name in roles_by_name:
                        user_obj.roles.append(roles_by_name[r_name])
                db.add(user_obj)
                total_imported_users += 1

            # Students
            student_map = {}
            for st in s_data.get("students", []):
                st_obj = Student(
                    student_code=st["student_code"],
                    full_name=st["full_name"],
                    first_name=st.get("first_name"),
                    last_name=st.get("last_name"),
                    gender=st.get("gender", "Male"),
                    date_of_birth=st.get("date_of_birth"),
                    class_section_id=class_map.get(st.get("class_name")),
                    house_id=house_map.get(st.get("house_name")),
                    dormitory_id=dorm_map.get(st.get("dormitory_name")),
                    residential_status=st.get("residential_status", "Day"),
                    program_name=st.get("program_name"),
                    bece_index_number=st.get("bece_index_number"),
                    is_active=st.get("is_active", True),
                    school_id=school.id
                )
                if hasattr(Student, 'enrollment_status'):
                    st_obj.enrollment_status = st.get("enrollment_status", "PLACED")
                db.add(st_obj)
                db.flush()
                student_map[st["student_code"]] = st_obj.id
                total_imported_students += 1

            # Guardians
            for g in s_data.get("guardians", []):
                st_id = student_map.get(g.get("student_code"))
                if st_id:
                    db.add(StudentGuardian(
                        student_id=st_id,
                        guardian_name=g["guardian_name"],
                        relationship_type=g.get("relationship_type", "Parent"),
                        primary_phone=g.get("primary_phone", "0000000000"),
                        alternative_phone=g.get("alternative_phone"),
                        occupation=g.get("occupation"),
                        residential_address=g.get("residential_address")
                    ))

            # Health Records
            for hr in s_data.get("health_records", []):
                st_id = student_map.get(hr.get("student_code"))
                if st_id:
                    db.add(StudentHealth(
                        student_id=st_id,
                        blood_group=hr.get("blood_group"),
                        allergies=hr.get("allergies"),
                        chronic_conditions=hr.get("chronic_conditions"),
                        emergency_contact=hr.get("emergency_contact")
                    ))

            # Fees & Payments
            fee_map = {}
            for f in s_data.get("fees", []):
                st_id = student_map.get(f.get("student_code"))
                if st_id:
                    f_obj = Fee(
                        student_id=st_id,
                        amount_due=f.get("amount_due", 0.0),
                        amount_paid=f.get("amount_paid", 0.0),
                        term=f.get("term", "Term 1"),
                        academic_year=f.get("academic_year", "2025/2026")
                    )
                    db.add(f_obj)
                    db.flush()
                    fee_map[f.get("student_code")] = f_obj.id

            for p in s_data.get("payments", []):
                f_id = fee_map.get(p.get("student_code"))
                if f_id:
                    db.add(Payment(
                        fee_id=f_id,
                        amount=p.get("amount", 0.0),
                        payment_method=p.get("payment_method", "Cash"),
                        receipt_number=p.get("receipt_number", "REC-001")
                    ))

            # Attendance
            for a in s_data.get("attendances", []):
                st_id = student_map.get(a.get("student_code"))
                if st_id:
                    a_kwargs = {
                        "student_id": st_id,
                        "status": a.get("status", "Present")
                    }
                    if hasattr(Attendance, 'term'):
                        a_kwargs["term"] = a.get("term", "Term 1")
                    if hasattr(Attendance, 'academic_year'):
                        a_kwargs["academic_year"] = a.get("academic_year", "2025/2026")
                    db.add(Attendance(**a_kwargs))

            # Scores
            for sc in s_data.get("scores", []):
                st_id = student_map.get(sc.get("student_code"))
                sub_id = subject_map.get(sc.get("subject_code"))
                if st_id and sub_id:
                    db.add(Score(
                        student_id=st_id,
                        subject_id=sub_id,
                        class_score=sc.get("class_score", 0.0),
                        exam_score=sc.get("exam_score", 0.0),
                        total_score=sc.get("total_score", 0.0),
                        grade=sc.get("grade", "A"),
                        remarks=sc.get("remarks", "Good"),
                        term=sc.get("term", "Term 1"),
                        academic_year=sc.get("academic_year", "2025/2026")
                    ))

            # Settings
            for k, v in s_data.get("settings", {}).items():
                db.add(Setting(key=k, value=str(v), school_id=school.id))

        db.commit()

        return {
            "status": "success",
            "message": f"Successfully synchronized {len(remote_schools)} school(s) and {total_imported_students} student(s) from cloud.",
            "synced_schools": len(remote_schools),
            "imported_students": total_imported_students,
            "imported_users": total_imported_users,
            "remote_url": remote_base
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database synchronization error: {str(e)}")

