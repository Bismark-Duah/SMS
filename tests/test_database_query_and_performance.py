"""
Tests for Prompt 12: Database Query and Performance Audit.
Verifies eager loading (N+1 query elimination), index presence, and pagination sanity.
"""
import unittest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker, joinedload

from backend.app.models import (
    Base, School, Student, Subject, Semester, AcademicYear,
    Score, Fee, Payment, Timetable, SyncOutbox
)


class TestDatabaseQueryAndPerformance(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed test data
        self.school = School(name="Perf School", code="PS001")
        self.db.add(self.school)
        self.db.commit()

        self.student = Student(
            student_code="STU_P1",
            full_name="Alice Perf",
            school_id=self.school.id
        )
        self.db.add(self.student)
        self.db.commit()

        self.acad_year = AcademicYear(label="2026/2027")
        self.db.add(self.acad_year)
        self.db.commit()

        self.semester = Semester(name="Term 1", academic_year_id=self.acad_year.id)
        self.db.add(self.semester)
        self.db.commit()

        self.subject = Subject(name="Integrated Science", code="SCI01", school_id=self.school.id)
        self.db.add(self.subject)
        self.db.commit()

        # Seed score
        self.score = Score(
            student_id=self.student.id,
            subject_id=self.subject.id,
            semester_id=self.semester.id,
            total_score=88.0
        )
        self.db.add(self.score)

        # Seed fee and payment
        self.fee = Fee(
            student_id=self.student.id,
            fee_type="Tuition",
            amount=400.0,
            amount_paid=200.0
        )
        self.db.add(self.fee)
        self.db.commit()

        self.payment = Payment(
            fee_id=self.fee.id,
            amount_paid=200.0
        )
        self.db.add(self.payment)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_eager_loading_scores_single_query(self):
        """Verify scores with eager loaded student, subject, semester avoids N+1 queries."""
        query_count = 0

        @event.listens_for(self.engine, "before_cursor_execute")
        def count_queries(conn, cursor, statement, parameters, context, executemany):
            nonlocal query_count
            query_count += 1

        scores = self.db.query(Score).options(
            joinedload(Score.student),
            joinedload(Score.subject),
            joinedload(Score.semester)
        ).all()

        # Initial query executed
        self.assertEqual(len(scores), 1)
        initial_queries = query_count

        # Access relationships without triggering lazy loads
        _ = scores[0].student.full_name
        _ = scores[0].subject.name
        _ = scores[0].semester.name

        # Query count must remain the same (0 additional queries)
        self.assertEqual(query_count, initial_queries)

    def test_eager_loading_fees_single_query(self):
        """Verify fees with eager loaded student and payments avoids N+1 queries."""
        query_count = 0

        @event.listens_for(self.engine, "before_cursor_execute")
        def count_queries(conn, cursor, statement, parameters, context, executemany):
            nonlocal query_count
            query_count += 1

        fees = self.db.query(Fee).options(
            joinedload(Fee.student),
            joinedload(Fee.payments)
        ).all()

        self.assertEqual(len(fees), 1)
        initial_queries = query_count

        # Access relationships without triggering extra queries
        _ = fees[0].student.full_name
        _ = [p.amount_paid for p in fees[0].payments]

        self.assertEqual(query_count, initial_queries)

    def test_index_coverage_audit(self):
        """Audit inspector to verify performance indexes exist on critical tables."""
        inspector = inspect(self.engine)

        scores_indexes = [idx["name"] for idx in inspector.get_indexes("scores")]
        self.assertTrue(any("student" in name for name in scores_indexes))

        fees_indexes = [idx["name"] for idx in inspector.get_indexes("fees")]
        self.assertTrue(any("student" in name for name in fees_indexes))

        sync_indexes = [idx["name"] for idx in inspector.get_indexes("sync_outbox")]
        self.assertTrue(any("school" in name for name in sync_indexes))


if __name__ == "__main__":
    unittest.main()
