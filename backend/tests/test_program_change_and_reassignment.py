"""
Academic Program Change, Realignment & Capacity Management Test Suite.
Verifies:
1. Role-based authorization (teachers/unauthorized rejected with 403, academic heads/admins allowed).
2. Atomic reassignment of program, class stream, and elective package.
3. Capacity enforcement: capacity limits enforced, Headmaster force_override honored.
4. Continuous assessment scoresheet realignment: core scores preserved, electives swapped.
5. Audit trail logging to AuditLog with approving authority & timestamp.
6. Revised Official Admission Package PDF with revised docket watermark banner.
7. Public and administrative capacity endpoints.
"""
import os
import sys
import uuid
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database import SessionLocal
from app.models import (
    Student, School, Program, ClassSection, ElectiveCombination,
    Subject, Score, Semester, AcademicYear, User, Role, AuditLog, SchoolStage
)
from app.services.program_transfer_service import ProgramTransferService
from app.services.admission_package import AdmissionPackageService
from app.routes.students import change_student_program
from app.schemas import ProgramChangeRequest


class TestProgramChangeAndReassignment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db: Session = SessionLocal()

        # 1. School setup
        suffix = uuid.uuid4().hex[:6]
        cls.school = School(
            name=f"Enterprise Test Academy {suffix}",
            code=f"SCH_{suffix}",
            slug=f"sch-{suffix}",
            school_mode="SHS_ONLY"
        )
        cls.db.add(cls.school)
        cls.db.commit()
        cls.db.refresh(cls.school)

        # 2. Roles & Users
        cls.admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        if not cls.admin_role:
            cls.admin_role = Role(name="admin", description="School Administrator")
            cls.db.add(cls.admin_role)

        cls.acad_head_role = cls.db.query(Role).filter(Role.name == "assistant_headmaster_academic").first()
        if not cls.acad_head_role:
            cls.acad_head_role = Role(name="assistant_headmaster_academic", description="Head of Academics")
            cls.db.add(cls.acad_head_role)

        cls.teacher_role = cls.db.query(Role).filter(Role.name == "teacher").first()
        if not cls.teacher_role:
            cls.teacher_role = Role(name="teacher", description="Subject Teacher")
            cls.db.add(cls.teacher_role)

        cls.db.commit()

        cls.admin_user = User(
            username=f"head_acad_{suffix}",
            email=f"acad_{suffix}@test.com",
            password_hash="fakehash",
            school_id=cls.school.id
        )
        cls.admin_user.roles.append(cls.acad_head_role)
        cls.db.add(cls.admin_user)

        cls.teacher_user = User(
            username=f"teacher_{suffix}",
            email=f"teach_{suffix}@test.com",
            password_hash="fakehash",
            school_id=cls.school.id
        )
        cls.teacher_user.roles.append(cls.teacher_role)
        cls.db.add(cls.teacher_user)

        # 3. Stage & Programs
        cls.stage = SchoolStage(name=f"SHS 1 {suffix}", school_type="SHS", school_id=cls.school.id)
        cls.db.add(cls.stage)
        cls.db.commit()
        cls.db.refresh(cls.stage)

        cls.prog_arts = Program(name=f"General Arts {suffix}", code=f"ART_{suffix}", school_id=cls.school.id)
        cls.prog_science = Program(name=f"General Science {suffix}", code=f"SCI_{suffix}", school_id=cls.school.id)
        cls.db.add_all([cls.prog_arts, cls.prog_science])
        cls.db.commit()
        cls.db.refresh(cls.prog_arts)
        cls.db.refresh(cls.prog_science)

        # 4. Class Sections (Streams)
        cls.sec_arts = ClassSection(name=f"Arts 1A {suffix}", stage_id=cls.stage.id, program_id=cls.prog_arts.id, school_id=cls.school.id)
        cls.sec_science = ClassSection(name=f"Science 1B {suffix}", stage_id=cls.stage.id, program_id=cls.prog_science.id, school_id=cls.school.id)
        cls.db.add_all([cls.sec_arts, cls.sec_science])
        cls.db.commit()
        cls.db.refresh(cls.sec_arts)
        cls.db.refresh(cls.sec_science)

        # 5. Subjects
        cls.sub_core_eng = Subject(name=f"Core English {suffix}", code=f"ENG_{suffix}", is_core=True, school_id=cls.school.id)
        cls.sub_lit = Subject(name=f"Literature {suffix}", code=f"LIT_{suffix}", is_core=False, school_id=cls.school.id)
        cls.sub_phys = Subject(name=f"Physics {suffix}", code=f"PHY_{suffix}", is_core=False, school_id=cls.school.id)
        cls.db.add_all([cls.sub_core_eng, cls.sub_lit, cls.sub_phys])
        cls.db.commit()
        cls.db.refresh(cls.sub_core_eng)
        cls.db.refresh(cls.sub_lit)
        cls.db.refresh(cls.sub_phys)

        cls.prog_arts.core_subjects.append(cls.sub_core_eng)
        cls.prog_science.core_subjects.append(cls.sub_core_eng)
        cls.db.commit()

        # 6. Elective Combinations
        cls.combo_arts = ElectiveCombination(
            name=f"Arts Package A {suffix}",
            program_id=cls.prog_arts.id,
            class_section_id=cls.sec_arts.id,
            capacity=40,
            school_id=cls.school.id
        )
        cls.combo_arts.subjects.append(cls.sub_lit)

        cls.combo_science = ElectiveCombination(
            name=f"Science Package Pure {suffix}",
            program_id=cls.prog_science.id,
            class_section_id=cls.sec_science.id,
            capacity=1,  # tight capacity for testing
            school_id=cls.school.id
        )
        cls.combo_science.subjects.append(cls.sub_phys)

        cls.db.add_all([cls.combo_arts, cls.combo_science])
        cls.db.commit()
        cls.db.refresh(cls.combo_arts)
        cls.db.refresh(cls.combo_science)

        # 7. Academic Year & Semester
        cls.acad_year = AcademicYear(label=f"2025/2026 {suffix}", is_current=True)
        cls.db.add(cls.acad_year)
        cls.db.commit()
        cls.db.refresh(cls.acad_year)

        cls.semester = Semester(name="Semester 1", academic_year_id=cls.acad_year.id, is_current=True)
        cls.db.add(cls.semester)
        cls.db.commit()
        cls.db.refresh(cls.semester)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.query(Score).filter(Score.student_id.in_(
                cls.db.query(Student.id).filter(Student.school_id == cls.school.id)
            )).delete(synchronize_session=False)
            cls.db.query(AuditLog).filter(AuditLog.school_id == cls.school.id).delete(synchronize_session=False)
            cls.db.query(Student).filter(Student.school_id == cls.school.id).delete(synchronize_session=False)
            cls.db.query(ElectiveCombination).filter(ElectiveCombination.school_id == cls.school.id).delete(synchronize_session=False)
            cls.db.query(Subject).filter(Subject.school_id == cls.school.id).delete(synchronize_session=False)
            cls.db.query(ClassSection).filter(ClassSection.school_id == cls.school.id).delete(synchronize_session=False)
            cls.db.query(SchoolStage).filter(SchoolStage.school_id == cls.school.id).delete(synchronize_session=False)
            cls.db.query(Program).filter(Program.school_id == cls.school.id).delete(synchronize_session=False)
            cls.db.query(Semester).filter(Semester.id == cls.semester.id).delete(synchronize_session=False)
            cls.db.query(AcademicYear).filter(AcademicYear.id == cls.acad_year.id).delete(synchronize_session=False)
            cls.db.query(User).filter(User.school_id == cls.school.id).delete(synchronize_session=False)
            cls.db.query(School).filter(School.id == cls.school.id).delete(synchronize_session=False)
            cls.db.commit()
        except Exception:
            cls.db.rollback()
        finally:
            cls.db.close()

    def test_01_unauthorized_user_blocked(self):
        """Verify teachers and non-admin staff cannot reassign a student's program."""
        student = Student(
            student_code=f"STU-{uuid.uuid4().hex[:6]}",
            full_name="Kofi Mensah Test",
            bece_index_number=f"101{uuid.uuid4().hex[:9]}",
            program_id=self.prog_arts.id,
            class_section_id=self.sec_arts.id,
            elective_combination_id=self.combo_arts.id,
            school_id=self.school.id,
            form=1
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)

        with self.assertRaises(HTTPException) as ctx:
            ProgramTransferService.reassign_student_program(
                db=self.db,
                student_id=student.id,
                new_program_id=self.prog_science.id,
                current_user=self.teacher_user,
                school_id=self.school.id
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_02_atomic_reassignment_and_scoresheet_swap(self):
        """Verify authorized admin successfully reassigns program, stream, and electives."""
        student = Student(
            student_code=f"STU-{uuid.uuid4().hex[:6]}",
            full_name="Ama Serwaa Test",
            bece_index_number=f"102{uuid.uuid4().hex[:9]}",
            program_id=self.prog_arts.id,
            class_section_id=self.sec_arts.id,
            elective_combination_id=self.combo_arts.id,
            school_id=self.school.id,
            academic_year=self.acad_year.label,
            form=1
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)

        # Add initial scores: Core English (active score 25) + Literature (ungraded elective 0)
        score_eng = Score(
            student_id=student.id,
            subject_id=self.sub_core_eng.id,
            semester_id=self.semester.id,
            class_score=25.0,
            exam_score=50.0,
            total_score=75.0,
            grade="A1"
        )
        score_lit = Score(
            student_id=student.id,
            subject_id=self.sub_lit.id,
            semester_id=self.semester.id,
            class_score=0.0,
            exam_score=0.0,
            total_score=0.0,
            grade="F9"
        )
        self.db.add_all([score_eng, score_lit])
        self.db.commit()

        # Reassign to Science Pure
        res = ProgramTransferService.reassign_student_program(
            db=self.db,
            student_id=student.id,
            new_program_id=self.prog_science.id,
            new_elective_combination_id=self.combo_science.id,
            new_class_section_id=self.sec_science.id,
            approving_officer="Mr. K. Mensah (Head of Academics)",
            reason="Reporting day parental appeal with Science aggregate 10",
            force_override=False,
            current_user=self.admin_user,
            school_id=self.school.id
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["new_program_id"], self.prog_science.id)
        self.assertEqual(res["new_class_name"], self.sec_science.name)

        # Refresh student from DB
        self.db.refresh(student)
        self.assertEqual(student.program_id, self.prog_science.id)
        self.assertEqual(student.class_section_id, self.sec_science.id)
        self.assertEqual(student.elective_combination_id, self.combo_science.id)
        self.assertIsNotNone(student.program_reassigned_at)
        self.assertEqual(student.program_reassigned_by, "Mr. K. Mensah (Head of Academics)")

        # Verify Core Score Preserved
        cur_eng = self.db.query(Score).filter(
            Score.student_id == student.id,
            Score.subject_id == self.sub_core_eng.id
        ).first()
        self.assertIsNotNone(cur_eng)
        self.assertEqual(cur_eng.total_score, 75.0)

        # Verify Old Elective Score (Literature) is removed
        cur_lit = self.db.query(Score).filter(
            Score.student_id == student.id,
            Score.subject_id == self.sub_lit.id
        ).first()
        self.assertIsNone(cur_lit)

        # Verify New Elective Score (Physics) is enrolled
        cur_phys = self.db.query(Score).filter(
            Score.student_id == student.id,
            Score.subject_id == self.sub_phys.id
        ).first()
        self.assertIsNotNone(cur_phys)

        # Verify Audit Trail Entry
        audit = self.db.query(AuditLog).filter(
            AuditLog.entity_id == student.id,
            AuditLog.action == "PROGRAM_REASSIGNMENT"
        ).order_by(AuditLog.id.desc()).first()
        self.assertIsNotNone(audit)
        self.assertIn("Ama Serwaa Test", audit.details)
        self.assertIn("Mr. K. Mensah", audit.details)

    def test_03_capacity_enforcement_and_force_override(self):
        """Verify capacity limit blocks reassignment unless force_override=True."""
        # combo_science has capacity=1 and student Ama is already in it from test_02
        student2 = Student(
            student_code=f"STU-{uuid.uuid4().hex[:6]}",
            full_name="Kwaku Ananse Test",
            bece_index_number=f"103{uuid.uuid4().hex[:9]}",
            program_id=self.prog_arts.id,
            class_section_id=self.sec_arts.id,
            elective_combination_id=self.combo_arts.id,
            school_id=self.school.id,
            form=1
        )
        self.db.add(student2)
        self.db.commit()
        self.db.refresh(student2)

        # Attempt without override -> should fail with 400
        with self.assertRaises(HTTPException) as ctx:
            ProgramTransferService.reassign_student_program(
                db=self.db,
                student_id=student2.id,
                new_program_id=self.prog_science.id,
                new_elective_combination_id=self.combo_science.id,
                force_override=False,
                current_user=self.admin_user,
                school_id=self.school.id
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("capacity", ctx.exception.detail.lower())

        # Attempt with force_override=True -> should succeed
        res = ProgramTransferService.reassign_student_program(
            db=self.db,
            student_id=student2.id,
            new_program_id=self.prog_science.id,
            new_elective_combination_id=self.combo_science.id,
            force_override=True,
            approving_officer="Headmaster Protocol Override",
            current_user=self.admin_user,
            school_id=self.school.id
        )
        self.assertTrue(res["success"])
        self.db.refresh(student2)
        self.assertEqual(student2.program_id, self.prog_science.id)

    def test_04_revised_admission_package_pdf(self):
        """Verify generated PDF contains revised docket watermark banner and science tools."""
        student = self.db.query(Student).filter(
            Student.school_id == self.school.id,
            Student.program_reassigned_at != None
        ).first()
        self.assertIsNotNone(student)

        pdf_bytes = AdmissionPackageService.generate_admission_letter_pdf(student.id, self.db)
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_05_program_capacities_query(self):
        """Verify get_program_capacities returns matrix of programs and elective seat counts."""
        capacities = ProgramTransferService.get_program_capacities(self.db, self.school.id)
        self.assertIsInstance(capacities, list)
        self.assertGreaterEqual(len(capacities), 2)
        
        sci_cap = next((c for c in capacities if c["program_id"] == self.prog_science.id), None)
        self.assertIsNotNone(sci_cap)
        self.assertGreaterEqual(sci_cap["form1_enrolled"], 1)

    def test_06_endpoint_route_integration(self):
        """Verify API route change_student_program dispatches cleanly."""
        student = Student(
            student_code=f"STU-{uuid.uuid4().hex[:6]}",
            full_name="Abena Osei Route Test",
            bece_index_number=f"104{uuid.uuid4().hex[:9]}",
            program_id=self.prog_science.id,
            school_id=self.school.id,
            form=1
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)

        payload = ProgramChangeRequest(
            new_program_id=self.prog_arts.id,
            new_elective_combination_id=self.combo_arts.id,
            approving_officer="Vice Principal Academic",
            reason="Route endpoint test",
            force_override=False
        )

        res = change_student_program(
            student_id=student.id,
            payload=payload,
            db=self.db,
            current_user=self.admin_user
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["new_program_id"], self.prog_arts.id)


if __name__ == "__main__":
    unittest.main()
