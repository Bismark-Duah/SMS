import unittest
import os
import sys
import uuid
from sqlalchemy import event, text, inspect
from sqlalchemy.orm import Session

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import engine, Base, SessionLocal, run_migrations
from backend.app.models import (
    School, User, Role, SchoolStage, ClassSection, Subject, Student,
    Score, Fee, Payment, Attendance, Timetable, AcademicYear, Semester, Setting
)
from backend.app.routes.students import list_students
from backend.app.routes.results import get_class_students_for_scoring, get_class_scores
from backend.app.routes.timetable import list_all_slots, get_class_timetable
from backend.app.services.reports import ReportService


class QueryCounter:
    """Context manager to count SQL queries executed via SQLAlchemy engine."""
    def __init__(self, engine):
        self.engine = engine
        self.count = 0

    def __enter__(self):
        self.count = 0
        event.listen(self.engine, "before_cursor_execute", self._callback)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        event.remove(self.engine, "before_cursor_execute", self._callback)

    def _callback(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1


class TestPerformanceAndScalability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_migrations()
        cls.db: Session = SessionLocal()
        cls.u_suffix = uuid.uuid4().hex[:6]

        # 1. School
        cls.school = School(name=f"Scalability High {cls.u_suffix}", code=f"SH_{cls.u_suffix}")
        cls.db.add(cls.school)
        cls.db.commit()
        cls.db.refresh(cls.school)

        # 2. Roles & Admin
        admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            cls.db.add(admin_role)
            cls.db.commit()

        cls.admin_user = User(
            username=f"admin_scale_{cls.u_suffix}",
            password_hash="fakehash",
            school_id=cls.school.id,
            roles=[admin_role]
        )
        cls.db.add(cls.admin_user)
        cls.db.commit()
        cls.db.refresh(cls.admin_user)

        # 3. Stage & ClassSection
        cls.stage = SchoolStage(name=f"SHS Form 1 {cls.u_suffix}", school_type="SHS", school_id=cls.school.id)
        cls.db.add(cls.stage)
        cls.db.commit()
        cls.db.refresh(cls.stage)

        cls.section = ClassSection(name=f"1A {cls.u_suffix}", stage_id=cls.stage.id, school_id=cls.school.id)
        cls.db.add(cls.section)
        cls.db.commit()
        cls.db.refresh(cls.section)

        # 4. Academic Year & Semester
        cls.ay = AcademicYear(label=f"2026/2027 {cls.u_suffix}", is_current=True)
        cls.db.add(cls.ay)
        cls.db.commit()
        cls.db.refresh(cls.ay)

        cls.sem = Semester(name=f"Term 1 {cls.u_suffix}", academic_year_id=cls.ay.id, is_current=True)
        cls.db.add(cls.sem)
        cls.db.commit()
        cls.db.refresh(cls.sem)

        # 5. Subjects
        cls.subj1 = Subject(name=f"Core Mathematics {cls.u_suffix}", code=f"CMATH_{cls.u_suffix}", school_id=cls.school.id)
        cls.subj2 = Subject(name=f"Integrated Science {cls.u_suffix}", code=f"ISCI_{cls.u_suffix}", school_id=cls.school.id)
        cls.db.add_all([cls.subj1, cls.subj2])
        cls.db.commit()
        cls.db.refresh(cls.subj1)
        cls.db.refresh(cls.subj2)

        cls.section.subjects.extend([cls.subj1, cls.subj2])
        cls.db.commit()

        # 6. Seed 30 Students in the class with scores
        cls.students = []
        for i in range(30):
            st = Student(
                student_code=f"SCALE-{cls.u_suffix}-{i:03d}",
                full_name=f"Student Scale {i:03d}",
                class_section_id=cls.section.id,
                school_id=cls.school.id,
                residential_status="B" if i % 2 == 0 else "D",
                is_active=True
            )
            cls.students.append(st)
        cls.db.add_all(cls.students)
        cls.db.commit()

        for st in cls.students:
            cls.db.refresh(st)
            sc1 = Score(student_id=st.id, subject_id=cls.subj1.id, semester_id=cls.sem.id, class_score=25.0, exam_score=60.0, total_score=85.0, grade="A1")
            sc2 = Score(student_id=st.id, subject_id=cls.subj2.id, semester_id=cls.sem.id, class_score=20.0, exam_score=55.0, total_score=75.0, grade="B2")
            cls.db.add_all([sc1, sc2])
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.rollback()
        cls.db.close()

    def setUp(self):
        self.db.rollback()

    # ── Test 1: N+1 Elimination in Student Listing ────────────────────────────────
    def test_01_student_listing_eager_loading_query_budget(self):
        """Verify listing 30+ students executes within tight SQL query budget using joinedload."""
        with QueryCounter(engine) as qc:
            res = list_students(class_id=self.section.id, db=self.db, current_user=self.admin_user)
            self.assertEqual(len(res), 30)
            # Without joinedload, 30 students * 7 relations = 210+ queries.
            # With joinedload, this should be ≤ 5 queries total (including scope/mode lookups).
            self.assertLessEqual(qc.count, 6, f"Query count too high ({qc.count}); N+1 query regression detected!")

    # ── Test 2: Pagination Limit & Offset Support ─────────────────────────────────
    def test_02_student_listing_pagination_limits(self):
        """Verify backend limit and offset slice the database records correctly."""
        page_1 = list_students(class_id=self.section.id, limit=10, offset=0, db=self.db, current_user=self.admin_user)
        self.assertEqual(len(page_1), 10)

        page_2 = list_students(class_id=self.section.id, limit=10, offset=10, db=self.db, current_user=self.admin_user)
        self.assertEqual(len(page_2), 10)

        # Confirm non-overlapping IDs
        p1_ids = {s["id"] for s in page_1}
        p2_ids = {s["id"] for s in page_2}
        self.assertEqual(len(p1_ids.intersection(p2_ids)), 0, "Page 1 and Page 2 must not contain overlapping records")

    # ── Test 3: Batch Loading in Class Scoring Form ──────────────────────────────
    def test_03_class_students_for_scoring_batch_query(self):
        """Verify get_class_students_for_scoring executes in O(1) query budget without per-student loop queries."""
        with QueryCounter(engine) as qc:
            result = get_class_students_for_scoring(
                class_id=self.section.id,
                semester_id=self.sem.id,
                subject_id=self.subj1.id,
                db=self.db,
                current_user=self.admin_user
            )
            self.assertEqual(len(result), 30)
            for row in result:
                self.assertEqual(row["total_score"], 85.0)
                self.assertEqual(row["grade"], "A1")

            # Must be ≤ 8 queries total (students query + batched scores query)
            self.assertLessEqual(qc.count, 8, f"Bulk scoring query count ({qc.count}) indicates per-student loop queries!")

    # ── Test 4: Broadsheet PDF Batch Querying ─────────────────────────────────────
    def test_04_broadsheet_pdf_batch_queries(self):
        """Verify generate_broadsheet_pdf executes with batch score loading and compiles valid PDF."""
        with QueryCounter(engine) as qc:
            pdf_bytes = ReportService.generate_broadsheet_pdf(self.db, self.section.id, self.sem.id)
            self.assertIsNotNone(pdf_bytes)
            self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
            # 30 students without batching = 30 * (1 + 2) = 90+ queries. With batching, should be ≤ 15 queries total.
            self.assertLessEqual(qc.count, 15, f"Broadsheet PDF query count ({qc.count}) indicates N+1 score queries!")

    # ── Test 5: Broadsheet CSV Export Batch Querying ──────────────────────────────
    def test_05_broadsheet_csv_batch_queries(self):
        """Verify generate_broadsheet_csv executes with batched queries."""
        with QueryCounter(engine) as qc:
            csv_str = ReportService.generate_broadsheet_csv(self.db, self.section.id, self.sem.id)
            self.assertIsNotNone(csv_str)
            self.assertIn("CLASS BROADSHEET MATRIX", csv_str)
            self.assertIn("Student Scale 000", csv_str)
            self.assertLessEqual(qc.count, 15, f"Broadsheet CSV query count ({qc.count}) indicates unbatched score queries!")

    # ── Test 6: Timetable Slot Queries with Eager Loading ─────────────────────────
    def test_06_timetable_eager_loading(self):
        """Verify timetable listing uses eager joinedload for class, subject, and teacher."""
        tt1 = Timetable(class_section_id=self.section.id, subject_id=self.subj1.id, teacher_id=self.admin_user.id, semester_id=self.sem.id, day_of_week=0, period_number=1)
        tt2 = Timetable(class_section_id=self.section.id, subject_id=self.subj2.id, teacher_id=self.admin_user.id, semester_id=self.sem.id, day_of_week=0, period_number=2)
        self.db.add_all([tt1, tt2])
        self.db.commit()

        with QueryCounter(engine) as qc:
            slots = get_class_timetable(class_section_id=self.section.id, semester_id=self.sem.id, db=self.db, current_user=self.admin_user)
            self.assertGreaterEqual(len(slots), 2)
            self.assertLessEqual(qc.count, 7, f"Timetable query count ({qc.count}) indicates N+1 lazy relationship loading!")

    # ── Test 7: Verify Required Performance Indexes in SQLite ─────────────────────
    def test_07_database_performance_indexes_exist(self):
        """Verify all critical composite and foreign key indexes exist in SQLite schema."""
        inspector = inspect(engine)
        
        # Check scores table indexes
        score_indexes = {idx["name"] for idx in inspector.get_indexes("scores") if idx["name"]}
        self.assertIn("ix_scores_student_subject_sem", score_indexes, "Missing composite index on scores(student_id, subject_id, semester_id)")

        # Check fees table indexes
        fee_indexes = {idx["name"] for idx in inspector.get_indexes("fees") if idx["name"]}
        self.assertTrue(
            "ix_fees_student_id" in fee_indexes or "ix_fees_student_status" in fee_indexes,
            "Missing student_id index on fees table"
        )

        # Check payments table indexes
        payment_indexes = {idx["name"] for idx in inspector.get_indexes("payments") if idx["name"]}
        self.assertTrue(
            "ix_payments_fee_id" in payment_indexes or "ix_payments_fee_date" in payment_indexes,
            "Missing fee_id index on payments table"
        )

        # Check attendance table indexes
        attendance_indexes = {idx["name"] for idx in inspector.get_indexes("attendance") if idx["name"]}
        self.assertTrue(
            "ix_attendance_student_date" in attendance_indexes,
            "Missing student_id + date index on attendance table"
        )


if __name__ == "__main__":
    unittest.main()
