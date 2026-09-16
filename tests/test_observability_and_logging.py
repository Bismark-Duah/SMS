"""
tests/test_observability_and_logging.py
Automated test suite for Prompt 21: Observability and Logging.
Verifies structured logging, secret redaction, security event tracking,
administrative audits, startup diagnostics, and system health endpoints.
"""

import json
import logging
import unittest
from fastapi.testclient import TestClient

from backend.app.logger import (
    sanitize_log_text,
    sanitize_dict_payload,
    StructuredJsonFormatter,
    log_security_event,
    log_admin_audit_event,
    log_startup_diagnostics,
    get_logger
)
from backend.app.main import app


class TestObservabilityAndLogging(unittest.TestCase):

    def test_01_sanitize_log_text_redacts_secrets(self):
        """Verify regex sanitization redacts passwords, JWTs, API keys, and connection strings."""
        mock_api_key = "sk_" + "live_" + "98765432101234567890abcdef"
        raw_msg = (
            'User login failed with payload: {"username": "admin", "password": "SuperSecretPassword123!"} '
            'and auth header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.xyz '
            f'Paystack key: {mock_api_key} '
            'DB string: postgresql://admin:MyDbPassword999@db.internal:5432/sms_db'
        )
        sanitized = sanitize_log_text(raw_msg)

        self.assertNotIn("SuperSecretPassword123!", sanitized)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", sanitized)
        self.assertNotIn(mock_api_key, sanitized)
        self.assertNotIn("MyDbPassword999", sanitized)

        self.assertIn("***REDACTED***", sanitized)
        self.assertIn("***REDACTED_JWT***", sanitized)
        self.assertIn("***REDACTED_KEY***", sanitized)

    def test_02_sanitize_dict_payload_recursive_scrubbing(self):
        """Verify recursive scrubbing of sensitive keys in nested dictionaries."""
        payload = {
            "school_id": 10,
            "admin": {
                "username": "sysadmin",
                "password": "ClearPassword!",
                "metadata": {
                    "secret_key": "private_secret_string",
                    "safe_field": "visible_value"
                }
            },
            "tokens": ["safe_item", {"access_token": "token_val"}]
        }
        scrubbed = sanitize_dict_payload(payload)

        self.assertEqual(scrubbed["school_id"], 10)
        self.assertEqual(scrubbed["admin"]["password"], "***REDACTED***")
        self.assertEqual(scrubbed["admin"]["metadata"]["secret_key"], "***REDACTED***")
        self.assertEqual(scrubbed["admin"]["metadata"]["safe_field"], "visible_value")
        self.assertEqual(scrubbed["tokens"][1]["access_token"], "***REDACTED***")

    def test_03_structured_json_formatter_validity(self):
        """StructuredJsonFormatter must output valid parseable JSON with all required keys."""
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="edumanage.test",
            level=logging.INFO,
            pathname="test_file.py",
            lineno=42,
            msg='Request processed with password: "secret_value"',
            args=(),
            exc_info=None
        )
        record.request_id = "req-test-1234"
        record.client_ip = "192.168.1.100"
        record.school_id = 5

        formatted_str = formatter.format(record)
        log_obj = json.loads(formatted_str)

        self.assertEqual(log_obj["logger"], "edumanage.test")
        self.assertEqual(log_obj["level"], "INFO")
        self.assertEqual(log_obj["request_id"], "req-test-1234")
        self.assertEqual(log_obj["client_ip"], "192.168.1.100")
        self.assertEqual(log_obj["school_id"], 5)
        self.assertNotIn("secret_value", log_obj["message"])
        self.assertIn("***REDACTED***", log_obj["message"])

    def test_04_log_security_event_scrubs_and_dispatches(self):
        """log_security_event must record security events without leaking sensitive data."""
        # Use custom memory handler to capture emitted log record
        sec_logger = get_logger("security")
        records = []
        class TestHandler(logging.Handler):
            def emit(self, rec):
                records.append(rec)

        handler = TestHandler()
        sec_logger.addHandler(handler)
        try:
            log_security_event(
                event_type="UNAUTHORIZED_LOGIN_ATTEMPT",
                severity="WARNING",
                details={"username": "attacker", "password": "hacked_password_99"},
                request_id="req-sec-999",
                client_ip="10.0.0.1",
                school_id=2
            )
            self.assertEqual(len(records), 1)
            rec = records[0]
            self.assertEqual(rec.security_event, "UNAUTHORIZED_LOGIN_ATTEMPT")
            self.assertEqual(rec.request_id, "req-sec-999")
            self.assertNotIn("hacked_password_99", rec.getMessage())
            self.assertIn("***REDACTED***", rec.getMessage())
        finally:
            sec_logger.removeHandler(handler)

    def test_05_log_admin_audit_event_dispatches(self):
        """log_admin_audit_event must capture administrative modifications."""
        audit_logger = get_logger("audit")
        records = []
        class TestHandler(logging.Handler):
            def emit(self, rec):
                records.append(rec)

        handler = TestHandler()
        audit_logger.addHandler(handler)
        try:
            log_admin_audit_event(
                action="UPDATE_GRADING_SCHEME",
                target_type="SchoolSetting",
                target_id=101,
                actor_user_id=1,
                school_id=3,
                details={"old_sba": 30, "new_sba": 50}
            )
            self.assertEqual(len(records), 1)
            rec = records[0]
            self.assertEqual(rec.audit_action, "UPDATE_GRADING_SCHEME")
            self.assertIn("UPDATE_GRADING_SCHEME", rec.getMessage())
            self.assertIn("SchoolSetting ID 101", rec.getMessage())
        finally:
            audit_logger.removeHandler(handler)

    def test_06_log_startup_diagnostics_emits_telemetry(self):
        """log_startup_diagnostics must record operational parameters safely."""
        diag_logger = get_logger("startup")
        records = []
        class TestHandler(logging.Handler):
            def emit(self, rec):
                records.append(rec)

        handler = TestHandler()
        diag_logger.addHandler(handler)
        try:
            log_startup_diagnostics(
                environment="production",
                db_engine="PostgreSQL",
                version="4.2.0",
                extra_info={"db_password": "sensitive_pwd", "worker_count": 4}
            )
            self.assertEqual(len(records), 1)
            msg = records[0].getMessage()
            self.assertIn("Environment=production", msg)
            self.assertIn("DB=PostgreSQL", msg)
            self.assertNotIn("sensitive_pwd", msg)
        finally:
            diag_logger.removeHandler(handler)

    def test_07_system_health_endpoints(self):
        """System health endpoints must return 200 with database telemetry."""
        client = TestClient(app)
        for endpoint in ("/health", "/api/health", "/api/system/health"):
            res = client.get(endpoint)
            self.assertEqual(res.status_code, 200, f"Failed on {endpoint}")
            data = res.json()
            self.assertIn("status", data)
            self.assertIn("database", data)
            self.assertEqual(data["status"], "healthy")
            self.assertIn("engine", data["database"])

    def test_08_system_telemetry_endpoint(self):
        """System telemetry endpoint must return 200 with entity counts."""
        client = TestClient(app)
        res = client.get("/api/system/telemetry")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("counts", data)
        self.assertIn("schools", data["counts"])
        self.assertIn("users", data["counts"])
        self.assertIn("students", data["counts"])


if __name__ == "__main__":
    unittest.main()
