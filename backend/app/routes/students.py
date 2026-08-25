from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session
from typing import Optional
import csv
import io
from datetime import datetime
from ..database import get_db
from ..models import Student, TeacherAssignment, User, ClassSection, Program, Setting, SchoolStage, StudentHealth, School
from ..schemas import StudentCreate
from ..dependencies import get_current_user, get_school_id, get_user_assigned_scope
from ..services.guardian_service import auto_link_guardian_for_student, auto_link_all_guardians
from ..services.allocation import allocate_student_house_and_dorm

router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _check_admin(current_user: User):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    role_names = [r.name.lower() for r in current_user.roles] if hasattr(current_user, 'roles') and current_user.roles else []
    admin_roles = {
        "admin", "super_admin", "headmaster", "headmistress",
        "assistant_headmaster_academic", "assistant_head_academic",
        "assistant_headmaster_admin", "assistant_head_admin"
    }
    if not any(r in admin_roles for r in role_names):
        raise HTTPException(status_code=403, detail="Only administrators can add, import, or delete student records.")

def _check_student_write_permission(current_user: User, student_class_id: Optional[int] = None, db: Session = None):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    role_names = [r.name.lower() for r in current_user.roles] if hasattr(current_user, 'roles') and current_user.roles else []
    admin_roles = {
        "admin", "super_admin", "headmaster", "headmistress",
        "assistant_headmaster_academic", "assistant_head_academic",
        "assistant_headmaster_admin", "assistant_head_admin"
    }
    if any(r in admin_roles for r in role_names):
        return
    scope = get_user_assigned_scope(current_user, db)
    if student_class_id and student_class_id in scope["class_ids"]:
        return
    raise HTTPException(status_code=403, detail="You can only manage student records for classes assigned to you.")


def _get_school_mode(db: Session, school_id: Optional[int] = None) -> str:
    if school_id:
        sch = db.query(School).filter(School.id == school_id).first()
        if sch and sch.school_mode:
            return sch.school_mode
    setting = db.query(Setting).filter(Setting.key == "school_mode").first()
    return setting.value if setting and setting.value else "COMBINED"


def _get_boarding_status(db: Session, school_id: Optional[int] = None) -> str:
    """Returns the boarding_status for the given school. Defaults to BOARDING_AND_DAY."""
    if school_id:
        sch = db.query(School).filter(School.id == school_id).first()
        if sch and sch.boarding_type:
            return sch.boarding_type.upper()
    setting = db.query(Setting).filter(Setting.key == "boarding_status").first()
    return setting.value.upper() if setting and setting.value else "BOARDING_AND_DAY"

def _student_dict(s: Student) -> dict:
    hp = s.health_profile
    return {
        "id": s.id,
        "student_code": s.student_code,
        "full_name": s.full_name,
        "class_section_id": s.class_section_id,
        "class_name": s.class_section.name if s.class_section else None,
        "program_id": s.program_id,
        "program_name": s.program.name if s.program else None,
        "parent_id": s.parent_id,
        "parent_username": s.parent.username if s.parent else None,
        "form": s.form,
        "gender": s.gender,
        "date_of_birth": str(s.date_of_birth)[:10] if s.date_of_birth else None,
        "address": s.address,
        "phone": s.phone,
        "guardian_name": s.guardian_name,
        "is_active": s.is_active if s.is_active is not None else True,
        "status": getattr(s, "status", "ACTIVE") or "ACTIVE",
        "created_at": str(s.created_at) if s.created_at else None,
        "house_id": s.house_id,
        "house_name": s.house.name if s.house else None,
        "dormitory_id": s.dormitory_id,
        "dormitory_name": s.dormitory.name if s.dormitory else None,
        "bece_index_number": s.bece_index_number,
        "enrolment_code": s.enrolment_code,
        "bece_raw_score": s.bece_raw_score,
        "bece_aggregate": s.bece_aggregate,
        "jhs_attended": s.jhs_attended,
        "residential_status": s.residential_status,
        "school_id": s.school_id,
        "school_name": s.school.name if s.school else None,
        "blood_group": hp.blood_group if hp else None,
        "allergies": hp.allergies if hp else None,
        "chronic_conditions": hp.chronic_conditions if hp else None,
        "pe_limitations": hp.pe_limitations if hp else None,
        "emergency_contact": hp.emergency_contact if hp else None,
        "doctor_clearance_status": hp.doctor_clearance_status if hp else True,
    }


# ── GET / — List Students ──────────────────────────────────────────────────────

