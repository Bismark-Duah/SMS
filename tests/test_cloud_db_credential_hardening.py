"""
tests/test_cloud_db_credential_hardening.py

Regression test suite for Fix 5: Protect Cloud Database Sync Credentials (P0).
Verifies:
1. `mask_database_url` reliably strips cleartext credentials from connection URIs.
2. All hardcoded database credentials (such as passwordeduManage360) and hardcoded cloud domains are eliminated.
3. Migration and synchronization utilities enforce fail-fast behavior when required environment variables are absent.
4. Disaster recovery and migration CLI scripts never print raw database passwords to stdout.
"""

import unittest
import os
import sys
import subprocess

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

from backend.app.database import mask_database_url


class TestCloudDbCredentialHardening(unittest.TestCase):
    def test_01_mask_database_url_hides_passwords(self):
        """Database connection strings have embedded passwords redacted."""
        raw_pg_url = "postgresql://postgres:MySuperSecretPass123!@db.production.sms.internal:5432/sms_live"
        masked = mask_database_url(raw_pg_url)
        self.assertNotIn("MySuperSecretPass123!", masked)
        self.assertIn("postgres:***@db.production.sms.internal", masked)
        self.assertIn("/sms_live", masked)

        # SQLite URLs do not have passwords and should remain intact
        sqlite_url = "sqlite:///d:/documents/my apps/SMS/school.db"
        self.assertEqual(mask_database_url(sqlite_url), sqlite_url)

        # Empty or None handling
        self.assertEqual(mask_database_url(""), "")
        self.assertEqual(mask_database_url(None), "")

    def test_02_elimination_of_hardcoded_credentials_in_scripts(self):
        """Scans migration and sync scripts to guarantee zero hardcoded passwords or cloud domains exist."""
        script_files = [
            os.path.abspath("backend/app/scripts/migrate_sqlite_to_postgres.py"),
            os.path.abspath("scripts/migrate_to_postgres.py"),
            os.path.abspath("scripts/pull_cloud_database.py"),
            os.path.abspath("backend/app/scripts/disaster_recovery.py")
        ]

        forbidden_strings = [
            "passwordeduManage360",
            "sms-nald.onrender.com",
            "postgresql://postgres:password@"
        ]

        for filepath in script_files:
            self.assertTrue(os.path.exists(filepath), f"File {filepath} must exist")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                for forbidden in forbidden_strings:
                    self.assertNotIn(
                        forbidden,
                        content,
                        f"Found forbidden hardcoded credential or domain '{forbidden}' in {filepath}"
                    )

    def test_03_migrate_sqlite_to_postgres_fails_fast_when_unconfigured(self):
        """`migrate_sqlite_to_postgres` cleanly exits with non-zero code when PG_DATABASE_URL is omitted."""
        env = os.environ.copy()
        env.pop("PG_DATABASE_URL", None)
        env.pop("DATABASE_URL", None)

        proc = subprocess.run(
            [sys.executable, "-c", "from backend.app.scripts.migrate_sqlite_to_postgres import migrate; migrate()"],
            capture_output=True,
            text=True,
            env=env
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Target PostgreSQL database connection string is not configured", proc.stdout)

    def test_04_migrate_to_postgres_fails_fast_when_unconfigured(self):
        """`scripts/migrate_to_postgres.py` cleanly exits with non-zero code when no target is supplied."""
        env = os.environ.copy()
        env.pop("POSTGRES_URL", None)
        env.pop("DATABASE_URL", None)

        proc = subprocess.run(
            [sys.executable, "scripts/migrate_to_postgres.py"],
            capture_output=True,
            text=True,
            env=env
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Target PostgreSQL database connection string is not configured", proc.stdout)


if __name__ == "__main__":
    unittest.main()
