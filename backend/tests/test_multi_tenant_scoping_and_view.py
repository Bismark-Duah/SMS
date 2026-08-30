"""
Automated Test Suite for Multi-Tenant Scoping, Zero-Trust BOLA Isolation & Enter View Performance
Verifies:
1. Multi-tenant Settings & Public Branding isolation between School A (Atwima Koforidua Basic) and School B (J.A. Kufuor STEM).
2. Zero-Trust BOLA boundary defense (non-super-admin users locked to their own school_id, ignoring spoofed headers).
3. Super Admin Enter View dynamic switching via X-School-Id and Session scoping.
4. Executive Analytics query execution speed and strict school tenant filtering.
"""
import sys
import os
import unittest
import uuid

# Setup path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.database import SessionLocal, Base, engine
from backend.app.models import School, User, Role, Setting, Student, ClassSection, SchoolStage
from backend.app.routes.settings import get_settings, get_public_branding, update_settings
from backend.app.routes.academic import get_executive_analytics
from backend.app.dependencies import get_school_id


class TestMultiTenantScopingAndView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()
        cls.u_suffix = uuid.uuid4().hex[:6]

        # Roles
        cls.sa_role = cls.db.query(Role).filter(Role.name == "super_admin").first()
        if not cls.sa_role:
            cls.sa_role = Role(name="super_admin")
            cls.db.add(cls.sa_role)
            cls.db.commit()

        cls.adm_role = cls.db.query(Role).filter(Role.name == "admin").first()
        if not cls.adm_role:
            cls.adm_role = Role(name="admin")
            cls.db.add(cls.adm_role)
            cls.db.commit()

        # School 1: J.A. Kufuor STEM Technical School
        cls.sch1 = School(
            name=f"J.A. Kufuor STEM Technical School {cls.u_suffix}",
            code=f"JAKS-{cls.u_suffix}",
            school_mode="SHS_ONLY",
            status="ACTIVE"
        )
        cls.db.add(cls.sch1)
        cls.db.commit()
        cls.db.refresh(cls.sch1)

        # School 2: Atwima Koforidua Basic School
        cls.sch2 = School(
            name=f"Atwima Koforidua Basic School {cls.u_suffix}",
            code=f"AKBS-{cls.u_suffix}",
            school_mode="BASIC_ONLY",
            status="ACTIVE"
        )
        cls.db.add(cls.sch2)
        cls.db.commit()
        cls.db.refresh(cls.sch2)

        # Super Admin User (school_id is None)
        cls.sa_user = User(
            username=f"sa_tenant_{cls.u_suffix}",
            email=f"sa_tenant_{cls.u_suffix}@test.gh",
            password_hash="mockhash",
            school_id=None,
            is_active=True,
            roles=[cls.sa_role]
        )
        cls.db.add(cls.sa_user)

        # School 2 Admin User (locked to school_id = sch2.id)
        cls.sch2_admin = User(
            username=f"sch2_admin_{cls.u_suffix}",
            email=f"sch2_admin_{cls.u_suffix}@test.gh",
            password_hash="mockhash",
            school_id=cls.sch2.id,
            is_active=True,
            roles=[cls.adm_role]
        )
        cls.db.add(cls.sch2_admin)

        # Create Students for School 2
        stage = SchoolStage(name=f"JHS_STAGE_{cls.u_suffix}", school_type="Basic")
        cls.db.add(stage)
        cls.db.commit()
        cls.db.refresh(stage)

        cls_sec = ClassSection(name=f"JHS 1A {cls.u_suffix}", stage_id=stage.id)
        cls.db.add(cls_sec)
        cls.db.commit()
        cls.db.refresh(cls_sec)

        cls.st1 = Student(
            student_code=f"AKBS-{cls.u_suffix}-001",
            full_name="Kwame Mensah",
            first_name="Kwame",
            last_name="Mensah",
            enrolment_code=f"AKBS-{cls.u_suffix}-001",
            class_section_id=cls_sec.id,
            school_id=cls.sch2.id,
            is_active=True
        )
        cls.db.add(cls.st1)
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.rollback()
        cls.db.close()

    def test_01_super_admin_enter_view_school2(self):
        """Verify Super Admin entering School 2 returns Atwima Koforidua Basic School branding and settings."""
        res = get_settings(
            db=self.db,
            current_user=self.sa_user,
            school_id=self.sch2.id,
            x_school_id=str(self.sch2.id)
        )
        self.assertEqual(res.get("school_name"), self.sch2.name)
        self.assertEqual(res.get("school_code"), self.sch2.code)
        self.assertEqual(res.get("school_mode"), "BASIC_ONLY")

    def test_02_super_admin_enter_view_school1(self):
        """Verify Super Admin entering School 1 returns J.A. Kufuor STEM Technical School branding and settings."""
        res = get_settings(
            db=self.db,
            current_user=self.sa_user,
            school_id=self.sch1.id,
            x_school_id=str(self.sch1.id)
        )
        self.assertEqual(res.get("school_name"), self.sch1.name)
        self.assertEqual(res.get("school_code"), self.sch1.code)
        self.assertEqual(res.get("school_mode"), "SHS_ONLY")

    def test_03_zero_trust_bola_defense(self):
        """
        Verify Zero-Trust BOLA Defense:
        When a regular admin from School 2 passes X-School-Id for School 1,
        get_school_id MUST ignore the header and strictly return School 2's id.
        """
        resolved_id = get_school_id(
            current_user=self.sch2_admin,
            x_school_id=str(self.sch1.id),
            request=None
        )
        self.assertEqual(resolved_id, self.sch2.id, "BOLA defense failed: non-superadmin was able to override tenant ID!")

        res = get_settings(
            db=self.db,
            current_user=self.sch2_admin,
            school_id=resolved_id,
            x_school_id=str(self.sch1.id)
        )
        self.assertEqual(res.get("school_name"), self.sch2.name)
        self.assertEqual(res.get("school_code"), self.sch2.code)

    def test_04_public_branding_tenant_isolation(self):
        """Verify public branding for portals isolates exact school without falling back to School 1."""
        brand2 = get_public_branding(
            db=self.db,
            x_school_id=str(self.sch2.id),
            school_id=self.sch2.id,
            mode=None
        )
        self.assertEqual(brand2.get("school_name"), self.sch2.name)
        self.assertEqual(brand2.get("school_mode"), "BASIC_ONLY")

        brand1 = get_public_branding(
            db=self.db,
            x_school_id=str(self.sch1.id),
            school_id=self.sch1.id,
            mode=None
        )
        self.assertEqual(brand1.get("school_name"), self.sch1.name)
        self.assertEqual(brand1.get("school_mode"), "SHS_ONLY")

    def test_05_executive_analytics_tenant_scoping_speed(self):
        """Verify executive analytics resolves scoped data in milliseconds for the specified school."""
        import time
        t0 = time.time()
        analytics = get_executive_analytics(
            db=self.db,
            current_user=self.sa_user,
            school_id=self.sch2.id
        )
        duration_ms = (time.time() - t0) * 1000

        self.assertEqual(analytics.get("school_mode"), "BASIC_ONLY")
        self.assertIn("academic", analytics)
        self.assertIn("domestic", analytics)
        # Latency should be well under 500ms
        self.assertLess(duration_ms, 500, f"Executive analytics took too long: {duration_ms:.2f}ms")

    def test_06_super_admin_update_settings_scoping(self):
        """Verify Super Admin updating settings for School 2 does not affect School 1."""
        update_settings(
            payload={"school_name": f"Renamed Basic School {self.u_suffix}", "school_mode": "BASIC_ONLY"},
            db=self.db,
            current_user=self.sa_user,
            school_id=self.sch2.id,
            x_school_id=str(self.sch2.id)
        )
        
        # Verify School 2 was updated
        res2 = get_settings(db=self.db, current_user=self.sa_user, school_id=self.sch2.id, x_school_id=str(self.sch2.id))
        self.assertEqual(res2.get("school_name"), f"Renamed Basic School {self.u_suffix}")

        # Verify School 1 was NOT altered
        res1 = get_settings(db=self.db, current_user=self.sa_user, school_id=self.sch1.id, x_school_id=str(self.sch1.id))
        self.assertEqual(res1.get("school_name"), self.sch1.name)


if __name__ == "__main__":
    unittest.main()

