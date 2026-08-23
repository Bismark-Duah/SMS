"""
Automated Verification Script for Fee Payment Receipts & Overdue Fee SMS Alerts
"""
import sys
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User, Role, ClassSection, Student, Fee, Payment, MessageLog
from backend.app.routes.fees import record_payment, update_overdue_statuses, PaymentCreate
from backend.app.routes.messaging import generate_report_payload

def run_tests():
    print("==================================================")
    print(" FEE PAYMENT & OVERDUE SMS ALERT VERIFICATION SUITE")
    print("==================================================")

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Setup Test Data
        print("\n[1] Setting up fee test environment...")

        role_admin = db.query(Role).filter(Role.name == "admin").first()
        if not role_admin:
            role_admin = Role(name="admin")
            db.add(role_admin)
            db.commit()

        user_admin = db.query(User).filter(User.username == "admin").first()

        class_sec = db.query(ClassSection).filter(ClassSection.name == "Form 1 Fee Test").first()
        if not class_sec:
            class_sec = ClassSection(name="Form 1 Fee Test", stage_id=1)
            db.add(class_sec)
            db.commit()

        st = db.query(Student).filter(Student.student_code == "FEE-STU-001").first()
        if not st:
            st = Student(
                student_code="FEE-STU-001",
                full_name="Yaw Boateng",
                class_section_id=class_sec.id,
                guardian_name="Mr. Boateng",
                phone="+233244998877",
                is_active=True
            )
            db.add(st)
            db.commit()

        # Clean up any past test runs for idempotency
        db.query(Payment).filter(Payment.fee_id.in_(db.query(Fee.id).filter(Fee.student_id == st.id))).delete(synchronize_session=False)
        db.query(Fee).filter(Fee.student_id == st.id).delete(synchronize_session=False)
        db.query(MessageLog).filter(MessageLog.student_id == st.id).delete(synchronize_session=False)
        db.commit()

        test_fee = Fee(
            student_id=st.id,
            fee_type="Tuition",
            description="Term 1 Tuition Fee",
            amount=500.0,
            amount_paid=0.0,
            due_date=datetime.utcnow() + timedelta(days=10),
            status="Pending"
        )
        db.add(test_fee)
        db.commit()
        db.refresh(test_fee)
        print(f"   [OK] Created Fee #{test_fee.id} of GHS 500.00 for {st.full_name}.")

        # 2. Test Record Payment Auto-drafts Receipt
        print("\n[2] Recording GHS 200.00 Payment and verifying PENDING Payment Receipt draft...")
        pay_req = PaymentCreate(amount_paid=200.0, payment_method="Mobile Money")
        record_payment(test_fee.id, pay_req, db=db, current_user=user_admin)

        db.refresh(test_fee)
        assert test_fee.amount_paid == 200.0, "Fee amount_paid should be 200.0!"
        assert test_fee.status == "Partial", f"Expected fee status Partial, got: {test_fee.status}"

        receipt_log = (
            db.query(MessageLog)
            .filter(
                MessageLog.student_id == st.id,
                MessageLog.message_type == "FEE_NOTICE",
                MessageLog.message_body.like("%payment of GHS 200.00%")
            )
            .first()
        )
        assert receipt_log is not None, "MessageLog payment receipt draft should be created!"
        assert receipt_log.status == "PENDING", f"Receipt status should be PENDING, got: {receipt_log.status}"
        assert "Yaw Boateng" in receipt_log.message_body, "Receipt body should mention student name!"
        assert "Remaining balance: GHS 300.00" in receipt_log.message_body, "Receipt body should state balance!"
        print(f"   [OK] Payment receipt logged as PENDING: {receipt_log.message_body}")

        # 3. Test Overdue Scanner Drafts Reminder
        print("\n[3] Simulating Past Due Date and verifying Overdue Fee SMS draft...")
        test_fee.due_date = datetime.utcnow() - timedelta(days=1)
        db.commit()

        update_overdue_statuses(db)
        db.refresh(test_fee)
        assert test_fee.status == "Overdue", f"Expected status Overdue, got: {test_fee.status}"

        overdue_log = (
            db.query(MessageLog)
            .filter(
                MessageLog.student_id == st.id,
                MessageLog.message_type == "FEE_NOTICE",
                MessageLog.message_body.like("%OVERDUE%")
            )
            .first()
        )
        assert overdue_log is not None, "Overdue fee notice message draft should be created!"
        assert overdue_log.status == "PENDING", f"Overdue notice status should be PENDING, got: {overdue_log.status}"
        print(f"   [OK] Overdue fee notice logged as PENDING: {overdue_log.message_body}")

        # 4. Test Payload Endpoint for FEE_NOTICE
        print("\n[4] Testing /messaging/report-payload with msg_type=FEE_NOTICE...")
        rep_res = generate_report_payload({"student_id": st.id, "msg_type": "FEE_NOTICE"}, db=db, current_user=user_admin)
        assert "overall_grade" in rep_res, "Payload response missing overall_grade!"
        print("   [OK] Fee notice payload generated successfully.")

        print("\n==================================================")
        print(" ALL FEE PAYMENT & OVERDUE SMS TESTS PASSED!      ")
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
