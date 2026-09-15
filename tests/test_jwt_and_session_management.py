"""
Tests for Prompt 7: JWT and Session Management Hardening
Audits strong secret key validation in production, token expiration,
signature integrity, server-side logout, school suspension enforcement,
and multi-device concurrency rules.
"""
import unittest
import os
import uuid
import hashlib
from unittest.mock import MagicMock
from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import User, Role, School, UserDeviceSession
from backend.app.services.auth import (
    create_jwt,
    decode_jwt,
    hash_password,
    get_secret_key,
    DEFAULT_INSECURE_SECRET
)
from backend.app.routes.auth import logout, login
from backend.app.dependencies import get_current_user
from backend.app.middleware.device_session_guard import register_device_session, is_session_active

class TestJWTAndSessionManagement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        self.db = self.Session()

        # Seed roles
        self.roles = {}
        for r_name in ["super_admin", "admin", "teacher", "student", "parent"]:
            r = Role(name=r_name)
            self.db.add(r)
            self.roles[r_name] = r
        self.db.commit()

        # Seed schools
        self.school_active = School(name="Active Academy", code=f"ACT-{uuid.uuid4().hex[:4]}", status="ACTIVE", school_mode="BASIC")
        self.school_suspended = School(name="Suspended Academy", code=f"SUS-{uuid.uuid4().hex[:4]}", status="SUSPENDED", school_mode="BASIC")
        self.db.add_all([self.school_active, self.school_suspended])
        self.db.commit()

        # Seed users
        self.teacher_active = User(
            username="active_teacher",
            email="teacher@active.local",
            password_hash=hash_password("TeacherPass123!"),
            school_id=self.school_active.id,
            is_active=True,
            token_version=1
        )
        self.teacher_suspended = User(
            username="suspended_teacher",
            email="teacher@suspended.local",
            password_hash=hash_password("SuspendedPass123!"),
            school_id=self.school_suspended.id,
            is_active=True,
            token_version=1
        )
        self.superadmin = User(
            username="super_user",
            email="super@master.local",
            password_hash=hash_password("SuperPass123!"),
            school_id=None,
            is_active=True,
            token_version=1
        )

        self.db.add_all([self.teacher_active, self.teacher_suspended, self.superadmin])
        self.teacher_active.roles = [self.roles["teacher"]]
        self.teacher_suspended.roles = [self.roles["teacher"]]
        self.superadmin.roles = [self.roles["super_admin"]]
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_production_secret_key_refusal(self):
        """In production environment, default insecure secret key must raise RuntimeError."""
        old_env = os.environ.get("ENVIRONMENT")
        old_secret = os.environ.get("SECRET_KEY")
        try:
            os.environ["ENVIRONMENT"] = "production"
            os.environ["SECRET_KEY"] = DEFAULT_INSECURE_SECRET
            with self.assertRaises(RuntimeError):
                get_secret_key()

            # With custom strong secret, it succeeds
            os.environ["SECRET_KEY"] = "super-strong-production-random-secret-key-123456789"
            key = get_secret_key()
            self.assertEqual(key, "super-strong-production-random-secret-key-123456789")
        finally:
            if old_env is not None:
                os.environ["ENVIRONMENT"] = old_env
            else:
                os.environ.pop("ENVIRONMENT", None)
            if old_secret is not None:
                os.environ["SECRET_KEY"] = old_secret
            else:
                os.environ.pop("SECRET_KEY", None)

    def test_expired_jwt_rejected(self):
        """Expired JWT tokens must fail validation with 401."""
        expired_token = create_jwt(
            payload={
                "user_id": self.teacher_active.id,
                "username": self.teacher_active.username,
                "school_id": self.school_active.id,
                "roles": ["teacher"],
                "token_version": 1
            },
            expires_in=-60  # expired 60 seconds ago
        )
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(f"Bearer {expired_token}", self.db)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("expired", ctx.exception.detail.lower())

    def test_tampered_jwt_signature_rejected(self):
        """Tokens with modified payloads or tampered signatures must raise 401."""
        valid_token = create_jwt({
            "user_id": self.teacher_active.id,
            "username": self.teacher_active.username,
            "school_id": self.school_active.id,
            "roles": ["teacher"],
            "token_version": 1
        })
        parts = valid_token.split(".")
        # Tamper signature by replacing last 4 characters
        tampered_sig = parts[2][:-4] + "ABCD"
        tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"

        with self.assertRaises(HTTPException) as ctx:
            get_current_user(f"Bearer {tampered_token}", self.db)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_logout_endpoint_terminates_session(self):
        """POST /logout must mark device session inactive and reject subsequent requests."""
        token = create_jwt({
            "user_id": self.teacher_active.id,
            "username": self.teacher_active.username,
            "school_id": self.school_active.id,
            "roles": ["teacher"],
            "token_version": 1
        })
        # Register device session
        register_device_session(
            user_id=self.teacher_active.id,
            user_role="teacher",
            user_agent="Chrome on Windows PC",
            client_ip="127.0.0.1",
            token=token,
            db=self.db
        )

        # Confirm token is active
        authed = get_current_user(f"Bearer {token}", self.db)
        self.assertEqual(authed.id, self.teacher_active.id)

        # Call logout
        req = MagicMock(spec=Request)
        req.client = MagicMock(host="127.0.0.1")
        req.headers = {}
        res = logout(
            request=req,
            authorization=f"Bearer {token}",
            current_user=self.teacher_active,
            db=self.db
        )
        self.assertEqual(res["status"], "success")

        # Session should now be inactive
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        sess = self.db.query(UserDeviceSession).filter(UserDeviceSession.session_token_hash == token_hash).first()
        self.assertIsNotNone(sess)
        self.assertFalse(sess.is_active)

        # Subsequent request with logged-out token must raise 401
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(f"Bearer {token}", self.db)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Session terminated", ctx.exception.detail)

    def test_suspended_school_blocks_user_access(self):
        """Users from suspended institutions must be denied access with 403."""
        token = create_jwt({
            "user_id": self.teacher_suspended.id,
            "username": self.teacher_suspended.username,
            "school_id": self.school_suspended.id,
            "roles": ["teacher"],
            "token_version": 1
        })
        register_device_session(
            user_id=self.teacher_suspended.id,
            user_role="teacher",
            user_agent="Firefox on Windows PC",
            client_ip="127.0.0.1",
            token=token,
            db=self.db
        )

        with self.assertRaises(HTTPException) as ctx:
            get_current_user(f"Bearer {token}", self.db)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("suspended", ctx.exception.detail.lower())

    def test_multi_device_policy_for_staff(self):
        """Staff logging in from a second device must invalidate their previous session."""
        token1 = create_jwt({"user_id": self.teacher_active.id, "username": self.teacher_active.username, "roles": ["teacher"], "token_version": 1})
        register_device_session(self.teacher_active.id, "teacher", "Chrome on Windows", "127.0.0.1", token1, self.db)
        self.assertTrue(is_session_active(token1, self.teacher_active.id, self.db))

        token2 = create_jwt({"user_id": self.teacher_active.id, "username": self.teacher_active.username, "roles": ["teacher"], "token_version": 1})
        register_device_session(self.teacher_active.id, "teacher", "Safari on Mac", "127.0.0.2", token2, self.db)

        # Second session is active, first session is terminated
        self.assertTrue(is_session_active(token2, self.teacher_active.id, self.db))
        self.assertFalse(is_session_active(token1, self.teacher_active.id, self.db))

        # First token now raises 401 in get_current_user
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(f"Bearer {token1}", self.db)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Session terminated", ctx.exception.detail)

if __name__ == "__main__":
    unittest.main()
