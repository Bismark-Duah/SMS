import unittest
import json
import hmac
import hashlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.models import Base, School, VoucherOrder, AdmissionVoucher, Setting
from backend.app.services.payment_orchestrator import (
    verify_paystack_webhook_signature,
    verify_hubtel_webhook_signature,
    get_paystack_secret_key,
    get_hubtel_secret_key,
    fulfill_voucher_order_atomic
)

class TestWebhookSecurityRigor(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        school = School(id=1, name="Achimota School", code="ACH", status="ACTIVE")
        self.session.add(school)
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_paystack_webhook_cryptographic_verification(self):
        secret = get_paystack_secret_key(self.session)
        raw_body = json.dumps({"event": "charge.success", "data": {"reference": "VCH-RIGOR-001"}}).encode("utf-8")
        
        valid_sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
        
        # Valid signature
        self.assertTrue(verify_paystack_webhook_signature(raw_body, valid_sig, db=self.session))
        
        # Tampered body / signature mismatch
        tampered_body = json.dumps({"event": "charge.success", "data": {"reference": "VCH-TAMPERED-001"}}).encode("utf-8")
        self.assertFalse(verify_paystack_webhook_signature(tampered_body, valid_sig, db=self.session))
        
        # Empty signature
        self.assertFalse(verify_paystack_webhook_signature(raw_body, "", db=self.session))
        self.assertFalse(verify_paystack_webhook_signature(raw_body, None, db=self.session))

    def test_hubtel_webhook_secret_verification(self):
        hubtel_secret = get_hubtel_secret_key(self.session)
        raw_body = json.dumps({"Data": {"ClientReference": "VCH-HUBTEL-001", "Status": "SUCCESS"}}).encode("utf-8")
        
        # Valid secret token
        self.assertTrue(verify_hubtel_webhook_signature(raw_body, secret_token=hubtel_secret, db=self.session))
        
        # Invalid secret token
        self.assertFalse(verify_hubtel_webhook_signature(raw_body, secret_token="wrong_token", db=self.session))
        
        # Valid HMAC header
        valid_hmac = hmac.new(hubtel_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        self.assertTrue(verify_hubtel_webhook_signature(raw_body, signature_header=valid_hmac, db=self.session))
        self.assertFalse(verify_hubtel_webhook_signature(raw_body, signature_header="invalid_hash", db=self.session))

    def test_atomic_fulfillment_lifecycle(self):
        # Create available voucher
        vch = AdmissionVoucher(serial_code="ACH-VCH-999", pin_code="8877", status="AVAILABLE")
        self.session.add(vch)
        self.session.commit()

        # Create pending order
        order = VoucherOrder(
            order_reference="VCH-AUTO-001",
            school_id=1,
            applicant_phone="0244123456",
            amount=100.0,
            status="PENDING"
        )
        self.session.add(order)
        self.session.commit()

        res = fulfill_voucher_order_atomic("VCH-AUTO-001", "PSTK-TX-12345", self.session)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["serial_code"], "ACH-VCH-999")
        self.assertEqual(res["pin_code"], "8877")

        # Verify order marked confirmed or delivered
        self.session.refresh(order)
        self.assertIn(order.status, ["CONFIRMED", "DELIVERED"])
        self.assertEqual(order.voucher_id, vch.id)

if __name__ == "__main__":
    unittest.main()
