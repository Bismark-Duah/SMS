import unittest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.database import Base
from backend.app.models import School, User, Role, Setting, Student, user_roles
from backend.app.routes.super_admin import update_school_profile, get_school_details, SchoolUpdateSchema
from fastapi import HTTPException

class TestSuperAdminSchoolEdit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        self.u_suffix = uuid.uuid4().hex[:6]

        # Create Super Admin Role
        self.super_role = self.db.query(Role).filter(Role.name == "super_admin").first()
        if not self.super_role:
            self.super_role = Role(name="super_admin")
            self.db.add(self.super_role)
            self.db.flush()

        # Create Admin Role
        self.admin_role = self.db.query(Role).filter(Role.name == "admin").first()
        if not self.admin_role:
            self.admin_role = Role(name="admin")
            self.db.add(self.admin_role)
            self.db.flush()

        # Create Super Admin User
        self.super_user = User(
            username=f"superadmin_{self.u_suffix}",
            email=f"super_{self.u_suffix}@example.com",
            password_hash="hashed_pw",
            is_active=True,
            school_id=None
        )
        self.db.add(self.super_user)
        self.db.flush()
        self.db.execute(user_roles.insert().values(user_id=self.super_user.id, role_id=self.super_role.id))

        # Create Regular Admin User (Non-Super Admin)
        self.regular_admin = User(
            username=f"regadmin_{self.u_suffix}",
            email=f"reg_{self.u_suffix}@example.com",
            password_hash="hashed_pw",
            is_active=True,
            school_id=1
        )
        self.db.add(self.regular_admin)
        self.db.flush()
        self.db.execute(user_roles.insert().values(user_id=self.regular_admin.id, role_id=self.admin_role.id))

        # Create Test School 1
        self.school1 = School(
            name=f"Atwima Koforidua Islamic Basic {self.u_suffix}",
            code=f"AK_{self.u_suffix}".upper(),
            school_mode="BASIC_ONLY",
            boarding_type="DAY_ONLY",
            status="ACTIVE"
        )
        self.db.add(self.school1)
        self.db.flush()

        # Add initial students and settings
        self.student1 = Student(
            student_code=f"STU_{self.u_suffix}",
            full_name="Kofi Mensah",
            first_name="Kofi",
            last_name="Mensah",
            school_id=self.school1.id,
            is_active=True
        )
        self.db.add(self.student1)
        self.db.add(Setting(school_id=self.school1.id, key="school_name", value=self.school1.name))
        self.db.add(Setting(school_id=self.school1.id, key="school_mode", value="BASIC_ONLY"))

        # Create Test School 2
        self.school2 = School(
            name=f"J.A. Kufuor STEM {self.u_suffix}",
            code=f"JAK_{self.u_suffix}".upper(),
            school_mode="SHS_ONLY",
            boarding_type="BOARDING_AND_DAY",
            status="ACTIVE"
        )
        self.db.add(self.school2)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_01_super_admin_can_edit_school_profile(self):
        """Verify Super Admin can update school name, code, mode, boarding, and contact info."""
        new_name = f"Atwima Koforidua Islamic Model Basic {self.u_suffix}"
        new_code = f"AKMB_{self.u_suffix}".upper()
        
        payload = SchoolUpdateSchema(
            name=new_name,
            code=new_code,
            school_mode="COMBINED",
            boarding_type="BOARDING_AND_DAY",
            phone="+233240001122",
            email="info@akmb.edu.gh",
            address="Atwima Koforidua Central",
            logo_url="data:image/svg+xml;base64,PHN2Zz48L3N2Zz4="
        )

        res = update_school_profile(
            school_id=self.school1.id,
            payload=payload,
            db=self.db,
            current_user=self.super_user
        )

        self.assertIn("updated successfully", res["message"])
        self.assertEqual(res["school"]["name"], new_name)
        self.assertEqual(res["school"]["code"], new_code)
        self.assertEqual(res["school"]["school_mode"], "COMBINED")
        self.assertEqual(res["school"]["boarding_type"], "BOARDING_AND_DAY")
        self.assertEqual(res["school"]["logo_url"], "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=")

        # Verify database model was updated
        db_school = self.db.query(School).filter(School.id == self.school1.id).first()
        self.assertEqual(db_school.name, new_name)
        self.assertEqual(db_school.code, new_code)
        self.assertEqual(db_school.school_mode, "COMBINED")

        # Verify tenant settings were synchronized
        name_setting = self.db.query(Setting).filter(Setting.school_id == self.school1.id, Setting.key == "school_name").first()
        self.assertEqual(name_setting.value, new_name)
        mode_setting = self.db.query(Setting).filter(Setting.school_id == self.school1.id, Setting.key == "school_mode").first()
        self.assertEqual(mode_setting.value, "COMBINED")

        # Verify students were NOT deleted or touched
        student = self.db.query(Student).filter(Student.school_id == self.school1.id).first()
        self.assertIsNotNone(student)
        self.assertEqual(student.first_name, "Kofi")

    def test_02_duplicate_code_is_rejected(self):
        """Verify assigning an existing school's code triggers a 400 error."""
        payload = SchoolUpdateSchema(
            code=self.school2.code  # Try to hijack School 2's code
        )

        with self.assertRaises(HTTPException) as ctx:
            update_school_profile(
                school_id=self.school1.id,
                payload=payload,
                db=self.db,
                current_user=self.super_user
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("already assigned", ctx.exception.detail)

    def test_03_get_school_details_endpoint(self):
        """Verify GET /schools/{id} returns full metadata for the edit modal."""
        details = get_school_details(
            school_id=self.school1.id,
            db=self.db,
            current_user=self.super_user
        )
        self.assertEqual(details["id"], self.school1.id)
        self.assertEqual(details["name"], self.school1.name)
        self.assertEqual(details["code"], self.school1.code)
        self.assertEqual(details["student_count"], 1)

    def test_04_regular_admin_cannot_override_locked_school_fields(self):
        """Verify regular school admin cannot change school_name, school_mode, or boarding_status via settings endpoint."""
        from backend.app.routes.settings import update_settings

        initial_name = self.school1.name
        initial_mode = self.school1.school_mode

        payload = {
            "school_name": "Malicious Admin Changed School Name",
            "school_mode": "SHS_ONLY",
            "report_motto": "Discipline and Hard Work"
        }

        res = update_settings(
            payload=payload,
            db=self.db,
            current_user=self.regular_admin,
            school_id=self.school1.id
        )

        # Reload school from database
        self.db.refresh(self.school1)

        # School name and mode must remain strictly unchanged
        self.assertEqual(self.school1.name, initial_name)
        self.assertEqual(self.school1.school_mode, initial_mode)

        # Legitimate school settings like motto SHOULD be updated
        motto_setting = self.db.query(Setting).filter(Setting.school_id == self.school1.id, Setting.key == "report_motto").first()
        self.assertIsNotNone(motto_setting)
        self.assertEqual(motto_setting.value, "Discipline and Hard Work")

    def test_05_dashboard_metrics_serialization(self):
        """Verify GET /super-admin/dashboard returns valid JSON-serializable numbers and lists."""
        import json
        from backend.app.routes.super_admin import get_super_admin_dashboard

        data = get_super_admin_dashboard(db=self.db, current_user=self.super_user)
        self.assertIn("total_schools", data)
        self.assertIn("schools", data)
        self.assertIn("comparative_analytics", data)
        self.assertIsInstance(data["total_fees_billed"], float)
        self.assertIsInstance(data["total_fees_collected"], float)
        self.assertIsInstance(data["overall_collection_rate"], float)

        # Must cleanly serialize to JSON without Decimal or date errors
        serialized = json.dumps(data)
        self.assertIsInstance(serialized, str)

if __name__ == "__main__":
    unittest.main()


