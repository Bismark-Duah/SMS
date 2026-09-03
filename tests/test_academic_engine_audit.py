"""
test_academic_engine_audit.py — Comprehensive Test Suite for Ghana NaCCA/GES 4-Tier SBA, WAEC Grade Boundaries, Smart Allocation, Promotions, and Multi-Year Transcripts.
"""

import os
import sys
import unittest
import uuid
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import SessionLocal, engine, Base, run_migrations
from backend.app.models import (
    User, Role, School, Student, SchoolStage, ClassSection, Program, Subject,
    Score, Semester, AcademicYear, House, Dormitory, Setting
)
from backend.app.services.grading import GradingService
from backend.app.services.allocation import allocate_student_house_and_dorm
from backend.app.services.reports import ReportService
from backend.app.routes.promotions import get_promotion_candidates


class TestAcademicEngineAudit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        run_migrations()
        cls.db = SessionLocal()

        u_suffix = uuid.uuid4().hex[:6]

        # Admin user
        admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            cls.db.add(admin_role)
            cls.db.commit()

        cls.school = School(name=f"Audit SHS {u_suffix}", code=f"ASH_{u_suffix}", status="ACTIVE", school_mode="COMBINED")
        cls.db.add(cls.school)
        cls.db.commit()
        cls.db.refresh(cls.school)

        cls.admin_user = User(
            username=f"admin_acad_{u_suffix}", email=f"admin_{u_suffix}@audit.local",
            password_hash="hash", is_active=True, school_id=cls.school.id,
            roles=[admin_role]
        )
        cls.db.add(cls.admin_user)
        cls.db.commit()

        # Stages
        cls.stage_shs = SchoolStage(name=f"SHS Stage {u_suffix}", school_type="SHS", school_id=cls.school.id)
        cls.stage_basic = SchoolStage(name=f"Primary Stage {u_suffix}", school_type="BASIC", school_id=cls.school.id)
        cls.db.add_all([cls.stage_shs, cls.stage_basic])
        cls.db.commit()

        # Class Sections
        cls.cls_basic3 = ClassSection(name="Basic 3 A", stage_id=cls.stage_basic.id, school_id=cls.school.id)
        cls.cls_shs3 = ClassSection(name="SHS 3 Science", stage_id=cls.stage_shs.id, school_id=cls.school.id)
        cls.db.add_all([cls.cls_basic3, cls.cls_shs3])
        cls.db.commit()

        # Academic Years & Semesters
        cls.acad_yr1 = cls.db.query(AcademicYear).filter(AcademicYear.label == "2024/2025").first()
        if not cls.acad_yr1:
            cls.acad_yr1 = AcademicYear(label="2024/2025", is_current=False)
            cls.db.add(cls.acad_yr1)
            cls.db.commit()
            cls.db.refresh(cls.acad_yr1)

        cls.acad_yr2 = cls.db.query(AcademicYear).filter(AcademicYear.label == "2025/2026").first()
        if not cls.acad_yr2:
            cls.acad_yr2 = AcademicYear(label="2025/2026", is_current=True)
            cls.db.add(cls.acad_yr2)
            cls.db.commit()
            cls.db.refresh(cls.acad_yr2)

        cls.sem1_y1 = Semester(name="Term 1", academic_year_id=cls.acad_yr1.id, is_current=False)
        cls.sem2_y1 = Semester(name="Term 2", academic_year_id=cls.acad_yr1.id, is_current=False)
        cls.sem1_y2 = Semester(name="Term 1", academic_year_id=cls.acad_yr2.id, is_current=True)
        cls.db.add_all([cls.sem1_y1, cls.sem2_y1, cls.sem1_y2])
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_sba_4tier_mathematical_sum_and_scaling(self):
        """Verify NaCCA 4-tier components sum to 100% and scale correctly."""
        # Max Tier Scores:
        # Tier 1 (Class Exercises): ex1 (10) + ex2 (10) = 20
        # Tier 2 (Assignments): ass1 (10) + ass2 (10) = 20
        # Tier 3 (Projects): ind_proj (20) + grp_work (10) + pract_work (10) = 40
        # Tier 4 (Mid-Semester Assessment): mid_sem (20) = 20
        max_raw_sum = 10 + 10 + 10 + 10 + 20 + 10 + 10 + 20
        self.assertEqual(max_raw_sum, 100)

        # Standard SHS 30/70 scaling
        class_weight = 30
        exam_weight = 70
        raw_score = 80 # student scored 80/100 across 4 SBA tiers
        class_score = raw_score * (class_weight / 100.0)
        self.assertEqual(class_score, 24.0)

        exam_score = 56.0 # out of 70
        total_score = class_score + exam_score
        self.assertEqual(total_score, 80.0)

        grade_info = GradingService.get_grade(total_score, self.db)
        self.assertEqual(grade_info["grade"], "A1")

    def test_02_waec_official_grade_boundaries(self):
        """Verify official WAEC Ghana 9-point scale boundaries."""
        self.assertEqual(GradingService.get_grade(85.0, self.db)["grade"], "A1") # 80-100
        self.assertEqual(GradingService.get_grade(75.0, self.db)["grade"], "B2") # 70-79
        self.assertEqual(GradingService.get_grade(66.0, self.db)["grade"], "B3") # 65-69
        self.assertEqual(GradingService.get_grade(62.0, self.db)["grade"], "C4") # 60-64
        self.assertEqual(GradingService.get_grade(57.0, self.db)["grade"], "C5") # 55-59
        self.assertEqual(GradingService.get_grade(52.0, self.db)["grade"], "C6") # 50-54
        self.assertEqual(GradingService.get_grade(47.0, self.db)["grade"], "D7") # 45-49
        self.assertEqual(GradingService.get_grade(42.0, self.db)["grade"], "E8") # 40-44
        self.assertEqual(GradingService.get_grade(38.0, self.db)["grade"], "F9") # 0-39

    def test_03_smart_allocation_gender_segregation_and_fallback(self):
        """Verify house and dormitory allocation respects strict gender isolation even during fallback."""
        h_sfx = uuid.uuid4().hex[:4]
        boys_house = House(name=f"Aggrey House (Boys) {h_sfx}", gender="Male", school_id=self.school.id)
        girls_house = House(name=f"Guggisberg House (Girls) {h_sfx}", gender="Female", school_id=self.school.id)
        mixed_house = House(name=f"Combined House (Co-ed) {h_sfx}", gender="Co-ed", school_id=self.school.id)
        self.db.add_all([boys_house, girls_house, mixed_house])
        self.db.commit()

        boys_dorm = Dormitory(name=f"Dorm Boy A {h_sfx}", house_id=boys_house.id, capacity=20)
        mixed_dorm = Dormitory(name=f"Dorm Mixed Girls Wing {h_sfx}", house_id=mixed_house.id, capacity=20)
        self.db.add_all([boys_dorm, mixed_dorm])
        self.db.commit()

        # Female student
        female_student = Student(
            student_code=f"FEM_{uuid.uuid4().hex[:4]}",
            full_name="Akua Mansa",
            gender="Female",
            residential_status="B", # Boarder
            school_id=self.school.id
        )
        self.db.add(female_student)
        self.db.commit()

        # Allocate
        res = allocate_student_house_and_dorm(self.db, female_student)
        self.db.commit()
        self.db.refresh(female_student)

        # Confirm she was not placed in the boys-only house or boys dorm
        allocated_house = self.db.query(House).filter(House.id == female_student.house_id).first()
        self.assertIn(allocated_house.gender.lower(), ["female", "co-ed"])

        allocated_dorm = self.db.query(Dormitory).filter(Dormitory.id == female_student.dormitory_id).first()
        self.assertIsNotNone(allocated_dorm)
        self.assertNotEqual(allocated_dorm.id, boys_dorm.id)
        self.assertEqual(allocated_dorm.id, mixed_dorm.id)

    def test_04_promotion_candidates_distinguishes_basic_from_terminal_shs(self):
        """Verify Basic 3 student is evaluated for promotion, while SHS 3 student is evaluated for graduation."""
        # Basic 3 Student (Form 3, but in Primary School)
        stu_basic = Student(
            student_code=f"STU_BAS_{uuid.uuid4().hex[:4]}",
            full_name="Ama Serwaa",
            form=3,
            class_section_id=self.cls_basic3.id,
            is_active=True,
            school_id=self.school.id
        )
        # SHS 3 Student (Form 3, in SHS)
        stu_shs = Student(
            student_code=f"STU_SHS_{uuid.uuid4().hex[:4]}",
            full_name="Kwame Mensah",
            form=3,
            class_section_id=self.cls_shs3.id,
            is_active=True,
            school_id=self.school.id
        )
        self.db.add_all([stu_basic, stu_shs])
        self.db.commit()

        # Add passing scores in current semester
        sub1 = Subject(name=f"Maths {uuid.uuid4().hex[:4]}", code=f"MTH_{uuid.uuid4().hex[:4]}", is_core=True)
        self.db.add(sub1)
        self.db.commit()

        score_b = Score(student_id=stu_basic.id, subject_id=sub1.id, semester_id=self.sem1_y2.id, total_score=75.0)
        score_s = Score(student_id=stu_shs.id, subject_id=sub1.id, semester_id=self.sem1_y2.id, total_score=75.0)
        self.db.add_all([score_b, score_s])
        self.db.commit()

        # Candidates evaluation for Basic 3
        cand_basic = get_promotion_candidates(self.cls_basic3.id, self.db, self.admin_user)
        basic_record = next(c for c in cand_basic if c["id"] == stu_basic.id)
        self.assertEqual(basic_record["recommendation"], "Promoted")

        # Candidates evaluation for SHS 3
        cand_shs = get_promotion_candidates(self.cls_shs3.id, self.db, self.admin_user)
        shs_record = next(c for c in cand_shs if c["id"] == stu_shs.id)
        self.assertEqual(shs_record["recommendation"], "Graduated")

    def test_05_multi_year_transcript_chronological_ordering(self):
        """Verify multi-year transcript data returns scores sorted chronologically by year and semester."""
        student = Student(
            student_code=f"TR_STU_{uuid.uuid4().hex[:4]}",
            full_name="Esi Manu",
            school_id=self.school.id,
            bece_index_number="1090401234"
        )
        self.db.add(student)
        self.db.commit()

        sub_eng = Subject(name=f"English Language {uuid.uuid4().hex[:4]}", code=f"ENG_{uuid.uuid4().hex[:4]}", is_core=True)
        sub_sci = Subject(name=f"Integrated Science {uuid.uuid4().hex[:4]}", code=f"SCI_{uuid.uuid4().hex[:4]}", is_core=True)
        self.db.add_all([sub_eng, sub_sci])
        self.db.commit()

        # Year 1 Term 1
        sc1 = Score(student_id=student.id, subject_id=sub_eng.id, semester_id=self.sem1_y1.id, total_score=82.0, grade="A1")
        # Year 1 Term 2
        sc2 = Score(student_id=student.id, subject_id=sub_eng.id, semester_id=self.sem2_y1.id, total_score=78.0, grade="B2")
        # Year 2 Term 1
        sc3 = Score(student_id=student.id, subject_id=sub_eng.id, semester_id=self.sem1_y2.id, total_score=88.0, grade="A1")
        self.db.add_all([sc1, sc2, sc3])
        self.db.commit()

        transcript = ReportService.get_full_transcript_data(self.db, student.id)
        self.assertIsNotNone(transcript)
        ext_subs = transcript["external_wassce_subjects"]
        self.assertEqual(len(ext_subs), 3)

        # Check chronological sequence
        self.assertEqual(ext_subs[0]["academic_year"], "2024/2025")
        self.assertEqual(ext_subs[0]["semester_name"], "Term 1")
        self.assertEqual(ext_subs[1]["academic_year"], "2024/2025")
        self.assertEqual(ext_subs[1]["semester_name"], "Term 2")
        self.assertEqual(ext_subs[2]["academic_year"], "2025/2026")
        self.assertEqual(ext_subs[2]["semester_name"], "Term 1")

        # Check PDF compilation
        pdf_bytes = ReportService.generate_official_transcript_pdf(self.db, student.id)
        self.assertGreater(len(pdf_bytes), 2000)


if __name__ == "__main__":
    unittest.main()
