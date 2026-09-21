"""
tests/test_multi_tenant_isolation_hardening.py

Regression test suite for Fix 6: Enforce Multi-Tenant Data Isolation (P0).
Verifies:
1. Non-superadmin users are strictly isolated to their own school institution.
2. Cross-school BOLA / IDOR attacks on students, fees, scores, and settings are blocked.
3. Attempting to spoof `X-School-Id` headers as a non-superadmin is rejected/ignored.
4. Users without a valid school association cannot read cross-tenant records.
5. Super Admins retain legitimate administrative oversight across schools.
"""

import unittest
import os
import sys
import uuid
from starlette.datastructures import Headers
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

from backend.app.database import SessionLocal, run_migrations
from backend.app.models import School, User, Role, Student, Fee, Setting
from backend.app.services.auth import hash_password
from backend.app.dependencies import get_school_id
from backend.app.routes.students import get_student, update_student, StudentCreate
from backend.app.routes.fees import get_fee, update_fee, record_payment, FeeUpdate, PaymentCreate
from backend.app.routes.results import create_score
from backend.app.routes.settings import get_settings, update_settings
from backend.app.schemas import ScoreCreate


class MockRequest:
    def __init__(self, client_ip="127.0.0.1", headers=None):
        self.client = type("Client", (), {"host": client_ip})()
        self.headers = Headers(headers or {})


class TestMultiTenantIsolationHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_migrations()

    def setUp(self):
        self.db = SessionLocal()

        # 1. Roles
        super_role = self.db.query(Role).filter(Role.name == "super_admin").first()
        if not super_role:
            super_role = Role(name="super_admin")
            self.db.add(super_role)

        admin_role = self.db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            self.db.add(admin_role)

        teacher_role = self.db.query(Role).filter(Role.name == "teacher").first()
        if not teacher_role:
            teacher_role = Role(name="teacher")
            self.db.add(teacher_role)
        self.db.commit()

        # 2. Schools A and B
        self.school_a = School(name="Institution Alpha", code=f"SCH_A_{uuid.uuid4().hex[:4]}", school_mode="COMBINED")
        self.school_b = School(name="Institution Beta", code=f"SCH_B_{uuid.uuid4().hex[:4]}", school_mode="COMBINED")
        self.db.add_all([self.school_a, self.school_b])
        self.db.commit()

        # 3. Users in School A and School B
        self.admin_a = User(
            username=f"admin_a_{uuid.uuid4().hex[:5]}",
            password_hash=hash_password("Pass123!"),
            school_id=self.school_a.id,
            is_active=True
        )
        self.admin_a.roles = [admin_role]

        self.admin_b = User(
            username=f"admin_b_{uuid.uuid4().hex[:5]}",
            password_hash=hash_password("Pass123!"),
            school_id=self.school_b.id,
            is_active=True
        )
        self.admin_b.roles = [admin_role]

        self.superadmin = User(
            username=f"super_{uuid.uuid4().hex[:5]}",
            password_hash=hash_password("Pass123!"),
            school_id=None,
            is_active=True
        )
        self.superadmin.roles = [super_role]

        self.db.add_all([self.admin_a, self.admin_b, self.superadmin])
        self.db.commit()

        # 4. Student & Fee in School B
        self.student_b = Student(
            student_code=f"STB_{uuid.uuid4().hex[:5]}",
            full_name="Student in School Beta",
            school_id=self.school_b.id,
            is_active=True
        )
        self.db.add(self.student_b)
        self.db.commit()

        self.fee_b = Fee(
            student_id=self.student_b.id,
            fee_type="Tuition",
            amount=500.0,
            amount_paid=0.0,
            status="Pending"
        )
        self.db.add(self.fee_b)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_01_get_school_id_locks_non_superadmin_and_resists_spoofing(self):
        """Non-superadmin is strictly locked to user.school_id regardless of spoofed X-School-Id."""
        # Admin A attempting to pass X-School-Id of School B
        effective_id = get_school_id(
            current_user=self.admin_a,
            x_school_id=str(self.school_b.id)
        )
        self.assertEqual(effective_id, self.school_a.id, "Non-superadmin must not be able to switch school via header")

        # Superadmin with explicit header
        super_target_id = get_school_id(
            current_user=self.superadmin,
            x_school_id=str(self.school_b.id)
        )
        self.assertEqual(super_target_id, self.school_b.id, "Superadmin should be permitted cross-school target header")

    def test_02_unassigned_non_superadmin_gets_sentinel_negative_id(self):
        """A user with no assigned school receives sentinel -1 to prevent leaking all tenants."""
        unassigned_user = User(
            username=f"orphan_{uuid.uuid4().hex[:5]}",
            password_hash=hash_password("Pass123!"),
            school_id=None,
            is_active=True
        )
        unassigned_user.roles = [self.db.query(Role).filter(Role.name == "teacher").first()]
        self.db.add(unassigned_user)
        self.db.commit()

        res_id = get_school_id(current_user=unassigned_user)
        self.assertEqual(res_id, -1, "Orphan non-superadmin user must receive sentinel -1")

    def test_03_cross_tenant_student_access_blocked(self):
        """Admin A cannot read or mutate Student B belonging to School B."""
        # 1. Read attempt
        with self.assertRaises(HTTPException) as ctx:
            get_student(
                student_id=self.student_b.id,
                db=self.db,
                current_user=self.admin_a
            )
        self.assertEqual(ctx.exception.status_code, 404)

        # 2. Update attempt
        with self.assertRaises(HTTPException) as ctx:
            update_student(
                student_id=self.student_b.id,
                student=StudentCreate(
                    student_code=self.student_b.student_code,
                    full_name="Attacker Tampered Name",
                    class_section_id=1
                ),
                db=self.db,
                current_user=self.admin_a
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_04_cross_tenant_fee_access_blocked(self):
        """Admin A cannot view, update, or record payment on Fee B belonging to School B."""
        # 1. View fee
        with self.assertRaises(HTTPException) as ctx:
            get_fee(
                fee_id=self.fee_b.id,
                db=self.db,
                current_user=self.admin_a
            )
        self.assertEqual(ctx.exception.status_code, 404)

        # 2. Update fee
        with self.assertRaises(HTTPException) as ctx:
            update_fee(
                fee_id=self.fee_b.id,
                payload=FeeUpdate(amount=10.0),
                db=self.db,
                current_user=self.admin_a
            )
        self.assertEqual(ctx.exception.status_code, 404)

        # 3. Record payment
        with self.assertRaises(HTTPException) as ctx:
            record_payment(
                fee_id=self.fee_b.id,
                payload=PaymentCreate(amount_paid=100.0, payment_method="Cash"),
                db=self.db,
                current_user=self.admin_a
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_05_cross_tenant_scores_creation_blocked(self):
        """Admin A cannot create exam scores for students in School B."""
        with self.assertRaises(HTTPException) as ctx:
            create_score(
                score=ScoreCreate(
                    student_id=self.student_b.id,
                    subject_id=1,
                    semester_id=1,
                    class_score=30.0,
                    exam_score=70.0
                ),
                db=self.db,
                current_user=self.admin_a
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("not found in your school", ctx.exception.detail.lower())

    def test_06_cross_tenant_settings_mutation_blocked(self):
        """Admin A cannot mutate settings of School B via X-School-Id spoofing."""
        # Admin A attempts to change School B's custom setting
        update_settings(
            payload={"system_theme": "crimson_danger"},
            db=self.db,
            current_user=self.admin_a,
            school_id=self.school_a.id,
            x_school_id=str(self.school_b.id)  # Spoofed
        )

        # Confirm School B did NOT receive the setting change
        setting_b = self.db.query(Setting).filter(
            Setting.school_id == self.school_b.id,
            Setting.key == "system_theme"
        ).first()
        self.assertTrue(setting_b is None or setting_b.value != "crimson_danger")

        # Confirm School A received the setting
        setting_a = self.db.query(Setting).filter(
            Setting.school_id == self.school_a.id,
            Setting.key == "system_theme"
        ).first()
        self.assertIsNotNone(setting_a)
        self.assertEqual(setting_a.value, "crimson_danger")


if __name__ == "__main__":
    unittest.main()
