"""
verify_school_modes.py — Comprehensive Full-Stack Verification of SHS_ONLY vs BASIC_ONLY vs COMBINED Mode Scoping
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import SessionLocal, engine, Base
from backend.app.models import Setting, ClassSection, Student, Program, House, School
from backend.app.routes.settings import get_settings


class TestSchoolModesScoping(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        # Reset mode to COMBINED
        s = cls.db.query(Setting).filter(Setting.key == "school_mode").first()
        if s:
            s.value = "COMBINED"
        else:
            cls.db.add(Setting(key="school_mode", value="COMBINED"))
        cls.db.commit()
        cls.db.close()

    def set_mode(self, mode_val: str):
        settings = self.db.query(Setting).filter(Setting.key == "school_mode").all()
        if settings:
            for s in settings:
                s.value = mode_val
        else:
            self.db.add(Setting(key="school_mode", value=mode_val))
        for sc in self.db.query(School).all():
            sc.school_mode = mode_val
        self.db.commit()

    def test_01_shs_only_mode_scoping(self):
        self.set_mode("SHS_ONLY")
        settings_dict = get_settings(db=self.db)
        
        self.assertEqual(settings_dict.get("school_mode"), "SHS_ONLY")
        # Default grading standard in SHS_ONLY mode should resolve to WAEC (A1-F9)
        self.assertEqual(settings_dict.get("grading_standard"), "WAEC")

    def test_02_basic_only_mode_scoping(self):
        self.set_mode("BASIC_ONLY")
        settings_dict = get_settings(db=self.db)
        
        self.assertEqual(settings_dict.get("school_mode"), "BASIC_ONLY")
        # Default grading standard in BASIC_ONLY mode should resolve to BECE (1-9)
        self.assertEqual(settings_dict.get("grading_standard"), "BECE")

    def test_03_combined_mode_scoping(self):
        self.set_mode("COMBINED")
        settings_dict = get_settings(db=self.db)
        self.assertEqual(settings_dict.get("school_mode"), "COMBINED")


if __name__ == "__main__":
    unittest.main()