@router.get("/")
def list_students(
    class_id: Optional[int] = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    mode = _get_school_mode(db, school_id)
    query = db.query(Student)

    # ── Multi-tenancy: scope to current school ──────────────────────────────
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)

    if mode == "BASIC_ONLY":
        query = query.outerjoin(ClassSection, Student.class_section_id == ClassSection.id)\
                     .outerjoin(SchoolStage, ClassSection.stage_id == SchoolStage.id)\
                     .filter((SchoolStage.school_type == "Basic") | (Student.school_type == "Basic") | (Student.class_section_id == None))
    elif mode == "SHS_ONLY":
        query = query.outerjoin(ClassSection, Student.class_section_id == ClassSection.id)\
                     .outerjoin(SchoolStage, ClassSection.stage_id == SchoolStage.id)\
                     .filter((SchoolStage.school_type == "SHS") | (Student.school_type == "SHS") | (Student.school_type == None) | (Student.class_section_id == None))

    if not include_inactive:
        query = query.filter(Student.is_active == True)

    # ── Role-based data scoping ─────────────────────────────────────────────
    scope = get_user_assigned_scope(current_user, db)
    if not scope["is_admin"]:
        role_names = [r.name.lower() for r in current_user.roles] if hasattr(current_user, 'roles') else []
        if "parent" in role_names:
            query = query.filter(Student.parent_id == current_user.id)
        else:
            filters = []
            if scope["class_ids"]:
                filters.append(Student.class_section_id.in_(scope["class_ids"]))
            if scope["house_ids"]:
                filters.append(Student.house_id.in_(scope["house_ids"]))
            if filters:
                from sqlalchemy import or_
                query = query.filter(or_(*filters))
            else:
                # User has no assigned classes or houses -> return empty
                return []

    if class_id and isinstance(class_id, int):
        query = query.filter(Student.class_section_id == class_id)

    try:
        students = query.order_by(Student.full_name).all()
        return [_student_dict(s) for s in students]
    except Exception as e:
        print("Error in list_students query:", e)
        return []



# ── GET /{id} — Student Profile ───────────────────────────────────────────────

@router.get("/{student_id}")
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(Student).filter(Student.id == student_id)
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)
    student = query.first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    return _student_dict(student)


# ── POST / — Create Student ───────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_student(
    student: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_admin(current_user)
    school_id = get_school_id(current_user)
    existing = db.query(Student).filter(Student.student_code == student.student_code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Student code '{student.student_code}' already exists.",
        )

    dob = None
    if student.date_of_birth:
        try:
            dob = datetime.strptime(student.date_of_birth, "%Y-%m-%d")
        except ValueError:
            pass

    db_student = Student(
        student_code=student.student_code,
        full_name=student.full_name,
        class_section_id=student.class_section_id,
        program_id=student.program_id,
        parent_id=student.parent_id,
        form=student.form,
        gender=student.gender,
        date_of_birth=dob,
        address=student.address,
        phone=student.phone,
        guardian_name=student.guardian_name,
        house_id=student.house_id,
        dormitory_id=student.dormitory_id,
        bece_index_number=student.bece_index_number,
        enrolment_code=student.enrolment_code,
        bece_raw_score=student.bece_raw_score,
        bece_aggregate=student.bece_aggregate,
        jhs_attended=getattr(student, 'jhs_attended', None),
        residential_status=student.residential_status or "B",
        school_id=school_id,
    )

    # ── DAY_ONLY Enforcement ──────────────────────────────────────────────────
    # Backend-level policy: override client-submitted values for DAY_ONLY schools.
    # This cannot be circumvented by direct API calls.
    boarding_status = _get_boarding_status(db, school_id)
    if boarding_status == "DAY_ONLY":
        db_student.residential_status = "D"   # Force to Day
        db_student.house_id = None            # No boarding house
        db_student.dormitory_id = None        # No dormitory

    db.add(db_student)
    db.flush()


    # Auto-allocate House & Dormitory if missing
    allocate_student_house_and_dorm(db, db_student)

    auto_link_guardian_for_student(db, db_student, auto_create=True)

    # Save StudentHealth profile
    if any([student.blood_group, student.allergies, student.chronic_conditions, student.pe_limitations, student.emergency_contact]):
        health = StudentHealth(
            student_id=db_student.id,
            blood_group=student.blood_group,
            allergies=student.allergies,
            chronic_conditions=student.chronic_conditions,
            pe_limitations=student.pe_limitations,
            emergency_contact=student.emergency_contact or student.phone,
            doctor_clearance_status=student.doctor_clearance_status if student.doctor_clearance_status is not None else True
        )
        db.add(health)

    db.commit()
    db.refresh(db_student)
    return _student_dict(db_student)


# ── PUT /{id} — Update Student ────────────────────────────────────────────────

