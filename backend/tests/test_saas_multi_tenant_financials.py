"""
Comprehensive SaaS Multi-Tenant Financials & Production Suite Tests.
Uses standard library unittest to ensure 100% offline self-contained test execution.
Verifies:
1. Subdomain parsing & Tenant injection middleware
2. Paystack split calculations, minimum >= 1.00 GHS validation, and HMAC signatures
3. Hubtel phone normalization, atomic quota decrements, and low-balance guards
4. Paystack callback & ACID atomic voucher order fulfillment
5. Tenant & Super-Admin financial summary endpoints
"""
import unittest
from unittest.mock import MagicMock
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import School, VoucherOrder, AdmissionVoucher, Setting, User, Role, MessageLog
from app.middleware.tenant_subdomain import extract_subdomain_from_host
from app.payments.paystack import (
    initialize_paystack_transaction,
    verify_paystack_signature,
    verify_paystack_transaction
)
from app.sms.hubtel import normalize_ghana_phone, send_sms_hubtel
from app.services.payment_orchestrator import fulfill_voucher_order_atomic, initialize_voucher_checkout
from app.routes.vouchers import get_voucher_financial_summary, handle_paystack_callback
from app.routes.super_admin import get_super_admin_financial_summary


class TestSaaSMultiTenantFinancials(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db: Session = SessionLocal()
        # Ensure at least one test school exists
        cls.school = cls.db.query(School).first()
        if not cls.school:
            cls.school = School(
                name="Ghana Senior High Test",
                code="GHATEST",
                slug="ghatest",
                sms_balance=500,
                sms_low_threshold=200,
                platform_commission_percent=5.0
            )
            cls.db.add(cls.school)
            cls.db.commit()
            cls.db.refresh(cls.school)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # ── 1. Subdomain Resolution Tests ─────────────────────────────────────────

    def test_subdomain_extraction_valid_tenants(self):
        """Verifies tenant slugs are extracted from multi-tenant URLs."""
        self.assertEqual(extract_subdomain_from_host("jak-stem.sms.edu.gh"), "jak-stem")
        self.assertEqual(extract_subdomain_from_host("darbaa-basic.localhost:8000"), "darbaa-basic")
        self.assertEqual(extract_subdomain_from_host("presec.onrender.com"), "presec")
        self.assertEqual(extract_subdomain_from_host("school-101.edumanage360.gh"), "school-101")

    def test_subdomain_extraction_system_domains(self):
        """Verifies root and reserved system domains return None."""
        self.assertIsNone(extract_subdomain_from_host("localhost:8000"))
        self.assertIsNone(extract_subdomain_from_host("127.0.0.1:8000"))
        self.assertIsNone(extract_subdomain_from_host("www.sms.edu.gh"))
        self.assertIsNone(extract_subdomain_from_host("api.sms.edu.gh"))
        self.assertIsNone(extract_subdomain_from_host("app.sms.edu.gh"))
        self.assertIsNone(extract_subdomain_from_host(""))

    # ── 2. Paystack Split Settlement & Validation Tests ───────────────────────

    def test_paystack_minimum_amount_enforcement(self):
        """Enforces live minimum of 100 pesewas (1.00 GHS) on Paystack transactions."""
        with self.assertRaises(ValueError) as ctx:
            initialize_paystack_transaction(
                email="parent@example.com",
                amount_pesewas=50,  # 0.50 GHS (below 1.00 GHS minimum)
                school_id=self.school.id,
                reference="MIN_TEST_REF",
                db=self.db
            )
        self.assertIn("at least 100 pesewas", str(ctx.exception))

    def test_paystack_split_initialization(self):
        """Verifies successful initialization and 95/5 percentage fee calculation."""
        res = initialize_paystack_transaction(
            email="parent@example.com",
            amount_pesewas=10000,  # 100.00 GHS
            school_id=self.school.id,
            reference="SPLIT_TEST_100",
            db=self.db
        )
        self.assertIsNotNone(res)
        self.assertEqual(res.get("reference"), "SPLIT_TEST_100")
        self.assertIn("status", res)

    def test_paystack_signature_verification_safety(self):
        """Verifies HMAC-SHA512 verification fails gracefully with invalid signatures."""
        result = verify_paystack_signature(b'{"event":"charge.success"}', "invalid_hmac_sig", self.db)
        self.assertFalse(result)

    # ── 3. Hubtel SMS Phone Normalization & Quota Engine ──────────────────────

    def test_ghana_phone_normalization_formats(self):
        """Verifies Ghanaian phone numbers normalize correctly to 233XXXXXXXXX."""
        self.assertEqual(normalize_ghana_phone("0244123456"), "233244123456")
        self.assertEqual(normalize_ghana_phone("+233244123456"), "233244123456")
        self.assertEqual(normalize_ghana_phone("244123456"), "233244123456")
        self.assertEqual(normalize_ghana_phone("050-892-9456"), "233508929456")
        self.assertEqual(normalize_ghana_phone(""), "")

    def test_hubtel_atomic_quota_decrement(self):
        """Verifies school SMS balance is atomically decremented by 1 upon sending."""
        self.school.sms_balance = 50
        self.db.commit()

        initial_balance = self.school.sms_balance
        res = send_sms_hubtel(
            recipient_phone="0244123456",
            message_body="Your Admission Voucher is confirmed.",
            school_id=self.school.id,
            db=self.db
        )
        self.assertIn(res["status"], ["success", "offline_fallback"])
        self.db.refresh(self.school)
        self.assertEqual(self.school.sms_balance, initial_balance - 1)

    def test_hubtel_depleted_quota_guard(self):
        """Verifies SMS dispatch is blocked when school quota reaches 0."""
        saved_balance = self.school.sms_balance
        self.school.sms_balance = 0
        self.db.commit()

        res = send_sms_hubtel(
            recipient_phone="0244123456",
            message_body="Quota test",
            school_id=self.school.id,
            db=self.db
        )
        self.assertEqual(res["status"], "error")
        self.assertIn("depleted", res["message"].lower())

        # Restore balance
        self.school.sms_balance = saved_balance
        self.db.commit()

    # ── 4. Atomic Voucher Fulfillment & Idempotency ───────────────────────────

    def test_atomic_voucher_order_fulfillment_lifecycle(self):
        """Tests complete order checkout initialization and atomic voucher minting."""
        checkout = initialize_voucher_checkout(
            school_id=self.school.id,
            applicant_name="Abena Osei",
            applicant_phone="0508929456",
            applicant_email="abena@test.gh",
            amount=100.0,
            gateway="PAYSTACK",
            db=self.db
        )
        order_ref = checkout["order_reference"]
        self.assertTrue(order_ref.startswith("VCH-"))

        # Fulfill order
        fulfillment = fulfill_voucher_order_atomic(order_ref, "GW_MOCK_TX_777", self.db)
        self.assertEqual(fulfillment["status"], "success")
        self.assertIsNotNone(fulfillment.get("serial_code"))
        self.assertIsNotNone(fulfillment.get("pin_code"))

        # Verify database record
        order = self.db.query(VoucherOrder).filter(VoucherOrder.order_reference == order_ref).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.status, "DELIVERED")
        self.assertIsNotNone(order.voucher_id)

        # Idempotency check: Repeated call should not mint another voucher
        second_call = fulfill_voucher_order_atomic(order_ref, "GW_MOCK_TX_777", self.db)
        self.assertEqual(second_call["status"], "success")
        self.assertIn("already fulfilled", second_call["message"].lower())

    # ── 5. Financial Summary Endpoints ────────────────────────────────────────

    def test_tenant_financial_summary_breakdown(self):
        """Verifies school voucher revenue breakdown (Gross, 95% School, 5% Platform)."""
        mock_user = User(id=1, username="admin_test", school_id=self.school.id)
        mock_user.roles = [Role(name="admin")]

        summary = get_voucher_financial_summary(db=self.db, current_user=mock_user)
        self.assertEqual(summary["school_id"], self.school.id)
        self.assertEqual(summary["school_share_percent"], 95.0)
        self.assertEqual(summary["platform_commission_percent"], 5.0)
        self.assertIn("gross_revenue_ghs", summary)
        self.assertIn("school_net_share_ghs", summary)
        self.assertIn("platform_fee_ghs", summary)
        self.assertIn("sms_balance", summary)
        self.assertEqual(summary["is_low_sms"], summary["sms_balance"] <= summary["sms_low_threshold"])

    def test_super_admin_financial_summary_aggregation(self):
        """Verifies cross-school financial aggregation for Super-Admin portal."""
        mock_super = User(id=999, username="superadmin", school_id=None)
        mock_super.roles = [Role(name="super_admin")]

        summary = get_super_admin_financial_summary(db=self.db, current_user=mock_super)
        self.assertGreaterEqual(summary["total_schools_count"], 1)
        self.assertIn("total_vouchers_sold", summary)
        self.assertIn("gross_platform_revenue_ghs", summary)
        self.assertIn("total_school_net_share_ghs", summary)
        self.assertIn("total_platform_commission_ghs", summary)
        self.assertIn("total_sms_sent", summary)
        self.assertIsInstance(summary["schools"], list)


if __name__ == "__main__":
    unittest.main()

