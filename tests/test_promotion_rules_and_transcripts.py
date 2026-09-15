"""
Tests for Prompt 14: Promotion Rules, Academic Transcripts, and Graduation Integrity.
Verifies tenant isolation, idempotency, parent scoping, and audit tracking.
"""
import unittest
from unittest.mock import MagicMock
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models import (
    Base, School, SchoolStage, Student, User, Role, ClassSection, AuditLog
)
from backend.app.routes.promotions import (
    promote_students, graduate_students, PromoteRequest, GraduateRequest
)
from backend.app.routes.reports import get_waec_transcript_by_index


class TestPromotionRulesAndTranscripts(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed roles
        self.admin_role = Role(name="admin")
        self.parent_role = Role(name="parent")
        self.db.add_all([self.admin_role, self.parent_role])
        self.db.commit()

        # Seed Schools
        self.school_a = School(name="School Alpha", code="SCH_A")
        self.school_b = School(name="School Beta", code="SCH_B")
        self.db.add_all([self.school_a, self.school_b])
        self.db.commit()

        # Seed School Stage
        self.stage = SchoolStage(name="SHS", school_type="SHS", school_id=self.school_a.id)
        self.db.add(self.stage)
        self.db.commit()

        # Seed Users
        self.admin_a = User(
            username="admin_a",
            password_hash="hash",
            school_id=self.school_a.id,
            is_active=True
        )
        self.admin_a.roles.append(self.admin_role)

        self.parent_a = User(
            username="parent_a",
            password_hash="hash",
            school_id=self.school_a.id,
            is_active=True
        )
        self.parent_a.roles.append(self.parent_role)

        self.db.add_all([self.admin_a, self.parent_a])
        self.db.commit()

        # Seed Classes for School A
        self.class_form1 = ClassSection(name="SHS 1A", stage_id=self.stage.id, school_id=self.school_a.id)
        self.class_form2 = ClassSection(name="SHS 2A", stage_id=self.stage.id, school_id=self.school_a.id)
        self.db.add_all([self.class_form1, self.class_form2])
        self.db.commit()

        # Seed Students
        self.student_a = Student(
            student_code="STU_A1",
            bece_index_number="1000000001",
            full_name="Alice Alpha",
            school_id=self.school_a.id,
            class_section_id=self.class_form1.id,
            form=1,
            is_active=True,
            parent_id=self.parent_a.id
        )
        self.student_b = Student(
            student_code="STU_B1",
            bece_index_number="2000000002",
            full_name="Bob Beta",
            school_id=self.school_b.id,
            form=1,
            is_active=True
        )
        self.db.add_all([self.student_a, self.student_b])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_cross_tenant_promotion_prevented(self):
        """Admin of School A cannot promote students belonging to School B."""
        req = PromoteRequest(
            student_ids=[self.student_b.id],
            target_class_section_id=self.class_form2.id,
            increment_form=True
        )
        with self.assertRaises(HTTPException) as ctx:
            promote_students(req, self.db, self.admin_a)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("No students found", ctx.exception.detail)

    def test_promotion_idempotency(self):
        """Promoting a student updates class and form; re-running does not double-increment form."""
        req = PromoteRequest(
            student_ids=[self.student_a.id],
            target_class_section_id=self.class_form2.id,
            increment_form=True
        )
        # First promotion
        res1 = promote_students(req, self.db, self.admin_a)
        self.assertIn("Successfully promoted", res1["message"])
        self.db.refresh(self.student_a)
        self.assertEqual(self.student_a.form, 2)
        self.assertEqual(self.student_a.class_section_id, self.class_form2.id)

        # Re-run promotion to same class section (should not increment form to 3)
        res2 = promote_students(req, self.db, self.admin_a)
        self.db.refresh(self.student_a)
        self.assertEqual(self.student_a.form, 2)
        self.assertEqual(self.student_a.class_section_id, self.class_form2.id)

    def test_cross_tenant_graduation_prevented(self):
        """Admin of School A cannot graduate students belonging to School B."""
        req = GraduateRequest(student_ids=[self.student_b.id])
        with self.assertRaises(HTTPException) as ctx:
            graduate_students(req, self.db, self.admin_a)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("No students found", ctx.exception.detail)

    def test_successful_graduation_sets_status_and_audit(self):
        """Graduation unlinks class section, sets status GRADUATED, and creates audit log."""
        req = GraduateRequest(student_ids=[self.student_a.id])
        res = graduate_students(req, self.db, self.admin_a)
        self.assertIn("Successfully graduated", res["message"])

        self.db.refresh(self.student_a)
        self.assertIsNone(self.student_a.class_section_id)
        self.assertFalse(self.student_a.is_active)
        self.assertEqual(self.student_a.status, "GRADUATED")

        # Verify audit log was created
        audit = self.db.query(AuditLog).filter(AuditLog.action == "STUDENTS_GRADUATED").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.school_id, self.school_a.id)

    def test_cross_tenant_transcript_lookup_prevented(self):
        """User from School A cannot access transcript for School B student by index."""
        with self.assertRaises(HTTPException) as ctx:
            get_waec_transcript_by_index("2000000002", self.db, self.admin_a)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_parent_cannot_view_non_ward_transcript(self):
        """Parent user cannot access transcript for another student even within same school."""
        # Create another student in School A not linked to parent_a
        student_other = Student(
            student_code="STU_OTHER",
            bece_index_number="1000000099",
            full_name="Other Student",
            school_id=self.school_a.id,
            parent_id=999999
        )
        self.db.add(student_other)
        self.db.commit()

        with self.assertRaises(HTTPException) as ctx:
            get_waec_transcript_by_index("1000000099", self.db, self.parent_a)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("registered ward", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
