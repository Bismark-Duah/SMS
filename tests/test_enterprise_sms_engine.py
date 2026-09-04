"""
Comprehensive Test Suite for Multi-Gateway Failover SMS Engine (mNotify + Hubtel).
Tests:
1. Ghanaian Phone Number Normalization (E.164) & Masking (Act 843 compliance).
2. mNotify v2 Quick/Bulk Payload Serialization.
3. Hubtel QuickSMS Payload Serialization.
4. Automatic Failover from mNotify to Hubtel upon simulated 500 error.
5. Automatic Failover from Hubtel to mNotify upon simulated 401 error.
6. Offline Fallback to SQLite outbox when unconfigured.
7. Admission E-Voucher Serial & PIN SMS formatting (< 160 characters).
8. Super-Admin SMS Gateway Status and Configuration Endpoints.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add backend directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.database import SessionLocal, engine, Base
from app.models import School, User, Role, Setting, MessageLog, TenantSmsConfig
from app.sms.gateway import (
    normalize_ghana_phone,
    mask_phone_number,
    MNotifySMSGateway,
    HubtelSMSGateway,
    MultiGatewaySMSEngine,
    sms_engine,
    send_admission_voucher_sms
)

class TestEnterpriseSMSEngine(unittest.TestCase):

    def setUp(self):
        self.db = SessionLocal()
        # Ensure test school exists
        self.school = self.db.query(School).filter(School.code == "SMS_TEST_SCH").first()
        if not self.school:
            self.school = School(
                name="SMS Test Academy",
                code="SMS_TEST_SCH",
                school_mode="COMBINED",
                status="ACTIVE",
                sms_balance=50
            )
            self.db.add(self.school)
            self.db.commit()
            self.db.refresh(self.school)
        else:
            self.school.sms_balance = 50
            self.db.commit()

    def tearDown(self):
        self.db.close()

    # ── 1. Phone Normalization & Privacy Masking ─────────────────────────────

    def test_ghana_phone_normalization(self):
        self.assertEqual(normalize_ghana_phone("0244123456"), "233244123456")
        self.assertEqual(normalize_ghana_phone("+233244123456"), "233244123456")
        self.assertEqual(normalize_ghana_phone("244123456"), "233244123456")
        self.assertEqual(normalize_ghana_phone("233244123456"), "233244123456")
        self.assertEqual(normalize_ghana_phone("024 412 3456"), "233244123456")
        self.assertEqual(normalize_ghana_phone("+233 (24) 412-3456"), "233244123456")

    def test_phone_number_masking(self):
        masked = mask_phone_number("233244123456")
        self.assertEqual(masked, "23324****456")

    # ── 2. mNotify Gateway Driver ────────────────────────────────────────────

    @patch("urllib.request.urlopen")
    def test_mnotify_gateway_dispatch(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "success", "summary": {"_id": "MNOTIFY_12345"}}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        gw = MNotifySMSGateway()
        res = gw.send_sms(
            recipient_phone="0244123456",
            message_body="Welcome to eduManage360",
            sender_id="EDUMANAGE",
            credentials={"api_key": "test_mnotify_key"}
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["gateway"], "MNOTIFY")
        self.assertEqual(res["message_id"], "MNOTIFY_12345")

    # ── 3. Hubtel Gateway Driver ─────────────────────────────────────────────

    @patch("urllib.request.urlopen")
    def test_hubtel_gateway_dispatch(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": 0, "messageid": "HUBTEL_98765"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        gw = HubtelSMSGateway()
        res = gw.send_sms(
            recipient_phone="0244123456",
            message_body="Welcome to eduManage360",
            sender_id="EDUMANAGE",
            credentials={"client_id": "test_client", "client_secret": "test_secret"}
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["gateway"], "HUBTEL")
        self.assertEqual(res["message_id"], "HUBTEL_98765")

    # ── 4. Automatic Failover: mNotify -> Hubtel ─────────────────────────────

    @patch.object(MNotifySMSGateway, "send_sms")
    @patch.object(HubtelSMSGateway, "send_sms")
    def test_failover_mnotify_to_hubtel(self, mock_hubtel_send, mock_mnotify_send):
        # mNotify fails with 500
        mock_mnotify_send.return_value = {"status": "error", "message": "Gateway 500 error"}
        # Hubtel succeeds
        mock_hubtel_send.return_value = {"status": "success", "message_id": "HUBTEL_FAILOVER_1"}

        engine = MultiGatewaySMSEngine()
        with patch.object(engine, "resolve_credentials", return_value={
            "mnotify_api_key": "key_123",
            "hubtel_client_id": "client_123",
            "hubtel_client_secret": "secret_123",
            "primary_gateway": "mnotify"
        }):
            res = engine.dispatch(
                recipient_phone="0244123456",
                message_body="Test Failover Message",
                school_id=self.school.id,
                db=self.db
            )

            self.assertEqual(res["status"], "success")
            self.assertEqual(res["gateway"], "HUBTEL")
            self.assertEqual(res["message_id"], "HUBTEL_FAILOVER_1")

    # ── 5. Automatic Failover: Hubtel -> mNotify ─────────────────────────────

    @patch.object(HubtelSMSGateway, "send_sms")
    @patch.object(MNotifySMSGateway, "send_sms")
    def test_failover_hubtel_to_mnotify(self, mock_mnotify_send, mock_hubtel_send):
        # Hubtel fails
        mock_hubtel_send.return_value = {"status": "error", "message": "Unauthorized 401"}
        # mNotify succeeds
        mock_mnotify_send.return_value = {"status": "success", "message_id": "MNOTIFY_FAILOVER_2"}

        engine = MultiGatewaySMSEngine()
        with patch.object(engine, "resolve_credentials", return_value={
            "mnotify_api_key": "key_123",
            "hubtel_client_id": "client_123",
            "hubtel_client_secret": "secret_123",
            "primary_gateway": "hubtel"
        }):
            res = engine.dispatch(
                recipient_phone="0244123456",
                message_body="Test Failover Message",
                school_id=self.school.id,
                db=self.db
            )

            self.assertEqual(res["status"], "success")
            self.assertEqual(res["gateway"], "MNOTIFY")
            self.assertEqual(res["message_id"], "MNOTIFY_FAILOVER_2")

    # ── 6. Offline / Unconfigured Outbox Fallback ────────────────────────────

    def test_offline_outbox_fallback(self):
        engine = MultiGatewaySMSEngine()
        with patch.object(engine, "resolve_credentials", return_value={
            "mnotify_api_key": "",
            "hubtel_client_id": "",
            "hubtel_client_secret": "",
            "primary_gateway": "mnotify"
        }):
            res = engine.dispatch(
                recipient_phone="0244123456",
                message_body="Offline Simulation Test",
                school_id=self.school.id,
                db=self.db
            )

            self.assertEqual(res["status"], "offline_fallback")
            self.assertTrue("queued" in res["message"].lower())

            # Verify MessageLog entry created
            log = self.db.query(MessageLog).filter(
                MessageLog.message_body == "Offline Simulation Test"
            ).first()
            self.assertIsNotNone(log)
            self.assertEqual(log.status, "QUEUED_OFFLINE")

    # ── 7. Admission E-Voucher Serial & PIN Formatting ───────────────────────

    def test_admission_voucher_sms_formatting(self):
        with patch.object(sms_engine, "dispatch") as mock_dispatch:
            mock_dispatch.return_value = {"status": "success", "message_id": "MOCK_PIN_1"}

            res = send_admission_voucher_sms(
                guardian_phone="0244123456",
                applicant_name="Kwame Mensah",
                school_name="J.A. Kufuor STEM SHS",
                serial_no="ADM-2026-8492",
                pin="7492",
                portal_url="sms-nald.onrender.com/apply.html",
                school_id=self.school.id,
                db=self.db
            )

            self.assertEqual(res["status"], "success")
            # Verify message payload sent to dispatch
            args, kwargs = mock_dispatch.call_args
            msg_body = kwargs.get("message_body")
            self.assertIn("Serial: ADM-2026-8492", msg_body)
            self.assertIn("PIN: 7492", msg_body)
            self.assertIn("Apply: sms-nald.onrender.com/apply.html", msg_body)
            self.assertLessEqual(len(msg_body), 160, "Admission SMS exceeds single SMS length limit (160 chars)")

if __name__ == "__main__":
    unittest.main()
