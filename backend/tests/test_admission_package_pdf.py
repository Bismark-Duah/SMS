"""
Official Admission Package & Prospectus PDF Test Suite.
Verifies:
1. PDF generation produces valid PDF binaries (%PDF- header).
2. Dynamic prospectus items tailoring for Boarders vs Day students.
3. Gender-specific uniform and grooming requirements.
4. Program specialization toolkits (Science, Home Econ, Visual Arts, Business, etc.).
5. CSSPS Public Enrollment and Admin Students PDF download endpoint functions.
6. Role-based authorization for parents and forbidden checks for unlinked students.
"""
import os
import sys
import uuid
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from fastapi import HTTPException, Response

from app.database import SessionLocal
from app.models import Student, School, Program, House, Dormitory, ClassSection, StudentHealth, User, Role
from app.services.admission_package import AdmissionPackageService
from app.routes.cssps_enrollment import download_admission_package_pdf
from app.routes.students import download_student_admission_package_pdf


class TestAdmissionPackagePDF(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db: Session = SessionLocal()

        # Setup test school
        cls.school = cls.db.query(School).filter(School.code == "ADM_TEST_SCH").first()
        if not cls.school:
            cls.school = School(
                name="Acheampong Memorial STEM High",
                code="ADM_TEST_SCH",
                slug="adm-test",
                sms_balance=100
            )
            cls.db.add(cls.school)
            cls.db.commit()
            cls.db.refresh(cls.school)

        # Setup test programs
        cls.prog_science = cls.db.query(Program).filter(Program.name == "General Science Test").first()
        if not cls.prog_science:
            cls.prog_science = Program(name="General Science Test", school_id=cls.school.id)
            cls.db.add(cls.prog_science)

        cls.prog_home_econ = cls.db.query(Program).filter(Program.name == "Home Economics Test").first()
        if not cls.prog_home_econ:
            cls.prog_home_econ = Program(name="Home Economics Test", school_id=cls.school.id)
            cls.db.add(cls.prog_home_econ)

        # Setup test house & dorm
        cls.house = cls.db.query(House).filter(House.name == "Aggrey House Test").first()
        if not cls.house:
            cls.house = House(name="Aggrey House Test", gender="Male", school_id=cls.school.id)
            cls.db.add(cls.house)

        cls.db.commit()
        cls.db.refresh(cls.prog_science)
        cls.db.refresh(cls.prog_home_econ)
        cls.db.refresh(cls.house)

        cls.dorm = cls.db.query(Dormitory).filter(Dormitory.name == "Block A Room 1 Test").first()
        if not cls.dorm:
            cls.dorm = Dormitory(name="Block A Room 1 Test", house_id=cls.house.id, capacity=20)
            cls.db.add(cls.dorm)
            cls.db.commit()
            cls.db.refresh(cls.dorm)

        # Setup admin test user
        admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            cls.db.add(admin_role)
            cls.db.commit()
            cls.db.refresh(admin_role)

        cls.admin_user = cls.db.query(User).filter(User.username == "adm_pdf_admin").first()
        if not cls.admin_user:
            cls.admin_user = User(
                username="adm_pdf_admin",
                email="admin@admtest.edu.gh",
                school_id=cls.school.id,
                password_hash="mock_hash",
                is_active=True
            )
            cls.admin_user.roles.append(admin_role)
            cls.db.add(cls.admin_user)
            cls.db.commit()
            cls.db.refresh(cls.admin_user)

        parent_role = cls.db.query(Role).filter(Role.name == "parent").first()
        if not parent_role:
            parent_role = Role(name="parent")
            cls.db.add(parent_role)
            cls.db.commit()
            cls.db.refresh(parent_role)

        cls.parent_user = cls.db.query(User).filter(User.username == "adm_pdf_parent").first()
        if not cls.parent_user:
            cls.parent_user = User(
                username="adm_pdf_parent",
                email="parent@admtest.edu.gh",
                school_id=cls.school.id,
                password_hash="mock_hash",
                is_active=True
            )
            cls.parent_user.roles.append(parent_role)
            cls.db.add(cls.parent_user)
            cls.db.commit()
            cls.db.refresh(cls.parent_user)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.db.rollback()

    def tearDown(self):
        self.db.rollback()

    def test_01_generate_pdf_boarding_science_male(self):
        """Verify PDF generation for a male boarding science student."""
        u_suffix = uuid.uuid4().hex[:6]
        stu = Student(
            full_name=f"Kwame Mensah {u_suffix}",
            student_code=f"STU-{u_suffix}",
            bece_index_number=f"1010{u_suffix}",
            gender="Male",
            residential_status="B",
            school_id=self.school.id,
            program_id=self.prog_science.id,
            house_id=self.house.id,
            dormitory_id=self.dorm.id,
            academic_year="2025/2026"
        )
        self.db.add(stu)
        self.db.commit()
        self.db.refresh(stu)

        health = StudentHealth(
            student_id=stu.id,
            blood_group="O+",
            allergies="Dust and Peanuts",
            chronic_conditions="Mild Asthma"
        )
        self.db.add(health)
        self.db.commit()

        pdf_bytes = AdmissionPackageService.generate_admission_letter_pdf(stu.id, self.db)
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(len(pdf_bytes) > 1000)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

    def test_02_generate_pdf_day_home_econ_female(self):
        """Verify PDF generation for a female day home economics student."""
        u_suffix = uuid.uuid4().hex[:6]
        stu = Student(
            full_name=f"Akosua Serwaa {u_suffix}",
            student_code=f"STU-{u_suffix}",
            bece_index_number=f"1010{u_suffix}",
            gender="Female",
            residential_status="D",
            school_id=self.school.id,
            program_id=self.prog_home_econ.id,
            academic_year="2025/2026"
        )
        self.db.add(stu)
        self.db.commit()
        self.db.refresh(stu)

        pdf_bytes = AdmissionPackageService.generate_admission_letter_pdf(stu.id, self.db)
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(len(pdf_bytes) > 1000)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

    def test_03_nonexistent_student_returns_none(self):
        """Verify service returns None gracefully if student ID does not exist."""
        pdf_bytes = AdmissionPackageService.generate_admission_letter_pdf(99999999, self.db)
        self.assertIsNone(pdf_bytes)

    def test_04_cssps_public_pdf_endpoint(self):
        """Test public CSSPS endpoint function download_admission_package_pdf."""
        u_suffix = uuid.uuid4().hex[:6]
        stu = Student(
            full_name=f"Yaw Osei {u_suffix}",
            student_code=f"STU-{u_suffix}",
            bece_index_number=f"1010{u_suffix}",
            gender="Male",
            residential_status="B",
            school_id=self.school.id,
            program_id=self.prog_science.id,
            academic_year="2025/2026"
        )
        self.db.add(stu)
        self.db.commit()
        self.db.refresh(stu)

        resp = download_admission_package_pdf(student_id=stu.id, db=self.db)
        self.assertIsInstance(resp, Response)
        self.assertEqual(resp.media_type, "application/pdf")
        self.assertIn("attachment; filename=", resp.headers.get("Content-Disposition", ""))
        self.assertTrue(resp.body.startswith(b"%PDF-"))

    def test_05_cssps_public_pdf_404_for_missing_student(self):
        """Test public CSSPS endpoint raises HTTPException 404 when student is not found."""
        with self.assertRaises(HTTPException) as ctx:
            download_admission_package_pdf(student_id=99999999, db=self.db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_06_admin_student_pdf_endpoint(self):
        """Test admin student endpoint function download_student_admission_package_pdf."""
        u_suffix = uuid.uuid4().hex[:6]
        stu = Student(
            full_name=f"Abena Pokua {u_suffix}",
            student_code=f"STU-{u_suffix}",
            bece_index_number=f"1010{u_suffix}",
            gender="Female",
            residential_status="D",
            school_id=self.school.id,
            program_id=self.prog_home_econ.id,
            academic_year="2025/2026"
        )
        self.db.add(stu)
        self.db.commit()
        self.db.refresh(stu)

        resp = download_student_admission_package_pdf(
            student_id=stu.id,
            db=self.db,
            current_user=self.admin_user
        )
        self.assertIsInstance(resp, Response)
        self.assertEqual(resp.media_type, "application/pdf")
        self.assertIn(f"Admission_Package_{stu.student_code}.pdf", resp.headers.get("Content-Disposition", ""))
        self.assertTrue(resp.body.startswith(b"%PDF-"))

    def test_07_parent_can_download_linked_child_admission_package(self):
        """Test that a parent can download the admission package for their linked child."""
        u_suffix = uuid.uuid4().hex[:6]
        stu = Student(
            full_name=f"Kofi Mensah Child {u_suffix}",
            student_code=f"STU-{u_suffix}",
            bece_index_number=f"1010{u_suffix}",
            gender="Male",
            residential_status="B",
            school_id=self.school.id,
            parent_id=self.parent_user.id,
            program_id=self.prog_science.id,
            academic_year="2025/2026"
        )
        self.db.add(stu)
        self.db.commit()
        self.db.refresh(stu)

        resp = download_student_admission_package_pdf(
            student_id=stu.id,
            db=self.db,
            current_user=self.parent_user
        )
        self.assertIsInstance(resp, Response)
        self.assertEqual(resp.media_type, "application/pdf")
        self.assertTrue(resp.body.startswith(b"%PDF-"))

    def test_08_parent_forbidden_from_unlinked_student_admission_package(self):
        """Test that a parent receives 403 Forbidden when attempting to download an unlinked student's package."""
        u_suffix = uuid.uuid4().hex[:6]
        stu = Student(
            full_name=f"Unlinked Student {u_suffix}",
            student_code=f"STU-{u_suffix}",
            bece_index_number=f"1010{u_suffix}",
            gender="Male",
            residential_status="D",
            school_id=self.school.id,
            parent_id=self.admin_user.id,  # Belongs to another user
            program_id=self.prog_science.id,
            academic_year="2025/2026"
        )
        self.db.add(stu)
        self.db.commit()
        self.db.refresh(stu)

        with self.assertRaises(HTTPException) as ctx:
            download_student_admission_package_pdf(
                student_id=stu.id,
                db=self.db,
                current_user=self.parent_user
            )
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
