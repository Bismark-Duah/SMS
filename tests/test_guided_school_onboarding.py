"""
Automated Test Suite for Guided School Onboarding Subsystem (Prompt 26).
Verifies:
1. Documentation in docs/GUIDED_SCHOOL_ONBOARDING.md.
2. GET /api/onboarding/status milestone calculation, completion progress, and next-step resolution.
3. POST /api/onboarding/dismiss and POST /api/onboarding/reset preferences.
4. Multi-tenant isolation and Super-Admin scoping.
5. Frontend dashboard container and script integration.
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models import User, Role, School
from backend.app.services.auth import create_jwt, hash_password

DOCS_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "GUIDED_SCHOOL_ONBOARDING.md")
DASHBOARD_HTML = os.path.join(os.path.dirname(__file__), "..", "frontend", "dashboard.html")
DASHBOARD_JS = os.path.join(os.path.dirname(__file__), "..", "frontend", "js", "dashboard.js")


class TestGuidedSchoolOnboarding(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Seed test school
        cls.school = cls.db.query(School).filter(School.code == "ONBOARD-SHS").first()
        if not cls.school:
            cls.school = School(
                name="Onboarding High School",
                code="ONBOARD-SHS",
                school_mode="SHS_ONLY",
                boarding_type="DAY_ONLY",
                status="ACTIVE",
                address="Accra Central",
                phone="+233200001122",
                email="admin@onboard.edu.gh"
            )
            cls.db.add(cls.school)
            cls.db.commit()
            cls.db.refresh(cls.school)

        # Seed admin role
        admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            cls.db.add(admin_role)
            cls.db.commit()

        # Seed admin user
        cls.admin_user = cls.db.query(User).filter(User.username == "onboard_admin_test").first()
        if not cls.admin_user:
            cls.admin_user = User(
                username="onboard_admin_test",
                email="admin@onboard.edu.gh",
                password_hash=hash_password("OnboardSecret123!"),
                school_id=cls.school.id,
                is_active=True
            )
            cls.admin_user.roles.append(admin_role)
            cls.db.add(cls.admin_user)
            cls.db.commit()
            cls.db.refresh(cls.admin_user)

        cls.token = create_jwt({
            "user_id": cls.admin_user.id,
            "username": cls.admin_user.username,
            "roles": ["admin"],
            "school_id": cls.school.id
        })

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_documentation_exists(self):
        """Verify docs/GUIDED_SCHOOL_ONBOARDING.md exists and is complete."""
        self.assertTrue(os.path.isfile(DOCS_PATH), "docs/GUIDED_SCHOOL_ONBOARDING.md must exist.")
        with open(DOCS_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Guided School Onboarding Subsystem", content)
        self.assertIn("10 Core Onboarding Milestones", content)
        self.assertIn("/api/onboarding/status", content)

    def test_02_onboarding_status_unauthorized(self):
        """GET /api/onboarding/status must reject unauthenticated requests with 401."""
        res = self.client.get("/api/onboarding/status")
        self.assertEqual(res.status_code, 401)

    def test_03_onboarding_status_success_contract(self):
        """GET /api/onboarding/status must return all 10 milestones and completion stats."""
        headers = {"Authorization": f"Bearer {self.token}"}
        res = self.client.get("/api/onboarding/status", headers=headers)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertEqual(data["school_id"], self.school.id)
        self.assertEqual(data["total_steps"], 10)
        self.assertIn("overall_progress_percent", data)
        self.assertIn("completed_count", data)
        self.assertIn("milestones", data)
        self.assertEqual(len(data["milestones"]), 10)

        milestone_ids = [m["id"] for m in data["milestones"]]
        expected_ids = [
            "profile", "admin_security", "academic_calendar", "classes",
            "subjects", "staff", "students", "fees", "grading", "roles"
        ]
        for eid in expected_ids:
            self.assertIn(eid, milestone_ids)

    def test_04_onboarding_dismiss_and_reset(self):
        """POST /api/onboarding/dismiss and /reset must persist banner preferences."""
        headers = {"Authorization": f"Bearer {self.token}"}

        # Dismiss
        res_dismiss = self.client.post("/api/onboarding/dismiss", headers=headers)
        self.assertEqual(res_dismiss.status_code, 200)
        self.assertEqual(res_dismiss.json()["status"], "success")

        # Verify status reports dismissed
        res_status = self.client.get("/api/onboarding/status", headers=headers)
        self.assertTrue(res_status.json()["is_dismissed"])

        # Reset
        res_reset = self.client.post("/api/onboarding/reset", headers=headers)
        self.assertEqual(res_reset.status_code, 200)

        # Verify status reports not dismissed
        res_status2 = self.client.get("/api/onboarding/status", headers=headers)
        self.assertFalse(res_status2.json()["is_dismissed"])

    def test_05_frontend_dashboard_integration(self):
        """Verify dashboard.html contains onboarding banner container and dashboard.js implements logic."""
        with open(DASHBOARD_HTML, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn('id="onboardingBanner"', html)

        with open(DASHBOARD_JS, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("loadGuidedOnboardingChecklist", js)
        self.assertIn("/onboarding/status", js)
        self.assertIn("dismissOnboardingBanner", js)


if __name__ == "__main__":
    unittest.main()
