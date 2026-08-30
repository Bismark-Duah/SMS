"""
Automated Test Suite for Enterprise Reactive Client State Bus, Theme Sync & Live Branding Reactivity
Verifies theme persistence via Settings API, client state bus module validity, smooth CSS transition tokens,
and instant branding state updates.
"""
import sys
import os
import unittest
import uuid
import json

# Setup path so tests can run standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.database import SessionLocal
from backend.app.models import School, User, Role, Setting
from backend.app.routes.settings import get_settings, update_settings


class TestStateBusAndLiveReactivity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.u_suffix = uuid.uuid4().hex[:6]

        cls.school = School(
            name=f"Enterprise Test Academy {cls.u_suffix}",
            code=f"ETA-{cls.u_suffix}",
            school_mode="COMBINED"
        )
        cls.db.add(cls.school)
        cls.db.commit()
        cls.db.refresh(cls.school)

        cls.admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        if not cls.admin_role:
            cls.admin_role = Role(name="admin")
            cls.db.add(cls.admin_role)
            cls.db.commit()

        cls.super_role = cls.db.query(Role).filter(Role.name == "super_admin").first()
        if not cls.super_role:
            cls.super_role = Role(name="super_admin")
            cls.db.add(cls.super_role)
            cls.db.commit()

        cls.admin_user = User(
            username=f"admin_state_{cls.u_suffix}",
            email=f"admin_state_{cls.u_suffix}@example.com",
            password_hash="mockhash",
            school_id=cls.school.id,
            roles=[cls.admin_role]
        )
        cls.db.add(cls.admin_user)

        cls.super_user = User(
            username=f"super_state_{cls.u_suffix}",
            email=f"super_state_{cls.u_suffix}@example.com",
            password_hash="mockhash",
            school_id=cls.school.id,
            roles=[cls.super_role]
        )
        cls.db.add(cls.super_user)
        cls.db.commit()
        cls.db.refresh(cls.admin_user)
        cls.db.refresh(cls.super_user)

    @classmethod
    def tearDownClass(cls):
        cls.db.rollback()
        cls.db.close()

    def test_01_state_bus_file_integrity(self):
        """Verify frontend/js/stateBus.js exists, has valid structure and required methods."""
        file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "js", "stateBus.js"))
        self.assertTrue(os.path.exists(file_path), "stateBus.js must exist in frontend/js/")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("SMSStateBus", content)
        self.assertIn("setTheme", content)
        self.assertIn("updateBranding", content)
        self.assertIn("subscribe", content)
        self.assertIn("BroadcastChannel", content)
        self.assertIn("broadcastLogout", content)

    def test_02_theme_persistence_via_api(self):
        """Verify updating system_theme via Settings API stores and returns the new theme instantly."""
        payload = {
            "school_name": f"Enterprise Test Academy {self.u_suffix}",
            "school_abbreviation": f"ETA-{self.u_suffix}",
            "system_theme": "ocean",
            "school_mode": "COMBINED",
            "boarding_status": "BOARDING_AND_DAY"
        }
        update_settings(payload, db=self.db, current_user=self.admin_user)

        res = get_settings(db=self.db, current_user=self.admin_user)
        self.assertEqual(res.get("system_theme"), "ocean")

    def test_03_branding_persistence_via_api(self):
        """Verify updating school branding via Settings API updates school metadata."""
        new_name = f"National Science & Tech College {self.u_suffix}"
        new_abbr = f"NSTC_{self.u_suffix}"
        payload = {
            "school_name": new_name,
            "school_abbreviation": new_abbr,
            "report_motto": "Knowledge is Light",
            "system_theme": "emerald",
            "school_mode": "SHS_ONLY",
            "boarding_status": "BOARDING_AND_DAY"
        }
        update_settings(payload, db=self.db, current_user=self.super_user)

        res = get_settings(db=self.db, current_user=self.super_user)
        self.assertEqual(res.get("school_name"), new_name)
        self.assertEqual(res.get("school_abbreviation"), new_abbr)
        self.assertEqual(res.get("report_motto"), "Knowledge is Light")
        self.assertEqual(res.get("system_theme"), "emerald")

    def test_04_smooth_css_transitions_present(self):
        """Verify frontend/css/styles.css contains the theme transition properties."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "css", "styles.css"))
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()

        self.assertIn("transition:", css_content)
        self.assertIn("cubic-bezier", css_content)



if __name__ == "__main__":
    unittest.main()
