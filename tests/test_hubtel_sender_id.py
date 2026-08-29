import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.models import Base, School, TenantSmsConfig, MessageLog
from backend.app.services.messaging_service import send_sms_via_hubtel

class TestHubtelSenderId(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        school = School(id=3, name="Presbyterian Boys Secondary School", code="PRESEC")
        self.session.add(school)

        sms_cfg = TenantSmsConfig(
            school_id=3,
            sender_id="PRESEC",
            provider="HUBTEL",
            status="ACTIVE"
        )
        self.session.add(sms_cfg)
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_send_sms_via_hubtel_dynamic_sender_id(self):
        """Verifies that SMS dispatch automatically resolves the tenant's approved 11-char Sender ID."""
        res = send_sms_via_hubtel(
            recipient_phone="0244123456",
            message_body="Your Admission Voucher PIN is 987654",
            school_id=3,
            db=self.session
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["sender_id"], "PRESEC")
        self.assertEqual(res["recipient"], "233244123456")

        # Verify audit log entry
        log = self.session.query(MessageLog).filter(MessageLog.recipient_phone == "233244123456").first()
        self.assertIsNotNone(log)
        self.assertIn("987654", log.message_body)

    def test_send_sms_via_hubtel_fallback_sender_id(self):
        """Verifies that non-configured schools gracefully fallback to EDUMANAGE."""
        res = send_sms_via_hubtel(
            recipient_phone="0501234567",
            message_body="Welcome to EduManage360",
            school_id=999,  # Unconfigured school
            db=self.session
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["sender_id"], "EDUMANAGE")

if __name__ == "__main__":
    unittest.main()
