"""
Comprehensive Verification Suite: Cybersecurity-Hardened Unified Payment Webhook Pipeline
Tests HMAC SHA-512 cryptographic validation, idempotency (anti-double spending),
dual-layer routing, fee ledger reconciliation, and background task integration.
"""
import unittest
import os
import sys
import json
import hmac
import hashlib
import asyncio
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import BackgroundTasks, HTTPException

from backend.app.models import Base, School, Student, Fee, Payment, VoucherOrder, Voucher, Setting
from backend.app.payments.paystack import get_paystack_secret_key, verify_paystack_signature
from backend.app.services.payment_orchestrator import process_unified_payment_webhook
from backend.app.routes.vouchers import paystack_webhook as vouchers_paystack_webhook
from backend.app.routes.fees import paystack_webhook as fees_paystack_webhook

class TestHardenedPaymentWebhookSecurity(unittest.TestCase):
    def setUp(self):
        # Create an isolated in-memory SQLite database
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()

        # Seed test school and secret setting
        self.school = School(id=1, name="Mfantsipim School", code="MOBA", status="ACTIVE")
        self.db.add(self.school)
        
        self.secret_setting = Setting(key="paystack_secret_key", value="sk_test_mfantsipim_secure_secret_key_123")
        self.db.add(self.secret_setting)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _generate_signature(self, payload_bytes: bytes, secret: str = None) -> str:
        sec = secret or get_paystack_secret_key(self.db)
        return hmac.new(sec.encode("utf-8"), payload_bytes, hashlib.sha512).hexdigest()

    # ── TEST 1: Cryptographic HMAC SHA-512 Signature Guard ──────────────────────
    def test_hmac_signature_guard_acceptance_and_rejection(self):
        """Verifies valid signatures are accepted while missing, empty, or tampered signatures are rejected with 401."""
        secret = get_paystack_secret_key(self.db)
        raw_body = json.dumps({
            "event": "charge.success",
            "data": {
                "reference": "VCH-2026-SEC01",
                "amount": 10000,
                "metadata": {"payment_type": "prospectus"}
            }
        }).encode("utf-8")

        valid_sig = self._generate_signature(raw_body, secret)

        # 1. Valid Signature -> True
        self.assertTrue(verify_paystack_signature(raw_body, valid_sig, db=self.db))

        # 2. Missing or None Signature -> False
        self.assertFalse(verify_paystack_signature(raw_body, None, db=self.db))
        self.assertFalse(verify_paystack_signature(raw_body, "", db=self.db))
        self.assertFalse(verify_paystack_signature(raw_body, "   ", db=self.db))

        # 3. Tampered payload with original signature -> False
        tampered_body = json.dumps({
            "event": "charge.success",
            "data": {
                "reference": "VCH-2026-TAMPERED",
                "amount": 10000,
                "metadata": {"payment_type": "prospectus"}
            }
        }).encode("utf-8")
        self.assertFalse(verify_paystack_signature(tampered_body, valid_sig, db=self.db))

        # 4. Forged signature with wrong secret -> False
        forged_sig = self._generate_signature(raw_body, "sk_test_attacker_fake_key")
        self.assertFalse(verify_paystack_signature(raw_body, forged_sig, db=self.db))

        # 5. Null payload bytes -> False (No NullPointerException)
        self.assertFalse(verify_paystack_signature(None, valid_sig, db=self.db))

    # ── TEST 2: Webhook Idempotency (Anti-Double Spending) ─────────────────────
    def test_webhook_idempotency_voucher_fulfillment(self):
        """Verifies repeated voucher webhook invocations return already_processed without duplicate vouchers."""
        # 1. Seed pending voucher order
        order = VoucherOrder(
            order_reference="VCH-IDEM-001",
            school_id=1,
            applicant_name="Kwame Mensah",
            applicant_phone="0244111222",
            applicant_email="kwame@example.com",
            amount=100.0,
            status="PENDING"
        )
        self.db.add(order)
        self.db.commit()

        webhook_payload = {
            "event": "charge.success",
            "data": {
                "reference": "VCH-IDEM-001",
                "amount": 10000,
                "id": "PSTK_TXN_99881",
                "metadata": {"payment_type": "prospectus"}
            }
        }
        body_bytes = json.dumps(webhook_payload).encode("utf-8")
        sig = self._generate_signature(body_bytes)

        # First call: Successfully fulfills order
        res1 = process_unified_payment_webhook(body_bytes, sig, db=self.db)
        self.assertEqual(res1.get("status"), "success")
        self.assertEqual(res1.get("payment_type"), "prospectus")

        self.db.refresh(order)
        self.assertIn(order.status, ["CONFIRMED", "DELIVERED"])
        first_voucher_id = order.voucher_id
        self.assertIsNotNone(first_voucher_id)

        # Count total vouchers in DB
        voucher_count_initial = self.db.query(Voucher).count()

        # Second call (Duplicate webhook): Idempotently recognized
        res2 = process_unified_payment_webhook(body_bytes, sig, db=self.db)
        self.assertEqual(res2.get("status"), "already_processed")
        self.assertEqual(res2.get("voucher_id"), first_voucher_id)

        # Third call: Idempotently recognized
        res3 = process_unified_payment_webhook(body_bytes, sig, db=self.db)
        self.assertEqual(res3.get("status"), "already_processed")

        # Verify no duplicate vouchers minted
        self.assertEqual(self.db.query(Voucher).count(), voucher_count_initial)

    def test_webhook_idempotency_fee_ledger_balance(self):
        """Verifies repeated school fee webhook deliveries do not double-credit ledger balance."""
        # 1. Seed student & fee record
        student = Student(
            id=10,
            school_id=1,
            student_code="MOBA-2026-010",
            full_name="Kofi Appiah",
            first_name="Kofi",
            last_name="Appiah",
            phone="0244333444",
            enrollment_status="ADMITTED"
        )
        self.db.add(student)
        self.db.flush()

        fee = Fee(
            id=101,
            student_id=student.id,
            fee_type="Tuition & Boarding",
            amount=500.00,
            amount_paid=0.00,
            status="Pending"
        )
        self.db.add(fee)
        self.db.commit()

        webhook_payload = {
            "event": "charge.success",
            "data": {
                "reference": "PSTK-FEE-101-10-20260910",
                "amount": 25000, # 250.00 GHS in pesewas
                "channel": "mobile_money",
                "metadata": {
                    "payment_type": "school_fees",
                    "fee_id": 101,
                    "student_id": 10
                }
            }
        }
        body_bytes = json.dumps(webhook_payload).encode("utf-8")
        sig = self._generate_signature(body_bytes)

        # First call: Processes fee payment of 250.00 GHS
        res1 = process_unified_payment_webhook(body_bytes, sig, db=self.db)
        self.assertEqual(res1.get("status"), "success")
        self.assertEqual(res1.get("amount_paid"), 250.00)
        self.assertEqual(res1.get("new_balance"), 250.00)

        self.db.refresh(fee)
        self.assertEqual(fee.amount_paid, 250.00)
        self.assertEqual(self.db.query(Payment).filter(Payment.fee_id == 101).count(), 1)

        # Second call (Duplicate webhook): Idempotent guard halts double-credit
        res2 = process_unified_payment_webhook(body_bytes, sig, db=self.db)
        self.assertEqual(res2.get("status"), "already_processed")

        # Verify payments count and fee amount_paid remained exactly 250.00
        self.db.refresh(fee)
        self.assertEqual(fee.amount_paid, 250.00)
        self.assertEqual(self.db.query(Payment).filter(Payment.fee_id == 101).count(), 1)

    # ── TEST 3: Dual-Layer Multi-Type Routing ───────────────────────────────────
    def test_dual_layer_routing_implicit_prefix(self):
        """Verifies routing when metadata is omitted but reference prefix is present."""
        # 1. Prefix 'VCH-...' routes to prospectus/voucher branch
        vch_order = VoucherOrder(
            order_reference="VCH-ROUTING-PREFIX-01",
            school_id=1,
            applicant_name="Ama Serwaa",
            applicant_phone="0244777888",
            amount=80.0,
            status="PENDING"
        )
        self.db.add(vch_order)
        self.db.commit()

        vch_payload = {
            "event": "charge.success",
            "data": {
                "reference": "VCH-ROUTING-PREFIX-01",
                "amount": 8000
                # Note: No metadata.payment_type provided
            }
        }
        vch_bytes = json.dumps(vch_payload).encode("utf-8")
        vch_sig = self._generate_signature(vch_bytes)

        res_vch = process_unified_payment_webhook(vch_bytes, vch_sig, db=self.db)
        self.assertEqual(res_vch.get("status"), "success")
        self.assertEqual(res_vch.get("payment_type"), "prospectus")

        # 2. Prefix 'PSTK-FEE-...' routes to school_fees branch
        student = Student(id=20, school_id=1, student_code="MOBA-020", full_name="Yaw Boateng", first_name="Yaw", last_name="Boateng")
        fee = Fee(id=202, student_id=20, fee_type="Library Levy", amount=120.0, amount_paid=0.0)
        self.db.add(student)
        self.db.add(fee)
        self.db.commit()

        fee_payload = {
            "event": "charge.success",
            "data": {
                "reference": "PSTK-FEE-202-20-9999",
                "amount": 12000
                # Note: No metadata.payment_type provided
            }
        }
        fee_bytes = json.dumps(fee_payload).encode("utf-8")
        fee_sig = self._generate_signature(fee_bytes)

        res_fee = process_unified_payment_webhook(fee_bytes, fee_sig, db=self.db)
        self.assertEqual(res_fee.get("status"), "success")
        self.assertEqual(res_fee.get("payment_type"), "school_fees")

        self.db.refresh(fee)
        self.assertEqual(fee.amount_paid, 120.0)
        self.assertEqual(fee.status, "Paid")

    # ── TEST 4: FastAPI Webhook Route Security Invocations ─────────────────────
    def test_fastapi_webhook_routes_http_signatures(self):
        """Verifies HTTP 401 on invalid/missing signatures and HTTP 200 on valid signatures."""
        order = VoucherOrder(
            order_reference="VCH-HTTP-TEST-001",
            school_id=1,
            applicant_name="Test Student",
            applicant_phone="0244999000",
            amount=100.0,
            status="PENDING"
        )
        self.db.add(order)
        self.db.commit()

        payload = {
            "event": "charge.success",
            "data": {
                "reference": "VCH-HTTP-TEST-001",
                "amount": 10000,
                "metadata": {"payment_type": "prospectus"}
            }
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        valid_sig = self._generate_signature(payload_bytes)

        # 1. Missing signature header on /api/vouchers/webhook/paystack -> 401 Unauthorized
        req_no_sig = MagicMock()
        req_no_sig.body = AsyncMock(return_value=payload_bytes)
        bg = BackgroundTasks()

        with self.assertRaises(HTTPException) as ctx_no_sig:
            asyncio.run(vouchers_paystack_webhook(
                request=req_no_sig,
                background_tasks=bg,
                x_paystack_signature=None,
                db=self.db
            ))
        self.assertEqual(ctx_no_sig.exception.status_code, 401)

        # 2. Tampered signature -> 401 Unauthorized
        with self.assertRaises(HTTPException) as ctx_bad_sig:
            asyncio.run(vouchers_paystack_webhook(
                request=req_no_sig,
                background_tasks=bg,
                x_paystack_signature="forged_invalid_signature",
                db=self.db
            ))
        self.assertEqual(ctx_bad_sig.exception.status_code, 401)

        # 3. Valid signature on vouchers webhook -> 200 OK
        res_valid = asyncio.run(vouchers_paystack_webhook(
            request=req_no_sig,
            background_tasks=bg,
            x_paystack_signature=valid_sig,
            db=self.db
        ))
        self.assertEqual(res_valid.get("status"), "success")

        # 4. Valid signature on fees webhook -> 200 OK (already_processed)
        res_fee = asyncio.run(fees_paystack_webhook(
            request=req_no_sig,
            background_tasks=bg,
            db=self.db,
            x_paystack_signature=valid_sig
        ))
        self.assertEqual(res_fee.get("status"), "already_processed")

if __name__ == "__main__":
    unittest.main()
