"""
test_fee_financial_audit.py — Comprehensive Test Suite for Offline Fee Receipt Generation, Balance Concurrency, and Anti-Fraud Protection
"""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException
from backend.app.database import SessionLocal, engine, Base, run_migrations
from backend.app.models import (
    User, Role, School, Student, Fee, Payment, ClassSection, SchoolStage
)
from backend.app.routes.fees import (
    record_payment, update_fee, delete_fee, download_payment_receipt_pdf,
    PaymentCreate, FeeUpdate, generate_receipt_number
)
from backend.app.services.sync_engine import apply_sync_bundle


class TestFeeFinancialAudit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        run_migrations()
        cls.db = SessionLocal()

        admin_role = cls.db.query(Role).filter(Role.name == "bursar").first()
        if not admin_role:
            admin_role = Role(name="bursar")
            cls.db.add(admin_role)
            cls.db.commit()

        # School A (Achimota)
        cls.sch_a = cls.db.query(School).filter(School.code == "ACH").first()
        if not cls.sch_a:
            cls.sch_a = School(name="Achimota Senior High", code="ACH", status="ACTIVE", school_mode="COMBINED")
            cls.db.add(cls.sch_a)
            cls.db.commit()
            cls.db.refresh(cls.sch_a)

        # School B (Prempeh)
        cls.sch_b = cls.db.query(School).filter(School.code == "PREM").first()
        if not cls.sch_b:
            cls.sch_b = School(name="Prempeh College", code="PREM", status="ACTIVE", school_mode="COMBINED")
            cls.db.add(cls.sch_b)
            cls.db.commit()
            cls.db.refresh(cls.sch_b)

        # Bursar Users
        cls.bursar_a = cls.db.query(User).filter(User.username == "bursar_ach").first()
        if not cls.bursar_a:
            cls.bursar_a = User(
                username="bursar_ach", email="bursar_a@test.local",
                password_hash="hash", is_active=True, school_id=cls.sch_a.id,
                roles=[admin_role]
            )
            cls.db.add(cls.bursar_a)

        cls.bursar_b = cls.db.query(User).filter(User.username == "bursar_prem").first()
        if not cls.bursar_b:
            cls.bursar_b = User(
                username="bursar_prem", email="bursar_b@test.local",
                password_hash="hash", is_active=True, school_id=cls.sch_b.id,
                roles=[admin_role]
            )
            cls.db.add(cls.bursar_b)

        cls.db.commit()

        # Stage & Class for School A
        stage_a = cls.db.query(SchoolStage).filter(SchoolStage.school_id == cls.sch_a.id).first()
        if not stage_a:
            stage_a = SchoolStage(name="Stage ACH", school_type="SHS", school_id=cls.sch_a.id)
            cls.db.add(stage_a)
            cls.db.commit()
            cls.db.refresh(stage_a)

        cs_a = cls.db.query(ClassSection).filter(ClassSection.school_id == cls.sch_a.id).first()
        if not cs_a:
            cs_a = ClassSection(name="Class ACH 1", stage_id=stage_a.id, school_id=cls.sch_a.id)
            cls.db.add(cs_a)
            cls.db.commit()
            cls.db.refresh(cs_a)

        # Student for School A
        cls.student_a = cls.db.query(Student).filter(Student.student_code == "ACH-001").first()
        if not cls.student_a:
            cls.student_a = Student(
                student_code="ACH-001", full_name="Kofi Mensah", first_name="Kofi", last_name="Mensah",
                school_id=cls.sch_a.id, class_section_id=cs_a.id, is_active=True
            )
            cls.db.add(cls.student_a)
            cls.db.commit()
            cls.db.refresh(cls.student_a)

        # Fee for Student A (Billed 1000 GHS)
        cls.fee_a = Fee(
            student_id=cls.student_a.id, fee_type="Tuition", amount=1000.0,
            amount_paid=0.0, status="Pending"
        )
        cls.db.add(cls.fee_a)
        cls.db.commit()
        cls.db.refresh(cls.fee_a)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_receipt_number_generation_and_tenant_scoping(self):
        """Verify receipt numbers are tenant-scoped and formatted cleanly."""
        rc_a = generate_receipt_number(self.db, school_id=self.sch_a.id)
        rc_b = generate_receipt_number(self.db, school_id=self.sch_b.id)

        self.assertTrue(rc_a.startswith("REC/ACH/"))
        self.assertTrue(rc_b.startswith("REC/PREM/"))
        self.assertNotEqual(rc_a, rc_b)

    def test_02_record_payment_and_atomic_balance(self):
        """Verify record_payment atomically increments amount_paid and generates persistent receipt_number."""
        pay_payload = PaymentCreate(
            amount_paid=400.0,
            payment_method="Cash",
            notes="First term partial deposit"
        )
        res = record_payment(
            fee_id=self.fee_a.id,
            payload=pay_payload,
            db=self.db,
            current_user=self.bursar_a
        )

        self.assertEqual(res["amount_paid"], 400.0)
        self.assertEqual(res["balance"], 600.0)
        self.assertEqual(res["status"], "Partial")

        # Check Payment row
        payment_row = self.db.query(Payment).filter(Payment.fee_id == self.fee_a.id).first()
        self.assertIsNotNone(payment_row)
        self.assertTrue(payment_row.receipt_number.startswith("REC/ACH/"))

    def test_03_overpayment_boundary_rejection(self):
        """Verify system rejects payment exceeding outstanding balance."""
        excess_payload = PaymentCreate(
            amount_paid=800.0,  # Balance is 600.0, so 800.0 must be rejected
            payment_method="Cash"
        )
        with self.assertRaises(HTTPException) as ctx:
            record_payment(
                fee_id=self.fee_a.id,
                payload=excess_payload,
                db=self.db,
                current_user=self.bursar_a
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("exceeds remaining balance", ctx.exception.detail)

    def test_04_anti_fraud_amount_reduction_guard(self):
        """Verify Bursar cannot reduce fee amount below what has already been collected."""
        # Student has paid 400.0 GHS. Bursar attempts to reduce billed amount to 250.0 GHS.
        fraud_update = FeeUpdate(amount=250.0)
        with self.assertRaises(HTTPException) as ctx:
            update_fee(
                fee_id=self.fee_a.id,
                payload=fraud_update,
                db=self.db,
                current_user=self.bursar_a
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Cannot reduce billed fee", ctx.exception.detail)

    def test_05_anti_fraud_fee_deletion_guard(self):
        """Verify Bursar cannot delete a fee record that has collected payments."""
        with self.assertRaises(HTTPException) as ctx:
            delete_fee(
                fee_id=self.fee_a.id,
                db=self.db,
                current_user=self.bursar_a
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Cannot delete fee record", ctx.exception.detail)

    def test_06_pdf_receipt_generation_with_tenant_number(self):
        """Verify PDF receipt compiles with persistent tenant receipt number."""
        payment_row = self.db.query(Payment).filter(Payment.fee_id == self.fee_a.id).first()
        response = download_payment_receipt_pdf(
            payment_id=payment_row.id,
            db=self.db,
            current_user=self.bursar_a
        )
        self.assertEqual(response.media_type, "application/pdf")
        self.assertGreater(len(response.body), 1000)
        self.assertIn(payment_row.receipt_number.replace('/', '_'), response.headers.get("Content-Disposition", ""))


if __name__ == "__main__":
    unittest.main()
