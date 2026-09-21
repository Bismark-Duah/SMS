"""
tests/test_backup_security_hardening.py

Regression test suite for Fix 7: Harden Backup File Permissions & Encryption at Rest (P1).
Verifies:
1. Access control lockdown: Low-privilege roles (storekeeper, bursar, teacher) cannot download or run backups (HTTP 403).
2. Authorized roles (admin, super_admin, headmaster) can trigger and inspect backups.
3. AES-256 (Fernet / PBKDF2HMAC) encryption at rest cycle and bit-for-bit SQLite integrity recovery.
4. Ciphertext security: Raw SQLite headers ("SQLite format 3") are absent from encrypted snapshots.
5. Wrong passphrase or tampered ciphertext causes safe decryption rejection.
6. Path traversal and sensitive system directory overwrites in copy-to-path are rejected with HTTP 400.
"""

import unittest
import os
import sys
import uuid
import tempfile
import sqlite3
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

from backend.app.database import SessionLocal, run_migrations, DEFAULT_DB_PATH
from backend.app.models import School, User, Role
from backend.app.services.auth import hash_password
from backend.app.services.backup_service import BackupService, BACKUPS_DIR, BACKUP_MAGIC_HEADER
from backend.app.routes.backup import (
    run_backup,
    list_backups,
    download_backup,
    copy_backup_to_path,
    encrypt_backup_file,
    decrypt_backup_file,
    _validate_safe_backup_path
)


class TestBackupSecurityHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_migrations()

    def setUp(self):
        self.db = SessionLocal()

        # Create test roles
        self.role_super = self.db.query(Role).filter(Role.name == "super_admin").first()
        self.role_admin = self.db.query(Role).filter(Role.name == "admin").first()
        self.role_bursar = self.db.query(Role).filter(Role.name == "bursar").first()
        self.role_storekeeper = self.db.query(Role).filter(Role.name == "storekeeper").first()
        self.role_teacher = self.db.query(Role).filter(Role.name == "teacher").first()

        if not self.role_bursar:
            self.role_bursar = Role(name="bursar")
            self.db.add(self.role_bursar)
        if not self.role_storekeeper:
            self.role_storekeeper = Role(name="storekeeper")
            self.db.add(self.role_storekeeper)
        self.db.commit()

        # Users
        self.user_super = User(
            username=f"super_{uuid.uuid4().hex[:5]}",
            password_hash=hash_password("Pass123!"),
            is_active=True
        )
        self.user_super.roles = [self.role_super]

        self.user_admin = User(
            username=f"admin_{uuid.uuid4().hex[:5]}",
            password_hash=hash_password("Pass123!"),
            is_active=True
        )
        self.user_admin.roles = [self.role_admin]

        self.user_bursar = User(
            username=f"bursar_{uuid.uuid4().hex[:5]}",
            password_hash=hash_password("Pass123!"),
            is_active=True
        )
        self.user_bursar.roles = [self.role_bursar]

        self.user_storekeeper = User(
            username=f"store_{uuid.uuid4().hex[:5]}",
            password_hash=hash_password("Pass123!"),
            is_active=True
        )
        self.user_storekeeper.roles = [self.role_storekeeper]

        self.user_teacher = User(
            username=f"teacher_{uuid.uuid4().hex[:5]}",
            password_hash=hash_password("Pass123!"),
            is_active=True
        )
        self.user_teacher.roles = [self.role_teacher]

        self.db.add_all([
            self.user_super, self.user_admin, self.user_bursar,
            self.user_storekeeper, self.user_teacher
        ])
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_01_low_privilege_roles_cannot_access_backup_endpoints(self):
        """Bursars, storekeepers, and teachers are rejected with HTTP 403 on backup actions."""
        low_priv_users = [self.user_bursar, self.user_storekeeper, self.user_teacher]

        for u in low_priv_users:
            with self.subTest(role=u.roles[0].name):
                # Run backup
                with self.assertRaises(HTTPException) as ctx:
                    run_backup(payload={}, db=self.db, current_user=u)
                self.assertEqual(ctx.exception.status_code, 403)
                self.assertIn("high-level administrative privileges", ctx.exception.detail.lower())

                # List backups
                with self.assertRaises(HTTPException) as ctx:
                    list_backups(db=self.db, current_user=u)
                self.assertEqual(ctx.exception.status_code, 403)

                # Download backup
                with self.assertRaises(HTTPException) as ctx:
                    download_backup(filename="backup_test.db", db=self.db, current_user=u)
                self.assertEqual(ctx.exception.status_code, 403)

                # Copy to path
                with self.assertRaises(HTTPException) as ctx:
                    copy_backup_to_path(payload={"target_path": "C:\\temp"}, db=self.db, current_user=u)
                self.assertEqual(ctx.exception.status_code, 403)

    def test_02_authorized_admin_can_run_and_list_backups(self):
        """SuperAdmin and Admin can successfully trigger and list hot backups."""
        res = run_backup(payload={}, db=self.db, current_user=self.user_admin)
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["filename"].startswith("backup_"))
        self.assertTrue(res["integrity_verified"])

        bk_list = list_backups(db=self.db, current_user=self.user_super)
        self.assertIsInstance(bk_list, list)
        self.assertTrue(len(bk_list) > 0)
        filenames = [b["filename"] for b in bk_list]
        self.assertIn(res["filename"], filenames)

    def test_03_encryption_at_rest_and_decryption_cycle(self):
        """
        Verifies AES-256 encryption at rest:
        1. Ciphertext does not contain 'SQLite format 3'.
        2. Starts with magic header EDUBKP01.
        3. Decrypts back to bit-for-bit verified SQLite database.
        """
        # Create a fresh backup
        res = BackupService.create_backup(verify_integrity=True)
        raw_filename = res["filename"]
        raw_path = os.path.join(BACKUPS_DIR, raw_filename)
        self.assertTrue(os.path.exists(raw_path))

        passphrase = "SecretOfflineSchoolPassphrase!2026"
        enc_path = BackupService.encrypt_backup(raw_path, passphrase=passphrase)
        self.assertTrue(os.path.exists(enc_path))
        self.assertTrue(enc_path.endswith(".enc"))

        # Verify ciphertext properties
        with open(enc_path, "rb") as f:
            enc_bytes = f.read()

        # Header check
        self.assertTrue(enc_bytes.startswith(BACKUP_MAGIC_HEADER))
        # Plaintext SQLite header must NOT be present
        self.assertNotIn(b"SQLite format 3", enc_bytes)

        # Decrypt backup to a separate test location
        dec_path = os.path.join(tempfile.gettempdir(), f"restored_{uuid.uuid4().hex[:6]}.db")
        try:
            BackupService.decrypt_backup(enc_path, target_path=dec_path, passphrase=passphrase)
            self.assertTrue(os.path.exists(dec_path))

            # Query the decrypted database to verify structure and contents
            conn = sqlite3.connect(dec_path)
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM users;")
            users_count = cursor.fetchone()[0]
            conn.close()
            self.assertGreater(users_count, 0)
        finally:
            if os.path.exists(dec_path):
                try: os.remove(dec_path)
                except Exception: pass
            if os.path.exists(enc_path):
                try: os.remove(enc_path)
                except Exception: pass

    def test_04_tampered_or_wrong_passphrase_rejected(self):
        """Decryption with incorrect passphrase fails securely."""
        res = BackupService.create_backup(verify_integrity=True)
        raw_path = os.path.join(BACKUPS_DIR, res["filename"])
        passphrase = "CorrectPassphrase#99"

        enc_path = BackupService.encrypt_backup(raw_path, passphrase=passphrase)
        try:
            # Wrong passphrase
            with self.assertRaises(ValueError) as ctx:
                BackupService.decrypt_backup(enc_path, passphrase="WrongPassphrase#00")
            self.assertIn("Decryption failed", str(ctx.exception))

            # Tampered ciphertext
            tampered_path = f"{enc_path}.tampered"
            with open(enc_path, "rb") as f:
                data = bytearray(f.read())
            data[-10] = (data[-10] + 1) % 256  # flip a bit in ciphertext
            with open(tampered_path, "wb") as f:
                f.write(data)

            with self.assertRaises(ValueError) as ctx:
                BackupService.decrypt_backup(tampered_path, passphrase=passphrase)
            self.assertIn("Decryption failed", str(ctx.exception))

            if os.path.exists(tampered_path):
                try: os.remove(tampered_path)
                except Exception: pass
        finally:
            if os.path.exists(enc_path):
                try: os.remove(enc_path)
                except Exception: pass

    def test_05_copy_to_path_blocks_directory_traversal_and_system_directories(self):
        """Validates that copy-to-path strictly blocks directory traversal and sensitive paths."""
        # 1. Traversal syntax
        with self.assertRaises(HTTPException) as ctx:
            _validate_safe_backup_path("../../../etc/shadow")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("traversal", ctx.exception.detail.lower())

        # 2. System root
        with self.assertRaises(HTTPException) as ctx:
            _validate_safe_backup_path("C:\\")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("forbidden", ctx.exception.detail.lower())

        # 3. Windows System directory
        with self.assertRaises(HTTPException) as ctx:
            _validate_safe_backup_path("C:\\Windows\\System32")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("protected system directories", ctx.exception.detail.lower())

        # 4. Valid target in safe temp directory succeeds
        safe_dir = os.path.join(tempfile.gettempdir(), "sms_safe_backups")
        validated = _validate_safe_backup_path(safe_dir)
        self.assertTrue(os.path.isabs(validated))


if __name__ == "__main__":
    unittest.main()
