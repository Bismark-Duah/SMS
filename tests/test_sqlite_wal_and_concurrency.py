import sys
import os
import uuid
import unittest
import threading
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# Setup path resolution
current_dir = os.path.dirname(os.path.abspath(__file__))
sms_root = os.path.abspath(os.path.join(current_dir, ".."))
backend_dir = os.path.join(sms_root, "backend")

if sms_root not in sys.path:
    sys.path.insert(0, sms_root)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from backend.app.database import (
    SessionLocal,
    Base,
    engine,
    is_sqlite,
    checkpoint_database,
    vacuum_database
)
from backend.app.models import School, Student, Setting, Score, Subject, Semester


class TestSQLiteWALAndConcurrency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()
        cls.u_suffix = uuid.uuid4().hex[:6]

        cls.school = School(
            name=f"WAL Test Academy {cls.u_suffix}",
            code=f"WTA-{cls.u_suffix}",
            school_mode="COMBINED"
        )
        cls.db.add(cls.school)
        cls.db.commit()
        cls.db.refresh(cls.school)

    @classmethod
    def tearDownClass(cls):
        cls.db.rollback()
        cls.db.close()

    def test_01_sqlite_pragmas_enabled(self):
        """Verify WAL, foreign_keys=ON, busy_timeout=30000, and wal_autocheckpoint=1000."""
        if not is_sqlite:
            self.skipTest("PostgreSQL active; skipping SQLite PRAGMA test.")

        with engine.connect() as conn:
            # 1. Foreign keys
            fk = conn.execute(text("PRAGMA foreign_keys;")).scalar()
            self.assertEqual(fk, 1, "Expected PRAGMA foreign_keys to be 1 (ON).")

            # 2. Journal Mode
            jm = conn.execute(text("PRAGMA journal_mode;")).scalar()
            self.assertEqual(str(jm).lower(), "wal", "Expected PRAGMA journal_mode to be 'wal'.")

            # 3. Busy Timeout
            bt = conn.execute(text("PRAGMA busy_timeout;")).scalar()
            self.assertEqual(bt, 30000, "Expected PRAGMA busy_timeout to be 30000 ms.")

            # 4. WAL Autocheckpoint
            ac = conn.execute(text("PRAGMA wal_autocheckpoint;")).scalar()
            self.assertEqual(ac, 1000, "Expected PRAGMA wal_autocheckpoint to be 1000 pages.")

    def test_02_foreign_key_constraint_enforcement(self):
        """Verify invalid foreign key insertion is strictly rejected by SQLite."""
        if not is_sqlite:
            self.skipTest("SQLite specific test.")

        invalid_session = SessionLocal()
        try:
            # Attempt to insert a score pointing to a non-existent student ID
            invalid_score = Score(
                student_id=99999999,  # Non-existent student
                subject_id=1,
                semester_id=1,
                total_score=95.0
            )
            invalid_session.add(invalid_score)
            with self.assertRaises(IntegrityError):
                invalid_session.commit()
        finally:
            invalid_session.rollback()
            invalid_session.close()

    def test_03_concurrent_multithreaded_writes(self):
        """Simulate simultaneous writes (e.g. Bursar + Secretary) to ensure no 'database is locked' errors."""
        num_threads = 6
        writes_per_thread = 5
        thread_errors = []

        def worker_write(thread_idx: int):
            db_session = SessionLocal()
            try:
                for w in range(writes_per_thread):
                    u = uuid.uuid4().hex[:6]
                    # Simulate rapid concurrent writes across settings and students
                    setting = Setting(
                        school_id=self.school.id,
                        key=f"conc_key_{thread_idx}_{w}_{u}",
                        value=f"val_{thread_idx}_{w}"
                    )
                    db_session.add(setting)
                    db_session.commit()
            except Exception as e:
                thread_errors.append(f"Thread {thread_idx} failed with: {str(e)}")
            finally:
                db_session.close()

        threads = [threading.Thread(target=worker_write, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(thread_errors), 0, f"Concurrent writes threw errors: {thread_errors}")

    def test_04_wal_checkpoint_and_vacuum(self):
        """Verify manual and scheduled checkpointing and vacuum maintenance operations."""
        if not is_sqlite:
            self.skipTest("SQLite specific test.")

        chk_res = checkpoint_database(mode="TRUNCATE")
        self.assertEqual(chk_res["status"], "success")
        self.assertEqual(chk_res["mode"], "TRUNCATE")

        vac_res = vacuum_database()
        self.assertEqual(vac_res["status"], "success")


if __name__ == "__main__":
    unittest.main()
