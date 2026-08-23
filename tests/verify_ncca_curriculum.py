import sys
import os
import json

from backend.app.database import SessionLocal, engine, Base
from backend.app.models import Student, Subject, Program, StudentGuardian, StudentHealth, Score, Semester, AcademicYear
from backend.app.ncca_seed import seed_ncca_curriculum
from backend.app.routes.cssps_enrollment import enroll_student
from backend.app.schemas import CSSPSEnrollmentCreate

def run_tests():
    print("==================================================")
    print("  VERIFYING NaCCA CURRICULUM, CSSPS & CUMULATIVE  ")
    from backend.app.database import run_migrations
    run_migrations()

    db = SessionLocal()

    # Clean up test student if exists
    ex_test = db.query(Student).filter(Student.bece_index_number == "100000000026").first()
    if ex_test:
        db.query(Score).filter(Score.student_id == ex_test.id).delete()
        db.delete(ex_test)
        db.commit()

    # 1. Test Seeding
    print("\n1. Testing NaCCA Curriculum & Basic School Seeding...")
    res = seed_ncca_curriculum(db)
    print("   [PASS]", res["message"])

    # Verify subjects count
    basic_count = db.query(Subject).filter(Subject.school_level == "Basic").count()
    shs_count = db.query(Subject).filter(Subject.school_level.in_(["SHS", "STEM"])).count()
    prog_count = db.query(Program).count()
    print(f"   Basic Subjects: {basic_count}, SHS/STEM Subjects: {shs_count}, Programs: {prog_count}")
    assert basic_count >= 10, "Basic subjects count failed"
    assert shs_count >= 15, "SHS subjects count failed"
    assert prog_count >= 16, "Programs count failed (expected 16 NaCCA Learning Areas)"

    # 2. Test CSSPS Enrollment
    print("\n2. Testing CSSPS Enrollment with BECE Index & Enrolment Code...")
    enroll_payload = CSSPSEnrollmentCreate(
        bece_index_number="100000000026",
        enrolment_code="CSSPS-2026-X89",
        first_name="Kwame",
        middle_name="Kofi",
        last_name="Mensah",
        gender="M",
        date_of_birth="2008-05-15",
        bece_raw_score=430,
        bece_aggregate=8,
        jhs_attended="Achimota Basic School",
        residential_status="B",
        guardian_name="Mr. Ebenezer Mensah",
        primary_phone="0244123456",
        alternative_phone="0200987654",
        residential_address="House No 45, Legon, Accra",
        blood_group="O+",
        allergies="Peanuts",
        medical_conditions="Mild Asthma"
    )

    result = enroll_student(enroll_payload, db)
    student_id = result["student_id"]
    print("   [PASS] Student Enrolled Successfully ID:", student_id)
    assert result["bece_index_number"] == "100000000026"
    assert result["enrolment_code"] == "CSSPS-2026-X89"

    # Test Duplicate Prevention
    try:
        enroll_student(enroll_payload, db)
        print("   [FAIL] Duplicate BECE index was allowed!")
        sys.exit(1)
    except Exception as e:
        print("   [PASS] Duplicate BECE index prevented:", getattr(e, "detail", str(e)))

    # 3. Test Guardian and Health relationships
    print("\n3. Testing Guardian & Health Profile Data Integrity...")
    student = db.query(Student).filter(Student.id == student_id).first()
    assert len(student.guardians) == 1, "Guardian creation failed"
    assert student.guardians[0].primary_phone == "0244123456"
    assert student.health_profile is not None, "Health profile creation failed"
    assert student.health_profile.blood_group == "O+"
    print("   [PASS] Guardian and Health relationships linked cleanly!")

    # 4. Test Cumulative Record Data
    print("\n4. Testing Cumulative Record Updates...")
    student.personality_traits = "Respectful, punctual, and highly attentive in class."
    student.leadership_notes = "Appointed Class Monitor in Form 1."
    student.teacher_observations = "Demonstrates exceptional aptitude in STEM problem solving."
    student.co_curricular_activities = "Member of Robotics Club and Chess Team."
    db.commit()

    db.refresh(student)
    assert student.personality_traits == "Respectful, punctual, and highly attentive in class."
    print("   [PASS] Cumulative Record fields saved successfully!")

    # 5. Test Transcript Generation
    print("\n5. Testing 100% SHS Academic Transcript Data Generation...")
    # Add dummy scores
    ac_year = db.query(AcademicYear).first()
    if not ac_year:
        ac_year = AcademicYear(label="2025/2026", is_current=True)
        db.add(ac_year)
        db.flush()

    sem = db.query(Semester).first()
    if not sem:
        sem = Semester(name="Term 1", academic_year_id=ac_year.id, is_current=True)
        db.add(sem)
        db.flush()

    core_math = db.query(Subject).filter(Subject.name == "Core Mathematics").first()
    robotics = db.query(Subject).filter(Subject.name == "Robotics and Coding (Form 2)").first()

    if core_math:
        db.add(Score(student_id=student_id, subject_id=core_math.id, semester_id=sem.id, total_score=85.0, grade="A1", remark="Excellent"))
    if robotics:
        db.add(Score(student_id=student_id, subject_id=robotics.id, semester_id=sem.id, total_score=92.0, grade="A1", remark="Outstanding"))
    db.commit()

    from backend.app.services.reports import ReportService
    tdata = ReportService.get_full_transcript_data(db, student_id)
    assert tdata is not None, "Transcript data generation returned None"
    assert len(tdata["external_wassce_subjects"]) + len(tdata["internal_transcript_subjects"]) == 2, "Transcript subjects count mismatch"
    print("   [PASS] Official Transcript Data generated with External vs Internal subject separation!")

    print("\n==================================================")
    print("     ALL VERIFICATION TESTS PASSED SUCCESSFULLY!  ")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
