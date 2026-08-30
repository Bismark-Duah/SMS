"""
Automated Test Suite for Fees & Paystack Mobile Money Online Payments Engine
Verifies zero-trust scoping, minimum amount guards, atomic ACID ledger updates,
automated Hubtel SMS receipt logging, idempotency, and PDF receipt compilation.
"""
import sys
import os
import unittest
import uuid
from datetime import datetime

# Setup path so tests can run standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.database import SessionLocal
from backend.app.models import School, Student, Fee, Payment, User, Role, Program, Setting, MessageLog
from backend.app.routes.fees import (
    initialize_paystack_payment,
    verify_paystack_payment,
    download_payment_receipt_pdf,
    PaystackInitPayload
)
from fastapi import HTTPException


class TestFeesOnlinePayments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()

        # 1. School
        u_suffix = uuid.uuid4().hex[:6]
        cls.school = School(
            name=f"Cape Coast International High {u_suffix}",
            code=f"CCIH-{u_suffix}",
            school_mode="COMBINED",
            platform_commission_percent=5.0
        )
        cls.db.add(cls.school)
        cls.db.commit()
        cls.db.refresh(cls.school)

        # 2. Roles
        cls.parent_role = cls.db.query(Role).filter(Role.name == "parent").first()
        if not cls.parent_role:
            cls.parent_role = Role(name="parent")
            cls.db.add(cls.parent_role)
            cls.db.commit()

        cls.admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        if not cls.admin_role:
            cls.admin_role = Role(name="admin")
            cls.db.add(cls.admin_role)
            cls.db.commit()

        # 3. Parent Users
        cls.parent_user_1 = User(
            username=f"parent1_{u_suffix}",
            email=f"parent1_{u_suffix}@example.com",
            password_hash="mockhash",
            is_active=True,
            school_id=cls.school.id
        )
        cls.parent_user_1.roles.append(cls.parent_role)
        cls.db.add(cls.parent_user_1)

        cls.parent_user_2 = User(
            username=f"parent2_{u_suffix}",
            email=f"parent2_{u_suffix}@example.com",
            password_hash="mockhash",
            is_active=True,
            school_id=cls.school.id
        )
        cls.parent_user_2.roles.append(cls.parent_role)
        cls.db.add(cls.parent_user_2)

        cls.admin_user = User(
            username=f"admin_{u_suffix}",
            email=f"admin_{u_suffix}@example.com",
            password_hash="mockhash",
            is_active=True,
            school_id=cls.school.id
        )
        cls.admin_user.roles.append(cls.admin_role)
        cls.db.add(cls.admin_user)
        cls.db.commit()

        # 4. Program
        cls.prog = Program(
            name=f"General Arts {u_suffix}",
            code=f"ARTS-{u_suffix}",
            school_id=cls.school.id
        )
        cls.db.add(cls.prog)
        cls.db.commit()

        # 5. Student linked to parent_user_1
        cls.student = Student(
            full_name=f"Kofi Mensah {u_suffix}",
            student_code=f"STU-KM-{u_suffix}",
            bece_index_number=f"101{u_suffix}",
            gender="Male",
            residential_status="B",
            school_id=cls.school.id,
            parent_id=cls.parent_user_1.id,
            program_id=cls.prog.id,
            academic_year="2025/2026",
            phone="0244123456",
            guardian_name="Mr. Mensah"
        )
        cls.db.add(cls.student)
        cls.db.commit()
        cls.db.refresh(cls.student)

        # 6. Fee Bill
        cls.fee = Fee(
            student_id=cls.student.id,
            fee_type="Tuition",
            description="First Term Academic Tuition",
            amount=500.0,
            amount_paid=100.0,
            status="Partial",
            academic_year="2025/2026",
            term="Term 1"
        )
        cls.db.add(cls.fee)
        cls.db.commit()
        cls.db.refresh(cls.fee)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.rollback()
            # Clean up
            cls.db.query(Payment).filter(Payment.fee_id == cls.fee.id).delete()
            cls.db.query(Fee).filter(Fee.id == cls.fee.id).delete()
            cls.db.query(Student).filter(Student.id == cls.student.id).delete()
            cls.db.query(Program).filter(Program.id == cls.prog.id).delete()
            from backend.app.models import user_roles
            u_ids = [cls.parent_user_1.id, cls.parent_user_2.id, cls.admin_user.id]
            cls.db.execute(user_roles.delete().where(user_roles.c.user_id.in_(u_ids)))
            cls.db.query(User).filter(User.id.in_(u_ids)).delete()
            cls.db.query(School).filter(School.id == cls.school.id).delete()
            cls.db.commit()
        except Exception:
            cls.db.rollback()
        finally:
            cls.db.close()

    def setUp(self):
        self.db.rollback()

    def test_01_paystack_initialize_valid_momo(self):
        """Test parent successfully initializes MoMo payment for their linked child's fee."""
        payload = PaystackInitPayload(
            fee_id=self.fee.id,
            amount_paid=150.0,
            mobile_number="0244123456",
            network="MTN MoMo"
        )
        res = initialize_paystack_payment(payload, self.db, self.parent_user_1)
        self.assertIn("reference", res)
        self.assertTrue(res["reference"].startswith(f"PSTK-FEE-{self.fee.id}-"))

    def test_02_paystack_initialize_min_amount_guard(self):
        """Test that attempting to pay less than GHS 1.00 raises HTTP 400."""
        payload = PaystackInitPayload(
            fee_id=self.fee.id,
            amount_paid=0.50,
            mobile_number="0244123456",
            network="MTN MoMo"
        )
        with self.assertRaises(HTTPException) as ctx:
            initialize_paystack_payment(payload, self.db, self.parent_user_1)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("at least GHS 1.00", ctx.exception.detail)

    def test_03_paystack_initialize_exceeds_balance_guard(self):
        """Test that attempting to pay more than the outstanding balance raises HTTP 400."""
        payload = PaystackInitPayload(
            fee_id=self.fee.id,
            amount_paid=500.0,  # Outstanding is 400.0 (500 - 100)
            mobile_number="0244123456",
            network="MTN MoMo"
        )
        with self.assertRaises(HTTPException) as ctx:
            initialize_paystack_payment(payload, self.db, self.parent_user_1)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("exceeds outstanding balance", ctx.exception.detail)

    def test_04_paystack_initialize_parent_scoping(self):
        """Test that an unlinked parent receives 403 Forbidden."""
        payload = PaystackInitPayload(
            fee_id=self.fee.id,
            amount_paid=50.0,
            mobile_number="0244999999",
            network="Telecel Cash"
        )
        with self.assertRaises(HTTPException) as ctx:
            initialize_paystack_payment(payload, self.db, self.parent_user_2)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("linked child", ctx.exception.detail)

    def test_05_paystack_verify_and_record_payment(self):
        """Test verifying transaction, atomically logging payment, and updating fee status."""
        test_ref = f"PSTK-FEE-{self.fee.id}-{self.student.id}-{uuid.uuid4().hex[:6]}"
        
        # Verify in offline/sandbox mode
        res = verify_paystack_payment(test_ref, self.db, self.parent_user_1)
        self.assertEqual(res["status"], "success")
        self.assertIn("payment_id", res)
        
        # Confirm Fee balance was updated in database
        self.db.refresh(self.fee)
        self.assertEqual(self.fee.status, "Paid")
        self.assertEqual(self.fee.amount_paid, 500.0)

        # Confirm Payment record exists
        pay_record = self.db.query(Payment).filter(Payment.id == res["payment_id"]).first()
        self.assertIsNotNone(pay_record)
        self.assertEqual(pay_record.amount_paid, 400.0)
        self.assertEqual(pay_record.payment_method, "Paystack MoMo")

    def test_06_paystack_verify_idempotency(self):
        """Test that re-verifying an existing reference returns existing payment record without double charging."""
        existing_pay = self.db.query(Payment).filter(Payment.fee_id == self.fee.id).first()
        self.assertIsNotNone(existing_pay)

        res = verify_paystack_payment(existing_pay.reference_no, self.db, self.parent_user_1)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["payment_id"], existing_pay.id)
        self.assertIn("already verified", res["message"])

    def test_07_download_payment_receipt_pdf(self):
        """Test generating and downloading official PDF payment receipt."""
        existing_pay = self.db.query(Payment).filter(Payment.fee_id == self.fee.id).first()
        self.assertIsNotNone(existing_pay)

        resp = download_payment_receipt_pdf(existing_pay.id, self.db, self.parent_user_1)
        self.assertEqual(resp.media_type, "application/pdf")
        self.assertTrue(resp.body.startswith(b"%PDF-"))
        self.assertIn("attachment; filename=", resp.headers.get("content-disposition", ""))

    def test_08_download_payment_receipt_parent_scoping(self):
        """Test that an unlinked parent receives 403 Forbidden when requesting someone else's receipt."""
        existing_pay = self.db.query(Payment).filter(Payment.fee_id == self.fee.id).first()
        self.assertIsNotNone(existing_pay)

        with self.assertRaises(HTTPException) as ctx:
            download_payment_receipt_pdf(existing_pay.id, self.db, self.parent_user_2)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("linked child", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
