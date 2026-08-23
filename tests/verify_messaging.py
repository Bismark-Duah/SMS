"""
Automated Verification Script for Bulk Messaging & SMS Delivery System
"""
import sys
from datetime import datetime
from sqlalchemy.orm import Session

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User, Role, ClassSection, Student, MessageLog, ExeatRecord, Semester, AcademicYear
from backend.app.routes.messaging import (
    get_messaging_recipients, generate_report_payload, log_sent_message, log_batch_messages, get_message_logs
)

def run_tests():
    print("==================================================")
    print(" BULK MESSAGING & DISPATCH VERIFICATION SUITE    ")
    print("==================================================")

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Setup Test Data
        print("\n[1] Setting up messaging test environment...")

        role_admin = db.query(Role).filter(Role.name == "admin").first()
        if not role_admin:
            role_admin = Role(name="admin")
            db.add(role_admin)
            db.commit()

        user_admin = db.query(User).filter(User.username == "test_messaging_admin").first()
        if not user_admin:
            user_admin = User(username="test_messaging_admin", email="msg_admin@school.edu", password_hash="pass", roles=[role_admin])
            db.add(user_admin)
            db.commit()

        class_sec = db.query(ClassSection).filter(ClassSection.name == "Form 1 MSG Test").first()
        if not class_sec:
            class_sec = ClassSection(name="Form 1 MSG Test", stage_id=1)
            db.add(class_sec)
            db.commit()

        st = db.query(Student).filter(Student.student_code == "MSG-STU-001").first()
        if not st:
            st = Student(
                student_code="MSG-STU-001",
                full_name="Kofi Mensah",
                class_section_id=class_sec.id,
                guardian_name="Mr. Mensah",
                phone="+233241234567",
                is_active=True
            )
            db.add(st)
            db.commit()
        else:
            st.class_section_id = class_sec.id
            st.full_name = "Kofi Mensah"
            st.phone = "+233241234567"
            db.commit()

        db.query(Student).filter(Student.class_section_id == class_sec.id, Student.id != st.id).update({"class_section_id": None})
        db.commit()

        exeat = db.query(ExeatRecord).filter(ExeatRecord.student_id == st.id).first()
        if not exeat:
            now = datetime.now()
            exeat = ExeatRecord(
                student_id=st.id,
                exeat_type="Medical Exeat",
                destination="Regional Hospital",
                reason="Routine checkup",
                expected_departure=now,
                expected_return=now,
                status="Approved"
            )
            db.add(exeat)
            db.commit()

        print("   [OK] Test student, class section, guardian phone, and Exeat record established.")

        # 2. Test Recipients Endpoint
        print("\n[2] Testing /recipients Endpoint...")
        recipients = get_messaging_recipients(class_id=class_sec.id, house_id=None, program_id=None, group_by_parent=False, db=db, current_user=user_admin)
        assert len(recipients) > 0, "Recipients list should not be empty!"
        assert recipients[0]["full_name"] == "Kofi Mensah", "Student name should match!"
        assert recipients[0]["phone"] == "+233241234567", "Guardian phone number should match!"
        print(f"   [OK] Retrieved {len(recipients)} recipient(s). Guardian Contact: {recipients[0]['phone']}")

        # 3. Test Terminal Report Payload Generation
        print("\n[3] Testing Terminal Report Payload Generation...")
        payload_req = {"student_id": st.id, "msg_type": "TERMINAL_REPORT"}
        res_rep = generate_report_payload(payload_req, db, user_admin)
        assert "whatsapp_payload" in res_rep and "sms_payload" in res_rep, "Payload response missing message body!"
        assert "Kofi Mensah" in res_rep["whatsapp_payload"], "WhatsApp payload missing student name!"
        assert "REPORT:" in res_rep["sms_payload"], "SMS payload missing REPORT header!"
        print("   [OK] Terminal report SMS & WhatsApp payloads generated.")

        # 4. Test Exeat Notice Payload Generation
        print("\n[4] Testing Exeat Pass Notice Payload Generation...")
        payload_ex = {"student_id": st.id, "msg_type": "EXEAT_NOTICE"}
        res_ex = generate_report_payload(payload_ex, db, user_admin)
        assert "EXEAT & LEAVE PASS NOTICE" in res_ex["whatsapp_payload"], "Exeat WhatsApp payload format mismatch!"
        assert "Medical Exeat" in res_ex["sms_payload"], "Exeat SMS payload missing Exeat type!"
        print("   [OK] Exeat notice payload generated.")

        # 5. Test Single and Batch Delivery Logging
        print("\n[5] Testing Outbox Delivery Logging...")
        log_req = {
            "student_id": st.id,
            "recipient_name": "Mr. Mensah",
            "recipient_phone": "+233241234567",
            "channel": "SMS",
            "message_type": "EXEAT_NOTICE",
            "message_body": res_ex["sms_payload"],
            "overall_grade": "Approved",
            "status": "SENT"
        }
        res_log = log_sent_message(log_req, db, user_admin)
        assert res_log["status"] == "success", "Single message log failed!"

        batch_req = [log_req, log_req]
        res_batch = log_batch_messages(batch_req, db, user_admin)
        assert res_batch["count"] == 2, "Batch log count mismatch!"
        print(f"   [OK] Logged single entry and batch of {res_batch['count']} delivery entries.")

        # 6. Test Outbox Log Retrieval
        print("\n[6] Testing Outbox History Query...")
        logs = get_message_logs(db, user_admin)
        assert len(logs) >= 3, "Outbox history should contain at least 3 logged records!"
        assert logs[0]["recipient_phone"] == "+233241234567", "Outbox log record phone mismatch!"
        print(f"   [OK] Outbox history query returned {len(logs)} entries.")

        print("\n==================================================")
        print(" ALL BULK MESSAGING VERIFICATION TESTS PASSED!   ")
        print("==================================================")

    except Exception as e:
        print(f"\n[FAIL] MESSAGING VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
