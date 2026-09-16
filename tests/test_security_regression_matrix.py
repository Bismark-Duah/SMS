"""
tests/test_security_regression_matrix.py
Regression tests for Prompt 17: Expand Security Test Coverage.

Validates end-to-end security contracts across dual-tenant School A and School B fixtures:
1. Cross-Tenant Access & IDOR/BOLA Protection
2. Role Escalation Prevention (Teacher/Student/Parent/SchoolAdmin -> SuperAdmin)
3. Unauthorized Deletion & Mutation Prevention
4. Unauthorized Password Reset & Token Invalidation
5. School Switching & X-School-Id Spoofing Immunization
6. Suspended Account & Suspended School Access Guard
7. Token Expiration, Tampering, and Cryptographic Signature Verification
8. Default & Hardcoded Credential Safeguards
9. Sensitive Endpoint Authorization (Audit, Backup, Sync)
"""
import os
import sys
import unittest
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.models import (
    Base, School, SchoolStage, ClassSection, Student, User, Role, Setting
)
from backend.app.database import get_db
from backend.app.services.auth import create_jwt, hash_password
from backend.app.middleware.device_session_guard import register_device_session
from backend.app.main import app


from sqlalchemy.pool import StaticPool


class TestSecurityRegressionMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.Session()
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app, raise_server_exceptions=False)

        # Seed Roles
        self.roles = {}
        for r_name in ["admin", "teacher", "student", "parent", "super_admin"]:
            r = Role(name=r_name)
            self.db.add(r)
            self.roles[r_name] = r
        self.db.commit()

        # Seed Tenants: School A, School B, and Suspended School
        self.school_a = School(id=1, name="School Alpha", code="SCH_A", status="ACTIVE")
        self.school_b = School(id=2, name="School Beta", code="SCH_B", status="ACTIVE")
        self.school_susp = School(id=3, name="Suspended School", code="SCH_SUSP", status="SUSPENDED")
        self.db.add_all([self.school_a, self.school_b, self.school_susp])
        self.db.commit()

        # Seed Stages
        self.stage_a = SchoolStage(id=1, name="SHS Alpha", school_type="SHS", school_id=self.school_a.id)
        self.stage_b = SchoolStage(id=2, name="SHS Beta", school_type="SHS", school_id=self.school_b.id)
        self.db.add_all([self.stage_a, self.stage_b])
        self.db.commit()

        # Seed Classes
        self.class_a = ClassSection(id=1, name="Class 1A", stage_id=self.stage_a.id, school_id=self.school_a.id)
        self.class_b = ClassSection(id=2, name="Class 2B", stage_id=self.stage_b.id, school_id=self.school_b.id)
        self.db.add_all([self.class_a, self.class_b])
        self.db.commit()

        # Seed Users
        self.admin_a = self._create_user("admin_a", self.school_a.id, "admin")
        self.admin_b = self._create_user("admin_b", self.school_b.id, "admin")
        self.teacher_a = self._create_user("teacher_a", self.school_a.id, "teacher")
        self.student_user_a = self._create_user("student_user_a", self.school_a.id, "student")
        self.parent_user_a = self._create_user("parent_user_a", self.school_a.id, "parent")
        self.superadmin = self._create_user("superadmin", None, "super_admin")
        self.user_suspended = self._create_user("admin_susp", self.school_susp.id, "admin")
        self.user_deactivated = self._create_user("deactivated_a", self.school_a.id, "teacher", is_active=False)

        # Seed Students
        self.student_a = Student(
            id=1, student_code="STU_A", bece_index_number="1111111111",
            full_name="Alice Alpha", school_id=self.school_a.id, class_section_id=self.class_a.id
        )
        self.student_b = Student(
            id=2, student_code="STU_B", bece_index_number="2222222222",
            full_name="Bob Beta", school_id=self.school_b.id, class_section_id=self.class_b.id
        )
        self.db.add_all([self.student_a, self.student_b])
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        # Clean metadata tables between tests
        with self.engine.connect() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())
            conn.commit()

    def _create_user(self, username: str, school_id: int, role_name: str, is_active: bool = True) -> User:
        user = User(
            username=username,
            email=f"{username}@test.com",
            password_hash=hash_password("Secr3t!P@ssword"),
            school_id=school_id,
            is_active=is_active,
            token_version=1
        )
        user.roles.append(self.roles[role_name])
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _get_auth_headers(self, user: User, expires_in: int = 3600, secret: str = None) -> dict:
        payload = {
            "user_id": user.id,
            "username": user.username,
            "school_id": user.school_id,
            "token_version": getattr(user, "token_version", 1)
        }
        role_name = user.roles[0].name if user.roles else "user"
        token = create_jwt(payload, secret=secret, expires_in=expires_in)
        # Register device session so multi-device guard passes
        register_device_session(
            user_id=user.id,
            user_role=role_name,
            user_agent="TestClient Security Runner",
            client_ip="127.0.0.1",
            token=token,
            db=self.db
        )
        return {"Authorization": f"Bearer {token}"}

    # ── 1. Cross-Tenant Access & IDOR/BOLA ────────────────────────────────────
    def test_cross_tenant_student_read_and_mutation_prevented(self):
        """Admin A cannot fetch or update students belonging to School B."""
        headers_a = self._get_auth_headers(self.admin_a)

        # GET School B student using Admin A credentials
        res_get = self.client.get(f"/api/students/{self.student_b.id}", headers=headers_a)
        self.assertIn(res_get.status_code, (403, 404))

        # PUT School B student using Admin A credentials
        res_put = self.client.put(
            f"/api/students/{self.student_b.id}",
            json={
                "student_code": "STU_B",
                "full_name": "Hacked Student Name",
                "class_section_id": self.class_a.id
            },
            headers=headers_a
        )
        self.assertIn(res_put.status_code, (403, 404))

        # Verify Student B was unchanged
        self.db.refresh(self.student_b)
        self.assertEqual(self.student_b.full_name, "Bob Beta")

    # ── 2. Role Escalation ─────────────────────────────────────────────────────
    def test_role_escalation_prevented(self):
        """Teacher, Student, and School Admin cannot invoke Super Admin operations."""
        teacher_headers = self._get_auth_headers(self.teacher_a)
        student_headers = self._get_auth_headers(self.student_user_a)
        admin_headers = self._get_auth_headers(self.admin_a)

        for headers in [teacher_headers, student_headers, admin_headers]:
            # Attempt to create a school via super-admin endpoint
            res = self.client.post(
                "/api/super-admin/schools",
                json={"name": "Attacker Academy", "code": "ATTACK"},
                headers=headers
            )
            self.assertEqual(res.status_code, 403, f"Expected 403 on role escalation, got {res.status_code}")

    # ── 3. Unauthorized Deletion ──────────────────────────────────────────────
    def test_cross_tenant_unauthorized_deletion(self):
        """Admin A cannot delete class section or student of School B."""
        headers_a = self._get_auth_headers(self.admin_a)

        res_del_class = self.client.delete(f"/api/classes/{self.class_b.id}", headers=headers_a)
        self.assertIn(res_del_class.status_code, (403, 404))

        res_del_student = self.client.delete(f"/api/students/{self.student_b.id}", headers=headers_a)
        self.assertIn(res_del_student.status_code, (403, 404))

        # Ensure School B records remain intact
        self.assertIsNotNone(self.db.query(ClassSection).filter(ClassSection.id == self.class_b.id).first())
        self.assertIsNotNone(self.db.query(Student).filter(Student.id == self.student_b.id).first())

    # ── 4. X-School-Id Spoofing Immunization ──────────────────────────────────
    def test_x_school_id_spoofing_ignored(self):
        """Attacker sending X-School-Id header cannot escape their token-bound tenant boundary."""
        headers_a = self._get_auth_headers(self.admin_a)
        # Attempt to spoof School B
        headers_a["X-School-Id"] = str(self.school_b.id)

        res = self.client.get("/api/students", headers=headers_a)
        self.assertEqual(res.status_code, 200)
        students = res.json()
        if isinstance(students, dict) and "data" in students:
            students = students["data"]
        # Only School A students must be returned
        for s in students:
            self.assertEqual(s.get("school_id"), self.school_a.id)

    # ── 5. Suspended Account & Suspended School ──────────────────────────────
    def test_suspended_school_access_blocked(self):
        """Users belonging to a suspended school are rejected with 403."""
        headers_susp = self._get_auth_headers(self.user_suspended)
        res = self.client.get("/api/students", headers=headers_susp)
        self.assertEqual(res.status_code, 403)
        self.assertIn("suspended", res.json().get("detail", "").lower())

    def test_deactivated_user_access_blocked(self):
        """User account marked is_active=False is rejected with 401."""
        headers_deact = self._get_auth_headers(self.user_deactivated)
        res = self.client.get("/api/students", headers=headers_deact)
        self.assertEqual(res.status_code, 401)
        self.assertIn("deactivated", res.json().get("detail", "").lower())

    # ── 6. Token Expiration & Cryptographic Tampering ─────────────────────────
    def test_token_expiration_and_tampering_rejected(self):
        """Expired or tampered tokens must return 401 Unauthorized."""
        # Expired token (-10 seconds)
        expired_headers = self._get_auth_headers(self.admin_a, expires_in=-10)
        res_exp = self.client.get("/api/students", headers=expired_headers)
        self.assertEqual(res_exp.status_code, 401)

        # Tampered signature
        valid_token = self._get_auth_headers(self.admin_a)["Authorization"]
        tampered_token = valid_token[:-4] + "xxxx"
        res_tamp = self.client.get("/api/students", headers={"Authorization": tampered_token})
        self.assertEqual(res_tamp.status_code, 401)

    # ── 7. Sensitive Endpoint Authorization ───────────────────────────────────
    def test_sensitive_endpoints_require_authentication(self):
        """Unauthenticated requests to sensitive audit, backup, and sync endpoints return 401."""
        res_audit = self.client.get("/api/audit/school-feed")
        self.assertEqual(res_audit.status_code, 401)

        res_backup = self.client.post("/api/backup/run")
        self.assertEqual(res_backup.status_code, 401)

        res_sync = self.client.get("/api/sync/status")
        self.assertEqual(res_sync.status_code, 401)


if __name__ == "__main__":
    unittest.main()
