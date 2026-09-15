"""
tests/test_default_credentials_hardening.py
Regression tests for Prompt 3: Elimination of Hardcoded Default Credentials & Backdoors.

Covers:
1. Proving that the hardcoded backdoor is eliminated: if a user changes their password,
   attempting to log in with "superadmin123!" or "Superadmin123!" returns 401 Unauthorized.
2. Proving that legitimate passwords succeed.
3. Proving that in production mode without INITIAL_SUPERADMIN_PASSWORD, universal default accounts are not created.
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from backend.app.models import Base, User, Role
from backend.app.routes.auth import login, _seed_db, _hash_password


class DummyClient:
    host = "127.0.0.1"


class DummyRequest:
    client = DummyClient()


class TestDefaultCredentialsHardening(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Seed roles
        self.super_role = Role(id=1, name="super_admin")
        self.session.add(self.super_role)
        self.session.commit()

        # Seed superadmin with custom strong password
        self.custom_password = "CustomSuperStrongPassword#2026!"
        self.superadmin = User(
            id=1,
            username="superadmin",
            email="superadmin@system.local",
            password_hash=_hash_password(self.custom_password),
            school_id=None,
            is_active=True,
        )
        self.superadmin.roles.append(self.super_role)
        self.session.add(self.superadmin)
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_legacy_default_password_backdoor_is_rejected(self):
        # Attacker tries the old hardcoded default passwords
        for bad_pwd in ["superadmin123!", "Superadmin123!"]:
            res = login(
                payload={"username": "superadmin", "password": bad_pwd},
                request=DummyRequest(),
                db=self.session
            )
            self.assertEqual(res.status_code, 401)
            # Verify the password hash was NOT reverted in the database
            self.session.refresh(self.superadmin)
            self.assertNotEqual(self.superadmin.password_hash, bad_pwd)

    def test_legitimate_custom_password_succeeds(self):
        res = login(
            payload={"username": "superadmin", "password": self.custom_password},
            request=DummyRequest(),
            db=self.session
        )
        import json
        self.assertEqual(res.status_code, 200)
        body = json.loads(res.body.decode("utf-8"))
        self.assertEqual(body.get("username"), "superadmin")
        self.assertIn("access_token", body)

    def test_production_environment_blocks_universal_defaults(self):
        # Empty the database
        self.session.query(User).delete()
        self.session.commit()

        # In production mode without INITIAL_SUPERADMIN_PASSWORD, _seed_db must not create default account
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "INITIAL_SUPERADMIN_PASSWORD": ""}):
            _seed_db(self.session)
            superadmin_user = self.session.query(User).filter(User.username == "superadmin").first()
            self.assertIsNone(superadmin_user)


if __name__ == "__main__":
    unittest.main()
