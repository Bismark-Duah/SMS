"""
Automated Verification Script for Attendance Tracking & Absence Alerts (via SMS)
"""
import sys
from datetime import datetime, date
from sqlalchemy.orm import Session

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User, Role, ClassSection, Student, Attendance, MessageLog
from backend.app.schemas import AttendanceCreate
from backend.app.routes.attendance import create_attendance, bulk_create_attendance
from backend.app.routes.messaging import log_sent_message, generate_report_payload

def run_tests():
    print("==================================================")
    print(" ATTENDANCE & SMS ABSENCE ALERT VERIFICATION SUITE")
    print("==================================================")

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Setup Test Data
        print("\n[1] Setting up attendance test environment...")

        role_admin = db.query(Role).filter(Role.name == "admin").first()
        if not role_admin:
            role_admin = Role(name="admin")
            db.add(role_admin)
            db.commit()

        user_admin = db.query(User).filter(User.username == "admin").first()

        class_sec = db.query(ClassSection).filter(ClassSection.name == "Form 1 Attendance Test").first()
        if not class_sec:
            class_sec = ClassSection(name="Form 1 Attendance Test", stage_id=1)
            db.add(class_sec)
            db.commit()

        st = db.query(Student).filter(Student.student_code == "ATT-STU-001").first()
        if not st:
            st = Student(
                student_code="ATT-STU-001",
                full_name="Abena Osei",
                class_section_id=class_sec.id,
                guardian_name="Mrs. Osei",
                phone="+233200001122",
                is_active=True
            )
            db.add(st)
            db.commit()

        # Clean up any remnants from previous test runs to ensure test idempotency
        db.query(Attendance).filter(Attendance.student_id == st.id).delete()
        db.query(MessageLog).filter(MessageLog.student_id == st.id).delete()
        db.commit()

        today_str = date.today().strftime("%Y-%m-%d")
        print(f"   [OK] Test student set up: {st.full_name} (Phone: {st.phone}). Testing date: {today_str}")

        # 2. Test Marking Absent Creates PENDING ABSENCE_ALERT
        print("\n[2] Marking Student ABSENT and verifying PENDING ABSENCE_ALERT draft creation...")
        att_payload = AttendanceCreate(student_id=st.id, date=today_str, status="Absent")
        create_attendance(att_payload, db=db, current_user=user_admin)

        msg_draft = (
            db.query(MessageLog)
            .filter(
                MessageLog.student_id == st.id,
                MessageLog.message_type == "ABSENCE_ALERT",
                MessageLog.message_body.like(f"%on {today_str}%")
            )
            .first()
        )

        assert msg_draft is not None, "MessageLog draft should be created when student is marked Absent!"
        assert msg_draft.status == "PENDING", f"Draft status should be PENDING, got: {msg_draft.status}"
        assert "Abena Osei" in msg_draft.message_body, "Message body should mention student name!"
        assert msg_draft.recipient_phone == "+233200001122", "Recipient phone mismatch!"
        print(f"   [OK] ABSENCE_ALERT created with status: {msg_draft.status}. Body: {msg_draft.message_body}")

        # 3. Test Re-marking Absent Does Not Create Duplicates
        print("\n[3] Re-marking Student ABSENT (Upsert) and asserting Duplicate Prevention...")
        create_attendance(att_payload, db=db, current_user=user_admin)

        all_alerts = (
            db.query(MessageLog)
            .filter(
                MessageLog.student_id == st.id,
                MessageLog.message_type == "ABSENCE_ALERT",
                MessageLog.message_body.like(f"%on {today_str}%")
            )
            .all()
        )
        assert len(all_alerts) == 1, f"Expected exactly 1 alert draft, found {len(all_alerts)}"
        print("   [OK] Re-marking attendance kept a single draft record (No duplicates).")

        # 4. Test Payload Endpoint for ABSENCE_ALERT
        print("\n[4] Testing /messaging/report-payload with msg_type=ABSENCE_ALERT...")
        rep_res = generate_report_payload({"student_id": st.id, "msg_type": "ABSENCE_ALERT"}, db=db, current_user=user_admin)
        assert "ABSENCE ALERT" in rep_res["whatsapp_payload"], "WhatsApp payload missing header!"
        assert rep_res["overall_grade"] == "ABSENT", "Overall grade should be ABSENT!"
        print("   [OK] Report payload correctly returns draft absence alert data.")

        # 5. Test Changing Status to Present Deletes PENDING Draft
        print("\n[5] Changing Student Attendance to PRESENT and asserting draft cleanup...")
        pres_payload = AttendanceCreate(student_id=st.id, date=today_str, status="Present")
        create_attendance(pres_payload, db=db, current_user=user_admin)

        deleted_draft = (
            db.query(MessageLog)
            .filter(
                MessageLog.student_id == st.id,
                MessageLog.message_type == "ABSENCE_ALERT",
                MessageLog.message_body.like(f"%on {today_str}%")
            )
            .first()
        )
        assert deleted_draft is None, "PENDING draft should be deleted when status changes away from Absent!"
        print("   [OK] Pending draft alert was automatically deleted when student was marked Present.")

        # 6. Test Marking Absent Again and Dispatching Log
        print("\n[6] Re-marking ABSENT and logging dispatch...")
        create_attendance(att_payload, db=db, current_user=user_admin)

        log_payload = {
            "student_id": st.id,
            "recipient_name": "Mrs. Osei",
            "recipient_phone": "+233200001122",
            "channel": "SMS",
            "message_type": "ABSENCE_ALERT",
            "message_body": f"Dear Mrs. Osei, please be informed that your child Abena Osei was marked ABSENT from school on {today_str}.",
            "overall_grade": "ABSENT",
            "status": "SENT"
        }
        res_log = log_sent_message(log_payload, db=db, current_user=user_admin)
        assert res_log["status"] == "success", "Log message execution failed!"

        final_log = db.query(MessageLog).filter(MessageLog.id == res_log["id"]).first()
        assert final_log.status == "SENT", f"Expected final status SENT, got: {final_log.status}"
        print(f"   [OK] Message draft status successfully updated to {final_log.status} upon dispatch.")

        print("\n==================================================")
        print(" ALL ATTENDANCE & SMS ALERT TESTS PASSED SUCCESSFULLY!")
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
