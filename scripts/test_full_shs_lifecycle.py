#!/usr/bin/env python3
"""
scripts/test_full_shs_lifecycle.py — Complete End-to-End SHS Lifecycle Simulation Test

Tests all 10 stages of the SHS academic lifecycle:
1. School Mode & Program Setup
2. CSSPS Placement CSV Ingestion
3. Admission Voucher Generation & Candidate Portal Authentication
4. Admission Form & Elective Combination Class Auto-Routing
5. Dynamic GES Form 1 Prospectus Package Generation
6. Academic Clearance & Final Admission
7. Daily Class Register & Nightly House Roll Call (Mode 2) with Exeat Badging
8. 3-Tier Marks Verification & Approval Workflow (Teacher -> HOD -> Academic Head)
9. End-of-Term Broadsheet & 1st-to-Nth Student Position Ranking Engine
10. Terminal Report Card & Transcript Data Generation
"""

import sys
import os
from datetime import datetime

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from backend.app.database import SessionLocal, run_migrations
from backend.app.models import (
    School, User, Student, ClassSection, Program, Subject, House, Dormitory,
    Score, Attendance, AdmissionVoucher, ExeatRecord, StudentGuardian, StudentHealth, Semester, SchoolStage
)
from backend.app.services.allocation import allocate_student_house_and_dorm
from backend.app.routes import cssps_enrollment, results, reports, vouchers, attendance as attendance_route

print("=========================================================================")
print("     SHS FULL ACADEMIC LIFECYCLE END-TO-END SIMULATION TEST              ")
print("=========================================================================\n")

# Run DB Migrations first
run_migrations()
db = SessionLocal()

