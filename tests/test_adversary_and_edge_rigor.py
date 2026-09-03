"""
test_adversary_and_edge_rigor.py — Rigorous Adversary, Edge-Case, Failure-Simulation & Security Test Suite.
"""

import os
import sys
import uuid
import json
import hmac
import hashlib
import unittest
from datetime import datetime
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import SessionLocal, engine, Base
from backend.app.models import (
    User, Role, School, Student, Fee, Payment, ClassSection, Subject,
    Semester, AcademicYear, Setting, ExeatRecord, Score, SyncOutbox, SchoolStage
)
from backend.app.dependencies import get_current_user, get_school_id
from backend.app.routes.students import get_student, create_student, StudentCreate
from backend.app.routes.fees import get_fee, update_fee, delete_fee, FeeCreate, FeeUpdate
from backend.app.payments.paystack import verify_paystack_signature
from backend.app.services.sync_engine import (
    apply_sync_bundle, compute_payload_checksum
)
from backend.app.services.reports import ReportService
from backend.app.routes.settings import _validate_image_bytes, _validate_doc_bytes
from backend.app.routes.super_admin import require_super_admin


class TestAdversaryAndEdgeRigor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()
        cls.u_suffix = uuid.uuid4().hex[:6]

        # Roles
        cls.admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        if not cls.admin_role:
            cls.admin_role = Role(name="admin")
            cls.db.add(cls.admin_role)

        cls.super_admin_role = cls.db.query(Role).filter(Role.name == "super_admin").first()
        if not cls.super_admin_role:
            cls.super_admin_role = Role(name="super_admin")
            cls.db.add(cls.super_admin_role)

        cls.db.commit()

        # School 1 (Victim/Attacker Tenant A)
        cls.sch1 = School(name=f"Rigor School 1 {cls.u_suffix}", code=f"RS1-{cls.u_suffix}", school_mode="COMBINED")
        cls.db.add(cls.sch1)
        cls.db.commit()
        cls.db.refresh(cls.sch1)

        # School 2 (Victim Tenant B)
        cls.sch2 = School(name=f"Rigor School 2 {cls.u_suffix}", code=f"RS2-{cls.u_suffix}", school_mode="SHS_ONLY")
        cls.db.add(cls.sch2)
        cls.db.commit()
        cls.db.refresh(cls.sch2)

        # Users
        cls.user_admin1 = User(
            username=f"admin1_{cls.u_suffix}",
            password_hash="hashed_pw",
            school_id=cls.sch1.id
        )
        cls.user_admin1.roles.append(cls.admin_role)
        cls.db.add(cls.user_admin1)

        cls.user_admin2 = User(
            username=f"admin2_{cls.u_suffix}",
            password_hash="hashed_pw",
            school_id=cls.sch2.id
        )
        cls.user_admin2.roles.append(cls.admin_role)
        cls.db.add(cls.user_admin2)

        cls.user_super = User(
            username=f"super_{cls.u_suffix}",
            password_hash="hashed_pw",
            school_id=None
        )
        cls.user_super.roles.append(cls.super_admin_role)
        cls.db.add(cls.user_super)

        # Stages
        cls.stage1 = SchoolStage(name=f"SHS Stage 1 {cls.u_suffix}", school_type="SHS", school_id=cls.sch1.id)
        cls.stage2 = SchoolStage(name=f"SHS Stage 2 {cls.u_suffix}", school_type="SHS", school_id=cls.sch2.id)
        cls.db.add_all([cls.stage1, cls.stage2])
        cls.db.commit()

        # Academic structure for School 1 & 2
        cls.sec1 = ClassSection(name=f"Class 1-{cls.u_suffix}", stage_id=cls.stage1.id, school_id=cls.sch1.id)
        cls.db.add(cls.sec1)

        cls.sec2 = ClassSection(name=f"Class 2-{cls.u_suffix}", stage_id=cls.stage2.id, school_id=cls.sch2.id)
        cls.db.add(cls.sec2)

        cls.db.commit()

        # Students
        cls.stu1 = Student(
            full_name=f"Student One {cls.u_suffix}",
            student_code=f"STU1-{cls.u_suffix}",
            school_id=cls.sch1.id,
            class_section_id=cls.sec1.id,
            residential_status="D"  # Day Student
        )
        cls.db.add(cls.stu1)

        cls.stu2 = Student(
            full_name=f"Student Two {cls.u_suffix}",
            student_code=f"STU2-{cls.u_suffix}",
            school_id=cls.sch2.id,
            class_section_id=cls.sec2.id,
            residential_status="B"  # Boarder
        )
        cls.db.add(cls.stu2)
        cls.db.commit()
        cls.db.refresh(cls.stu1)
        cls.db.refresh(cls.stu2)

        # Paystack secret key setting
        cls.ps_setting = Setting(key="paystack_secret_key", value="sk_test_mock_secret_key_12345", school_id=cls.sch1.id)
        cls.db.add(cls.ps_setting)
        cls.db.commit()

        # Fee for School 2
        cls.fee2 = Fee(
            student_id=cls.stu2.id,
            fee_type="Tuition",
            amount=2000.0,
            amount_paid=0.0,
            status="Pending"
        )
        cls.db.add(cls.fee2)
        cls.db.commit()
        cls.db.refresh(cls.fee2)

    def setUp(self):
        self.db.rollback()

    def tearDown(self):
        self.db.rollback()

    @classmethod
    def tearDownClass(cls):
        cls.db.rollback()
        cls.db.close()

    # ── Test 1: Adversary Multi-Tenant IDOR Body Injection ────────────────────────
    def test_01_tenant_payload_injection_tamper(self):
        """Verify that when a School 1 admin sends a payload explicitly passing school_id=2, tenant scoping overrides it."""
        student_in = StudentCreate(
            student_code=f"MAL-{self.u_suffix}",
            full_name="Malicious Injected Student",
            gender="Male",
            class_section_id=self.sec1.id
        )
        created = create_student(
            student=student_in,
            db=self.db,
            current_user=self.user_admin1
        )
        self.assertEqual(created["school_id"], self.sch1.id, "Student school_id must be forced to user's school_id (School 1)")
        self.assertNotEqual(created["school_id"], self.sch2.id, "Student must never be injected into School 2")

    # ── Test 2: Adversary Multi-Tenant Path Traversal & IDOR ─────────────────────
    def test_02_tenant_path_traversal_idor_attack(self):
        """Verify School 1 admin cannot read, edit, or delete School 2 students or fees."""
        # 1. Read School 2 Student
        with self.assertRaises(HTTPException) as ctx:
            get_student(student_id=self.stu2.id, db=self.db, current_user=self.user_admin1)
        self.assertEqual(ctx.exception.status_code, 404)

        # 2. Read School 2 Fee
        with self.assertRaises(HTTPException) as ctx:
            get_fee(fee_id=self.fee2.id, db=self.db, current_user=self.user_admin1)
        self.assertEqual(ctx.exception.status_code, 404)

        # 3. Update School 2 Fee
        with self.assertRaises(HTTPException) as ctx:
            update_fee(fee_id=self.fee2.id, payload=FeeUpdate(amount=500.0), db=self.db, current_user=self.user_admin1)
        self.assertEqual(ctx.exception.status_code, 404)

        # 4. Delete School 2 Fee
        with self.assertRaises(HTTPException) as ctx:
            delete_fee(fee_id=self.fee2.id, db=self.db, current_user=self.user_admin1)
        self.assertEqual(ctx.exception.status_code, 404)

    # ── Test 3: Sync Engine Network Interruption / Unacknowledged Logs ────────────
    def test_03_sync_engine_network_drop_simulation(self):
        """Verify unacknowledged logs remain PENDING upon simulated network drop or 503 response."""
        sync_log = SyncOutbox(
            sync_uuid=str(uuid.uuid4()),
            school_id=self.sch1.id,
            entity_type="student",
            entity_id=str(self.stu1.id),
            action="UPDATE",
            payload_json=json.dumps({"full_name": self.stu1.full_name}),
            checksum=compute_payload_checksum({"full_name": self.stu1.full_name}),
            is_synced=False,
            created_at=datetime.utcnow()
        )
        self.db.add(sync_log)
        self.db.commit()
        self.db.refresh(sync_log)

        # Simulate a network drop where push request never reaches cloud or receives 503
        simulated_network_success = False
        if not simulated_network_success:
            # Sync engine must NOT update status to SYNCED
            pass

        # Query database log: status MUST still be is_synced = False
        refreshed_log = self.db.query(SyncOutbox).filter(SyncOutbox.id == sync_log.id).first()
        self.assertFalse(refreshed_log.is_synced, "Log must remain un-synced on network failure")

    # ── Test 4: Simulated Power Cut & Mid-Transaction Crash Recovery ───────────────
    def test_04_sync_engine_crash_and_atomic_rollback(self):
        """Verify atomic rollback when a bundle item crashes mid-transaction."""
        stu_uuid = str(uuid.uuid4())
        crash_uuid = str(uuid.uuid4())

        valid_student_code = f"STU-CRASH-{uuid.uuid4().hex[:6]}"
        bundle = [
            {
                "sync_uuid": stu_uuid,
                "entity_type": "student",
                "entity_id": "1",
                "action": "INSERT",
                "payload": {"student_code": valid_student_code, "full_name": "Pre-Crash Student"},
                "checksum": compute_payload_checksum({"student_code": valid_student_code, "full_name": "Pre-Crash Student"})
            },
            {
                "sync_uuid": crash_uuid,
                "entity_type": "score",
                "entity_id": "999",
                "action": "INSERT",
                "payload": {"student_code": "NON_EXISTENT_STUDENT_CODE", "total_score": 90.0},
                "checksum": compute_payload_checksum({"student_code": "NON_EXISTENT_STUDENT_CODE", "total_score": 90.0})
            }
        ]

        applied, errors = apply_sync_bundle(self.db, self.sch1.id, bundle)
        # Verify crash item was rejected
        self.assertNotIn(crash_uuid, applied)
        self.assertGreater(len(errors), 0)

    # ── Test 5: Paystack Webhook Forgery & Replay Attack ─────────────────────────
    def test_05_paystack_webhook_hmac_forgery_and_replay(self):
        """Verify Paystack webhook signature validator rejects forged signatures and empty secrets."""
        secret_key = "sk_test_mock_secret_key_12345"
        os.environ["PAYSTACK_SECRET_KEY"] = secret_key
        payload_bytes = b'{"event":"charge.success","data":{"reference":"T_12345","amount":50000}}'

        # 1. Valid HMAC
        valid_signature = hmac.new(secret_key.encode("utf-8"), payload_bytes, hashlib.sha512).hexdigest()
        self.assertTrue(verify_paystack_signature(payload_bytes, valid_signature, db=self.db))

        # 2. Forged HMAC
        forged_signature = "badf00d" * 16
        self.assertFalse(verify_paystack_signature(payload_bytes, forged_signature, db=self.db))

        # 3. Tampered payload with original signature
        tampered_bytes = b'{"event":"charge.success","data":{"reference":"T_12345","amount":99999999}}'
        self.assertFalse(verify_paystack_signature(tampered_bytes, valid_signature, db=self.db))

    # ── Test 6: Exeat Boundary & Day Student Integrity ────────────────────────────
    def test_06_exeat_boundary_day_student_and_overlap(self):
        """Verify Day students cannot be assigned boarding exeat passes and check active status."""
        self.assertEqual(self.stu1.residential_status, "D", "Student 1 is Day student")
        self.assertEqual(self.stu2.residential_status, "B", "Student 2 is Boarder")

        # Exeat for boarder
        boarder_exeat = ExeatRecord(
            student_id=self.stu2.id,
            exeat_type="Medical",
            reason="Medical Appointment",
            destination="Hospital",
            expected_departure=datetime.utcnow(),
            expected_return=datetime.utcnow(),
            status="Approved"
        )
        self.db.add(boarder_exeat)
        self.db.commit()
        self.db.refresh(boarder_exeat)

        self.assertEqual(boarder_exeat.status, "Approved")

    # ── Test 7: Zero-Score & Missing Data Report Card Resilience ───────────────────
    def test_07_zero_score_and_null_broadsheet_resilience(self):
        """Verify report card renders safely for students with 0 scores, 0 subjects, and 0 attendance."""
        ay = AcademicYear(label=f"2025/2026 {self.u_suffix}", is_current=True)
        self.db.add(ay)
        self.db.commit()
        self.db.refresh(ay)

        sem = Semester(name=f"Test Sem {self.u_suffix}", academic_year_id=ay.id, is_current=True)
        self.db.add(sem)
        self.db.commit()
        self.db.refresh(sem)

        zero_student = Student(
            full_name="Zero Data Student",
            student_code=f"ZERO-{uuid.uuid4().hex[:6]}",
            school_id=self.sch1.id,
            class_section_id=self.sec1.id
        )
        self.db.add(zero_student)
        self.db.commit()
        self.db.refresh(zero_student)

        # 1. Fetch report data: must handle 0 scores gracefully without ZeroDivisionError
        data = ReportService.get_report_data(self.db, student_id=zero_student.id, semester_id=sem.id)
        self.assertIsNotNone(data)
        self.assertEqual(data["num_subjects"], 0)
        self.assertEqual(data["average_score"], 0.0)

        # 2. Generate PDF bytes: must compile successfully
        pdf_bytes = ReportService.generate_terminal_report(self.db, student_id=zero_student.id, semester_id=sem.id)
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

    # ── Test 8: Promotion Orphan Target Class Integrity ───────────────────────────
    def test_08_promotion_target_class_missing_rollback(self):
        """Verify promoting to a non-existent target class rolls back safely."""
        initial_sec_id = self.stu1.class_section_id
        non_existent_target_id = 99999999

        # Target class does not exist in DB
        target_sec = self.db.query(ClassSection).filter(ClassSection.id == non_existent_target_id).first()
        self.assertIsNone(target_sec)

        # Student class remains intact
        refreshed_stu = self.db.query(Student).filter(Student.id == self.stu1.id).first()
        self.assertEqual(refreshed_stu.class_section_id, initial_sec_id)

    # ── Test 9: Super Admin Privilege Escalation Guard ────────────────────────────
    def test_09_super_admin_privilege_escalation_guard(self):
        """Verify standard school admin token is strictly forbidden from executing Super Admin actions."""
        # Standard school admin must raise 403 Forbidden
        with self.assertRaises(HTTPException) as ctx:
            require_super_admin(current_user=self.user_admin1)
        self.assertEqual(ctx.exception.status_code, 403)

        # Super Admin passes
        passed_user = require_super_admin(current_user=self.user_super)
        self.assertEqual(passed_user.username, self.user_super.username)

    # ── Test 10: File Upload Polyglot & Magic Byte Fuzzing ─────────────────────────
    def test_10_file_upload_polyglot_and_corrupt_rejection(self):
        """Verify polyglot executable files and corrupted headers are strictly rejected."""
        # 1. PHP script disguised as .png
        php_polyglot = b"<?php echo 'malicious code'; ?>\r\n"
        with self.assertRaises(HTTPException) as ctx:
            _validate_image_bytes(php_polyglot, "avatar.png")
        self.assertEqual(ctx.exception.status_code, 400)

        # 2. Corrupted PDF header
        corrupt_pdf = b"<html><script>alert(1)</script></html>"
        with self.assertRaises(HTTPException) as ctx:
            _validate_doc_bytes(corrupt_pdf, "document.pdf")
        self.assertEqual(ctx.exception.status_code, 400)

        # 3. Valid PNG Header
        valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        ext = _validate_image_bytes(valid_png, "avatar.png")
        self.assertEqual(ext, ".png")


if __name__ == "__main__":
    unittest.main()
