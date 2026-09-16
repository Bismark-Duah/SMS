"""
tests/test_frontend_authorization_assumptions.py
Automated test suite for Prompt 23: Frontend Authorization Assumptions.
Verifies frontend guard fetch interception, client-side role validation,
and backend security boundary enforcement against client-side tampering.
"""

import os
import unittest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models import User, Role, School
from backend.app.services.auth import create_jwt, hash_password


class TestFrontendAuthorizationAssumptions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Seed test school and roles
        cls.school = cls.db.query(School).filter(School.id == 23).first()
        if not cls.school:
            cls.school = School(id=23, name="Frontend Audit Academy", code="FAA", status="ACTIVE")
            cls.db.add(cls.school)
            cls.db.commit()

        # Seed teacher and admin users
        cls.teacher_role = cls.db.query(Role).filter(Role.name == "teacher").first()
        if not cls.teacher_role:
            cls.teacher_role = Role(name="teacher")
            cls.db.add(cls.teacher_role)
            cls.db.commit()

        cls.teacher = cls.db.query(User).filter(User.username == "fa_teacher").first()
        if not cls.teacher:
            cls.teacher = User(
                username="fa_teacher",
                email="teacher@faa.edu.gh",
                password_hash=hash_password("TeacherPass123!"),
                school_id=23,
                is_active=True
            )
            cls.teacher.roles = [cls.teacher_role]
            cls.db.add(cls.teacher)
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_guard_js_contains_fetch_interceptor(self):
        """guard.js must install a global fetch interceptor handling 401 and 403 responses."""
        guard_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "js", "guard.js"))
        self.assertTrue(os.path.exists(guard_path))
        with open(guard_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("window._guardFetchInstalled", content)
        self.assertIn("response.status === 401", content)
        self.assertIn("response.status === 403", content)
        self.assertIn("redirectToLogin", content)
        self.assertIn("Authorization", content)
        self.assertIn("X-School-Id", content)

    def test_02_guard_js_page_roles_coverage(self):
        """guard.js PAGE_ROLES must cover sensitive admin pages."""
        guard_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "js", "guard.js"))
        with open(guard_path, "r", encoding="utf-8") as f:
            content = f.read()

        for page in ("super-admin.html", "users.html", "fees.html", "settings.html", "promotions.html"):
            self.assertIn(f"'{page}'", content)

    def test_03_backend_blocks_teacher_from_admin_impersonation(self):
        """Teacher client cannot trigger /api/auth/impersonate/{id} even if UI button was unhidden."""
        token = create_jwt({"sub": "fa_teacher", "user_id": self.teacher.id, "school_id": 23, "roles": ["teacher"]})
        res = self.client.post("/api/auth/impersonate/1", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 403)
        self.assertIn("detail", res.json())

    def test_04_backend_blocks_teacher_from_backup_execution(self):
        """Teacher client cannot trigger /api/backup/run."""
        token = create_jwt({"sub": "fa_teacher", "user_id": self.teacher.id, "school_id": 23, "roles": ["teacher"]})
        res = self.client.post("/api/backup/run", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 403)

    def test_05_backend_blocks_teacher_from_super_admin_endpoints(self):
        """Teacher client cannot access /api/super-admin/schools."""
        token = create_jwt({"sub": "fa_teacher", "user_id": self.teacher.id, "school_id": 23, "roles": ["teacher"]})
        res = self.client.get("/api/super-admin/schools", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 403)

    def test_06_tampered_school_id_header_ignored_or_rejected(self):
        """Client-supplied X-School-Id header cannot trick backend into leaking another tenant's data."""
        # Teacher is at school_id 23; sends X-School-Id: 1
        token = create_jwt({"sub": "fa_teacher", "user_id": self.teacher.id, "school_id": 23, "roles": ["teacher"]})
        res = self.client.get(
            "/api/students/",
            headers={"Authorization": f"Bearer {token}", "X-School-Id": "1"}
        )
        self.assertEqual(res.status_code, 200)
        # All returned students must belong to school 23, never school 1
        students = res.json()
        for s in students:
            self.assertEqual(s.get("school_id"), 23)

    def test_07_invalid_or_expired_token_returns_401(self):
        """Invalid token triggers 401 Unauthorized with standardized error format."""
        res = self.client.get("/api/auth/me", headers={"Authorization": "Bearer invalid_token_123"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("detail", res.json())


if __name__ == "__main__":
    unittest.main()
