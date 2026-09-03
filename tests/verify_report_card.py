import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import (
    User, Role, Department, ClassSection, Subject, Semester, Student, Score,
    StudentSemesterSummary, Setting, ClassSectionReportStatus, House, Dormitory
)
from backend.app.services.reports import ReportService

def run_tests():
    print("==================================================")
    print(" TERMINAL REPORT CARD GENERATOR SUITE             ")
    print("==================================================")

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Verify Data & Test Setup
        print("\n[1] Preparing Report Card Test Data...")

        # School Settings
        set_logo = db.query(Setting).filter(Setting.key == "school_logo").first()
        if not set_logo:
            db.add(Setting(key="school_logo", value="uploads/test_logo.png"))

        set_sig = db.query(Setting).filter(Setting.key == "headmaster_signature").first()
        if not set_sig:
            db.add(Setting(key="headmaster_signature", value="uploads/test_sig.png"))

        db.commit()

        # Boarding House & Dorm
        house_sci = db.query(House).filter(House.name == "Test Science House").first()
        if not house_sci:
            house_sci = House(name="Test Science House", gender="Boys")
            db.add(house_sci)
            db.commit()

        dorm_a = db.query(Dormitory).filter(Dormitory.name == "Block A Dorm").first()
        if not dorm_a:
            dorm_a = Dormitory(name="Block A Dorm", house_id=house_sci.id)
            db.add(dorm_a)
            db.commit()

        # Semester
        sem = db.query(Semester).filter(Semester.name == "Test Term 1").first()
        if not sem:
            sem = Semester(name="Test Term 1", is_current=True, academic_year_id=1)
            db.add(sem)
            db.commit()

        # Class Section
        class_sec = db.query(ClassSection).filter(ClassSection.name == "Form 1 Test STEM").first()
        if not class_sec:
            class_sec = ClassSection(name="Form 1 Test STEM", stage_id=1)
            db.add(class_sec)
            db.commit()

        # Student
        st1 = db.query(Student).filter(Student.student_code == "ACAD-STU-001").first()
        if not st1:
            st1 = Student(student_code="ACAD-STU-001", full_name="Kojo Mensah", class_section_id=class_sec.id)
            db.add(st1)
        else:
            st1.class_section_id = class_sec.id

        st1.house_id = house_sci.id
        st1.dormitory_id = dorm_a.id
        db.commit()

        print("   [OK] Test student and settings ready.")

        # 2. Test Report Data Generation
        print("\n[2] Testing ReportService.get_report_data()...")
        data = ReportService.get_report_data(db, st1.id, sem.id)
        assert data is not None, "Report data should not be None!"

        print("   [OK] Report payload assembled successfully.")
        print(f"        - School Name: {data['school_name']}")
        print(f"        - Headmaster Sig: {data['headmaster_signature']}")
        print(f"        - Student Name: {data['student']['full_name']}")
        print(f"        - House/Dorm: {data['student']['house_name']} ({data['student']['dormitory_name']})")
        print(f"        - Overall Rank: {data['position_text']}")
        print(f"        - Published Status: {data['is_published']}")

        # 3. Test Publishing Status Updates
        print("\n[3] Testing Report Card Publishing Status Checks...")
        status_rec = db.query(ClassSectionReportStatus).filter(
            ClassSectionReportStatus.class_section_id == class_sec.id,
            ClassSectionReportStatus.semester_id == sem.id
        ).first()

        if not status_rec:
            status_rec = ClassSectionReportStatus(class_section_id=class_sec.id, semester_id=sem.id, is_published=True)
            db.add(status_rec)
            db.commit()
        else:
            status_rec.is_published = True
            db.commit()

        data_pub = ReportService.get_report_data(db, st1.id, sem.id)
        assert data_pub["is_published"] == True, "Report card status should reflect is_published = True!"
        print("   [OK] Report Card published status check passed.")

        # 4. Test Student Remarks Mapping
        print("\n[4] Testing Remarks Mapping...")
        summary = db.query(StudentSemesterSummary).filter(
            StudentSemesterSummary.student_id == st1.id,
            StudentSemesterSummary.semester_id == sem.id
        ).first()

        if summary:
            assert data["summary_data"]["attitude"] == summary.attitude, "Attitude remark mismatch!"
            assert data["summary_data"]["conduct"] == summary.conduct, "Conduct remark mismatch!"
            print(f"   [OK] Form Teacher Remarks: '{summary.form_teacher_remarks}'")

        print("\n==================================================")
        print(" ALL REPORT CARD VERIFICATION TESTS PASSED!       ")
        print("==================================================")

    except Exception as e:
        print(f"\n[FAIL] REPORT CARD VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
