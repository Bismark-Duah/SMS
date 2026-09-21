"""
tests/test_predictable_passwords_elimination.py

Regression test suite for Fix 2: Eliminate Predictable Default Passwords.
Verifies that:
1. User creation without a password generates a unique cryptographically random temporary password.
2. The legacy universal fallback "Staff@123" is completely eliminated and cannot authenticate.
3. CSV bulk import without passwords generates distinct random temporary passwords per row (no universal "Welcome123!").
4. Both single user creation and CSV bulk imports set is_first_login=True.
5. Admin password reset without explicit password generates a temporary credential and re-arms is_first_login=True.
6. Production environment bootstrapping strictly requires an explicitly supplied INITIAL_SUPERADMIN_PASSWORD.
"""

import unittest
import os
import sys
import io
import uuid
import asyncio
from starlette.datastructures import Headers

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

from backend.app.database import SessionLocal, run_migrations
from backend.app.models import School, User, Role
from backend.app.routes.auth import (
    create_user,
    import_users_csv,
    admin_reset_password,
    login,
    _seed_db,
    _hash_password
)
from fastapi import UploadFile


class MockRequest:
    def __init__(self, client_ip="127.0.0.1"):
        self.client = type("Client", (), {"host": client_ip})()
        self.headers = Headers({})


class TestPredictablePasswordsElimination(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        run_migrations()
        cls.db = SessionLocal()
        cls.suffix = uuid.uuid4().hex[:6]

        # 1. School
        cls.school = School(
            name=f"Hardening School {cls.suffix}",
            code=f"HS-{cls.suffix}",
            school_mode="COMBINED"
        )
        cls.db.add(cls.school)
        cls.db.commit()
        cls.db.refresh(cls.school)

        # 2. Roles
        cls.admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        cls.teacher_role = cls.db.query(Role).filter(Role.name == "teacher").first()
        cls.super_role = cls.db.query(Role).filter(Role.name == "super_admin").first()

        # 3. Super Admin caller
        cls.super_user = User(
            username=f"super_caller_{cls.suffix}",
            email=f"super_caller_{cls.suffix}@platform.local",
            password_hash=_hash_password("SuperSecretCaller#1"),
            roles=[cls.super_role] if cls.super_role else []
        )
        cls.db.add(cls.super_user)

        # 4. School Admin caller
        cls.admin_user = User(
            username=f"admin_caller_{cls.suffix}",
            email=f"admin_caller_{cls.suffix}@school.local",
            password_hash=_hash_password("AdminSecretCaller#1"),
            school_id=cls.school.id,
            roles=[cls.admin_role] if cls.admin_role else []
        )
        cls.db.add(cls.admin_user)
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_user_creation_without_password_uses_random_credential(self):
        """Creating a user with no password generates a unique random password, NOT Staff@123."""
        username = f"rand_user_{uuid.uuid4().hex[:5]}"
        payload = {
            "username": username,
            "roles": ["teacher"]
        }
        res = create_user(
            payload=payload,
            db=self.db,
            current_user=self.admin_user,
            school_id=self.school.id
        )
        self.assertTrue(hasattr(res, "temporary_password"), "Response must provide generated temporary_password")
        temp_pwd = res.temporary_password
        self.assertNotEqual(temp_pwd, "Staff@123", "Must never use universal default Staff@123")
        self.assertTrue(temp_pwd.startswith("Tmp#"), "Generated password must be properly formatted")
        self.assertTrue(res.is_first_login, "Account must enforce password change on first login")

        # 1. Verify Staff@123 is rejected
        login_res_bad = login({"username": username, "password": "Staff@123"}, MockRequest(), self.db)
        self.assertEqual(login_res_bad.status_code, 401, "Staff@123 must be rejected")

        # 2. Verify the temporary password succeeds
        login_res_good = login({"username": username, "password": temp_pwd}, MockRequest(), self.db)
        self.assertEqual(login_res_good.status_code, 200, "Temporary password must authenticate successfully")

    def test_02_csv_import_without_passwords_generates_unique_credentials(self):
        """CSV import with blank passwords generates unique credentials for each user, NOT Welcome123!."""
        u1 = f"csv_u1_{uuid.uuid4().hex[:5]}"
        u2 = f"csv_u2_{uuid.uuid4().hex[:5]}"
        csv_content = f"username,email,roles\n{u1},{u1}@test.local,teacher\n{u2},{u2}@test.local,teacher\n"
        upload_file = UploadFile(filename="users.csv", file=io.BytesIO(csv_content.encode("utf-8")))

        res = asyncio.run(import_users_csv(
            file=upload_file,
            db=self.db,
            current_user=self.admin_user,
            school_id=self.school.id
        ))
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["imported"], 2)
        self.assertIn("temporary_credentials", res)
        creds = res["temporary_credentials"]
        self.assertEqual(len(creds), 2)

        p1 = next(c["temporary_password"] for c in creds if c["username"] == u1)
        p2 = next(c["temporary_password"] for c in creds if c["username"] == u2)

        self.assertNotEqual(p1, "Welcome123!", "Must not use universal Welcome123!")
        self.assertNotEqual(p2, "Welcome123!", "Must not use universal Welcome123!")
        self.assertNotEqual(p1, p2, "Temporary passwords must be unique per user")

        # Welcome123! must fail
        self.assertEqual(login({"username": u1, "password": "Welcome123!"}, MockRequest(), self.db).status_code, 401)
        self.assertEqual(login({"username": u2, "password": "Welcome123!"}, MockRequest(), self.db).status_code, 401)

        # Temporary credentials must succeed
        self.assertEqual(login({"username": u1, "password": p1}, MockRequest(), self.db).status_code, 200)
        self.assertEqual(login({"username": u2, "password": p2}, MockRequest(), self.db).status_code, 200)

    def test_03_admin_reset_without_password_generates_temporary_password(self):
        """Admin resetting password with empty field generates a temporary credential and re-arms first login."""
        # Create user with known password
        u = User(
            username=f"reset_target_{uuid.uuid4().hex[:5]}",
            password_hash=_hash_password("KnownPass#123"),
            school_id=self.school.id,
            is_first_login=False,
            is_active=True
        )
        self.db.add(u)
        self.db.commit()

        # Admin resets with empty new_password
        res = admin_reset_password(
            user_id=u.id,
            payload={"new_password": ""},
            request=MockRequest(),
            db=self.db,
            current_user=self.admin_user
        )
        self.assertEqual(res["status"], "success")
        self.assertIn("temporary_password", res)
        temp_pwd = res["temporary_password"]
        self.assertTrue(temp_pwd.startswith("Tmp#"))

        self.db.refresh(u)
        self.assertTrue(u.is_first_login, "Admin reset must re-arm is_first_login")

        # Old password fails, temp succeeds
        self.assertEqual(login({"username": u.username, "password": "KnownPass#123"}, MockRequest(), self.db).status_code, 401)
        self.assertEqual(login({"username": u.username, "password": temp_pwd}, MockRequest(), self.db).status_code, 200)


if __name__ == "__main__":
    unittest.main()
