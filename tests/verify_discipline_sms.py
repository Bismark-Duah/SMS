"""
Automated Verification Script for Discipline Incident SMS Alerts
"""
import sys
from datetime import datetime
from sqlalchemy.orm import Session

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User, Role, ClassSection, Student, DisciplineRecord, MessageLog
from backend.app.routes.discipline import create_record, RecordCreate
from backend.app.routes.messaging import generate_report_payload

def run_tests():
    print("==================================================")
    print(" DISCIPLINE INCIDENT SMS ALERT VERIFICATION SUITE ")
    print("==================================================")

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Setup Test Data
        print("\n[1] Setting up discipline test environment...")

        role_admin = db.query(Role).filter(Role.name == "admin").first()
        if not role_admin:
            role_admin = Role(name="admin")
            db.add(role_admin)
            db.commit()

        user_admin = db.query(User).filter(User.username == "admin").first()

        class_sec = db.query(ClassSection).filter(ClassSection.name == "Form 1 Discipline Test").first()
        if not class_sec:
            class_sec = ClassSection(name="Form 1 Discipline Test", stage_id=1)
            db.add(class_sec)
            db.commit()

        st = db.query(Student).filter(Student.student_code == "DISC-STU-001").first()
        if not st:
            st = Student(
                student_code="DISC-STU-001",
                full_name="Kwadwo Frimpong",
                class_section_id=class_sec.id,
                guardian_name="Mr. Frimpong",
                phone="+233277112233",
                is_active=True
            )
            db.add(st)
            db.commit()

        # Idempotency cleanup
        db.query(DisciplineRecord).filter(DisciplineRecord.student_id == st.id).delete(synchronize_session=False)
        db.query(MessageLog).filter(MessageLog.student_id == st.id).delete(synchronize_session=False)
        db.commit()

        print(f"   [OK] Test student initialized: {st.full_name} (Phone: {st.phone}).")

        # 2. Test Create Discipline Record with notify_parent=True
        print("\n[2] Logging Disciplinary Incident (Suspension) with notify_parent=True...")
        rec_payload = RecordCreate(
            student_id=st.id,
            incident_type="Suspension",
            description="Repeated lateness and unexcused absence from morning assembly.",
            action_taken="3-day internal suspension with campus grounds service.",
            notify_parent=True
        )
        created_rec = create_record(rec_payload, db=db, current_user=user_admin)
        assert created_rec["parent_notified"] == True, "parent_notified should be True!"

        # 3. Assert PENDING MessageLog Draft Entry Created
        print("\n[3] Verifying PENDING DISCIPLINE_NOTICE draft creation...")
        disc_log = (
            db.query(MessageLog)
            .filter(
                MessageLog.student_id == st.id,
                MessageLog.message_type == "DISCIPLINE_NOTICE"
            )
            .first()
        )
        assert disc_log is not None, "MessageLog discipline notice draft should be created!"
        assert disc_log.status == "PENDING", f"Expected PENDING status, got: {disc_log.status}"
        assert "Kwadwo Frimpong" in disc_log.message_body, "Message body should mention student name!"
        assert "Suspension" in disc_log.message_body, "Message body should mention incident type!"
        assert "3-day internal suspension" in disc_log.message_body, "Message body should mention action taken!"
        print(f"   [OK] PENDING discipline alert drafted: {disc_log.message_body}")

        # 4. Test Report Payload Endpoint for DISCIPLINE_NOTICE
        print("\n[4] Testing /messaging/report-payload with msg_type=DISCIPLINE_NOTICE...")
        rep_res = generate_report_payload({"student_id": st.id, "msg_type": "DISCIPLINE_NOTICE"}, db=db, current_user=user_admin)
        assert "DISCIPLINE NOTICE" in rep_res["whatsapp_payload"], "WhatsApp payload missing header!"
        assert rep_res["overall_grade"] == "DISCIPLINE", "Overall grade should be DISCIPLINE!"
        print("   [OK] Disciplinary payload returned successfully.")

        print("\n==================================================")
        print(" ALL DISCIPLINE INCIDENT SMS TESTS PASSED!       ")
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
