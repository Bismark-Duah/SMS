"""
tests/test_sha256_migration_hardening.py

Test suite for Fix 3: Finish SHA-256 Password Migration (P0).
Verifies:
1. `audit_password_hashes` accurately identifies legacy SHA-256 hashes vs modern bcrypt ($2b$).
2. `remediate_legacy_sha256_accounts` sets is_first_login=True on dormant legacy accounts without altering modern accounts.
3. Transparent JIT upgrade during login converts legacy SHA-256 to modern bcrypt ($2b$).
4. SuperAdmin endpoints `/super-admin/credential-audit` and `/super-admin/remediate-legacy-passwords` enforce SuperAdmin authorization.
5. All write paths (user creation, reset) strictly generate bcrypt hashes and never store SHA-256.
"""

import unittest
import os
import sys
import uuid
import hashlib
from starlette.datastructures import Headers

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

from backend.app.database import SessionLocal, run_migrations
from backend.app.models import School, User, Role
from backend.app.services.auth import (
    hash_password,
    verify_password,
    is_legacy_sha256_hash,
    audit_password_hashes,
    remediate_legacy_sha256_accounts,
)
from backend.app.routes.auth import (
    create_user,
    admin_reset_password,
    login,
    _legacy_sha256_hash
)
from backend.app.routes.super_admin import (
    super_admin_credential_audit,
    super_admin_remediate_legacy_passwords
)


class MockRequest:
    def __init__(self, client_ip="127.0.0.1", user_agent="PyTest-Audit-Runner"):
        self.client = type("Client", (), {"host": client_ip})()
        self.headers = Headers({"user-agent": user_agent, "x-forwarded-for": client_ip})


