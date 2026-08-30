"""
Automated Test Suite for Multi-Year Cumulative Records, Official Transcripts PDF & Class Progression Engine
Verifies official 3-year SHS academic transcript compilation, NaCCA basic cumulative record folder PDF,
intelligent class promotion evaluation rules, batch promotions, cohort graduation, and promotion docket PDFs.
"""
import sys
import os
import unittest
import uuid
from datetime import datetime, date

# Setup path so tests can run standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.database import SessionLocal
from backend.app.models import (
    School, Student, User, Role, Program, AcademicYear, Semester,
    ClassSection, Score, Subject, Attendance, Setting, SchoolStage,
    StudentSemesterSummary
)
from backend.app.services.reports import ReportService
from backend.app.routes.reports import get_official_transcript_pdf
from backend.app.routes.cumulative_records import get_cumulative_record_pdf
from backend.app.routes.promotions import (
    get_promotion_candidates,
    promote_students,
    graduate_students,
    get_promotion_docket_pdf,
    PromoteRequest,
    GraduateRequest
)
from fastapi import HTTPException


class TestTranscriptsAndPromotions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        u_suffix = uuid.uuid4().hex[:6]

        # 1. School
        cls.school = School(
            name=f"Presbyterian Boys' SHS {u_suffix}",
            code=f"PRESEC-{u_suffix}",
            school_mode="SHS_ONLY"
        )
        cls.db.add(cls.school)
        cls.db.commit()
        cls.db.refresh(cls.school)

        # Foreign School for isolation tests
        cls.other_school = School(
            name=f"Opoku Ware School {u_suffix}",
            code=f"OWASS-{u_suffix}",
            school_mode="SHS_ONLY"
        )
        cls.db.add(cls.other_school)
        cls.db.commit()
        cls.db.refresh(cls.other_school)

        # 2. Roles
        cls.admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        if not cls.admin_role:
            cls.admin_role = Role(name="admin")
            cls.db.add(cls.admin_role)
            cls.db.commit()

        # 3. Users
        cls.admin_user = User(
            username=f"admin_trans_{u_suffix}",
            email=f"admin_trans_{u_suffix}@example.com",
            password_hash="mockhash",
            school_id=cls.school.id,
            roles=[cls.admin_role]
        )
        cls.db.add(cls.admin_user)
        cls.db.commit()
        cls.db.refresh(cls.admin_user)

        # 4. Academic Year & Semesters
        cls.acad_year = AcademicYear(label=f"2025/2026_{u_suffix}", is_current=True)
        cls.db.add(cls.acad_year)
        cls.db.commit()
        cls.db.refresh(cls.acad_year)

        cls.sem1 = Semester(name=f"Sem 1 {u_suffix}", academic_year_id=cls.acad_year.id, is_current=False)
        cls.sem2 = Semester(name=f"Sem 2 {u_suffix}", academic_year_id=cls.acad_year.id, is_current=True)
        cls.db.add_all([cls.sem1, cls.sem2])
        cls.db.commit()
        cls.db.refresh(cls.sem1)
        cls.db.refresh(cls.sem2)

        # 5. Program, Stage & Class Sections
        cls.stage1 = SchoolStage(name=f"SHS 1 {u_suffix}", school_type="SHS")
        cls.stage2 = SchoolStage(name=f"SHS 2 {u_suffix}", school_type="SHS")
        cls.db.add_all([cls.stage1, cls.stage2])
        cls.db.commit()
        cls.db.refresh(cls.stage1)
        cls.db.refresh(cls.stage2)

        cls.program = Program(
            name=f"General Science {u_suffix}",
            code=f"SCI-{u_suffix}",
            school_id=cls.school.id
        )
        cls.db.add(cls.program)
        cls.db.commit()
        cls.db.refresh(cls.program)

        cls.class_sec1 = ClassSection(
            name=f"Science 1A {u_suffix}",
            stage_id=cls.stage1.id,
            program_id=cls.program.id
        )
        cls.class_sec2 = ClassSection(
            name=f"Science 2A {u_suffix}",
            stage_id=cls.stage2.id,
            program_id=cls.program.id
        )
        cls.db.add_all([cls.class_sec1, cls.class_sec2])
        cls.db.commit()
        cls.db.refresh(cls.class_sec1)
        cls.db.refresh(cls.class_sec2)

        # 6. Subjects
        cls.sub_core_math = Subject(
            name=f"Core Mathematics {u_suffix}",
            code=f"MTH-{u_suffix}",
            is_core=True,
            school_id=cls.school.id
        )
        cls.sub_physics = Subject(
            name=f"Physics {u_suffix}",
            code=f"PHY-{u_suffix}",
            is_core=False,
            school_id=cls.school.id
        )
        cls.sub_robotics = Subject(
            name=f"Robotics and Coding {u_suffix}",
            code=f"ROB-{u_suffix}",
            is_core=False,
            assessment_type="Internal_Transcript",
            school_id=cls.school.id
        )
        cls.db.add_all([cls.sub_core_math, cls.sub_physics, cls.sub_robotics])
        cls.db.commit()
        cls.db.refresh(cls.sub_core_math)
        cls.db.refresh(cls.sub_physics)
        cls.db.refresh(cls.sub_robotics)

        # 7. Students
        cls.st_pass = Student(
            student_code=f"ST-PRO1-{u_suffix}",
            first_name="Kwesi",
            last_name="Arthur",
            full_name="Kwesi Arthur",
            gender="Male",
            form=1,
            class_section_id=cls.class_sec1.id,
            program_id=cls.program.id,
            school_id=cls.school.id,
            is_active=True
        )
        cls.st_fail = Student(
            student_code=f"ST-PRO2-{u_suffix}",
            first_name="Akosua",
            last_name="Serwaa",
            full_name="Akosua Serwaa",
            gender="Female",
            form=1,
            class_section_id=cls.class_sec1.id,
            program_id=cls.program.id,
            school_id=cls.school.id,
            is_active=True
        )
        cls.st_foreign = Student(
            student_code=f"ST-FOR-{u_suffix}",
            first_name="Foreign",
            last_name="Student",
            full_name="Foreign Student",
            school_id=cls.other_school.id,
            is_active=True
        )
        cls.db.add_all([cls.st_pass, cls.st_fail, cls.st_foreign])
        cls.db.commit()
        cls.db.refresh(cls.st_pass)
        cls.db.refresh(cls.st_fail)
        cls.db.refresh(cls.st_foreign)

        # 8. Scores (Passing student vs failing student)
        score1 = Score(student_id=cls.st_pass.id, subject_id=cls.sub_core_math.id, semester_id=cls.sem1.id, total_score=85.0, grade="A1", remark="Excellent")
        score2 = Score(student_id=cls.st_pass.id, subject_id=cls.sub_physics.id, semester_id=cls.sem1.id, total_score=78.0, grade="B2", remark="Very Good")
        score3 = Score(student_id=cls.st_pass.id, subject_id=cls.sub_robotics.id, semester_id=cls.sem1.id, total_score=92.0, grade="A1", remark="Outstanding")

        score4 = Score(student_id=cls.st_fail.id, subject_id=cls.sub_core_math.id, semester_id=cls.sem1.id, total_score=38.0, grade="F9", remark="Fail")
        score5 = Score(student_id=cls.st_fail.id, subject_id=cls.sub_physics.id, semester_id=cls.sem1.id, total_score=42.0, grade="E8", remark="Pass")

        cls.db.add_all([score1, score2, score3, score4, score5])

        # 9. Attendance
        cls.db.add(Attendance(student_id=cls.st_pass.id, date=datetime.now().date(), status="Present", attendance_type="daily"))
        cls.db.add(Attendance(student_id=cls.st_fail.id, date=datetime.now().date(), status="Absent", attendance_type="daily"))

        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.rollback()
        cls.db.close()

    def test_01_official_transcript_pdf_generation(self):
        """Verify generating 3-year SHS academic transcript PDF and endpoint."""
        pdf_bytes = ReportService.generate_official_transcript_pdf(self.db, self.st_pass.id)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"), "Transcript must be a valid PDF binary")

        # Verify endpoint response
        resp = get_official_transcript_pdf(self.st_pass.id, db=self.db, current_user=self.admin_user)
        self.assertEqual(resp.media_type, "application/pdf")
        self.assertIn("Official_Transcript_", resp.headers["Content-Disposition"])

    def test_02_basic_cumulative_folder_pdf_generation(self):
        """Verify generating basic cumulative record folder PDF and endpoint."""
        pdf_bytes = ReportService.generate_basic_cumulative_folder_pdf(self.db, self.st_pass.id)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"), "Cumulative folder must be a valid PDF binary")

        # Verify endpoint response
        resp = get_cumulative_record_pdf(self.st_pass.id, db=self.db, current_user=self.admin_user)
        self.assertEqual(resp.media_type, "application/pdf")
        self.assertIn("Cumulative_Record_Folder_", resp.headers["Content-Disposition"])

    def test_03_promotion_candidates_evaluation(self):
        """Verify intelligent promotion decision evaluation rules."""
        candidates = get_promotion_candidates(self.class_sec1.id, db=self.db, current_user=self.admin_user)
        self.assertGreaterEqual(len(candidates), 2)

        c_pass = next(c for c in candidates if c["id"] == self.st_pass.id)
        c_fail = next(c for c in candidates if c["id"] == self.st_fail.id)

        self.assertEqual(c_pass["recommendation"], "Promoted")
        self.assertGreaterEqual(c_pass["average_score"], 80.0)

        self.assertEqual(c_fail["recommendation"], "Repeat")
        self.assertLess(c_fail["average_score"], 45.0)

    def test_04_batch_promotion_execution(self):
        """Verify executing batch promotion updates class section and increments form."""
        payload = PromoteRequest(
            student_ids=[self.st_pass.id],
            target_class_section_id=self.class_sec2.id,
            increment_form=True
        )
        res = promote_students(payload, db=self.db, current_user=self.admin_user)
        self.assertIn("Successfully promoted", res["message"])

        # Check DB update
        self.db.refresh(self.st_pass)
        self.assertEqual(self.st_pass.class_section_id, self.class_sec2.id)
        self.assertEqual(self.st_pass.form, 2)

    def test_05_graduation_execution(self):
        """Verify graduating students deactivates enrolment and sets GRADUATED status."""
        payload = GraduateRequest(student_ids=[self.st_pass.id])
        res = graduate_students(payload, db=self.db, current_user=self.admin_user)
        self.assertIn("Successfully graduated", res["message"])

        self.db.refresh(self.st_pass)
        self.assertIsNone(self.st_pass.class_section_id)
        self.assertFalse(self.st_pass.is_active)
        self.assertEqual(self.st_pass.status, "GRADUATED")

    def test_06_promotion_docket_pdf_generation(self):
        """Verify generating the official GES class promotion decision docket PDF."""
        resp = get_promotion_docket_pdf(self.class_sec1.id, db=self.db, current_user=self.admin_user)
        self.assertEqual(resp.media_type, "application/pdf")
        self.assertTrue(resp.body.startswith(b"%PDF-"), "Promotion docket must be a valid PDF binary")
        self.assertIn("Promotion_Docket_", resp.headers["Content-Disposition"])

    def test_07_tenant_isolation_guards(self):
        """Verify foreign school students cannot be accessed for transcripts or promotion."""
        with self.assertRaises(HTTPException) as cm1:
            get_official_transcript_pdf(self.st_foreign.id, db=self.db, current_user=self.admin_user)
        self.assertEqual(cm1.exception.status_code, 404)

        with self.assertRaises(HTTPException) as cm2:
            get_cumulative_record_pdf(self.st_foreign.id, db=self.db, current_user=self.admin_user)
        self.assertEqual(cm2.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
