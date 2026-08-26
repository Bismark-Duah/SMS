"""
verify_school_catalog_subscription.py — Comprehensive Test Suite for Master Catalog & School Active Subject Subscriptions
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

class TestSchoolCatalogSubscription(unittest.TestCase):

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
        cls.super_admin = cls.db.query(User).filter(User.username == "test_super_admin").first()
        if not cls.super_admin:
            role = cls.db.query(Role).filter(Role.name == "super_admin").first()
            if not role:
                role = Role(name="super_admin")
                cls.db.add(role)
                cls.db.flush()
            cls.super_admin = User(username="test_super_admin", email="super@sms.test", password_hash="dummy")
            cls.super_admin.roles.append(role)
            cls.db.add(cls.super_admin)
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_super_admin_provisions_stem_school(self):
        """Test Super Admin provisions a pure STEM school with only STEM & Science subjects"""
        school = self.db.query(School).filter(School.code == "JAK-STEM-CAT").first()
        if not school:
            school = School(
                name="J.A. Kufuor STEM Academy",
                code="JAK-STEM-CAT",
                school_mode="SHS_ONLY",
                boarding_type="BOARDING_AND_DAY",
                status="ACTIVE"
            )
            self.db.add(school)
            self.db.flush()

        # Select 10 STEM & Science subjects
        target_names = [
            "Core Mathematics", "English Language (SHS)", "Social Studies (SHS)", "General Science (Core)",
            "Physics", "Chemistry", "Biology", "Additional Mathematics",
            "Computer Science (Elective)", "Robotics Engineering"
        ]
        target_subs = self.db.query(Subject).filter(Subject.name.in_(target_names)).all()
        self.assertGreaterEqual(len(target_subs), 8)

        school.active_subjects = target_subs
        self.db.commit()
        self.db.refresh(school)

        self.assertEqual(len(school.active_subjects), len(target_subs))
        print(f"[OK] Step 1: School '{school.name}' provisioned with {len(school.active_subjects)} active subjects.")

    def test_02_school_admin_subject_scoping(self):
        """Test School Admin only sees their school's active subscribed subjects (not 80+ global subjects)"""
        school = self.db.query(School).filter(School.code == "JAK-STEM-CAT").first()
        self.assertIsNotNone(school)

        # Mock School Admin user
        admin_user = User(id=99881, username="jak_admin_cat", email="jak@cat.test", school_id=school.id, roles=[self.admin_role])
        
        # Query subjects for this school
        scoped_subjects = list_subjects(
            school_level=None,
            exclude_basic=False,
            include_inactive=False,
            db=self.db,
            current_user=admin_user,
            x_school_id=str(school.id)
        )

        scoped_names = [s.name for s in scoped_subjects]
        print(f"[OK] Step 2: School Admin sees {len(scoped_subjects)} scoped subjects: {scoped_names[:5]}...")

        # Verify active subjects are present
        self.assertIn("Physics", scoped_names)
        self.assertIn("Core Mathematics", scoped_names)
        self.assertIn("Computer Science (Elective)", scoped_names)

        # Verify unaccredited subjects are strictly excluded
        self.assertNotIn("Basketry", scoped_names)
        self.assertNotIn("Leatherwork", scoped_names)
        self.assertNotIn("Cosmetology & Beauty Therapy", scoped_names)
        self.assertNotIn("Typewriting & Keyboarding", scoped_names)
        self.assertNotIn("Rhymes, Phonics & Language", scoped_names)

    def test_03_super_admin_updates_accreditation(self):
        """Test Super Admin updates accreditation to add Economics and Geography"""
        school = self.db.query(School).filter(School.code == "JAK-STEM-CAT").first()
        self.assertIsNotNone(school)

        current_sub_ids = [s.id for s in school.active_subjects]
        
        # Find Economics and Geography
        new_subs = self.db.query(Subject).filter(Subject.name.in_(["Economics", "Geography"])).all()
        for ns in new_subs:
            if ns.id not in current_sub_ids:
                current_sub_ids.append(ns.id)

        # Call update_school_accreditation API
        payload = SchoolAccreditationUpdateSchema(subject_ids=current_sub_ids)
        res = update_school_accreditation(
            school_id=school.id,
            payload=payload,
            db=self.db,
            current_user=self.super_admin
        )

        self.assertEqual(res["status"], "success")
        self.assertGreaterEqual(res["active_subjects_count"], len(current_sub_ids))

        # Check School Admin view now includes newly added subjects
        admin_user = User(id=99881, username="jak_admin_cat", email="jak@cat.test", school_id=school.id, roles=[self.admin_role])
        scoped_subjects = list_subjects(
            db=self.db,
            current_user=admin_user,
            x_school_id=str(school.id)
        )
        scoped_names = [s.name for s in scoped_subjects]
        self.assertIn("Economics", scoped_names)
        self.assertIn("Geography", scoped_names)
        print(f"[OK] Step 3: Accreditation expanded to {len(scoped_subjects)} subjects including Economics & Geography.")

    def test_04_cross_tenant_isolation(self):
        """Test Business School only sees Business subjects and cannot see STEM/Engineering subjects"""
        stem_school = self.db.query(School).filter(School.code == "JAK-STEM-CAT").first()
        
        biz_school = self.db.query(School).filter(School.code == "KUMASI-BIZ-CAT").first()
        if not biz_school:
            biz_school = School(
                name="Kumasi Business Academy",
                code="KUMASI-BIZ-CAT",
                school_mode="SHS_ONLY",
                boarding_type="DAY_ONLY",
                status="ACTIVE"
            )
            self.db.add(biz_school)
            self.db.flush()

        biz_subs = self.db.query(Subject).filter(Subject.name.in_([
            "Core Mathematics", "English Language (SHS)", "Social Studies (SHS)",
            "Business Management", "Financial Accounting", "Cost Accounting", "Economics"
        ])).all()
        biz_school.active_subjects = biz_subs
        self.db.commit()

        biz_admin = User(id=99882, username="biz_admin_cat", email="biz@cat.test", school_id=biz_school.id, roles=[self.admin_role])
        biz_scoped = list_subjects(db=self.db, current_user=biz_admin, x_school_id=str(biz_school.id))
        biz_names = [s.name for s in biz_scoped]

        # Business Admin sees Business
        self.assertIn("Business Management", biz_names)
        self.assertIn("Financial Accounting", biz_names)
        self.assertIn("Cost Accounting", biz_names)

        # Business Admin CANNOT see pure STEM subjects
        self.assertNotIn("Physics", biz_names)
        self.assertNotIn("Chemistry", biz_names)
        self.assertNotIn("Robotics Engineering", biz_names)

        print("[OK] Step 4: Cross-tenant isolation verified between STEM Academy and Business Academy.")

    def test_05_custom_school_specific_elective(self):
        """Test custom local elective created by a school is strictly private to that school"""
        stem_school = self.db.query(School).filter(School.code == "JAK-STEM-CAT").first()
        biz_school = self.db.query(School).filter(School.code == "KUMASI-BIZ-CAT").first()

        # Add custom elective for STEM school
        custom_sub = self.db.query(Subject).filter(Subject.name == "STEM AI Innovation Lab").first()
        if not custom_sub:
            custom_sub = Subject(
                name="STEM AI Innovation Lab",
                code="AI-LAB-STEM",
                is_core=False,
                category="Elective",
                school_level="STEM",
                school_id=stem_school.id
            )
            self.db.add(custom_sub)
            self.db.commit()

        stem_admin = User(id=99881, username="jak_admin_cat", email="jak@cat.test", school_id=stem_school.id, roles=[self.admin_role])
        stem_scoped = list_subjects(db=self.db, current_user=stem_admin, x_school_id=str(stem_school.id))
        stem_names = [s.name for s in stem_scoped]

        biz_admin = User(id=99882, username="biz_admin_cat", email="biz@cat.test", school_id=biz_school.id, roles=[self.admin_role])
        biz_scoped = list_subjects(db=self.db, current_user=biz_admin, x_school_id=str(biz_school.id))
        biz_names = [s.name for s in biz_scoped]

        self.assertIn("STEM AI Innovation Lab", stem_names)
        self.assertNotIn("STEM AI Innovation Lab", biz_names)
        print("[OK] Step 5: Custom school elective 'STEM AI Innovation Lab' is private to STEM School.")

if __name__ == "__main__":
    unittest.main()
