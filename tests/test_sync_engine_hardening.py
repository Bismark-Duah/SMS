import sys
import os
import uuid
import unittest
from datetime import datetime, timedelta

# Setup path resolution
current_dir = os.path.dirname(os.path.abspath(__file__))
sms_root = os.path.abspath(os.path.join(current_dir, ".."))
backend_dir = os.path.join(sms_root, "backend")

if sms_root not in sys.path:
    sys.path.insert(0, sms_root)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from backend.app.database import SessionLocal, Base, engine
from backend.app.models import User, Role, School, Student, Score, Subject, Semester, Fee
from backend.app.services.sync_engine import (
    apply_sync_bundle,
    compute_payload_checksum
)


class TestSyncEngineHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()
        cls.u_suffix = uuid.uuid4().hex[:6]

        # Setup test school
        cls.school = School(
            name=f"Hardened Sync Academy {cls.u_suffix}",
            code=f"HSA-{cls.u_suffix}",
            school_mode="COMBINED"
        )
        cls.db.add(cls.school)
        cls.db.commit()
        cls.db.refresh(cls.school)

        # Setup subject & semester
        cls.subject = cls.db.query(Subject).first()
        if not cls.subject:
            cls.subject = Subject(name="Core Mathematics", code=f"MATH-{cls.u_suffix}", is_core=True)
            cls.db.add(cls.subject)
            cls.db.commit()
            cls.db.refresh(cls.subject)

        cls.semester = cls.db.query(Semester).first()
        if not cls.semester:
            cls.semester = Semester(name="Term 1", is_current=True)
            cls.db.add(cls.semester)
            cls.db.commit()
            cls.db.refresh(cls.semester)

    @classmethod
    def tearDownClass(cls):
        cls.db.rollback()
        cls.db.close()

    def test_01_topological_dependency_sorting(self):
        """Verify child fee and score arrive BEFORE parent student, but topological sorting applies student first."""
        u = uuid.uuid4().hex[:6]
        student_code = f"ST-TOPO-{u}"

        fee_uuid = str(uuid.uuid4())
        fee_payload = {
            "student_code": student_code,
            "fee_type": "Tuition Fee",
            "amount": 1500.0,
            "amount_paid": 500.0,
            "status": "Partial"
        }

        student_uuid = str(uuid.uuid4())
        student_payload = {
            "student_code": student_code,
            "full_name": "Topological Order Student",
            "gender": "Female",
            "phone": "0245000000"
        }

        # Out-of-order bundle (Child fee placed before parent student)
        bundle = [
            {
                "sync_uuid": fee_uuid,
                "entity_type": "fee",
                "entity_id": f"fee_{u}",
                "action": "INSERT",
                "payload": fee_payload,
                "checksum": compute_payload_checksum(fee_payload)
            },
            {
                "sync_uuid": student_uuid,
                "entity_type": "student",
                "entity_id": f"stu_{u}",
                "action": "INSERT",
                "payload": student_payload,
                "checksum": compute_payload_checksum(student_payload)
            }
        ]

        applied, errors = apply_sync_bundle(self.db, self.school.id, bundle)
        self.assertEqual(len(errors), 0, f"Expected zero errors but got: {errors}")
        self.assertIn(fee_uuid, applied)
        self.assertIn(student_uuid, applied)

        # Verify student exists in DB
        st = self.db.query(Student).filter(Student.school_id == self.school.id, Student.student_code == student_code).first()
        self.assertIsNotNone(st)
        self.assertEqual(st.full_name, "Topological Order Student")

        # Verify fee exists in DB linked to student
        fee = self.db.query(Fee).filter(Fee.student_id == st.id).first()
        self.assertIsNotNone(fee)
        self.assertEqual(fee.amount, 1500.0)

    def test_02_missing_parent_rejection_no_silent_drop(self):
        """Verify child score without existing parent student raises explicit error and is NOT acknowledged."""
        missing_code = f"MISSING-STU-{uuid.uuid4().hex[:6]}"
        score_uuid = str(uuid.uuid4())
        score_payload = {
            "student_code": missing_code,
            "subject_id": self.subject.id,
            "semester_id": self.semester.id,
            "total_score": 85.0,
            "grade": "A1"
        }

        bundle = [
            {
                "sync_uuid": score_uuid,
                "entity_type": "score",
                "entity_id": "9999",
                "action": "INSERT",
                "payload": score_payload,
                "checksum": compute_payload_checksum(score_payload)
            }
        ]

        applied, errors = apply_sync_bundle(self.db, self.school.id, bundle)
        self.assertNotIn(score_uuid, applied)
        self.assertGreater(len(errors), 0)
        self.assertIn("Parent student", errors[0])

    def test_03_checksum_mismatch_rejection(self):
        """Verify payload tampered in-memory fails SHA-256 validation."""
        u = uuid.uuid4().hex[:6]
        stu_uuid = str(uuid.uuid4())
        valid_payload = {"student_code": f"ST-CHK-{u}", "full_name": "Valid Name"}
        tampered_payload = {"student_code": f"ST-CHK-{u}", "full_name": "Tampered In-Memory"}

        bundle = [
            {
                "sync_uuid": stu_uuid,
                "entity_type": "student",
                "entity_id": f"stu_{u}",
                "action": "INSERT",
                "payload": tampered_payload,
                "checksum": compute_payload_checksum(valid_payload)  # Checksum does not match tampered payload
            }
        ]

        applied, errors = apply_sync_bundle(self.db, self.school.id, bundle)
        self.assertNotIn(stu_uuid, applied)
        self.assertGreater(len(errors), 0)
        self.assertIn("Checksum mismatch", errors[0])

    def test_04_truthy_trap_field_clearing(self):
        """Verify setting an empty string clears the field rather than being skipped."""
        u = uuid.uuid4().hex[:6]
        student_code = f"ST-CLEAR-{u}"

        # 1. Create student with phone and address
        st = Student(
            student_code=student_code,
            full_name="Student To Clear",
            phone="0241112233",
            address="Initial Address",
            school_id=self.school.id
        )
        self.db.add(st)
        self.db.commit()
        self.db.refresh(st)

        # 2. Delta clearing phone and address to empty strings
        clear_uuid = str(uuid.uuid4())
        clear_payload = {
            "student_code": student_code,
            "phone": "",
            "address": ""
        }

        bundle = [
            {
                "sync_uuid": clear_uuid,
                "entity_type": "student",
                "entity_id": str(st.id),
                "action": "UPDATE",
                "payload": clear_payload,
                "checksum": compute_payload_checksum(clear_payload)
            }
        ]

        applied, errors = apply_sync_bundle(self.db, self.school.id, bundle)
        self.assertEqual(len(errors), 0)
        self.assertIn(clear_uuid, applied)

        self.db.refresh(st)
        self.assertEqual(st.phone, "")
        self.assertEqual(st.address, "")


if __name__ == "__main__":
    unittest.main()
