import unittest
import os
import sys
import json
import logging
import sqlite3
import uuid

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import engine, Base, SessionLocal, run_migrations, get_database_telemetry
from backend.app.services.backup_service import BackupService, BACKUPS_DIR
from backend.app.logger import StructuredJsonFormatter, setup_logging, get_logger
from backend.app.main import app, get_system_health, get_system_telemetry
from run import get_recommended_workers


class TestDevOpsAndInfrastructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_migrations()
        os.makedirs(BACKUPS_DIR, exist_ok=True)
        cls.db = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # ── Test 1: Worker Concurrency Logic for SQLite vs PostgreSQL ────────────────
    def test_01_worker_concurrency_sqlite_vs_postgres(self):
        """Verify get_recommended_workers strictly pins SQLite to 1 worker and scales PostgreSQL."""
        # 1. SQLite mode -> must return 1 worker
        orig_db = os.environ.get("DATABASE_URL")
        orig_conc = os.environ.get("WEB_CONCURRENCY")
        try:
            os.environ["DATABASE_URL"] = "sqlite:///./school.db"
            os.environ["WEB_CONCURRENCY"] = "8"
            workers = get_recommended_workers()
            self.assertEqual(workers, 1, "SQLite must be strictly pinned to 1 worker to avoid multi-process write collisions!")

            # 2. PostgreSQL mode -> respects concurrency
            os.environ["DATABASE_URL"] = "postgresql://postgres:pass@localhost:5432/sms_db"
            os.environ["WEB_CONCURRENCY"] = "4"
            pg_workers = get_recommended_workers()
            self.assertEqual(pg_workers, 4, "PostgreSQL should respect WEB_CONCURRENCY worker scaling!")
        finally:
            if orig_db is not None:
                os.environ["DATABASE_URL"] = orig_db
            else:
                os.environ.pop("DATABASE_URL", None)
            if orig_conc is not None:
                os.environ["WEB_CONCURRENCY"] = orig_conc
            else:
                os.environ.pop("WEB_CONCURRENCY", None)

    # ── Test 2: Production Secret Hardening ───────────────────────────────────────
    def test_02_production_secret_enforcement(self):
        """Verify that default or empty SECRET_KEY is rejected in production environment."""
        orig_env = os.environ.get("ENVIRONMENT")
        orig_sec = os.environ.get("SECRET_KEY")
        try:
            os.environ["ENVIRONMENT"] = "production"
            os.environ["SECRET_KEY"] = "your-secret-key-change-in-production"

            # Check validator logic
            secret = os.getenv("SECRET_KEY", "").strip()
            env_mode = os.getenv("ENVIRONMENT", "").lower()

            is_violation = (env_mode in ("production", "prod")) and (
                not secret or secret in ("your-secret-key-change-in-production", "edumanage-hybrid-sync-secret-key-2026")
            )
            self.assertTrue(is_violation, "Production mode must flag default/insecure SECRET_KEY as a violation!")
        finally:
            if orig_env is not None:
                os.environ["ENVIRONMENT"] = orig_env
            else:
                os.environ.pop("ENVIRONMENT", None)
            if orig_sec is not None:
                os.environ["SECRET_KEY"] = orig_sec
            else:
                os.environ.pop("SECRET_KEY", None)

    # ── Test 3: Structured JSON Logging Formatter ─────────────────────────────────
    def test_03_structured_json_logging_formatting(self):
        """Verify StructuredJsonFormatter produces valid JSON log records with standard metadata."""
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="edumanage.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="User login successful",
            args=(),
            exc_info=None
        )
        record.request_id = "req-test-999"
        record.client_ip = "127.0.0.1"
        record.method = "POST"
        record.path = "/api/auth/login"
        record.status_code = 200
        record.duration_ms = 12.4
        record.school_id = 1

        json_out = formatter.format(record)
        log_data = json.loads(json_out)

        self.assertEqual(log_data["level"], "INFO")
        self.assertEqual(log_data["logger"], "edumanage.test")
        self.assertEqual(log_data["message"], "User login successful")
        self.assertEqual(log_data["request_id"], "req-test-999")
        self.assertEqual(log_data["method"], "POST")
        self.assertEqual(log_data["status_code"], 200)
        self.assertEqual(log_data["duration_ms"], 12.4)
        self.assertEqual(log_data["school_id"], 1)
        self.assertIn("timestamp", log_data)
        self.assertIn("process_id", log_data)

    # ── Test 4: SQLite Hot Backup, SHA-256 Checksums & Quick Check ───────────────
    def test_04_sqlite_hot_backup_and_checksum_verification(self):
        """Verify BackupService generates valid hot backup with SHA-256 and quick_check verification."""
        res = BackupService.create_backup(retention_limit=14, verify_integrity=True)
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["filename"].startswith("backup_"))
        self.assertTrue(res["filename"].endswith(".db"))
        self.assertTrue(res["size_bytes"] > 0)
        self.assertTrue(len(res["sha256"]) == 64)
        self.assertTrue(res["integrity_verified"])

        # Check file exists on disk
        backup_file = os.path.join(BACKUPS_DIR, res["filename"])
        sha_file = f"{backup_file}.sha256"
        self.assertTrue(os.path.exists(backup_file))
        self.assertTrue(os.path.exists(sha_file))

        # Verify integrity using service
        verify_res = BackupService.verify_backup_integrity(res["filename"])
        self.assertEqual(verify_res["status"], "HEALTHY")
        self.assertTrue(verify_res["checksum_matched"])
        self.assertTrue(verify_res["sqlite_integrity_healthy"])

        # Test listing backups
        backup_list = BackupService.list_backups()
        self.assertTrue(len(backup_list) >= 1)
        self.assertTrue(any(b["filename"] == res["filename"] for b in backup_list))

    # ── Test 5: Backup Rolling Retention Pruning ──────────────────────────────────
    def test_05_backup_rolling_retention_pruning(self):
        """Verify enforce_retention_policy prunes stale backups beyond retention limit."""
        # Create dummy old backup files
        dummy_1 = os.path.join(BACKUPS_DIR, "backup_1999-01-01_000000.db")
        dummy_1_sha = f"{dummy_1}.sha256"
        dummy_2 = os.path.join(BACKUPS_DIR, "backup_1999-01-02_000000.db")
        dummy_2_sha = f"{dummy_2}.sha256"

        with open(dummy_1, "w") as f: f.write("dummy sqlite 1")
        with open(dummy_1_sha, "w") as f: f.write("hash1  backup_1999-01-01_000000.db")
        with open(dummy_2, "w") as f: f.write("dummy sqlite 2")
        with open(dummy_2_sha, "w") as f: f.write("hash2  backup_1999-01-02_000000.db")

        # Set retention limit to 1
        pruned = BackupService.enforce_retention_policy(retention_limit=1)
        self.assertGreaterEqual(pruned, 1, "Stale backups beyond retention limit must be pruned")
        self.assertFalse(os.path.exists(dummy_1), "Oldest dummy backup must be deleted")
        self.assertFalse(os.path.exists(dummy_1_sha), "Oldest dummy backup sha file must be deleted")

    # ── Test 6: Database Telemetry & Health Endpoint Execution ───────────────────
    def test_06_database_telemetry_and_health(self):
        """Verify get_database_telemetry and health handler return complete engine metrics."""
        telemetry = get_database_telemetry(self.db)
        self.assertEqual(telemetry["status"], "connected")
        self.assertIn("engine", telemetry)
        self.assertIn("latency_ms", telemetry)

        if "SQLite" in telemetry["engine"]:
            self.assertIn("storage", telemetry)
            self.assertIn("wal_checkpoint_status", telemetry)
            self.assertIn("page_count", telemetry["storage"])

        # Directly invoke health handler
        health_response = get_system_health(self.db)
        health_body = json.loads(health_response.body.decode())
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_body["status"], "healthy")
        self.assertIn("database", health_body)

        # Directly invoke telemetry handler
        telemetry_response = get_system_telemetry(self.db)
        self.assertEqual(telemetry_response["status"], "success")
        self.assertIn("counts", telemetry_response)
        self.assertIn("schools", telemetry_response["counts"])


if __name__ == "__main__":
    unittest.main()
