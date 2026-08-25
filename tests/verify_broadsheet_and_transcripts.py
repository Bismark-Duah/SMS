import os
import sys

# Ensure backend path is available
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import (
    School, Program, Subject, ClassSection, SchoolStage,
    ElectiveCombination, Student, Score, Semester, AcademicYear, User, Role
)
from backend.app.routes.academic_hierarchy import get_class_broadsheet
from backend.app.routes.cumulative_records import get_cumulative_record
from backend.app.services.grading import GradingService

def run_tests():
    print("================================================================")
    print("TEST SUITE: Phase 4 Master Broadsheet & Transcripts")
    print("================================================================")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Setup Admin User
        admin_user = db.query(User).filter(User.username == "test_admin_phase4").first()
        if not admin_user:
            admin_role = db.query(Role).filter(Role.name == "admin").first()
            if not admin_role:
                admin_role = Role(name="admin")
                db.add(admin_role)
                db.commit()

            admin_user = User(username="test_admin_phase4", email="admin4@school.com", password_hash="dummy", school_id=1)
            admin_user.roles.append(admin_role)
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

        # 2. Get or create Class Section & Semester
        sem = db.query(Semester).filter(Semester.is_current == True).first()
        if not sem:
            ay = db.query(AcademicYear).first()
            if not ay:
                ay = AcademicYear(label="2025/2026", is_current=True)
                db.add(ay)
                db.commit()
                db.refresh(ay)
            sem = Semester(name="Semester 1", academic_year_id=ay.id, is_current=True)
            db.add(sem)
            db.commit()
            db.refresh(sem)

        sec = db.query(ClassSection).first()
        assert sec is not None, "ClassSection should exist from previous tests"

        # 3. Call get_class_broadsheet
        broadsheet = get_class_broadsheet(class_section_id=sec.id, semester_id=sem.id, db=db, current_user=admin_user)
        assert broadsheet is not None
        assert hasattr(broadsheet, "students")
        assert hasattr(broadsheet, "subjects")

        print(f"[OK] Master Broadsheet generated for Class: '{broadsheet.class_name}' ({broadsheet.semester_name})")
        print(f"   - Subjects in matrix: {[s['name'] for s in broadsheet.subjects]}")
        print(f"   - Students in broadsheet: {len(broadsheet.students)}")

        if broadsheet.students:
            sample_student = broadsheet.students[0]
            print(f"   - Sample Student: {sample_student.student_name} (Rank #{sample_student.class_rank}, Total: {sample_student.total_marks}, Avg: {sample_student.average_mark}%, Best 6 Agg: {sample_student.aggregate})")
            assert hasattr(sample_student, "aggregate"), "Broadsheet student must have aggregate field"

        # 4. Test Cumulative Records Endpoint
        st = db.query(Student).filter(Student.class_section_id == sec.id).first()
        if not st:
            st = db.query(Student).first()

        if st:
            cum_record = get_cumulative_record(student_id=st.id, db=db, current_user=admin_user)
            assert cum_record is not None
            assert "scholastic_summary" in cum_record
            assert "attendance_conduct" in cum_record
            print(f"[OK] Cumulative 3-Year Record verified for: {cum_record['full_name']} ({cum_record['student_code']})")
            print(f"   - Total Assessments Logged: {cum_record['scholastic_summary']['total_assessments']}")
            print(f"   - Overall Scholastic Average: {cum_record['scholastic_summary']['overall_average']}%")

        print("\n================================================================")
        print("SUCCESS: ALL PHASE 4 BROADSHEET & TRANSCRIPT TESTS PASSED 100%!")
        print("================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
