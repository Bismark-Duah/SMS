import unittest
import hmac
import hashlib
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.models import Base, School, SchoolSubaccount, VoucherOrder
from backend.app.services.payment_orchestrator import (
    create_or_update_paystack_subaccount,
    verify_paystack_webhook_signature,
    initialize_voucher_checkout,
    PAYSTACK_SECRET_KEY
)

class TestPaymentOrchestrator(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        school = School(id=2, name="Prempeh College", code="PREMPEH")
        self.session.add(school)
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_create_or_update_paystack_subaccount(self):
        """Verifies subaccount provisioning and split percentage persistence."""
        res = create_or_update_paystack_subaccount(
            school_id=2,
            business_name="Prempeh College PTA",
            settlement_bank="MTN",
            account_number="0244123456",
            percentage_charge=98.0,
            db=self.session
        )
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["subaccount_code"].startswith("ACCT_2_MTN_"))
        
        sub = self.session.query(SchoolSubaccount).filter(SchoolSubaccount.school_id == 2).first()
        self.assertIsNotNone(sub)
        self.assertEqual(sub.account_number, "0244123456")
        self.assertEqual(sub.percentage_split, 98.0)

    def test_verify_paystack_webhook_signature(self):
        """Verifies HMAC-SHA512 webhook signature verification."""
        payload = json.dumps({"event": "charge.success", "data": {"reference": "VCH-1234"}}).encode("utf-8")
        valid_signature = hmac.new(PAYSTACK_SECRET_KEY.encode("utf-8"), payload, hashlib.sha512).hexdigest()
        
        self.assertTrue(verify_paystack_webhook_signature(payload, valid_signature))
        self.assertFalse(verify_paystack_webhook_signature(payload, "invalid_signature_hash"))
        self.assertFalse(verify_paystack_webhook_signature(payload, ""))

    def test_initialize_voucher_checkout(self):
        """Verifies checkout initialization and subaccount attachment."""
        create_or_update_paystack_subaccount(
            school_id=2,
            business_name="Prempeh College",
            settlement_bank="GCB",
            account_number="1234567890",
            percentage_charge=98.0,
            db=self.session
        )

        checkout = initialize_voucher_checkout(
            school_id=2,
            applicant_name="Kofi Annan",
            applicant_phone="0244555666",
            applicant_email="kofi@annan.com",
            amount=100.0,
            gateway="PAYSTACK",
            db=self.session
        )

        self.assertTrue(checkout["order_reference"].startswith("VCH-"))
        self.assertEqual(checkout["amount"], 100.0)
        self.assertTrue(checkout["subaccount_code"].startswith("ACCT_2_GCB_"))
        
        order = self.session.query(VoucherOrder).filter(VoucherOrder.order_reference == checkout["order_reference"]).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.status, "PENDING")

if __name__ == "__main__":
    unittest.main()
