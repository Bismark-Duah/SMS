"""
tests/test_system_telemetry_hardening.py

Regression test suite for Fix 1: Protect System Telemetry.
Verifies that:
1. Unauthenticated requests to /api/system/telemetry are rejected with HTTP 401.
2. School admins cannot access system telemetry (HTTP 403), preventing cross-school info leaks.
3. Teachers and staff cannot access system telemetry (HTTP 403).
4. Super Admins can access full telemetry (HTTP 200) with database stats and counts.
5. Public health endpoints (/api/system/health, /health) are accessible but sanitized,
   never leaking internal infrastructure, replica IPs, pool stats, or entity counts.
"""

import unittest
import os
import sys
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

from backend.app.database import SessionLocal, run_migrations
from backend.app.main import app
from backend.app.models import School, User, Role
from backend.app.routes.auth import _hash_password
from backend.app.services.auth import create_jwt


class TestSystemTelemetryHardening(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        run_migrations()
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()
        cls.suffix = uuid.uuid4().hex[:6]

        # 1. School
        cls.school = School(
            name=f"Telemetry School {cls.suffix}",
            code=f"TS-{cls.suffix}",
            school_mode="COMBINED"
        )
        cls.db.add(cls.school)
        cls.db.commit()
        cls.db.refresh(cls.school)

        # 2. Roles
        teacher_role = cls.db.query(Role).filter(Role.name == "teacher").first()
        admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        super_admin_role = cls.db.query(Role).filter(Role.name == "super_admin").first()
        if not super_admin_role:
            super_admin_role = Role(name="super_admin", description="Super Admin")
            cls.db.add(super_admin_role)
            cls.db.flush()

        # 3. Teacher
        cls.teacher = User(
            username=f"teacher_telem_{cls.suffix}",
            email=f"teacher_{cls.suffix}@test.local",
            password_hash=_hash_password("Pass123!"),
            school_id=cls.school.id,
            roles=[teacher_role] if teacher_role else []
        )
        cls.db.add(cls.teacher)

        # 4. School Admin
        cls.admin = User(
            username=f"admin_telem_{cls.suffix}",
            email=f"admin_{cls.suffix}@test.local",
            password_hash=_hash_password("Pass123!"),
            school_id=cls.school.id,
            roles=[admin_role] if admin_role else []
        )
        cls.db.add(cls.admin)

        # 5. Super Admin
        cls.super_admin = User(
            username=f"super_telem_{cls.suffix}",
            email=f"super_{cls.suffix}@test.local",
            password_hash=_hash_password("Pass123!"),
            roles=[super_admin_role]
        )
        cls.db.add(cls.super_admin)
        cls.db.commit()

        # Generate JWT tokens for test cases
        cls.teacher_token = create_jwt({
            "user_id": cls.teacher.id,
            "username": cls.teacher.username,
            "school_id": cls.school.id,
            "roles": ["teacher"],
            "token_version": 1
        })

        cls.admin_token = create_jwt({
            "user_id": cls.admin.id,
            "username": cls.admin.username,
            "school_id": cls.school.id,
            "roles": ["admin"],
            "token_version": 1
        })

        cls.super_admin_token = create_jwt({
            "user_id": cls.super_admin.id,
            "username": cls.super_admin.username,
            "roles": ["super_admin"],
            "token_version": 1
        })

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_unauthenticated_telemetry_access_denied(self):
        """Unauthenticated requests to /api/system/telemetry must return 401 Unauthorized."""
        res = self.client.get("/api/system/telemetry")
        self.assertEqual(res.status_code, 401, f"Expected 401, got {res.status_code}: {res.text}")

    def test_02_school_admin_telemetry_access_denied(self):
        """School Admin cannot view cross-school system telemetry (must return 403 Forbidden)."""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = self.client.get("/api/system/telemetry", headers=headers)
        self.assertEqual(res.status_code, 403, f"Expected 403, got {res.status_code}: {res.text}")
        self.assertIn("Super Admin", res.json().get("detail", ""))

    def test_03_teacher_telemetry_access_denied(self):
        """Teacher/Staff cannot view system telemetry (must return 403 Forbidden)."""
        headers = {"Authorization": f"Bearer {self.teacher_token}"}
        res = self.client.get("/api/system/telemetry", headers=headers)
        self.assertEqual(res.status_code, 403, f"Expected 403, got {res.status_code}: {res.text}")

    def test_04_super_admin_telemetry_access_granted(self):
        """Super Admin can successfully access detailed system telemetry."""
        headers = {"Authorization": f"Bearer {self.super_admin_token}"}
        res = self.client.get("/api/system/telemetry", headers=headers)
        self.assertEqual(res.status_code, 200, f"Expected 200, got {res.status_code}: {res.text}")
        data = res.json()
        self.assertEqual(data.get("status"), "success")
        self.assertIn("database", data)
        self.assertIn("counts", data)
        self.assertIn("schools", data["counts"])
        self.assertIn("users", data["counts"])
        self.assertIn("students", data["counts"])

    def test_05_public_health_probe_sanitized(self):
        """Public health endpoint is unauthenticated but sanitized to prevent information leaks."""
        for path in ["/health", "/api/health", "/api/system/health"]:
            res = self.client.get(path)
            self.assertIn(res.status_code, [200, 503], f"Unexpected status {res.status_code} for {path}")
            data = res.json()
            self.assertIn("status", data)
            self.assertIn("database", data)
            # Must NOT expose sensitive infrastructure details
            self.assertNotIn("schools", data)
            self.assertNotIn("users", data)
            self.assertNotIn("students", data)
            self.assertNotIn("counts", data)
            # Must be a safe string, not a nested dict exposing pool or replica metrics
            self.assertIsInstance(data["database"], str, "database field in public health check must be a simple status string")
            self.assertIn(data["database"], ["connected", "disconnected"])


if __name__ == "__main__":
    unittest.main()
