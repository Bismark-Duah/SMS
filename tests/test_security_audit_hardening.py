"""
test_security_audit_hardening.py — Automated Test Suite for Pydantic Validation, File Upload Security, and CORS Hardening.
"""

import os
import sys
import unittest
import uuid
import io
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.routes.fees import FeeCreate, PaymentCreate, FeeUpdate
from backend.app.schemas import ScoreCreate
from backend.app.routes.settings import _validate_image_bytes, _validate_doc_bytes
from backend.app.main import DEFAULT_LOCAL_ORIGINS, allow_creds, allowed_origins
from fastapi import HTTPException


class TestSecurityAuditHardening(unittest.TestCase):

    def test_01_fee_and_payment_pydantic_positive_amount_enforcement(self):
        """Verify Pydantic models reject negative or zero amounts for fees and payments."""
        # Valid amount
        fee = FeeCreate(student_id=1, fee_type="Tuition", amount=150.0)
        self.assertEqual(fee.amount, 150.0)

        # Invalid negative amount
        with self.assertRaises(ValidationError):
            FeeCreate(student_id=1, fee_type="Tuition", amount=-50.0)

        # Invalid zero amount
        with self.assertRaises(ValidationError):
            FeeCreate(student_id=1, fee_type="Tuition", amount=0.0)

        # Invalid negative payment
        with self.assertRaises(ValidationError):
            PaymentCreate(amount_paid=-100.0)

        # Invalid zero payment
        with self.assertRaises(ValidationError):
            PaymentCreate(amount_paid=0.0)

    def test_02_score_create_range_validation(self):
        """Verify ScoreCreate rejects out-of-bounds score inputs."""
        # Valid score
        score = ScoreCreate(student_id=1, subject_id=1, semester_id=1, ex1=10.0, class_score=30.0, exam_score=70.0)
        self.assertEqual(score.class_score, 30.0)

        # Invalid negative score
        with self.assertRaises(ValidationError):
            ScoreCreate(student_id=1, subject_id=1, semester_id=1, class_score=-10.0)

        # Invalid score > max allowed range (ex1 max is 20)
        with self.assertRaises(ValidationError):
            ScoreCreate(student_id=1, subject_id=1, semester_id=1, ex1=25.0)

    def test_03_file_upload_magic_byte_verification(self):
        """Verify file upload validator inspects magic bytes and rejects counterfeit file headers."""
        # 1. Fake PNG (text renamed to .png)
        fake_png = b"This is not a real PNG image, just plain text."
        with self.assertRaises(HTTPException) as ctx:
            _validate_image_bytes(fake_png, "photo.png")
        self.assertEqual(ctx.exception.status_code, 400)

        # 2. Valid PNG Magic Bytes
        valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50
        ext = _validate_image_bytes(valid_png, "photo.png")
        self.assertEqual(ext, ".png")

        # 3. Fake PDF
        fake_pdf = b"NOT_A_PDF_HEADER"
        with self.assertRaises(HTTPException) as ctx:
            _validate_doc_bytes(fake_pdf, "conduct.pdf")
        self.assertEqual(ctx.exception.status_code, 400)

        # 4. Valid PDF Magic Bytes
        valid_pdf = b"%PDF-1.4\n%test content\n%%EOF"
        ext_doc = _validate_doc_bytes(valid_pdf, "conduct.pdf")
        self.assertEqual(ext_doc, ".pdf")

    def test_04_file_upload_size_limit_enforcement(self):
        """Verify validator enforces 5MB image limit and 10MB document limit."""
        # 6MB PNG -> reject
        large_png = b"\x89PNG\r\n\x1a\n" + (b"\x00" * (6 * 1024 * 1024))
        with self.assertRaises(HTTPException) as ctx:
            _validate_image_bytes(large_png, "huge.png")
        self.assertEqual(ctx.exception.status_code, 400)

        # 12MB PDF -> reject
        large_pdf = b"%PDF-1.4\n" + (b"\x00" * (12 * 1024 * 1024))
        with self.assertRaises(HTTPException) as ctx:
            _validate_doc_bytes(large_pdf, "huge.pdf")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_05_cors_configuration_defaults(self):
        """Verify default offline development CORS origins are properly defined and safe."""
        self.assertIn("http://localhost:8000", DEFAULT_LOCAL_ORIGINS)
        self.assertIn("http://127.0.0.1:8000", DEFAULT_LOCAL_ORIGINS)
        self.assertIn("http://localhost:3000", DEFAULT_LOCAL_ORIGINS)
        self.assertIn("http://localhost:5500", DEFAULT_LOCAL_ORIGINS)
        # Verify credentials are only allowed with explicit non-wildcard origins
        if allowed_origins == ["*"]:
            self.assertFalse(allow_creds)
        else:
            self.assertTrue(allow_creds)


if __name__ == "__main__":
    unittest.main()
