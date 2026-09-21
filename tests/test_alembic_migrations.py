"""
Tests for Prompt 10: Alembic Migration Strategy and Schema Evolution.
Verifies Alembic environment configuration, programmatic migration execution,
and schema version tracking.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from backend.app.database import engine, Base, run_migrations, apply_alembic_migrations, BASE_DIR


class TestAlembicMigrations(unittest.TestCase):
    def test_alembic_ini_and_directory_structure(self):
        """Verify Alembic configuration files and directory structure exist."""
        root_ini = os.path.join(BASE_DIR, "alembic.ini")
        backend_ini = os.path.join(BASE_DIR, "backend", "alembic.ini")
        env_py = os.path.join(BASE_DIR, "backend", "alembic", "env.py")
        versions_dir = os.path.join(BASE_DIR, "backend", "alembic", "versions")

        self.assertTrue(os.path.exists(root_ini), f"Missing {root_ini}")
        self.assertTrue(os.path.exists(backend_ini), f"Missing {backend_ini}")
        self.assertTrue(os.path.exists(env_py), f"Missing {env_py}")
        self.assertTrue(os.path.isdir(versions_dir), f"Missing {versions_dir}")

    def test_alembic_versions_exist(self):
        """Verify at least one baseline migration revision exists in versions directory."""
        versions_dir = os.path.join(BASE_DIR, "backend", "alembic", "versions")
        revisions = [f for f in os.listdir(versions_dir) if f.endswith(".py") and not f.startswith("__")]
        self.assertGreaterEqual(len(revisions), 1, "Expected at least 1 Alembic revision file.")

    def test_apply_alembic_migrations_programmatic(self):
        """Verify apply_alembic_migrations executes without error."""
        success = apply_alembic_migrations()
        self.assertTrue(success, "apply_alembic_migrations() failed to execute.")

        with engine.connect() as conn:
            # Verify alembic_version table exists and has head revision
            result = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            self.assertIsNotNone(result, "alembic_version table was empty or missing.")
            self.assertIn(result[0], ["0001_baseline", "0002_constraints"])

    def test_run_migrations_end_to_end(self):
        """Verify run_migrations() completes end-to-end and synchronizes all schema objects."""
        run_migrations()
        with engine.connect() as conn:
            # Verify core tables and columns exist
            critical_tables = [
                "users", "students", "schools", "subjects", "timetable",
                "fees", "settings", "revoked_reset_tokens", "audit_logs"
            ]
            for table_name in critical_tables:
                res = conn.execute(text(f"SELECT 1 FROM {table_name} LIMIT 1"))
                self.assertIsNotNone(res)

    def test_database_migrations_documentation_exists(self):
        """Verify DATABASE_MIGRATIONS.md exists and documents dual-engine lifecycle."""
        doc_path = os.path.join(BASE_DIR, "DATABASE_MIGRATIONS.md")
        self.assertTrue(os.path.exists(doc_path), "DATABASE_MIGRATIONS.md must exist at project root")
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Dual-Engine Architecture", content)
        self.assertIn("SQLite 3", content)
        self.assertIn("PostgreSQL", content)
        self.assertIn("alembic upgrade head", content)
        self.assertIn("alembic downgrade -1", content)


if __name__ == "__main__":
    unittest.main()

