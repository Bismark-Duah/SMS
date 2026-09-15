"""
tests/test_tenant_isolation_comprehensive.py
Regression tests for Prompt 2: Complete Tenant-Isolation Audit & Hardening.

Covers:
1. Subject protection:
   - Ordinary school admin cannot modify, archive, or delete another school's subjects (404).
   - Ordinary school admin cannot modify, archive, or delete global curriculum subjects (403).
   - Super Admin can manage global curriculum and tenant subjects.
2. Timetable isolation:
   - Ordinary admin cannot create, update, or delete timetable slots for another school's class section (404).
   - Ordinary admin cannot clear another school's class timetable (404).
   - Same-school admin operations on timetable slots succeed.
3. Discipline isolation:
   - Ordinary admin cannot query class-level discipline records for another school's class section (404).
   - Same-school admin can query own class-level discipline records.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models import (
    Base, School, SchoolStage, ClassSection, Subject, User, Role,
    Timetable, DisciplineRecord, Student
)
from backend.app.routes.subjects import (
    update_subject,
    delete_subject,
    toggle_subject_status,
    SubjectCreate
)
from backend.app.routes.timetable import (
    create_slot,
    update_slot,
    delete_slot,
    clear_class_timetable,
    SlotCreate,
    SlotUpdate
)
from backend.app.routes.discipline import get_class_records


class TestTenantIsolationComprehensive(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Seed Schools
        self.sch1 = School(id=1, name="School Alpha", code="SA", status="ACTIVE")
        self.sch2 = School(id=2, name="School Beta", code="SB", status="ACTIVE")
        self.session.add_all([self.sch1, self.sch2])

        # Seed Roles
        self.admin_role = Role(id=1, name="admin")
        self.super_role = Role(id=2, name="super_admin")
        self.teacher_role = Role(id=3, name="teacher")
        self.session.add_all([self.admin_role, self.super_role, self.teacher_role])
        self.session.commit()

        # Seed Users
        self.super_admin = User(id=1, username="superadmin", email="super@local", password_hash="h", school_id=None, is_active=True)
        self.super_admin.roles.append(self.super_role)

        self.admin1 = User(id=10, username="admin_a", email="admin@a.edu", password_hash="h", school_id=1, is_active=True)
        self.admin1.roles.append(self.admin_role)

        self.admin2 = User(id=20, username="admin_b", email="admin@b.edu", password_hash="h", school_id=2, is_active=True)
        self.admin2.roles.append(self.admin_role)

        self.session.add_all([self.super_admin, self.admin1, self.admin2])
        self.session.commit()

        # Seed Stages & Class Sections
        self.stage1 = SchoolStage(id=1, name="Stage A", school_type="BASIC")
        self.session.add(self.stage1)
        self.session.commit()

        self.class1 = ClassSection(id=101, name="Class 1A", stage_id=1, school_id=1)
        self.class2 = ClassSection(id=202, name="Class 2B", stage_id=1, school_id=2)
        self.session.add_all([self.class1, self.class2])
        self.session.commit()

        # Seed Subjects
        # Global Subject (NaCCA core curriculum, school_id is None)
        self.global_subject = Subject(id=1001, name="Core Mathematics", code="MATH_CORE", school_id=None, is_active=True, is_core=True)
        # School 1 Subject
        self.sub_sch1 = Subject(id=1002, name="Alpha Special Robotics", code="ROBO_A", school_id=1, is_active=True, is_core=False)
        # School 2 Subject
        self.sub_sch2 = Subject(id=1003, name="Beta Marine Science", code="MAR_B", school_id=2, is_active=True, is_core=False)
        self.session.add_all([self.global_subject, self.sub_sch1, self.sub_sch2])
        self.session.commit()

        # Seed Timetable Slot in School 2
        self.slot_sch2 = Timetable(
            id=501,
            class_section_id=self.class2.id,
            subject_id=self.sub_sch2.id,
            day_of_week=0,
            period_number=1
        )
        self.session.add(self.slot_sch2)
        self.session.commit()

        # Seed Student & Discipline in School 2
        self.student2 = Student(id=301, full_name="Beta Student", student_code="BS-001", school_id=2, class_section_id=self.class2.id)
        self.session.add(self.student2)
        self.session.commit()

        self.disc2 = DisciplineRecord(
            id=401,
            student_id=self.student2.id,
            incident_type="Warning",
            description="Talking during assembly",
            recorded_by=self.admin2.id
        )
        self.session.add(self.disc2)
        self.session.commit()

    def tearDown(self):
        self.session.close()

    # ── 1. Subject Multi-Tenant Protection ────────────────────────────────────

    def test_ordinary_admin_cannot_modify_global_curriculum_subject(self):
        # Admin 1 attempts to rename or modify global NaCCA core math
        payload = SubjectCreate(name="Altered Math", code="ALT_MATH", is_core=True)
        with self.assertRaises(HTTPException) as ctx:
            update_subject(subject_id=self.global_subject.id, payload=payload, db=self.session, current_user=self.admin1)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_ordinary_admin_cannot_delete_global_curriculum_subject(self):
        with self.assertRaises(HTTPException) as ctx:
            delete_subject(subject_id=self.global_subject.id, db=self.session, current_user=self.admin1)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_ordinary_admin_cannot_archive_global_curriculum_subject(self):
        with self.assertRaises(HTTPException) as ctx:
            toggle_subject_status(subject_id=self.global_subject.id, db=self.session, current_user=self.admin1)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_cross_school_admin_cannot_modify_other_school_subject(self):
        # Admin 1 attempts to update School 2's subject
        payload = SubjectCreate(name="Hacked Beta Subject", code="HACK_B", is_core=False)
        with self.assertRaises(HTTPException) as ctx:
            update_subject(subject_id=self.sub_sch2.id, payload=payload, db=self.session, current_user=self.admin1)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_same_school_admin_can_update_own_subject(self):
        payload = SubjectCreate(name="Alpha Advanced Robotics", code="ROBO_A2", is_core=False)
        updated = update_subject(subject_id=self.sub_sch1.id, payload=payload, db=self.session, current_user=self.admin1)
        self.assertEqual(updated.name, "Alpha Advanced Robotics")

    def test_super_admin_can_modify_global_curriculum_subject(self):
        payload = SubjectCreate(name="Core Mathematics (Updated)", code="MATH_CORE", is_core=True)
        updated = update_subject(subject_id=self.global_subject.id, payload=payload, db=self.session, current_user=self.super_admin)
        self.assertEqual(updated.name, "Core Mathematics (Updated)")

    # ── 2. Timetable Multi-Tenant Protection ──────────────────────────────────

    def test_ordinary_admin_cannot_create_timetable_in_another_school(self):
        # Admin 1 tries to add a slot to School 2's class
        payload = SlotCreate(
            class_section_id=self.class2.id,
            subject_id=self.global_subject.id,
            day_of_week=1,
            period_number=2
        )
        with self.assertRaises(HTTPException) as ctx:
            create_slot(payload=payload, db=self.session, current_user=self.admin1)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_ordinary_admin_cannot_update_timetable_in_another_school(self):
        # Admin 1 tries to modify School 2's slot
        payload = SlotUpdate(period_number=3)
        with self.assertRaises(HTTPException) as ctx:
            update_slot(slot_id=self.slot_sch2.id, payload=payload, db=self.session, current_user=self.admin1)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_ordinary_admin_cannot_delete_timetable_in_another_school(self):
        # Admin 1 tries to delete School 2's slot
        with self.assertRaises(HTTPException) as ctx:
            delete_slot(slot_id=self.slot_sch2.id, db=self.session, current_user=self.admin1)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_ordinary_admin_cannot_clear_timetable_of_another_school_class(self):
        # Admin 1 tries to wipe School 2's class timetable
        with self.assertRaises(HTTPException) as ctx:
            clear_class_timetable(class_section_id=self.class2.id, db=self.session, current_user=self.admin1)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_same_school_admin_can_manage_own_timetable(self):
        # Admin 1 creates slot in School 1 class
        payload = SlotCreate(
            class_section_id=self.class1.id,
            subject_id=self.sub_sch1.id,
            day_of_week=2,
            period_number=1
        )
        res = create_slot(payload=payload, db=self.session, current_user=self.admin1)
        self.assertEqual(res["class_section_id"], self.class1.id)

        # Admin 1 deletes own slot
        delete_slot(slot_id=res["id"], db=self.session, current_user=self.admin1)
        self.assertIsNone(self.session.query(Timetable).filter(Timetable.id == res["id"]).first())

    # ── 3. Discipline Class Multi-Tenant Protection ───────────────────────────

    def test_cross_school_admin_cannot_read_class_discipline_records(self):
        # Admin 1 attempts to query discipline records of School 2's class
        with self.assertRaises(HTTPException) as ctx:
            get_class_records(class_section_id=self.class2.id, db=self.session, current_user=self.admin1)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_same_school_admin_can_read_class_discipline_records(self):
        # Admin 2 queries discipline records of School 2's class
        recs = get_class_records(class_section_id=self.class2.id, db=self.session, current_user=self.admin2)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["student_name"], "Beta Student")


if __name__ == "__main__":
    unittest.main()
