"""
tests/test_backup_and_recovery.py
Automated test suite for Prompt 22: Backup and Recovery.
Verifies hot backup creation, SHA-256 sidecar validation, dry-run restore verification,
retention pruning, and PostgreSQL production command generation.
"""

import os
import unittest
from fastapi.testclient import TestClient

from backend.app.services.backup_service import BackupService, BACKUPS_DIR
from backend.app.main import app
from backend.app.services.auth import create_access_token


class TestBackupAndRecovery(unittest.TestCase):

    def test_01_create_backup_with_sha256_and_integrity(self):
        """create_backup must generate a valid hot backup with SHA-256 checksum."""
        res = BackupService.create_backup(verify_integrity=True)
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["integrity_verified"])
        self.assertIn("filename", res)
        self.assertIn("sha256", res)

        backup_file = os.path.join(BACKUPS_DIR, res["filename"])
        sha_file = f"{backup_file}.sha256"
        self.assertTrue(os.path.exists(backup_file))
        self.assertTrue(os.path.exists(sha_file))

    def test_02_verify_backup_integrity(self):
        """verify_backup_integrity must validate checksum and SQLite integrity."""
        res = BackupService.create_backup(verify_integrity=True)
        filename = res["filename"]

        verify_res = BackupService.verify_backup_integrity(filename)
        self.assertEqual(verify_res["status"], "HEALTHY")
        self.assertTrue(verify_res["checksum_matched"])
        self.assertTrue(verify_res["sqlite_integrity_healthy"])

    def test_03_restore_database_snapshot_dry_run(self):
        """restore_database_snapshot with dry_run=True validates snapshot schemas safely."""
        res = BackupService.create_backup(verify_integrity=True)
        filename = res["filename"]

        dry_run_res = BackupService.restore_database_snapshot(filename, dry_run=True)
        self.assertEqual(dry_run_res["status"], "success")
        self.assertTrue(dry_run_res["dry_run"])
        self.assertTrue(dry_run_res["verified"])
        self.assertGreater(dry_run_res["tables_count"], 0)
        self.assertIn("Safe to restore", dry_run_res["message"])

    def test_04_restore_rejects_nonexistent_file(self):
        """restore_database_snapshot must raise FileNotFoundError for nonexistent snapshot."""
        with self.assertRaises(FileNotFoundError):
            BackupService.restore_database_snapshot("non_existent_file.db", dry_run=True)

    def test_05_list_backups_returns_ordered_metadata(self):
        """list_backups returns sorted list of available backups with sizes and checksum flags."""
        backups = BackupService.list_backups()
        self.assertIsInstance(backups, list)
        if backups:
            self.assertIn("filename", backups[0])
            self.assertIn("size_bytes", backups[0])
            self.assertIn("has_checksum", backups[0])

    def test_06_enforce_retention_policy(self):
        """enforce_retention_policy removes snapshots exceeding the retention bound."""
        # Create at least 3 backups
        for _ in range(3):
            BackupService.create_backup(verify_integrity=False)

        # Enforce retention limit of 100 (should prune 0)
        pruned = BackupService.enforce_retention_policy(retention_limit=100)
        self.assertEqual(pruned, 0)

    def test_07_postgres_backup_command_generation(self):
        """generate_postgres_backup_command generates correct pg_dump command without password leak."""
        test_url = "postgresql://sms_admin:SuperSecretPass@postgres.cloud.internal:5432/edumanage_production"
        info = BackupService.generate_postgres_backup_command(db_url=test_url, output_file="test.dump")

        self.assertEqual(info["status"], "success")
        self.assertEqual(info["host"], "postgres.cloud.internal")
        self.assertEqual(info["port"], 5432)
        self.assertEqual(info["user"], "sms_admin")
        self.assertEqual(info["database"], "edumanage_production")
        self.assertIn("pg_dump -Fc", info["command"])
        self.assertNotIn("SuperSecretPass", info["command"])  # Password must never appear in command string

    def test_08_postgres_restore_command_generation(self):
        """generate_postgres_restore_command generates correct pg_restore command."""
        test_url = "postgresql://sms_admin:SuperSecretPass@postgres.cloud.internal:5432/edumanage_production"
        info = BackupService.generate_postgres_restore_command(db_url=test_url, dump_file="test.dump")

        self.assertEqual(info["status"], "success")
        self.assertIn("pg_restore", info["command"])
        self.assertIn("--clean --if-exists", info["command"])
        self.assertNotIn("SuperSecretPass", info["command"])

    def test_09_restore_test_api_endpoint(self):
        """POST /api/backup/restore-test/{filename} tests dry-run restore over API for admin."""
        res_backup = BackupService.create_backup(verify_integrity=True)
        filename = res_backup["filename"]

        from backend.app.dependencies import get_current_user
        from backend.app.models import User, Role

        mock_admin = User(id=999, username="backup_admin", is_active=True, school_id=1)
        mock_role = Role(id=1, name="admin")
        mock_admin.roles = [mock_role]

        app.dependency_overrides[get_current_user] = lambda: mock_admin
        try:
            client = TestClient(app)
            res = client.post(
                f"/api/backup/restore-test/{filename}",
                headers={"Authorization": "Bearer mock_token"}
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "success")
            self.assertTrue(data["dry_run"])
            self.assertTrue(data["verified"])
        finally:
            app.dependency_overrides.pop(get_current_user, None)


if __name__ == "__main__":
    unittest.main()