class TestSha256MigrationHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_migrations()

    def setUp(self):
        self.db = SessionLocal()
        self.school_code = f"AUD_{uuid.uuid4().hex[:6]}"
        self.school = School(
            name="SHA-256 Audit School",
            code=self.school_code,
            school_mode="COMBINED",
            ownership_type="PRIVATE"
        )
        self.db.add(self.school)
        self.db.commit()
        self.db.refresh(self.school)

        super_role = self.db.query(Role).filter(Role.name == "super_admin").first()
        if not super_role:
            super_role = Role(name="super_admin")
            self.db.add(super_role)
            self.db.commit()

        teacher_role = self.db.query(Role).filter(Role.name == "teacher").first()
        if not teacher_role:
            teacher_role = Role(name="teacher")
            self.db.add(teacher_role)
            self.db.commit()

        self.superadmin_user = User(
            username=f"super_{uuid.uuid4().hex[:6]}",
            password_hash=hash_password("SuperSecret123!"),
            school_id=None,
            is_active=True,
            is_first_login=False
        )
        self.superadmin_user.roles = [super_role]
        self.db.add(self.superadmin_user)

        self.regular_user = User(
            username=f"teach_{uuid.uuid4().hex[:6]}",
            password_hash=hash_password("TeacherSecret123!"),
            school_id=self.school.id,
            is_active=True,
            is_first_login=False
        )
        self.regular_user.roles = [teacher_role]
        self.db.add(self.regular_user)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_01_audit_identifies_legacy_sha256_hashes(self):
        """Auditor accurately isolates legacy SHA-256 hashes from bcrypt."""
        u_legacy = f"legacy_{uuid.uuid4().hex[:6]}"
        legacy_pwd = "OldLegacyPass123!"
        sha256_hash = hashlib.sha256(legacy_pwd.encode("utf-8")).hexdigest()
        self.assertEqual(len(sha256_hash), 64)
        self.assertTrue(is_legacy_sha256_hash(sha256_hash))

        legacy_user = User(
            username=u_legacy,
            password_hash=sha256_hash,
            school_id=self.school.id,
            is_active=True,
            is_first_login=False
        )
        self.db.add(legacy_user)
        self.db.commit()

        audit = audit_password_hashes(self.db)
        self.assertGreaterEqual(audit["total_users"], 3)
        self.assertGreaterEqual(audit["bcrypt_secure"], 2)
        self.assertGreaterEqual(audit["legacy_sha256"], 1)

        legacy_names = [a["username"] for a in audit["legacy_accounts"]]
        self.assertIn(u_legacy, legacy_names)

    def test_02_remediation_flags_dormant_legacy_accounts_for_rotation(self):
        """Remediation re-arms is_first_login=True exclusively for legacy SHA-256 accounts."""
        u_dormant = f"dormant_{uuid.uuid4().hex[:6]}"
        dormant_hash = hashlib.sha256("DormantPass123!".encode("utf-8")).hexdigest()

        dormant_user = User(
            username=u_dormant,
            password_hash=dormant_hash,
            school_id=self.school.id,
            is_active=True,
            is_first_login=False  # Initially False
        )
        self.db.add(dormant_user)
        self.db.commit()

        res = remediate_legacy_sha256_accounts(self.db)
        self.assertIn(u_dormant, res["remediated_users"])

        self.db.refresh(dormant_user)
        self.assertTrue(dormant_user.is_first_login, "Legacy account must have is_first_login armed")

        # Confirm modern bcrypt accounts were NOT changed
        self.db.refresh(self.regular_user)
        self.assertFalse(self.regular_user.is_first_login, "Bcrypt accounts must not have is_first_login altered")

    def test_03_jit_migration_on_login_upgrades_hash_to_bcrypt(self):
        """Logging in with a legacy SHA-256 account seamlessly upgrades hash to bcrypt ($2b$)."""
        u_migrate = f"migrate_{uuid.uuid4().hex[:6]}"
        plain_pwd = "MySecretToMigrate123!"
        sha256_hash = hashlib.sha256(plain_pwd.encode("utf-8")).hexdigest()

        user = User(
            username=u_migrate,
            password_hash=sha256_hash,
            school_id=self.school.id,
            is_active=True,
            is_first_login=False
        )
        self.db.add(user)
        self.db.commit()

        # Login with correct password
        login_res = login(
            payload={"username": u_migrate, "password": plain_pwd},
            request=MockRequest(),
            db=self.db
        )
        self.assertEqual(login_res.status_code, 200, "Login must succeed with legacy SHA-256 password")

        # Verify hash in database was automatically upgraded to bcrypt
        self.db.refresh(user)
        self.assertTrue(user.password_hash.startswith(("$2a$", "$2b$", "$2y$")), "Hash must now be bcrypt")
        self.assertNotEqual(len(user.password_hash), 64)

        # Confirm verify_password now returns (True, False) indicating modern hash (no rehash needed)
        is_valid, needs_rehash = verify_password(plain_pwd, user.password_hash)
        self.assertTrue(is_valid)
        self.assertFalse(needs_rehash, "Upgraded hash must not need rehash")

    def test_04_super_admin_audit_and_remediation_endpoints(self):
        """Super Admin endpoints enforce authorization and return correct audit payload."""
        # 1. Access by Super Admin -> succeeds
        audit_res = super_admin_credential_audit(db=self.db, current_user=self.superadmin_user)
        self.assertEqual(audit_res["status"], "success")
        self.assertIn("data", audit_res)
        self.assertIn("bcrypt_secure", audit_res["data"])

        remediate_res = super_admin_remediate_legacy_passwords(db=self.db, current_user=self.superadmin_user)
        self.assertEqual(remediate_res["status"], "success")

        # 2. Access by regular user -> forbidden (HTTP 403)
        with self.assertRaises(Exception) as ctx:
            super_admin_credential_audit(db=self.db, current_user=self.regular_user)
        self.assertIn("403", str(ctx.exception))

    def test_05_all_user_creation_paths_strictly_produce_bcrypt(self):
        """User creation and resets strictly produce bcrypt ($2b$) hashes."""
        u_new = f"fresh_{uuid.uuid4().hex[:6]}"
        created = create_user(
            payload={"username": u_new, "password": "FreshSecurePass123!"},
            db=self.db,
            current_user=self.superadmin_user,
            school_id=self.school.id
        )
        new_user = self.db.query(User).filter(User.username == u_new).first()
        self.assertIsNotNone(new_user)
        self.assertTrue(new_user.password_hash.startswith(("$2a$", "$2b$", "$2y$")))

        # Test admin reset
        admin_reset_password(
            user_id=new_user.id,
            payload={"new_password": "NewResetPassword123!"},
            db=self.db,
            current_user=self.superadmin_user
        )
        self.db.refresh(new_user)
        self.assertTrue(new_user.password_hash.startswith(("$2a$", "$2b$", "$2y$")))


if __name__ == "__main__":
    unittest.main()
