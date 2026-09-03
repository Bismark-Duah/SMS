import sys
import os
import uuid
import unittest
from datetime import datetime

# Setup path resolution
current_dir = os.path.dirname(os.path.abspath(__file__))
sms_root = os.path.abspath(os.path.join(current_dir, ".."))
backend_dir = os.path.join(sms_root, "backend")

if sms_root not in sys.path:
    sys.path.insert(0, sms_root)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from backend.app.database import SessionLocal, Base, engine
from backend.app.models import User, Role, School, SyncOutbox, Student
from backend.app.routes.sync import (
    get_super_admin_sync_overview,
    trigger_school_sync,
    trigger_all_schools_sync
)
from backend.app.services.sync_engine import log_sync_change
from fastapi import HTTPException


class TestSuperAdminSyncMonitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()
        u_suffix = uuid.uuid4().hex[:6]

        # 1. Create 2 test schools
        cls.school1 = School(
            name=f"Sync Test Academy 1 {u_suffix}",
            code=f"STA1-{u_suffix}",
            school_mode="COMBINED"
        )
        cls.school2 = School(
            name=f"Sync Test Academy 2 {u_suffix}",
            code=f"STA2-{u_suffix}",
            school_mode="SHS_ONLY"
        )
        cls.db.add_all([cls.school1, cls.school2])
        cls.db.commit()
        cls.db.refresh(cls.school1)
        cls.db.refresh(cls.school2)

        # 2. Roles
        cls.super_admin_role = cls.db.query(Role).filter(Role.name == "super_admin").first()
        if not cls.super_admin_role:
            cls.super_admin_role = Role(name="super_admin")
            cls.db.add(cls.super_admin_role)
            cls.db.commit()

        cls.teacher_role = cls.db.query(Role).filter(Role.name == "teacher").first()
        if not cls.teacher_role:
            cls.teacher_role = Role(name="teacher")
            cls.db.add(cls.teacher_role)
            cls.db.commit()

        # 3. Super admin user & normal teacher user
        cls.super_admin_user = User(
            username=f"super_{u_suffix}",
            email=f"super_{u_suffix}@example.com",
            password_hash="hash",
            roles=[cls.super_admin_role]
        )
        cls.teacher_user = User(
            username=f"teacher_{u_suffix}",
            email=f"teacher_{u_suffix}@example.com",
            password_hash="hash",
            school_id=cls.school1.id,
            roles=[cls.teacher_role]
        )
        cls.db.add_all([cls.super_admin_user, cls.teacher_user])
        cls.db.commit()
        cls.db.refresh(cls.super_admin_user)
        cls.db.refresh(cls.teacher_user)

    @classmethod
    def tearDownClass(cls):
        cls.db.rollback()
        cls.db.close()

    def test_01_role_guard_non_super_admin_forbidden(self):
        """Verify non-super-admins cannot access sync monitor overview or trigger syncs."""
        with self.assertRaises(HTTPException) as cm1:
            get_super_admin_sync_overview(db=self.db, current_user=self.teacher_user)
        self.assertEqual(cm1.exception.status_code, 403)

        with self.assertRaises(HTTPException) as cm2:
            trigger_school_sync(self.school1.id, db=self.db, current_user=self.teacher_user)
        self.assertEqual(cm2.exception.status_code, 403)

        with self.assertRaises(HTTPException) as cm3:
            trigger_all_schools_sync(db=self.db, current_user=self.teacher_user)
        self.assertEqual(cm3.exception.status_code, 403)

    def test_02_super_admin_telemetry_overview(self):
        """Verify super admin can retrieve real-time telemetry across all schools."""
        overview = get_super_admin_sync_overview(db=self.db, current_user=self.super_admin_user)
        self.assertEqual(overview["status"], "success")
        self.assertGreaterEqual(overview["total_schools"], 2)
        self.assertIn("schools", overview)

        sch1_telemetry = next((s for s in overview["schools"] if s["school_id"] == self.school1.id), None)
        self.assertIsNotNone(sch1_telemetry)
        self.assertEqual(sch1_telemetry["school_code"], self.school1.code)

    def test_03_outbox_queue_and_single_school_sync(self):
        """Verify queuing outbox entries updates pending_count and single-school trigger syncs them."""
        u = uuid.uuid4().hex[:6]
        # Queue 2 changes for school1
        entry1 = log_sync_change(self.db, self.school1.id, "student", f"101_{u}", "INSERT", {"student_code": f"ST-S1-{u}", "full_name": "Test Student 1"})
        entry2 = log_sync_change(self.db, self.school1.id, "setting", f"sett_{u}", "UPDATE", {"key": f"sett_{u}", "value": "Test Value"})
        self.db.commit()

        # Check telemetry reflects queued outbox deltas
        overview = get_super_admin_sync_overview(db=self.db, current_user=self.super_admin_user)
        sch1_telemetry = next(s for s in overview["schools"] if s["school_id"] == self.school1.id)
        self.assertGreaterEqual(sch1_telemetry["pending_count"], 2)
        self.assertEqual(sch1_telemetry["health_state"], "PENDING_SYNC")

        # Trigger single school sync
        res = trigger_school_sync(self.school1.id, db=self.db, current_user=self.super_admin_user)
        self.assertEqual(res["status"], "success")
        self.assertGreaterEqual(res["synced_count"], 2)

        # Refresh entries
        self.db.refresh(entry1)
        self.db.refresh(entry2)
        self.assertTrue(entry1.is_synced)
        self.assertTrue(entry2.is_synced)

        # Confirm queue is now 0 and state is HEALTHY
        overview_after = get_super_admin_sync_overview(db=self.db, current_user=self.super_admin_user)
        sch1_after = next(s for s in overview_after["schools"] if s["school_id"] == self.school1.id)
        self.assertEqual(sch1_after["pending_count"], 0)
        self.assertEqual(sch1_after["health_state"], "HEALTHY")

    def test_04_global_multi_school_trigger_sync(self):
        """Verify triggering global network sync synchronizes all pending schools in one atomic pass."""
        u = uuid.uuid4().hex[:6]
        # Queue deltas for both school1 and school2
        e1 = log_sync_change(self.db, self.school1.id, "setting", f"sch_name_{u}", "UPDATE", {"key": f"sch_name_{u}", "value": "Updated Academy 1"})
        e2 = log_sync_change(self.db, self.school2.id, "student", f"202_{u}", "INSERT", {"student_code": f"ST-S2-{u}", "full_name": "Test Student 2"})
        self.db.commit()

        # Global trigger
        res = trigger_all_schools_sync(db=self.db, current_user=self.super_admin_user)
        self.assertEqual(res["status"], "success")
        self.assertGreaterEqual(res["total_synced"], 2)

        self.db.refresh(e1)
        self.db.refresh(e2)
        self.assertTrue(e1.is_synced)
        self.assertTrue(e2.is_synced)


if __name__ == "__main__":
    unittest.main()
