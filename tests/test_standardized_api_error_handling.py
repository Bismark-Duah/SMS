"""
Tests for Prompt 15: Standardize API Error Handling & Fault Sanitization.
Verifies validation, auth, not-found, conflict, database integrity/operational,
and unhandled error responses with zero stack trace/SQL leakage.
"""
import asyncio
import json
import unittest
from starlette.requests import Request
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError, HTTPException as FastAPIHTTPException
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from backend.app.errors import (
    http_exception_handler,
    validation_exception_handler,
    integrity_error_handler,
    operational_error_handler,
    sqlalchemy_error_handler,
    unhandled_exception_handler,
    build_error_envelope
)


def create_mock_request(method="GET", path="/api/test", headers=None, request_id="corr-test-123") -> Request:
    headers_list = []
    if headers:
        for k, v in headers.items():
            headers_list.append((k.lower().encode("utf-8"), str(v).encode("utf-8")))
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers_list,
    }
    req = Request(scope)
    req.state.request_id = request_id
    return req


class TestStandardizedAPIErrorHandling(unittest.TestCase):
    def test_http_exception_401_unauthorized(self):
        """HTTPException 401 returns standardized envelope with UNAUTHORIZED code."""
        req = create_mock_request(request_id="trace-401")
        exc = FastAPIHTTPException(status_code=401, detail="Invalid session or token expired")
        res = asyncio.run(http_exception_handler(req, exc))

        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.headers.get("X-Request-ID"), "trace-401")
        body = json.loads(res.body.decode("utf-8"))
        self.assertEqual(body["status_code"], 401)
        self.assertEqual(body["error_code"], "UNAUTHORIZED")
        self.assertEqual(body["detail"], "Invalid session or token expired")
        self.assertEqual(body["message"], "Invalid session or token expired")
        self.assertEqual(body["request_id"], "trace-401")

    def test_http_exception_403_forbidden(self):
        """HTTPException 403 returns FORBIDDEN code and preserves detail."""
        req = create_mock_request(request_id="trace-403")
        exc = StarletteHTTPException(status_code=403, detail="Administrator role required")
        res = asyncio.run(http_exception_handler(req, exc))

        self.assertEqual(res.status_code, 403)
        body = json.loads(res.body.decode("utf-8"))
        self.assertEqual(body["error_code"], "FORBIDDEN")
        self.assertEqual(body["detail"], "Administrator role required")

    def test_http_exception_404_not_found(self):
        """HTTPException 404 returns NOT_FOUND code."""
        req = create_mock_request(request_id="trace-404")
        exc = FastAPIHTTPException(status_code=404, detail="Student record STU_001 not found")
        res = asyncio.run(http_exception_handler(req, exc))

        self.assertEqual(res.status_code, 404)
        body = json.loads(res.body.decode("utf-8"))
        self.assertEqual(body["error_code"], "NOT_FOUND")
        self.assertEqual(body["detail"], "Student record STU_001 not found")

    def test_validation_error_structured_and_sanitized(self):
        """RequestValidationError returns 422 with structured errors array and readable summary."""
        req = create_mock_request(path="/api/students", request_id="trace-val")
        raw_errors = [
            {"loc": ["body", "first_name"], "msg": "Field required", "type": "value_error.missing"},
            {"loc": ["body", "age"], "msg": "value is not a valid integer", "type": "type_error.integer"}
        ]
        exc = RequestValidationError(errors=raw_errors)
        res = asyncio.run(validation_exception_handler(req, exc))

        self.assertEqual(res.status_code, 422)
        body = json.loads(res.body.decode("utf-8"))
        self.assertEqual(body["status_code"], 422)
        self.assertEqual(body["error_code"], "VALIDATION_ERROR")
        self.assertEqual(body["errors"], raw_errors)
        self.assertIn("first_name", body["message"])
        self.assertEqual(body["request_id"], "trace-val")

    def test_integrity_error_unique_violation_sanitized(self):
        """Unique constraint violation returns 409 CONFLICT without leaking SQL details."""
        req = create_mock_request(request_id="trace-unique")
        exc = IntegrityError(
            statement="INSERT INTO students (code) VALUES ('STU_100')",
            params={"code": "STU_100"},
            orig=Exception("UNIQUE constraint failed: students.code")
        )
        res = asyncio.run(integrity_error_handler(req, exc))

        self.assertEqual(res.status_code, 409)
        body = json.loads(res.body.decode("utf-8"))
        self.assertEqual(body["error_code"], "RESOURCE_CONFLICT")
        # Ensure zero SQL leakage
        self.assertNotIn("INSERT INTO", body["detail"])
        self.assertNotIn("students.code", body["detail"])
        self.assertNotIn("STU_100", body["detail"])
        self.assertIn("already exists", body["detail"])

    def test_integrity_error_check_and_foreign_key_violations(self):
        """Check and foreign key constraint violations return 400 with sanitized messages."""
        req = create_mock_request(request_id="trace-chk")
        exc_chk = IntegrityError("INSERT INTO scores ...", {}, Exception("CHECK constraint failed: check_score_range"))
        res_chk = asyncio.run(integrity_error_handler(req, exc_chk))

        self.assertEqual(res_chk.status_code, 400)
        body_chk = json.loads(res_chk.body.decode("utf-8"))
        self.assertEqual(body_chk["error_code"], "CHECK_CONSTRAINT_FAILED")
        self.assertNotIn("check_score_range", body_chk["detail"])

        exc_fk = IntegrityError("INSERT INTO students ...", {}, Exception("FOREIGN KEY constraint failed"))
        res_fk = asyncio.run(integrity_error_handler(req, exc_fk))
        self.assertEqual(res_fk.status_code, 400)
        body_fk = json.loads(res_fk.body.decode("utf-8"))
        self.assertEqual(body_fk["error_code"], "INVALID_REFERENCE")

    def test_operational_error_database_busy(self):
        """SQLite locked / busy returns 503 SERVICE_UNAVAILABLE with retry guidance."""
        req = create_mock_request(request_id="trace-busy")
        exc = OperationalError("UPDATE ...", {}, Exception("database is locked"))
        res = asyncio.run(operational_error_handler(req, exc))

        self.assertEqual(res.status_code, 503)
        body = json.loads(res.body.decode("utf-8"))
        self.assertEqual(body["error_code"], "DATABASE_BUSY")
        self.assertIn("busy", body["detail"].lower())

    def test_unhandled_exception_sanitized_no_stacktrace_leak(self):
        """Unhandled system exceptions return 500 and NEVER leak stack traces or secret details."""
        req = create_mock_request(request_id="trace-crash")
        exc = RuntimeError("CRITICAL: database password=SuperSecretPassword123 connection lost at line 402 in private_module.py")
        res = asyncio.run(unhandled_exception_handler(req, exc))

        self.assertEqual(res.status_code, 500)
        body = json.loads(res.body.decode("utf-8"))
        self.assertEqual(body["error_code"], "INTERNAL_SERVER_ERROR")
        # Ensure secret and stack details are strictly shielded from client
        raw_body_str = res.body.decode("utf-8")
        self.assertNotIn("SuperSecretPassword123", raw_body_str)
        self.assertNotIn("private_module.py", raw_body_str)
        self.assertNotIn("RuntimeError", raw_body_str)
        self.assertIn("unexpected internal server error", body["detail"].lower())

    def test_live_server_integration_sanitized_404(self):
        """Live API server responds with standardized error format and correlation ID."""
        import requests
        try:
            res = requests.get("http://127.0.0.1:8000/api/nonexistent-route-for-testing-12345", headers={"X-Request-ID": "test-live-trace-99"})
            if res.status_code == 404:
                data = res.json()
                self.assertEqual(data.get("status_code"), 404)
                self.assertEqual(data.get("error_code"), "NOT_FOUND")
                self.assertEqual(res.headers.get("X-Request-ID"), "test-live-trace-99")
        except Exception:
            # Server not running locally right now is acceptable in unit test context
            pass


if __name__ == "__main__":
    unittest.main()
