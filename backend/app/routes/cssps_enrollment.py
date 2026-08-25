import csv
import io
import re
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models import Student, StudentGuardian, StudentHealth, Program, House, ClassSection, User
from ..schemas import CSSPSEnrollmentCreate
from ..services.allocation import allocate_student_house_and_dorm
from ..dependencies import get_current_user, get_school_id

router = APIRouter(prefix="/api/cssps", tags=["CSSPS Enrollment"])

@router.post("/enroll", status_code=status.HTTP_201_CREATED)
def enroll_student(data: CSSPSEnrollmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    school_id = get_school_id(current_user)
    clean_bece = data.bece_index_number.strip()
    # Validate 12-char BECE Index Number
    if len(clean_bece) != 12:
        raise HTTPException(
            status_code=400,
            detail="BECE Index Number must be exactly 12 characters (10-digit candidate index + 2-digit exam year)."
        )

    # Check uniqueness of bece_index_number
    ex_index = db.query(Student).filter(Student.bece_index_number == clean_bece).first()
    if ex_index:
        raise HTTPException(
            status_code=400,
            detail=f"Student with BECE Index Number '{clean_bece}' is already enrolled."
        )

    # Check uniqueness of enrolment_code if provided
    clean_code = data.enrolment_code.strip() if data.enrolment_code else f"CSSPS-{clean_bece}"
    ex_code = db.query(Student).filter(Student.enrolment_code == clean_code).first()
    if ex_code:
        raise HTTPException(
            status_code=400,
            detail=f"Quick Enrolment Code '{clean_code}' has already been used."
        )

    # Construct full name
    mid = f" {data.middle_name.strip()}" if data.middle_name and data.middle_name.strip() else ""
    full_name = f"{data.first_name.strip()}{mid} {data.last_name.strip()}"

    # Auto-generate student_code
    student_code = f"SHS-{clean_bece}"

    # Parse date_of_birth if present
    dob = None
    if data.date_of_birth:
        try:
            dob = datetime.strptime(data.date_of_birth, "%Y-%m-%d")
        except ValueError:
            pass

    # Resolve class_section if possible (Form 1 of assigned program)
    class_sec_id = None
    if data.program_id:
        form1_sec = db.query(ClassSection).filter(ClassSection.program_id == data.program_id).first()
        if form1_sec:
            class_sec_id = form1_sec.id

    # Create Student record
    student = Student(
        student_code=student_code,
        full_name=full_name,
        first_name=data.first_name.strip(),
        middle_name=data.middle_name.strip() if data.middle_name else None,
        last_name=data.last_name.strip(),
        bece_index_number=clean_bece,
        enrolment_code=clean_code,
        bece_raw_score=data.bece_raw_score,
        bece_aggregate=data.bece_aggregate,
        jhs_attended=data.jhs_attended,
        residential_status=data.residential_status.upper() if data.residential_status else "B",
        enrollment_status="Fully Registered",
        school_type="SHS",
        form=1,
        gender=data.gender,
        date_of_birth=dob,
        program_id=data.program_id,
        class_section_id=class_sec_id,
        house_id=data.house_id,
        guardian_name=data.guardian_name,
        phone=data.primary_phone,
        address=data.residential_address,
        school_id=school_id
    )
    db.add(student)
    db.flush()

    # Auto-allocate House & Dormitory if not provided
    allocate_student_house_and_dorm(db, student)

    # Create Primary Guardian
    guardian = StudentGuardian(
        student_id=student.id,
        guardian_name=data.guardian_name,
        relationship_type="Parent/Guardian",
        primary_phone=data.primary_phone,
        alternative_phone=data.alternative_phone,
        residential_address=data.residential_address
    )
    db.add(guardian)

    # Create Health Profile
    health = StudentHealth(
        student_id=student.id,
        blood_group=data.blood_group,
        allergies=data.allergies,
        chronic_conditions=data.medical_conditions,
        pe_limitations=data.pe_limitations,
        emergency_contact=data.emergency_contact or data.primary_phone,
        doctor_clearance_status=data.doctor_clearance_status if data.doctor_clearance_status is not None else True
    )
    db.add(health)

    db.commit()
    db.refresh(student)

    return {
        "message": "Student successfully enrolled via CSSPS placement verification!",
        "student_id": student.id,
        "student_code": student.student_code,
        "full_name": student.full_name,
        "bece_index_number": student.bece_index_number,
        "enrolment_code": student.enrolment_code,
        "residential_status": student.residential_status,
        "enrollment_status": student.enrollment_status
    }

@router.get("/verify/{index_number}")
def verify_bece_index(index_number: str, db: Session = Depends(get_db)):
    clean_idx = index_number.strip()
    student = db.query(Student).filter(Student.bece_index_number == clean_idx).first()
    if student:
        return {
            "is_enrolled": True,
            "student_id": student.id,
            "full_name": student.full_name,
            "bece_aggregate": student.bece_aggregate,
            "residential_status": student.residential_status
        }
    return {"is_enrolled": False, "message": "Index number is available for enrollment."}

@router.post("/import-csv", status_code=status.HTTP_201_CREATED)
async def import_cssps_csv(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    school_id = get_school_id(current_user)
    content = await file.read()
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = content.decode("latin-1", errors="replace")

    lines = [l for l in decoded.splitlines() if l.strip()]
    if not lines:
        return {"status": "error", "imported": 0, "skipped": 0, "total": 0, "errors": ["Uploaded file is empty."]}

    # Auto-detect delimiter (comma, semicolon, or tab)
    first_line = lines[0]
    delimiter = ","
    if ";" in first_line and first_line.count(";") > first_line.count(","):
        delimiter = ";"
    elif "\t" in first_line and first_line.count("\t") > first_line.count(","):
        delimiter = "\t"

    stream = io.StringIO(decoded)
    raw_reader = csv.DictReader(stream, delimiter=delimiter)

    imported_count = 0
    skipped_count = 0
    errors = []

    programs_by_name = {p.name.lower(): p.id for p in db.query(Program).all()}
    programs_by_code = {p.code.lower(): p.id for p in db.query(Program).all() if p.code}

    # Enterprise Column Aliases
    BECE_INDEX_ALIASES = [
        "bece_index_number", "index_number", "bece_index", "index_no", "indexno",
        "index_num", "index", "candidate_index", "candidate_index_number",
        "bece_reg_no", "candidate_no", "jhs_index", "student_index",
        "bece_index_no", "index_number_10_digits", "index_number_12_digits",
        "bece_id", "candidate_id"
    ]
    ENROL_CODE_ALIASES = [
        "enrolment_code", "enrollment_code", "code", "admission_code",
        "placement_code", "enrol_code", "quick_code"
    ]
    FIRST_NAME_ALIASES = ["first_name", "firstname", "first", "given_name"]
    MIDDLE_NAME_ALIASES = ["middle_name", "middlename", "middle", "other_names", "other_name"]
    LAST_NAME_ALIASES = ["last_name", "lastname", "surname", "family_name"]
    FULL_NAME_ALIASES = ["full_name", "fullname", "name", "student_name", "candidate_name", "student"]
    GENDER_ALIASES = ["gender", "sex"]
    DOB_ALIASES = ["date_of_birth", "dob", "birth_date", "birthdate"]
    RAW_SCORE_ALIASES = ["bece_raw_score", "raw_score", "score", "total_score"]
    AGGREGATE_ALIASES = ["bece_aggregate", "aggregate", "agg", "best_6", "best_six", "bece_agg"]
    JHS_ALIASES = ["jhs_attended", "jhs", "junior_high", "school_attended", "previous_school", "jhs_name"]
    PROGRAM_ALIASES = ["program_name", "program", "course", "programme", "programme_name", "stream"]
    RESIDENTIAL_ALIASES = ["residential_status", "res_status", "residential", "status_res", "boarding_status", "residence", "res_type"]
    GUARDIAN_ALIASES = ["guardian_name", "parent_name", "guardian", "parent", "father_name", "mother_name", "next_of_kin"]
    PHONE_ALIASES = ["primary_phone", "phone", "phone_number", "contact", "mobile", "telephone", "guardian_phone", "cell_phone"]
    ALT_PHONE_ALIASES = ["alternative_phone", "alt_phone", "emergency_phone", "other_phone", "phone2", "alt_contact"]
    ADDRESS_ALIASES = ["address", "residential_address", "home_address", "location", "residence_address", "postal_address"]
    CLASS_ALIASES = ["class_name", "class", "section", "class_section", "assigned_class"]

    def get_val(row_dict, aliases, default=""):
        for alias in aliases:
            if alias in row_dict and row_dict[alias] is not None:
                val_str = str(row_dict[alias]).strip()
                if val_str:
                    return val_str
        return default

    line_num = 1
    for raw_row in raw_reader:
        line_num += 1
        if not raw_row or not any(v for v in raw_row.values() if v and str(v).strip()):
            continue

        # Clean and normalize dictionary keys (strip BOM, quotes, non-alphanumeric to underscores)
        row = {}
        for k, v in raw_row.items():
            if k is not None:
                clean_k = re.sub(r'[^a-z0-9_]', '_', k.strip().lstrip('\ufeff').replace('"', '').replace("'", "").strip().lower())
                clean_k = re.sub(r'_+', '_', clean_k).strip('_')
                row[clean_k] = v.strip() if isinstance(v, str) else v

        bece_idx = get_val(row, BECE_INDEX_ALIASES)
        if isinstance(bece_idx, str):
            bece_idx = bece_idx.strip()

        # Handle scientific notation conversion from Excel (e.g. 1.00E+11)
        if "e+" in str(bece_idx).lower():
            try:
                bece_idx = str(int(float(bece_idx)))
            except ValueError:
                pass

        # Clean digits - BECE index numbers must be numeric
        clean_digits = "".join(filter(str.isdigit, str(bece_idx)))
        bece_idx = clean_digits

        if not bece_idx or len(bece_idx) < 8 or len(bece_idx) > 20:
            errors.append(f"Row {line_num}: Invalid or missing BECE Index Number '{bece_idx}'")
            skipped_count += 1
            continue

        student_code = f"SHS-{bece_idx}"

        # Check existing student in database
        existing = db.query(Student).filter(
            (Student.bece_index_number == bece_idx) | (Student.student_code == student_code)
        ).first()
        if existing:
            errors.append(f"Row {line_num}: Candidate '{existing.full_name}' (Index: {bece_idx}) is already enrolled.")
            skipped_count += 1
            continue

        # Isolate every row in a database savepoint so an error never breaks subsequent rows
        try:
            with db.begin_nested():
                enrol_code = get_val(row, ENROL_CODE_ALIASES, f"CSSPS-{bece_idx}")
                # Ensure enrolment code uniqueness
                if db.query(Student).filter(Student.enrolment_code == enrol_code).first():
                    enrol_code = f"CSSPS-{bece_idx}-{uuid.uuid4().hex[:4].upper()}"

                first_name = get_val(row, FIRST_NAME_ALIASES)
                middle_name = get_val(row, MIDDLE_NAME_ALIASES)
                last_name = get_val(row, LAST_NAME_ALIASES)
                full_name_raw = get_val(row, FULL_NAME_ALIASES)

                if not first_name and not last_name and full_name_raw:
                    parts = full_name_raw.split()
                    if len(parts) >= 2:
                        first_name = parts[0]
                        last_name = parts[-1]
                        middle_name = " ".join(parts[1:-1])
                    else:
                        first_name = parts[0] if parts else "Candidate"
                        last_name = ""

                full_name = f"{first_name} {middle_name} {last_name}".replace("  ", " ").strip()
                if not full_name:
                    full_name = f"CSSPS Candidate {bece_idx}"

                gender_raw = get_val(row, GENDER_ALIASES, "Male").upper()
                if gender_raw.startswith("F"):
                    gender = "Female"
                else:
                    gender = "Male"

                dob = None
                dob_str = get_val(row, DOB_ALIASES)
                if dob_str:
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                        try:
                            dob = datetime.strptime(dob_str, fmt)
                            break
                        except ValueError:
                            pass

                raw_score_str = get_val(row, RAW_SCORE_ALIASES)
                raw_score = int(raw_score_str) if raw_score_str.isdigit() else None

                agg_str = get_val(row, AGGREGATE_ALIASES)
                aggregate = int(agg_str) if agg_str.isdigit() else None

                jhs = get_val(row, JHS_ALIASES)

                prog_str = get_val(row, PROGRAM_ALIASES).lower()
                prog_id = programs_by_name.get(prog_str) or programs_by_code.get(prog_str)
                if not prog_id:
                    prog_id_raw = row.get("program_id")
                    if prog_id_raw and str(prog_id_raw).isdigit():
                        prog_id = int(prog_id_raw)

                if not prog_id and prog_str:
                    if "tech" in prog_str:
                        prog_id = programs_by_name.get("technical") or programs_by_name.get("applied technology")
                    elif "sci" in prog_str:
                        prog_id = programs_by_name.get("general science")
                    elif "art" in prog_str:
                        prog_id = programs_by_name.get("general arts")
                    elif "bus" in prog_str:
                        prog_id = programs_by_name.get("business")
                    elif "home" in prog_str or "econ" in prog_str:
                        prog_id = programs_by_name.get("home economics")
                    elif "agric" in prog_str:
                        prog_id = programs_by_name.get("agriculture")
                    elif "stem" in prog_str:
                        prog_id = programs_by_name.get("stem engineering") or programs_by_name.get("stem computer science")
                    else:
                        for p_name, p_id in programs_by_name.items():
                            if prog_str in p_name or p_name in prog_str:
                                prog_id = p_id
                                break

                res_raw = get_val(row, RESIDENTIAL_ALIASES, "B").upper()
                if res_raw.startswith("D") or "DAY" in res_raw:
                    res_status = "D"
                else:
                    res_status = "B"

                guardian = get_val(row, GUARDIAN_ALIASES)
                phone = get_val(row, PHONE_ALIASES)
                alt_phone = get_val(row, ALT_PHONE_ALIASES)
                address = get_val(row, ADDRESS_ALIASES)

                class_sec_id = None
                class_name_input = get_val(row, CLASS_ALIASES)

                if class_name_input:
                    from sqlalchemy import func
                    matched_sec = db.query(ClassSection).filter(
                        func.lower(ClassSection.name) == class_name_input.lower()
                    ).first()
                    if not matched_sec:
                        all_secs = db.query(ClassSection).all()
                        for sec in all_secs:
                            if class_name_input.lower() in sec.name.lower() or sec.name.lower() in class_name_input.lower():
                                matched_sec = sec
                                break
                    if matched_sec:
                        class_sec_id = matched_sec.id
                        if not prog_id:
                            prog_id = matched_sec.program_id

                if not class_sec_id and prog_id:
                    form1_sec = db.query(ClassSection).filter(ClassSection.program_id == prog_id).first()
                    if form1_sec:
                        class_sec_id = form1_sec.id

                student = Student(
                    student_code=student_code,
                    full_name=full_name,
                    first_name=first_name,
                    middle_name=middle_name if middle_name else None,
                    last_name=last_name if last_name else None,
                    bece_index_number=bece_idx,
                    enrolment_code=enrol_code,
                    bece_raw_score=raw_score,
                    bece_aggregate=aggregate,
                    jhs_attended=jhs,
                    residential_status=res_status,
                    enrollment_status="Fully Registered",
                    school_type="SHS",
                    form=1,
                    gender=gender,
                    date_of_birth=dob,
                    program_id=prog_id,
                    class_section_id=class_sec_id,
                    guardian_name=guardian,
                    phone=phone,
                    address=address,
                    school_id=school_id
                )
                db.add(student)
                db.flush()

                # Auto-allocate House & Dormitory
                try:
                    allocate_student_house_and_dorm(db, student)
                except Exception as alloc_err:
                    print(f"House allocation warning on row {line_num}: {alloc_err}")

                if guardian or phone:
                    g_rec = StudentGuardian(
                        student_id=student.id,
                        guardian_name=guardian or "Parent/Guardian",
                        relationship_type="Parent/Guardian",
                        primary_phone=phone or "N/A",
                        alternative_phone=alt_phone,
                        residential_address=address
                    )
                    db.add(g_rec)

                h_rec = StudentHealth(
                    student_id=student.id,
                    emergency_contact=phone or "N/A",
                    doctor_clearance_status=True
                )
                db.add(h_rec)

                imported_count += 1
        except Exception as row_exc:
            errors.append(f"Row {line_num} (Index {bece_idx}): {str(row_exc)}")
            skipped_count += 1

    db.commit()
    return {
        "status": "success",
        "imported": imported_count,
        "skipped": skipped_count,
        "total": line_num - 1,
        "errors": errors
    }


# ── Candidate Online/Offline Admission Form Completion ─────────────────────────

from pydantic import BaseModel

class CandidateAdmissionForm(BaseModel):
    student_id: int
    serial_code: Optional[str] = None
    elective_combination: Optional[str] = None
    guardian_name: Optional[str] = None
    primary_phone: Optional[str] = None
    alternative_phone: Optional[str] = None
    residential_address: Optional[str] = None
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    emergency_contact: Optional[str] = None


@router.post("/complete-form")
def complete_admission_form(
    data: CandidateAdmissionForm,
    db: Session = Depends(get_db)
):
    """
    Candidate completes School Admission Form with Elective Combination Choice.
    Auto-routes student to the matching Class Section stream and Boarding House.
    """
    student = db.query(Student).filter(Student.id == data.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student placement record not found.")

    if data.guardian_name:
        student.guardian_name = data.guardian_name.strip()
    if data.primary_phone:
        student.phone = data.primary_phone.strip()
    if data.residential_address:
        student.address = data.residential_address.strip()
    if data.elective_combination:
        student.elective_combination = data.elective_combination.strip()

    # 1. Elective Combination -> Class Section Auto Routing Engine
    if data.elective_combination and student.program_id:
        program_sections = db.query(ClassSection).filter(ClassSection.program_id == student.program_id).all()
        matched_sec = None
        combo_str = data.elective_combination.lower()

        for sec in program_sections:
            if combo_str in sec.name.lower() or sec.name.lower() in combo_str:
                matched_sec = sec
                break

        if not matched_sec and program_sections:
            # Match by index if combination choice is Option A/B/C/D
            if "option b" in combo_str or "combo 2" in combo_str or "he 2" in combo_str or "sci 2" in combo_str:
                matched_sec = program_sections[min(1, len(program_sections) - 1)]
            elif "option c" in combo_str or "combo 3" in combo_str or "he 3" in combo_str or "sci 3" in combo_str:
                matched_sec = program_sections[min(2, len(program_sections) - 1)]
            elif "option d" in combo_str or "combo 4" in combo_str or "he 4" in combo_str or "sci 4" in combo_str:
                matched_sec = program_sections[min(3, len(program_sections) - 1)]
            else:
                matched_sec = program_sections[0]

        if matched_sec:
            student.class_section_id = matched_sec.id

    # 2. Auto-allocate Boarding House & Dormitory if Boarder
    allocate_student_house_and_dorm(db, student)

    # 3. Update Health Profile
    health = db.query(StudentHealth).filter(StudentHealth.student_id == student.id).first()
    if not health:
        health = StudentHealth(student_id=student.id)
        db.add(health)

    if data.blood_group:
        health.blood_group = data.blood_group
    if data.allergies:
        health.allergies = data.allergies
    if data.medical_conditions:
        health.chronic_conditions = data.medical_conditions
    if data.emergency_contact:
        health.emergency_contact = data.emergency_contact

    # 4. Consume Voucher
    if data.serial_code:
        from ..models import AdmissionVoucher
        voucher = db.query(AdmissionVoucher).filter(AdmissionVoucher.serial_code == data.serial_code.strip()).first()
        if voucher:
            voucher.status = "USED"
            voucher.used_at = datetime.now()
            voucher.bece_index_number = student.bece_index_number

    student.enrollment_status = "FORM_COMPLETED"
    db.commit()

    return {
        "success": True,
        "message": "Admission Form completed successfully!",
        "student_id": student.id,
        "full_name": student.full_name,
        "class_name": student.class_section.name if student.class_section else "Unassigned",
        "house_name": student.house.name if student.house else "Day Student",
        "dormitory_name": student.dormitory.name if student.dormitory else "N/A",
        "enrollment_status": student.enrollment_status
    }


@router.get("/prospectus-package/{student_id}")
def get_prospectus_package(student_id: int, db: Session = Depends(get_db)):
    """
    Generates customized GES Form 1 Prospectus Package and Official Admission Letter data.
    Auto-tailors checklist items based on Gender, Boarding/Day, and Program Specialization.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")

    is_boarder = (student.residential_status or "B").upper() == "B"
    gender = (student.gender or "Male").strip().capitalize()
    prog_name = student.program.name if hasattr(student, 'program') and student.program else "General Studies"

    # Core Academic Items (All Students)
    academic_items = [
        "1 Original Oxford / Helix Mathematical Set",
        "1 Casio Scientific Calculator (fx-991ES Plus or ClassWiz)",
        "8 to 12 Single-Line Hardcover Exercise Books & 2 Graph Books",
        "1 Good News Bible or Holy Quran",
        "1 English Dictionary (Oxford Advanced Learner's) & Modern Atlas",
        "Blue & Black Ballpoint Pens, 2B Pencils, Eraser, 30cm Ruler",
        "1 School Bag / Rucksack (Black or Navy Blue)"
    ]

    # Boarding Items (Boarders Only)
    boarding_items = []
    if is_boarder:
        boarding_items = [
            "1 Single Mattress Cover / Mackintosh Sheet (2.5ft x 6ft)",
            "2 Pairs of House Color-Coded Bedsheets (Light Blue / White / Pink)",
            "1 Pillow & 2 Pillow Cases (Matching House colors)",
            "1 Heavy Blanket or Duvet",
            "1 Treated Mosquito Net (Box or Bell shape)",
            "1 Plastic Bucket & 1 Washing Basin (Medium size)",
            "Toiletries: Bath Soap (4 bars), Soap Dish, Washing Powder, Toothbrush & Paste (2 tubes), 2 Bath Towels, 1 Pack Toilet Rolls (10 pcs)",
            "Sanitation: 1 Native/Ceiling Broom, 1 Scrubbing Brush, 1 Mop & Bucket, 1 Bottle Disinfectant (Dettol/Parazone)",
            "Mess Utensils: 1 Stainless Steel Cutlery Set, 1 Covered Plate & Soup Bowl, 1 Insulated Water Bottle/Flask"
        ]

    # Gender-Specific Clothing & Grooming
    gender_items = []
    if gender.startswith("M") or gender.startswith("m"):
        gender_items = [
            "3 White Short-Sleeved Official Shirts",
            "2 School Trousers (School color)",
            "1 Black Formal Leather Belt",
            "2 Sets House Jersey & Shorts",
            "2 Pairs Pyjamas for sleeping",
            "1 Pair Black Formal Leather Shoes & 3 Pairs Black Socks",
            "1 Pair White Canvas / Sports Shoes & White Socks (for PE)",
            "1 Pair Bathroom Flip-Flops",
            "Hair Clipper / Pocket Comb (Compliant with GES low haircut guideline)"
        ]
    else:
        gender_items = [
            "3 School Official Dresses (Below-the-knee length)",
            "2 White Short-Sleeved Blouses & School Skirts",
            "2 House Slips / House Dresses (Below-the-knee length)",
            "2 Night Gowns or Pyjamas",
            "1 Pair Black Flat Leather Shoes (Low heel) & 3 Pairs White Socks",
            "1 Pair White Canvas / Sports Shoes & White Socks (for PE)",
            "1 Pair Bathroom Flip-Flops",
            "4 Packs Sanitary Pads & Personal Hygiene Supplies",
            "Black Hair Ribbons / Hair Bands"
        ]

    # Program Specialization Practical Tools
    program_items = []
    prog_lower = prog_name.lower()
    if "home" in prog_lower or "econ" in prog_lower:
        program_items = [
            "1 White Kitchen Apron & Chef Cap",
            "3 Kitchen Towels & Oven Gloves",
            "1 Measuring Tape, Fabric Scissors & Pins (Clothing & Textiles)"
        ]
    elif "sci" in prog_lower or "agric" in prog_lower or "stem" in prog_lower:
        program_items = [
            "1 White Knee-Length Laboratory Coat (Cotton)",
            "1 Safety Goggles",
            "1 Pair Wellington Boots (Agriculture practicals)"
        ]
    elif "art" in prog_lower or "tech" in prog_lower or "engineer" in prog_lower:
        program_items = [
            "1 A2 Drawing Board & T-Square",
            "Set Squares (45° & 60°), French Curves",
            "Drawing Pencils (HB, 2B, 4B, 6B) & Drawing Pad",
            "Protective Work Apron & Safety Boots"
        ]
    elif "bus" in prog_lower:
        program_items = [
            "3-Column Financial Accounting Ledger Notebooks"
        ]

    school_name = student.school.name if hasattr(student, 'school') and student.school else "Senior High School"

    from ..models import Setting, StudentHealth
    def _setting_val(key, default=""):
        s = db.query(Setting).filter(Setting.key == key).first()
        return s.value if s else default

    conduct_text = _setting_val("code_of_conduct_text", "1. ATTENDANCE & PUNCTUALITY: All students must attend morning assemblies and classes on time.")
    pledge_text = _setting_val("student_pledge_text", "I solemnly pledge to uphold the highest standards of academic integrity, personal discipline, and respect for school rules.")
    conduct_pdf_url = _setting_val("code_of_conduct_pdf_url", "")

    health = db.query(StudentHealth).filter(StudentHealth.student_id == student.id).first()
    blood_group = health.blood_group if health and health.blood_group else "O+"
    allergies = health.allergies if health and health.allergies else "None Reported"
    med_conditions = health.chronic_conditions if health and health.chronic_conditions else "None Reported"

    return {
        "student_info": {
            "id": student.id,
            "full_name": student.full_name,
            "student_code": student.student_code,
            "bece_index_number": student.bece_index_number,
            "program_name": prog_name,
            "class_name": student.class_section.name if student.class_section else "Form 1",
            "house_name": student.house.name if student.house else "Day Student",
            "dormitory_name": student.dormitory.name if student.dormitory else "N/A",
            "residential_status": "Boarding" if is_boarder else "Day",
            "gender": gender,
            "blood_group": blood_group,
            "allergies": allergies,
            "medical_conditions": med_conditions,
            "enrollment_status": student.enrollment_status or "PLACED",
            "school_name": school_name,
            "academic_year": student.academic_year or "2025/2026",
            "qr_verification_code": f"VERIFIED-{student.student_code}-{student.bece_index_number}"
        },
        "prospectus": {
            "academic_supplies": academic_items,
            "boarding_supplies": boarding_items,
            "clothing_and_grooming": gender_items,
            "program_practical_tools": program_items
        },
        "code_of_conduct": {
            "rules_text": conduct_text,
            "honor_pledge": pledge_text,
            "document_pdf_url": conduct_pdf_url
        }
    }


@router.post("/final-clearance/{student_id}")
def final_admission_clearance(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Assistant Head Academic / Admissions Secretariat gives final sign-off.
    Transitions student status to FULLY_ADMITTED (activates on Class & House Roster).
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student placement record not found.")

    student.enrollment_status = "FULLY_ADMITTED"
    db.commit()

    return {
        "success": True,
        "message": f"Student {student.full_name} is now FULLY ADMITTED to {student.class_section.name if student.class_section else 'Form 1'}!",
        "enrollment_status": "FULLY_ADMITTED"
    }
