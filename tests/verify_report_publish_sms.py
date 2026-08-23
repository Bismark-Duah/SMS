"""
Automated Verification Script for Report Card Publication SMS Alerts
"""
import sys
from datetime import datetime
from sqlalchemy.orm import Session

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User, Role, ClassSection, Semester, AcademicYear, Student, MessageLog, ClassSectionReportStatus
from backend.app.routes.academic_hierarchy import publish_class_reports

def run_tests():
    print("==================================================")
    print(" REPORT CARD PUBLICATION SMS VERIFICATION SUITE   ")
    print("==================================================")

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Setup Test Data
        print("\n[1] Setting up report publication test environment...")

        role_admin = db.query(Role).filter(Role.name == "admin").first()
        if not role_admin:
            role_admin = Role(name="admin")
            db.add(role_admin)
            db.commit()

        user_admin = db.query(User).filter(User.username == "admin").first()

        class_sec = db.query(ClassSection).filter(ClassSection.name == "Form 1 Report Pub Test").first()
        if not class_sec:
            class_sec = ClassSection(name="Form 1 Report Pub Test", stage_id=1)
            db.add(class_sec)
            db.commit()

        ay = db.query(AcademicYear).filter(AcademicYear.label == "2025/2026 Pub Test").first()
        if not ay:
            ay = AcademicYear(label="2025/2026 Pub Test", is_current=True)
            db.add(ay)
            db.commit()

        sem = db.query(Semester).filter(Semester.name == "Term 1 Pub Test").first()
        if not sem:
            sem = Semester(name="Term 1 Pub Test", academic_year_id=ay.id, is_current=True)
            db.add(sem)
            db.commit()

        st = db.query(Student).filter(Student.student_code == "PUB-STU-001").first()
        if not st:
            st = Student(
                student_code="PUB-STU-001",
                full_name="Kwesi Appiah",
                class_section_id=class_sec.id,
                guardian_name="Mr. Appiah",
                phone="+233245556677",
                is_active=True
            )
            db.add(st)
            db.commit()
        else:
            st.class_section_id = class_sec.id
            st.full_name = "Kwesi Appiah"
            st.phone = "+233245556677"
            db.commit()

        # Idempotency cleanup
        db.query(ClassSectionReportStatus).filter(
            ClassSectionReportStatus.class_section_id == class_sec.id,
            ClassSectionReportStatus.semester_id == sem.id
        ).delete(synchronize_session=False)
        db.query(MessageLog).filter(MessageLog.student_id == st.id).delete(synchronize_session=False)
        db.commit()

        print(f"   [OK] Test environment initialized: Student {st.full_name} in {class_sec.name} ({sem.name}).")

        # 2. Test Publishing Reports Creates PENDING MessageLog Draft
        print("\n[2] Calling publish_class_reports() and verifying PENDING SMS draft creation...")
        res_pub = publish_class_reports(class_section_id=class_sec.id, semester_id=sem.id, db=db, current_user=user_admin)
        assert "published" in res_pub["message"], "Publication response message mismatch!"

        pub_log = (
            db.query(MessageLog)
            .filter(
                MessageLog.student_id == st.id,
                MessageLog.message_type == "TERMINAL_REPORT"
            )
            .first()
        )
        assert pub_log is not None, "MessageLog terminal report publication draft should be created!"
        assert pub_log.status == "PENDING", f"Expected status PENDING, got: {pub_log.status}"
        assert "Kwesi Appiah" in pub_log.message_body, "Message body should mention student name!"
        assert "Term 1 Pub Test" in pub_log.message_body, "Message body should mention semester name!"
        print(f"   [OK] PENDING report publication alert drafted: {pub_log.message_body}")

        # 3. Test Re-publishing Does Not Create Duplicates
        print("\n[3] Re-publishing reports and asserting duplicate prevention...")
        publish_class_reports(class_section_id=class_sec.id, semester_id=sem.id, db=db, current_user=user_admin)

        all_pub_logs = (
            db.query(MessageLog)
            .filter(
                MessageLog.student_id == st.id,
                MessageLog.message_type == "TERMINAL_REPORT"
            )
            .all()
        )
        assert len(all_pub_logs) == 1, f"Expected exactly 1 message log draft, found {len(all_pub_logs)}"
        print("   [OK] Re-publishing kept a single draft record (No duplicates).")

        print("\n==================================================")
        print(" ALL REPORT CARD PUBLICATION SMS TESTS PASSED!    ")
        print("==================================================")

    except Exception as e:
        print(f"\n[FAIL] VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
