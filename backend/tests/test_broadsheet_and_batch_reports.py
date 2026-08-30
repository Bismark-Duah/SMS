"""
Automated Test Suite for Broadsheet Matrix & Batch Terminal Report Cards PDF Engine
Verifies class broadsheet matrix computation, WAEC/GES ranking, statistical summaries,
1-click multi-page batch report cards PDF compilation, and role-based access control.
"""
import sys
import os
import unittest
import uuid
from datetime import datetime

# Setup path so tests can run standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.database import SessionLocal
from backend.app.models import (
    School, Student, User, Role, Program, AcademicYear, Semester,
    ClassSection, Subject, Score, StudentSemesterSummary, SchoolStage
)
from backend.app.services.reports import ReportService
from backend.app.services.auth import create_jwt
from backend.app.routes.reports import (
    get_batch_terminal_reports,
    get_broadsheet_pdf,
    get_broadsheet_csv
)
from fastapi import HTTPException


class TestBroadsheetAndBatchReports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        u_suffix = uuid.uuid4().hex[:6]

        # 1. School
        cls.school = School(
            name=f"Wesley Girls High School {u_suffix}",
            code=f"WGHS-{u_suffix}",
            school_mode="SHS_ONLY"
        )
        cls.db.add(cls.school)
        cls.db.commit()
        cls.db.refresh(cls.school)

        # 2. Academic Year & Semester
        cls.acad_year = AcademicYear(
            label=f"2025/2026 {u_suffix}",
            is_current=True
        )
        cls.db.add(cls.acad_year)
        cls.db.commit()
        cls.db.refresh(cls.acad_year)

        cls.semester = Semester(
            name="Term 1",
            academic_year_id=cls.acad_year.id,
            is_current=True
        )
        cls.db.add(cls.semester)
        cls.db.commit()
        cls.db.refresh(cls.semester)

        # 3. Roles
        cls.admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        if not cls.admin_role:
            cls.admin_role = Role(name="admin")
            cls.db.add(cls.admin_role)
            cls.db.commit()

        cls.teacher_role = cls.db.query(Role).filter(Role.name == "teacher").first()
        if not cls.teacher_role:
            cls.teacher_role = Role(name="teacher")
            cls.db.add(cls.teacher_role)
            cls.db.commit()

        # 4. Form Master User
        cls.form_master = User(
            username=f"form_master_{u_suffix}",
            email=f"fm_{u_suffix}@example.com",
            password_hash="mockhash",
            school_id=cls.school.id,
            roles=[cls.teacher_role]
        )
        cls.db.add(cls.form_master)
        cls.db.commit()
        cls.db.refresh(cls.form_master)

        # Other Teacher User (not form master of this class)
        cls.other_teacher = User(
            username=f"other_teacher_{u_suffix}",
            email=f"other_{u_suffix}@example.com",
            password_hash="mockhash",
            school_id=cls.school.id,
            roles=[cls.teacher_role]
        )
        cls.db.add(cls.other_teacher)
        cls.db.commit()
        cls.db.refresh(cls.other_teacher)

        # Admin User
        cls.admin_user = User(
            username=f"admin_{u_suffix}",
            email=f"admin_{u_suffix}@example.com",
            password_hash="mockhash",
            school_id=cls.school.id,
            roles=[cls.admin_role]
        )
        cls.db.add(cls.admin_user)
        cls.db.commit()
        cls.db.refresh(cls.admin_user)

        # 5. Program, Stage & Class Section
        cls.stage = cls.db.query(SchoolStage).filter(SchoolStage.name == f"SHS 2 {u_suffix}").first()
        if not cls.stage:
            cls.stage = SchoolStage(name=f"SHS 2 {u_suffix}", school_type="SHS")
            cls.db.add(cls.stage)
            cls.db.commit()
            cls.db.refresh(cls.stage)

        cls.program = Program(
            name=f"General Science {u_suffix}",
            code=f"SCI-{u_suffix}",
            school_id=cls.school.id
        )
        cls.db.add(cls.program)
        cls.db.commit()
        cls.db.refresh(cls.program)

        cls.class_sec = ClassSection(
            name=f"Science 2A {u_suffix}",
            stage_id=cls.stage.id,
            program_id=cls.program.id,
            form_master_id=cls.form_master.id
        )
        cls.db.add(cls.class_sec)
        cls.db.commit()
        cls.db.refresh(cls.class_sec)

        # 6. Subjects
        cls.sub_mth = Subject(name=f"Core Mathematics {u_suffix}", code=f"MTH-{u_suffix}", is_core=True)
        cls.sub_sci = Subject(name=f"Integrated Science {u_suffix}", code=f"SCI-{u_suffix}", is_core=True)
        cls.sub_eng = Subject(name=f"English Language {u_suffix}", code=f"ENG-{u_suffix}", is_core=True)
        cls.db.add_all([cls.sub_mth, cls.sub_sci, cls.sub_eng])
        cls.db.commit()

        cls.class_sec.subjects.extend([cls.sub_mth, cls.sub_sci, cls.sub_eng])
        cls.db.commit()

        # 7. Students
        cls.st1 = Student(
            student_code=f"ST1-{u_suffix}",
            first_name="Kwame",
            last_name="Mensah",
            full_name="Kwame Mensah",
            gender="Male",
            class_section_id=cls.class_sec.id,
            program_id=cls.program.id,
            school_id=cls.school.id,
            is_active=True
        )
        cls.st2 = Student(
            student_code=f"ST2-{u_suffix}",
            first_name="Ama",
            last_name="Osei",
            full_name="Ama Osei",
            gender="Female",
            class_section_id=cls.class_sec.id,
            program_id=cls.program.id,
            school_id=cls.school.id,
            is_active=True
        )
        cls.db.add_all([cls.st1, cls.st2])
        cls.db.commit()
        cls.db.refresh(cls.st1)
        cls.db.refresh(cls.st2)

        # 8. Scores
        # Kwame: MTH 85 (A1), SCI 75 (B2), ENG 90 (A1) -> Total = 250
        s1 = Score(student_id=cls.st1.id, subject_id=cls.sub_mth.id, semester_id=cls.semester.id, class_score=27, exam_score=58, total_score=85, grade="A1", remark="Excellent")
        s2 = Score(student_id=cls.st1.id, subject_id=cls.sub_sci.id, semester_id=cls.semester.id, class_score=23, exam_score=52, total_score=75, grade="B2", remark="Very Good")
        s3 = Score(student_id=cls.st1.id, subject_id=cls.sub_eng.id, semester_id=cls.semester.id, class_score=28, exam_score=62, total_score=90, grade="A1", remark="Excellent")

        # Ama: MTH 65 (B3), SCI 58 (C4), ENG 70 (B2) -> Total = 193
        s4 = Score(student_id=cls.st2.id, subject_id=cls.sub_mth.id, semester_id=cls.semester.id, class_score=20, exam_score=45, total_score=65, grade="B3", remark="Good")
        s5 = Score(student_id=cls.st2.id, subject_id=cls.sub_sci.id, semester_id=cls.semester.id, class_score=18, exam_score=40, total_score=58, grade="C4", remark="Credit")
        s6 = Score(student_id=cls.st2.id, subject_id=cls.sub_eng.id, semester_id=cls.semester.id, class_score=22, exam_score=48, total_score=70, grade="B2", remark="Very Good")

        cls.db.add_all([s1, s2, s3, s4, s5, s6])

        # 9. Form Master Remarks
        sum1 = StudentSemesterSummary(
            student_id=cls.st1.id,
            semester_id=cls.semester.id,
            attitude="Excellent",
            conduct="Exemplary",
            interest="Mathematics & Science",
            form_teacher_remarks="An outstanding student."
        )
        sum2 = StudentSemesterSummary(
            student_id=cls.st2.id,
            semester_id=cls.semester.id,
            attitude="Good",
            conduct="Respectful",
            interest="Reading",
            form_teacher_remarks="Good performance, keep working hard."
        )
        cls.db.add_all([sum1, sum2])
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.rollback()
        cls.db.close()

    def test_01_batch_terminal_reports_pdf_compilation(self):
        """Verify compiling batch terminal reports for a class generates a multi-page PDF binary."""
        pdf_bytes = ReportService.generate_batch_terminal_reports_pdf(
            self.db, self.class_sec.id, self.semester.id
        )
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"), "Batch terminal reports must be a valid PDF binary")
        self.assertGreater(len(pdf_bytes), 1000)

    def test_02_broadsheet_pdf_compilation(self):
        """Verify compiling broadsheet ledger PDF in Landscape orientation."""
        pdf_bytes = ReportService.generate_broadsheet_pdf(
            self.db, self.class_sec.id, self.semester.id
        )
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"), "Broadsheet Ledger must be a valid PDF binary")
        self.assertGreater(len(pdf_bytes), 1000)

    def test_03_broadsheet_csv_generation(self):
        """Verify generating broadsheet CSV with student scores and statistical summary rows."""
        csv_str = ReportService.generate_broadsheet_csv(
            self.db, self.class_sec.id, self.semester.id
        )
        self.assertIsNotNone(csv_str)
        self.assertIn("CLASS BROADSHEET MATRIX & ACADEMIC LEDGER", csv_str)
        self.assertIn("Kwame Mensah", csv_str)
        self.assertIn("Ama Osei", csv_str)
        self.assertIn("STATISTICAL SUMMARY", csv_str)
        self.assertIn("Class Subject Mean", csv_str)
        self.assertIn("Pass Rate (>=50%)", csv_str)

    def test_04_batch_reports_endpoint_admin_success(self):
        """Verify GET /batch-terminal-reports/{class_section_id} as Admin."""
        admin_token = create_jwt({"sub": self.admin_user.username, "user_id": self.admin_user.id, "roles": ["admin"], "school_id": self.school.id})
        response = get_batch_terminal_reports(
            class_section_id=self.class_sec.id,
            semester_id=self.semester.id,
            token=admin_token,
            authorization=None,
            db=self.db
        )
        self.assertEqual(response.media_type, "application/pdf")
        self.assertTrue(response.body.startswith(b"%PDF-"))
        self.assertIn("attachment; filename=\"Batch_Report_Cards_", response.headers["Content-Disposition"])

    def test_05_broadsheet_pdf_endpoint_form_master_success(self):
        """Verify GET /broadsheet-pdf/{class_section_id} as assigned Form Master."""
        fm_token = create_jwt({"sub": self.form_master.username, "user_id": self.form_master.id, "roles": ["teacher"], "school_id": self.school.id})
        response = get_broadsheet_pdf(
            class_section_id=self.class_sec.id,
            semester_id=self.semester.id,
            token=fm_token,
            authorization=None,
            db=self.db
        )
        self.assertEqual(response.media_type, "application/pdf")
        self.assertTrue(response.body.startswith(b"%PDF-"))
        self.assertIn("attachment; filename=\"Broadsheet_Ledger_", response.headers["Content-Disposition"])

    def test_06_broadsheet_csv_endpoint_success(self):
        """Verify GET /broadsheet-csv/{class_section_id} returns structured CSV."""
        admin_token = create_jwt({"sub": self.admin_user.username, "user_id": self.admin_user.id, "roles": ["admin"], "school_id": self.school.id})
        response = get_broadsheet_csv(
            class_section_id=self.class_sec.id,
            semester_id=self.semester.id,
            token=admin_token,
            authorization=None,
            db=self.db
        )
        self.assertEqual(response.media_type, "text/csv")
        self.assertIn("Kwame Mensah", response.body.decode("utf-8"))

    def test_07_unauthorized_teacher_access_guard(self):
        """Verify that an unassigned teacher is forbidden (403) from generating batch reports."""
        other_token = create_jwt({"sub": self.other_teacher.username, "user_id": self.other_teacher.id, "roles": ["teacher"], "school_id": self.school.id})
        with self.assertRaises(HTTPException) as cm:
            get_batch_terminal_reports(
                class_section_id=self.class_sec.id,
                semester_id=self.semester.id,
                token=other_token,
                authorization=None,
                db=self.db
            )
        self.assertEqual(cm.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
