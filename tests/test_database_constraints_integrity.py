"""
Tests for Prompt 11: Database Constraints, Foreign Key Integrity, and Cascades.
Verifies unique constraints, check constraints, and cascade delete integrity.
"""
import unittest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from backend.app.models import (
    Base, School, Student, User, Subject, Semester, AcademicYear,
    Score, Fee, Payment, Timetable, StudentSemesterSummary, Setting, ClassSection
)


class TestDatabaseConstraintsAndIntegrity(unittest.TestCase):
    def setUp(self):
        # Create an in-memory SQLite engine with PRAGMA foreign_keys=ON
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed minimal fixtures
        self.school = School(name="Test School", code="TS001")
        self.db.add(self.school)
        self.db.commit()

        self.student = Student(
            student_code="STU001",
            full_name="John Doe",
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

        self.subject = Subject(name="Core Mathematics", code="MTH01", school_id=self.school.id)
        self.db.add(self.subject)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        from sqlalchemy import text
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF;"))
            conn.commit()
        Base.metadata.drop_all(self.engine)

    def test_score_unique_constraint_rejects_duplicate(self):
        """Duplicate scores for the same (student_id, subject_id, semester_id) must raise IntegrityError."""
        score1 = Score(
            student_id=self.student.id,
            subject_id=self.subject.id,
            semester_id=self.semester.id,
            class_score=30.0,
            exam_score=50.0,
            total_score=80.0
        )
        self.db.add(score1)
        self.db.commit()

        score2 = Score(
            student_id=self.student.id,
            subject_id=self.subject.id,
            semester_id=self.semester.id,
            class_score=25.0,
            exam_score=60.0,
            total_score=85.0
        )
        self.db.add(score2)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_score_check_constraints_reject_out_of_range(self):
        """Negative scores or scores > 100 must be rejected by check constraints."""
        invalid_score_negative = Score(
            student_id=self.student.id,
            subject_id=self.subject.id,
            semester_id=self.semester.id,
            total_score=-5.0
        )
        self.db.add(invalid_score_negative)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

        invalid_score_high = Score(
            student_id=self.student.id,
            subject_id=self.subject.id,
            semester_id=self.semester.id,
            total_score=150.0
        )
        self.db.add(invalid_score_high)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_fee_check_constraint_rejects_negative_amount(self):
        """Fees with negative amount must be rejected by check constraint."""
        invalid_fee = Fee(
            student_id=self.student.id,
            fee_type="Tuition",
            amount=-100.0
        )
        self.db.add(invalid_fee)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_payment_check_constraint_rejects_zero_or_negative(self):
        """Payment amount <= 0 must be rejected by check constraint."""
        fee = Fee(
            student_id=self.student.id,
            fee_type="Tuition",
            amount=500.0
        )
        self.db.add(fee)
        self.db.commit()

        invalid_payment = Payment(
            fee_id=fee.id,
            amount_paid=0.0
        )
        self.db.add(invalid_payment)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_student_semester_summary_unique_constraint(self):
        """Duplicate summaries for the same (student_id, semester_id) must be rejected."""
        sum1 = StudentSemesterSummary(
            student_id=self.student.id,
            semester_id=self.semester.id,
            attitude="Excellent"
        )
        self.db.add(sum1)
        self.db.commit()

        sum2 = StudentSemesterSummary(
            student_id=self.student.id,
            semester_id=self.semester.id,
            attitude="Good"
        )
        self.db.add(sum2)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_cascade_delete_student_removes_dependent_records(self):
        """Deleting a student must cascade-delete scores, fees, and payments without orphan records."""
        fee = Fee(
            student_id=self.student.id,
            fee_type="Tuition",
            amount=500.0
        )
        self.db.add(fee)
        self.db.commit()

        payment = Payment(
            fee_id=fee.id,
            amount_paid=250.0
        )
        self.db.add(payment)

        score = Score(
            student_id=self.student.id,
            subject_id=self.subject.id,
            semester_id=self.semester.id,
            total_score=75.0
        )
        self.db.add(score)
        self.db.commit()

        # Delete student
        self.db.delete(self.student)
        self.db.commit()

        # Verify child records were cascaded
        self.assertEqual(self.db.query(Score).count(), 0)
        self.assertEqual(self.db.query(Fee).count(), 0)
        self.assertEqual(self.db.query(Payment).count(), 0)


if __name__ == "__main__":
    unittest.main()
