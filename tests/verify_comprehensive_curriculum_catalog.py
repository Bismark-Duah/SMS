"""
verify_comprehensive_curriculum_catalog.py — Test Suite for Complete National Curriculum Catalog & Cross-Cutting Electives
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import SessionLocal, engine, Base
from backend.app.models import School, Subject, Program, User, Role
from backend.app.ncca_seed import seed_ncca_curriculum
from backend.app.routes.subjects import list_subjects
from backend.app.routes.super_admin import get_school_accreditation, update_school_accreditation, SchoolAccreditationUpdateSchema

class TestComprehensiveCurriculumCatalog(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()
        seed_ncca_curriculum(cls.db)

        # Admin Role
        cls.admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        if not cls.admin_role:
            cls.admin_role = Role(name="admin")
            cls.db.add(cls.admin_role)
            cls.db.flush()

        # Super Admin User
        cls.super_admin = cls.db.query(User).filter(User.username == "test_super_admin_catalog").first()
        if not cls.super_admin:
            role = cls.db.query(Role).filter(Role.name == "super_admin").first()
            if not role:
                role = Role(name="super_admin")
                cls.db.add(role)
                cls.db.flush()
            cls.super_admin = User(username="test_super_admin_catalog", email="super_cat@sms.test", password_hash="dummy")
            cls.super_admin.roles.append(role)
            cls.db.add(cls.super_admin)
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_verify_all_official_subjects_seeded(self):
        """Test all newly added official WAEC/NaCCA subjects are present in the database"""
        required_subjects = [
            # Visual Arts
            "Art and Design Foundation", "Art and Design Studio", "Design and Communication",
            "General Knowledge in Art", "Graphic Design", "Picture Making", "Textiles", "Ceramics", "Sculpture",
            # Home Economics
            "Management in Living", "Clothing and Textiles", "Food and Nutrition",
            "Catering & Hospitality", "Garment Making & Fashion", "Cosmetology & Beauty Therapy",
            # Technical & TVET
            "Applied Technology", "Technical Drawing", "Applied Electricity", "Electronics", "Auto Mechanics",
            # Agriculture
            "General Agriculture", "Animal Husbandry", "Crop Husbandry & Horticulture", "Fisheries"
        ]

        all_names = {s.name for s in self.db.query(Subject).all()}
        for sub_name in required_subjects:
            self.assertIn(sub_name, all_names, f"Missing required official subject: '{sub_name}'")

        print(f"[OK] Step 1: All {len(required_subjects)} newly added official Ghanaian subjects verified in Master Catalog.")

    def test_02_verify_cross_cutting_electives_categorization(self):
        """Test get_school_accreditation categorizes cross-cutting electives in their dedicated section"""
        school = self.db.query(School).filter(School.code == "JAK-STEM-CAT").first()
        if not school:
            school = School(name="Test SHS", code="TEST-SHS-CAT", school_mode="SHS_ONLY")
            self.db.add(school)
            self.db.commit()

        data = get_school_accreditation(school_id=school.id, db=self.db, current_user=self.super_admin)
        grouped = data["grouped_catalog"]

        self.assertIn("🌐 Cross-Cutting / Multi-Track Electives", grouped)
        cross_cutting_subs = [s["name"] for s in grouped["🌐 Cross-Cutting / Multi-Track Electives"]]

        # Verify key cross-cutting electives are present
        self.assertIn("Additional Mathematics", cross_cutting_subs)
        self.assertIn("Economics", cross_cutting_subs)
        self.assertIn("Geography", cross_cutting_subs)
        self.assertIn("Chemistry", cross_cutting_subs)
        self.assertIn("Biology", cross_cutting_subs)
        self.assertIn("General Knowledge in Art", cross_cutting_subs)
        self.assertIn("French (Elective)", cross_cutting_subs)

        print(f"[OK] Step 2: Dedicated Cross-Cutting section verified with {len(cross_cutting_subs)} shared electives.")

    def test_03_verify_visual_arts_and_home_econs_presets(self):
        """Test Visual Arts and Home Economics presets contain their official subjects"""
        school = self.db.query(School).filter(School.code == "JAK-STEM-CAT").first()
        data = get_school_accreditation(school_id=school.id, db=self.db, current_user=self.super_admin)
        presets = data["presets"]

        self.assertIn("visual_arts", presets)
        self.assertIn("home_economics", presets)
        self.assertIn("science_stem", presets)

        # Get subject names by IDs
        sub_map = {s.id: s.name for s in self.db.query(Subject).all()}
        va_names = [sub_map[sid] for sid in presets["visual_arts"]["subject_ids"] if sid in sub_map]
        he_names = [sub_map[sid] for sid in presets["home_economics"]["subject_ids"] if sid in sub_map]

        # Verify Visual Arts Preset
        self.assertIn("Art and Design Foundation", va_names)
        self.assertIn("Art and Design Studio", va_names)
        self.assertIn("Design and Communication", va_names)
        self.assertIn("General Knowledge in Art", va_names)

        # Verify Home Economics Preset
        self.assertIn("Management in Living", he_names)
        self.assertIn("Clothing and Textiles", he_names)
        self.assertIn("Food and Nutrition", he_names)
        self.assertIn("Biology", he_names)

        print("[OK] Step 3: Presets verified for Visual Arts and Home Economics.")

    def test_04_school_admin_view_with_home_econs_preset(self):
        """Test activating Home Economics on a school scopes its catalog to Home Economics subjects"""
        he_school = self.db.query(School).filter(School.code == "HE-ACAD-TEST").first()
        if not he_school:
            he_school = School(
                name="St. Catherine Home Economics Academy",
                code="HE-ACAD-TEST",
                school_mode="SHS_ONLY",
                boarding_type="BOARDING_AND_DAY",
                status="ACTIVE"
            )
            self.db.add(he_school)
            self.db.flush()

        data = get_school_accreditation(school_id=he_school.id, db=self.db, current_user=self.super_admin)
        he_preset_sub_ids = data["presets"]["home_economics"]["subject_ids"]

        # Apply Home Economics accreditation
        payload = SchoolAccreditationUpdateSchema(subject_ids=he_preset_sub_ids)
        res = update_school_accreditation(school_id=he_school.id, payload=payload, db=self.db, current_user=self.super_admin)
        self.assertEqual(res["status"], "success")

        # Mock School Admin user
        he_admin = User(id=99971, username="he_admin_test", email="he@test.com", school_id=he_school.id, roles=[self.admin_role])
        scoped = list_subjects(db=self.db, current_user=he_admin, x_school_id=str(he_school.id))
        scoped_names = [s.name for s in scoped]

        # Verify Home Economics subjects present
        self.assertIn("Management in Living", scoped_names)
        self.assertIn("Clothing and Textiles", scoped_names)
        self.assertIn("Food and Nutrition", scoped_names)
        self.assertIn("General Knowledge in Art", scoped_names)
        self.assertIn("Biology", scoped_names)

        # Verify unaccredited subjects excluded
        self.assertNotIn("Auto Mechanics", scoped_names)
        self.assertNotIn("Robotics Engineering", scoped_names)
        self.assertNotIn("Leatherwork", scoped_names)

        print(f"[OK] Step 4: St. Catherine Home Economics Academy scoped to {len(scoped_names)} accredited subjects.")

if __name__ == "__main__":
    unittest.main()
