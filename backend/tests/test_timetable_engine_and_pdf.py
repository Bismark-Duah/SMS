"""
Automated Test Suite for Master Class & Teacher Timetable Engine with Collision Detection and Official PDF Dockets
Verifies timetable slot assignment, teacher double-booking prevention, room/science lab collision rejection,
official landscape A4 class weekly timetable PDF generation, and teacher weekly teaching schedule PDF docket.
"""
import sys
import os
import unittest
import uuid

# Setup path so tests can run standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.database import SessionLocal
from backend.app.models import (
    School, User, Role, ClassSection, SchoolStage, Subject, Timetable, Program
)
from backend.app.routes.timetable import (
    create_slot,
    update_slot,
    get_class_timetable,
    get_teacher_timetable,
    get_class_timetable_pdf,
    get_teacher_timetable_pdf,
    check_conflicts,
    SlotCreate,
    SlotUpdate
)
from fastapi import HTTPException


class TestTimetableEngineAndPdf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        u_suffix = uuid.uuid4().hex[:6]

        # 1. Schools
        cls.school = School(
            name=f"Achimota School {u_suffix}",
            code=f"ACH-{u_suffix}",
            school_mode="SHS_ONLY"
        )
        cls.db.add(cls.school)
        cls.db.commit()
        cls.db.refresh(cls.school)

        cls.other_school = School(
            name=f"Wesley Girls' High School {u_suffix}",
            code=f"WGHS-{u_suffix}",
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

        cls.teacher_role = cls.db.query(Role).filter(Role.name == "teacher").first()
        if not cls.teacher_role:
            cls.teacher_role = Role(name="teacher")
            cls.db.add(cls.teacher_role)
            cls.db.commit()

        # 3. Users
        cls.admin_user = User(
            username=f"admin_tt_{u_suffix}",
            email=f"admin_tt_{u_suffix}@example.com",
            password_hash="mockhash",
            school_id=cls.school.id,
            roles=[cls.admin_role]
        )
        cls.teacher_mr_mensah = User(
            username=f"mr_mensah_{u_suffix}",
            email=f"mensah_{u_suffix}@example.com",
            password_hash="mockhash",
            school_id=cls.school.id,
            roles=[cls.teacher_role]
        )
        cls.teacher_madam_arhin = User(
            username=f"madam_arhin_{u_suffix}",
            email=f"arhin_{u_suffix}@example.com",
            password_hash="mockhash",
            school_id=cls.school.id,
            roles=[cls.teacher_role]
        )
        cls.db.add_all([cls.admin_user, cls.teacher_mr_mensah, cls.teacher_madam_arhin])
        cls.db.commit()
        cls.db.refresh(cls.admin_user)
        cls.db.refresh(cls.teacher_mr_mensah)
        cls.db.refresh(cls.teacher_madam_arhin)

        # 4. Programs, Classes & Stage
        cls.stage = SchoolStage(name=f"SHS 1 {u_suffix}", school_type="SHS")
        cls.db.add(cls.stage)
        cls.db.commit()
        cls.db.refresh(cls.stage)

        cls.prog1 = Program(name=f"General Arts {u_suffix}", school_id=cls.school.id)
        cls.prog2 = Program(name=f"General Science {u_suffix}", school_id=cls.other_school.id)
        cls.db.add_all([cls.prog1, cls.prog2])
        cls.db.commit()
        cls.db.refresh(cls.prog1)
        cls.db.refresh(cls.prog2)

        cls.class_1a = ClassSection(name=f"Science 1A {u_suffix}", stage_id=cls.stage.id, program_id=cls.prog1.id)
        cls.class_1b = ClassSection(name=f"Science 1B {u_suffix}", stage_id=cls.stage.id, program_id=cls.prog1.id)
        cls.class_1c = ClassSection(name=f"Science 1C {u_suffix}", stage_id=cls.stage.id, program_id=cls.prog1.id)
        cls.foreign_class = ClassSection(name=f"Foreign Class {u_suffix}", stage_id=cls.stage.id, program_id=cls.prog2.id)
        cls.db.add_all([cls.class_1a, cls.class_1b, cls.class_1c, cls.foreign_class])
        cls.db.commit()
        cls.db.refresh(cls.class_1a)
        cls.db.refresh(cls.class_1b)
        cls.db.refresh(cls.class_1c)
        cls.db.refresh(cls.foreign_class)

        cls.room_lab = f"Physics Lab {u_suffix}"
        cls.room_102 = f"Room 102 {u_suffix}"

        # 5. Subjects
        cls.sub_physics = Subject(name=f"Physics {u_suffix}", code=f"PHY-{u_suffix}", is_core=False, school_id=cls.school.id)
        cls.sub_chem = Subject(name=f"Chemistry {u_suffix}", code=f"CHE-{u_suffix}", is_core=False, school_id=cls.school.id)
        cls.db.add_all([cls.sub_physics, cls.sub_chem])
        cls.db.commit()
        cls.db.refresh(cls.sub_physics)
        cls.db.refresh(cls.sub_chem)

    @classmethod
    def tearDownClass(cls):
        cls.db.rollback()
        cls.db.close()

    def test_01_create_slot_success(self):
        """Verify admin can create a valid timetable slot."""
        payload = SlotCreate(
            class_section_id=self.class_1a.id,
            subject_id=self.sub_physics.id,
            teacher_id=self.teacher_mr_mensah.id,
            day_of_week=0, # Monday
            period_number=1,
            start_time="08:00",
            end_time="08:45",
            room=self.room_lab
        )
        res = create_slot(payload, db=self.db, current_user=self.admin_user)
        self.assertIsNotNone(res["id"])
        self.assertEqual(res["subject_name"], self.sub_physics.name)
        self.assertEqual(res["room"], self.room_lab)

    def test_02_teacher_double_booking_collision_rejection(self):
        """Verify system rejects assigning the same teacher to another class at the same day & period."""
        payload = SlotCreate(
            class_section_id=self.class_1b.id,
            subject_id=self.sub_physics.id,
            teacher_id=self.teacher_mr_mensah.id, # Clashes with Monday Period 1 in Science 1A
            day_of_week=0,
            period_number=1,
            start_time="08:00",
            end_time="08:45",
            room=self.room_102
        )
        with self.assertRaises(HTTPException) as cm:
            create_slot(payload, db=self.db, current_user=self.admin_user)
        self.assertEqual(cm.exception.status_code, 409)
        self.assertIn("already assigned to another class", cm.exception.detail)

    def test_03_room_lab_collision_rejection(self):
        """Verify system rejects assigning the same room/science lab to another class at the same day & period."""
        payload = SlotCreate(
            class_section_id=self.class_1c.id,
            subject_id=self.sub_chem.id,
            teacher_id=self.teacher_madam_arhin.id,
            day_of_week=0,
            period_number=1,
            start_time="08:00",
            end_time="08:45",
            room=self.room_lab # Clashes with Science 1A in Physics Lab
        )
        with self.assertRaises(HTTPException) as cm:
            create_slot(payload, db=self.db, current_user=self.admin_user)
        self.assertEqual(cm.exception.status_code, 409)
        self.assertIn("already allocated to", cm.exception.detail)


    def test_04_class_timetable_pdf_generation(self):
        """Verify generating official A4 landscape class weekly timetable PDF."""
        resp = get_class_timetable_pdf(self.class_1a.id, db=self.db, current_user=self.admin_user)
        self.assertEqual(resp.media_type, "application/pdf")
        self.assertTrue(resp.body.startswith(b"%PDF-"), "Class timetable must be a valid PDF binary")
        self.assertIn("Timetable_", resp.headers["Content-Disposition"])

    def test_05_teacher_schedule_pdf_generation(self):
        """Verify generating official A4 landscape teacher teaching schedule PDF."""
        resp = get_teacher_timetable_pdf(self.teacher_mr_mensah.id, db=self.db, current_user=self.admin_user)
        self.assertEqual(resp.media_type, "application/pdf")
        self.assertTrue(resp.body.startswith(b"%PDF-"), "Teacher schedule must be a valid PDF binary")
        self.assertIn("Teacher_Schedule_", resp.headers["Content-Disposition"])

    def test_06_conflict_detection_endpoint(self):
        """Verify admin can query conflicts."""
        conflicts = check_conflicts(db=self.db, current_user=self.admin_user)
        self.assertIsInstance(conflicts, list)

    def test_07_tenant_isolation_guards(self):
        """Verify cross-school class timetable cannot be accessed."""
        with self.assertRaises(HTTPException) as cm:
            get_class_timetable_pdf(self.foreign_class.id, db=self.db, current_user=self.admin_user)
        self.assertEqual(cm.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