@router.put("/{student_id}")
def update_student(
    student_id: int,
    student: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(Student).filter(Student.id == student_id)
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)
    db_student = query.first()
    if not db_student:
        raise HTTPException(status_code=404, detail="Student not found.")

    _check_student_write_permission(current_user, db_student.class_section_id, db)

    dob = None
    if student.date_of_birth:
        try:
            dob = datetime.strptime(student.date_of_birth, "%Y-%m-%d")
        except ValueError:
            pass

    db_student.student_code = student.student_code
    db_student.full_name = student.full_name
    db_student.class_section_id = student.class_section_id
    db_student.program_id = student.program_id
    db_student.parent_id = student.parent_id
    db_student.form = student.form
    db_student.gender = student.gender
    db_student.date_of_birth = dob
    db_student.address = student.address
    db_student.phone = student.phone
    db_student.guardian_name = student.guardian_name
    db_student.house_id = student.house_id
    db_student.dormitory_id = student.dormitory_id
    db_student.bece_index_number = student.bece_index_number
    db_student.enrolment_code = student.enrolment_code
    db_student.bece_raw_score = student.bece_raw_score
    db_student.bece_aggregate = student.bece_aggregate
    db_student.jhs_attended = student.jhs_attended
    # ── DAY_ONLY Enforcement ─────────────────────────────────────────────────
    # Backend enforces residential status regardless of frontend submission
    boarding_status = _get_boarding_status(db, school_id)
    if boarding_status == "DAY_ONLY":
        db_student.residential_status = "D"
        db_student.house_id = None
        db_student.dormitory_id = None
    else:
        db_student.residential_status = student.residential_status

    auto_link_guardian_for_student(db, db_student, auto_create=True)

    # Update or create health profile
    health = db.query(StudentHealth).filter(StudentHealth.student_id == db_student.id).first()
    if not health:
        health = StudentHealth(student_id=db_student.id)
        db.add(health)
    
    health.blood_group = student.blood_group
    health.allergies = student.allergies
    health.chronic_conditions = student.chronic_conditions
    health.pe_limitations = student.pe_limitations
    health.emergency_contact = student.emergency_contact or student.phone
    if student.doctor_clearance_status is not None:
        health.doctor_clearance_status = student.doctor_clearance_status

    db.commit()
    db.refresh(db_student)
    return _student_dict(db_student)


# ── DELETE /{id} — Soft-Delete Student ───────────────────────────────────────

@router.delete("/{student_id}")
def deactivate_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_admin(current_user)
    school_id = get_school_id(current_user)
    query = db.query(Student).filter(Student.id == student_id)
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)
    db_student = query.first()
    if not db_student:
        raise HTTPException(status_code=404, detail="Student not found.")

    db_student.is_active = False
    db_student.status = "INACTIVE"
    db.commit()
    return {"message": f"Student {db_student.full_name} has been deactivated."}


# ── POST /auto-link-guardians — Bulk Auto Link ────────────────────────────────

@router.post("/auto-link-guardians")
def auto_link_guardians_endpoint(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _check_admin(current_user)
    stats = auto_link_all_guardians(db)
    return {"status": "success", "data": stats}


# ── POST /{id}/link-parent ────────────────────────────────────────────────────

@router.post("/{student_id}/link-parent")
def link_parent(student_id: int, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _check_admin(current_user)
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    student.parent_id = payload.get("parent_id")
    db.commit()
    return {"message": "Parent linked successfully"}


# ── POST /import-csv ──────────────────────────────────────────────────────────

@router.post("/import-csv")
async def import_students_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_admin(current_user)
    school_id = get_school_id(current_user)
    content = await file.read()
    decoded = content.decode("utf-8")
    stream = io.StringIO(decoded)
    reader = csv.DictReader(stream)

    imported_count = 0
    errors = []

    for row in reader:
        try:
            db_student = Student(
                full_name=row.get("full_name"),
                student_code=row.get("student_code"),
                class_section_id=int(row["class_section_id"]) if row.get("class_section_id") else None,
                program_id=int(row["program_id"]) if row.get("program_id") else None,
                form=int(row["form"]) if row.get("form") else None,
                gender=row.get("gender"),
                guardian_name=row.get("guardian_name"),
                phone=row.get("phone"),
                address=row.get("address"),
                school_id=school_id,
            )
            db.add(db_student)
            db.flush()
            auto_link_guardian_for_student(db, db_student, auto_create=True)
            imported_count += 1
        except Exception as e:
            errors.append(f"Row {reader.line_num}: {str(e)}")

    db.commit()
    return {"status": "success", "imported": imported_count, "errors": errors}