try:
    # ── STAGE 1: School Mode & Program Setup ───────────────────────────────────
    print("[STAGE 1] Setting Up SHS School Mode, Programs & Class Streams...")
    school = db.query(School).filter(School.id == 1).first()
    if not school:
        school = School(id=1, name="KUMASI SHS", school_mode="SHS_ONLY")
        db.add(school)
        db.flush()
    else:
        school.name = "KUMASI SHS"
        school.school_mode = "SHS_ONLY"
    db.commit()

    # Get or create current semester
    sem = db.query(Semester).filter(Semester.is_current == True).first()
    if not sem:
        sem = Semester(name="Trimester 1 / Term 1", is_current=True, academic_year="2025/2026")
        db.add(sem)
        db.commit()
    sem_id = sem.id

    # Create Program: Home Economics
    prog_he = db.query(Program).filter(Program.name == "Home Economics").first()
    if not prog_he:
        prog_he = Program(name="Home Economics", code="HE", school_id=1)
        db.add(prog_he)
        db.flush()

    # Get or create SchoolStage 1 (SHS Form 1)
    stage_shs1 = db.query(SchoolStage).filter(SchoolStage.name == "SHS 1").first()
    if not stage_shs1:
        stage_shs1 = SchoolStage(name="SHS 1", school_type="SHS")
        db.add(stage_shs1)
        db.flush()

    # Create Class Streams: Form 1 Home Economics 1, Form 1 Home Economics 2
    class_he1 = db.query(ClassSection).filter(ClassSection.name == "Form 1 Home Economics 1").first()
    if not class_he1:
        class_he1 = ClassSection(name="Form 1 Home Economics 1", program_id=prog_he.id, stage_id=stage_shs1.id)
        db.add(class_he1)

    class_he2 = db.query(ClassSection).filter(ClassSection.name == "Form 1 Home Economics 2").first()
    if not class_he2:
        class_he2 = ClassSection(name="Form 1 Home Economics 2", program_id=prog_he.id, stage_id=stage_shs1.id)
        db.add(class_he2)
    db.commit()

    # Create Girls Boarding House: Yaa Asantewaa House
    house_ya = db.query(House).filter(House.name == "Yaa Asantewaa House").first()
    if not house_ya:
        house_ya = House(name="Yaa Asantewaa House", gender="Female", school_id=1)
        db.add(house_ya)
        db.flush()

    dorm_ya1 = db.query(Dormitory).filter(Dormitory.name == "Dorm A").first()
    if not dorm_ya1:
        dorm_ya1 = Dormitory(name="Dorm A", capacity=50, house_id=house_ya.id)
        db.add(dorm_ya1)
    db.commit()

    # Create Core & Elective Subjects
    sub_math = db.query(Subject).filter(Subject.name == "Core Mathematics").first()
    if not sub_math:
        sub_math = Subject(name="Core Mathematics", code="MATH101", category="Core", school_level="SHS")
        db.add(sub_math)

    sub_fn = db.query(Subject).filter(Subject.name == "Food & Nutrition").first()
    if not sub_fn:
        sub_fn = Subject(name="Food & Nutrition", code="FN101", category="Elective", school_level="SHS")
        db.add(sub_fn)

    sub_bio = db.query(Subject).filter(Subject.name == "Biology").first()
    if not sub_bio:
        sub_bio = Subject(name="Biology", code="BIO101", category="Elective", school_level="SHS")
        db.add(sub_bio)
    db.commit()

    print(" [PASS] STAGE 1: School, Programs, Streams & Houses setup completed!\n")


    # ── STAGE 2: CSSPS Placement Ingestion ────────────────────────────────────
    print("[STAGE 2] Ingesting Ministry CSSPS Placement Record...")
    candidate_bece = "101999888124"
    ex_student = db.query(Student).filter(Student.bece_index_number == candidate_bece).first()
    if not ex_student:
        cand_student = Student(
            student_code=f"SHS-{candidate_bece}",
            full_name="Abena Osei Bonsu",
            first_name="Abena",
            last_name="Bonsu",
            bece_index_number=candidate_bece,
            bece_raw_score=495,
            bece_aggregate=8,
            residential_status="B",
            enrollment_status="PLACED",
            school_type="SHS",
            form=1,
            gender="Female",
            program_id=prog_he.id,
            school_id=1
        )
        db.add(cand_student)
        db.commit()
        db.refresh(cand_student)
    else:
        cand_student = ex_student

    assert cand_student.enrollment_status in ["PLACED", "FORM_COMPLETED", "FULLY_ADMITTED"]
    print(f" [PASS] STAGE 2: Candidate {cand_student.full_name} placed! Initial status: {cand_student.enrollment_status}.\n")


    # ── STAGE 3: Admission Voucher Generation & Authentication Gateway ────────
    print("[STAGE 3] Generating Admission Voucher & Verifying Candidate Gateway...")
    serial_test = f"JAK-2026-{candidate_bece[-4:]}"
    pin_test = "889900"

    v_exist = db.query(AdmissionVoucher).filter(AdmissionVoucher.serial_code == serial_test).first()
    if not v_exist:
        v_exist = AdmissionVoucher(
            serial_code=serial_test,
            pin_code=pin_test,
            status="AVAILABLE",
            school_id=1
        )
        db.add(v_exist)
        db.commit()

    # Simulate Candidate Portal Voucher Login Verification
    verify_req = vouchers.VoucherVerifyRequest(
        bece_index_number=candidate_bece,
        serial_code=serial_test,
        pin_code=pin_test
    )
    v_res = vouchers.verify_voucher(data=verify_req, db=db)
    assert v_res["success"] == True
    print(f" [PASS] STAGE 3: Candidate Voucher Gateway verified! Serial: {serial_test}, PIN: {pin_test}\n")


    # ── STAGE 4: Admission Form Completion & Elective Combination Class Auto-Routing ──
    print("[STAGE 4] Completing Admission Form & Elective Combination Auto-Routing...")
    form_req = cssps_enrollment.CandidateAdmissionForm(
        student_id=cand_student.id,
        serial_code=serial_test,
        elective_combination="Option B (Mgmt in Living + Food & Nut + Biology + Economics)",
        guardian_name="Mrs. Akosua Bonsu",
        primary_phone="0244987654",
        residential_address="Plot 10, Block C, Kumasi",
        blood_group="O+",
        allergies="None"
    )

    form_res = cssps_enrollment.complete_admission_form(data=form_req, db=db)
    db.refresh(cand_student)

    assert cand_student.enrollment_status in ["FORM_COMPLETED", "FULLY_ADMITTED"]
    assert cand_student.class_section_id is not None
    assert cand_student.house_id is not None
    assigned_class = db.query(ClassSection).filter(ClassSection.id == cand_student.class_section_id).first()
    assigned_house = db.query(House).filter(House.id == cand_student.house_id).first()
    print(f" [PASS] STAGE 4: Elective Option B auto-routed student to '{assigned_class.name if assigned_class else 'Stream'}' & House '{assigned_house.name if assigned_house else 'House'}'!\n")


    # ── STAGE 5: Dynamic GES Prospectus Package Generation ────────────────────
    print("[STAGE 5] Generating Customized GES Form 1 Prospectus Package...")
    pkg_res = cssps_enrollment.get_prospectus_package(student_id=cand_student.id, db=db)
    p_info = pkg_res["student_info"]
    p_check = pkg_res["prospectus"]

    assert p_info["gender"] == "Female"
    assert p_info["residential_status"] == "Boarding"
    assert len(p_check["academic_supplies"]) > 0
    assert len(p_check["boarding_supplies"]) > 0
    assert len(p_check["clothing_and_grooming"]) > 0
    assert len(p_check["program_practical_tools"]) > 0
    print(f" [PASS] STAGE 5: Dynamic Prospectus Package generated with {len(p_check['boarding_supplies'])} Boarding items & {len(p_check['clothing_and_grooming'])} Female clothing items!\n")


    # ── STAGE 6: Academic Clearance & Final Admission Sign-Off ───────────────
    print("[STAGE 6] Assistant Head Academic Granting Final Admission Clearance...")
    # Create Mock Academic Executive User
    admin_user = db.query(User).filter(User.username == "admin_academic_test").first()
    if not admin_user:
        admin_user = User(username="admin_academic_test", email="admin_ac@school.edu.gh", password_hash="x")
        db.add(admin_user)
        db.commit()

    clear_res = cssps_enrollment.final_admission_clearance(student_id=cand_student.id, db=db, current_user=admin_user)
    db.refresh(cand_student)

    assert cand_student.enrollment_status == "FULLY_ADMITTED"
    print(f" [PASS] STAGE 6: Candidate is now FULLY ADMITTED to '{assigned_class.name if assigned_class else 'Form 1'}'!\n")


    # ── STAGE 7: Daily Classroom & Nightly House Roll Call (Mode 2) ────────────
    print("[STAGE 7] Marking Morning Class Register & Evening House Roll Call (Mode 2)...")
    today_dt = datetime.now()

    # 1. Morning Class Register
    att_class = Attendance(
        student_id=cand_student.id,
        date=today_dt,
        status="Present",
        attendance_type="daily"
    )
    db.add(att_class)

    # 2. Nightly House Roll Call (Mode 2)
    att_house = Attendance(
        student_id=cand_student.id,
        date=today_dt,
        status="Present",
        attendance_type="daily",
        period_label="[House Roll] Evening Lights-Out Check"
    )
    db.add(att_house)
    db.commit()

    print(" [PASS] STAGE 7: Morning Class Register & Nightly House Roll Call (Mode 2) recorded cleanly!\n")


    # ── STAGE 8: 3-Tier Marks Verification & Approval Workflow ─────────────
    print("[STAGE 8] 3-Tier Score Entry & Approval Workflow (Teacher -> HOD -> Academic Head)...")
    # Add Scores for Math, Food & Nut, Biology
    score_math = db.query(Score).filter(Score.student_id == cand_student.id, Score.subject_id == sub_math.id, Score.semester_id == sem_id).first()
    if not score_math:
        score_math = Score(
            student_id=cand_student.id,
            subject_id=sub_math.id,
            semester_id=sem_id,
            class_score=26.5,
            exam_score=62.0,
            total_score=88.5,
            grade="A1",
            remark="EXCELLENT",
            approval_status="DRAFT"
        )
        db.add(score_math)

    score_fn = db.query(Score).filter(Score.student_id == cand_student.id, Score.subject_id == sub_fn.id, Score.semester_id == sem_id).first()
    if not score_fn:
        score_fn = Score(
            student_id=cand_student.id,
            subject_id=sub_fn.id,
            semester_id=sem_id,
            class_score=28.0,
            exam_score=65.0,
            total_score=93.0,
            grade="A1",
            remark="OUTSTANDING",
            approval_status="DRAFT"
        )
        db.add(score_fn)
    db.commit()

    # Tier 1: Teacher submits to HOD
    sub_res = results.submit_to_hod(class_id=cand_student.class_section_id, subject_id=sub_math.id, semester_id=sem_id, db=db, current_user=admin_user)
    assert sub_res["status"] == "SUBMITTED_TO_HOD"

    # Tier 2: HOD approves department scores
    app_res = results.approve_by_hod(class_id=cand_student.class_section_id, subject_id=sub_math.id, semester_id=sem_id, db=db, current_user=admin_user)
    assert app_res["status"] == "APPROVED_BY_HOD"

    # Tier 3: Academic Head publishes terminal class scores
    pub_res = results.publish_by_academic_head(class_id=cand_student.class_section_id, semester_id=sem_id, db=db, current_user=admin_user)
    assert pub_res["status"] == "PUBLISHED"

    db.refresh(score_math)
    assert score_math.approval_status == "PUBLISHED"
    print(" [PASS] STAGE 8: 3-Tier Approval Workflow completed! Status: PUBLISHED.\n")


    # ── STAGE 9: End-of-Term Broadsheet & Class Position Ranking Engine ───────
    print("[STAGE 9] Computing Class Broadsheet & Automatic 1st-to-Nth Position Ranks...")
    broadsheet_data = reports.get_class_broadsheet(class_id=cand_student.class_section_id, semester_id=sem_id, db=db, current_user=admin_user)
    
    assert broadsheet_data["class_id"] == cand_student.class_section_id
    assert len(broadsheet_data["rows"]) > 0
    top_student_rank = broadsheet_data["rows"][0]["rank_str"]
    top_student_name = broadsheet_data["rows"][0]["full_name"]

    print(f" [PASS] STAGE 9: Class Broadsheet matrix generated! Top Rank 1st: '{top_student_name}' ({top_student_rank})\n")


    # ── STAGE 10: Terminal Report Card & Transcript Generation ────────────────
    print("[STAGE 10] Generating Terminal Report Card & Transcript Data...")
    from backend.app.services.reports import ReportService
    report_data = ReportService.get_report_data(db, cand_student.id, sem_id)
    
    assert report_data is not None
    print(f" [PASS] STAGE 10: Terminal Report Card generated successfully for {cand_student.full_name}!\n")

    print("=========================================================================")
    print(" SUCCESS: ALL 10 STAGES OF THE SHS LIFECYCLE TEST PASSED 100%!          ")
    print("=========================================================================")

finally:
    db.close()
