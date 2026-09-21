"""
tests/test_password_reset_token_hardening.py

Regression test suite for Fix 4: Enforce Password Reset Token Expiry (P0).
Verifies:
1. Strict 10-minute TTL enforcement (expired tokens rejected with HTTP 401).
2. Immediate replay attack mitigation (consumed token cannot be used again).
3. Persistent nonce revocation survival across process restarts (cleared in-memory cache).
4. Token version invalidation (prior tokens invalidated when credentials rotated).
5. Token scope integrity (standard auth access tokens rejected for password reset).
"""

import unittest
import os
import sys
import uuid
import time
from starlette.datastructures import Headers

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

from backend.app.database import SessionLocal, run_migrations
from backend.app.models import School, User, Role, RevokedResetToken
from backend.app.services.auth import hash_password, create_jwt
from backend.app.routes.auth import (
    reset_forgot_password,
    _used_recovery_jtis
)
from fastapi import HTTPException


class MockRequest:
    def __init__(self, client_ip="127.0.0.1"):
        self.client = type("Client", (), {"host": client_ip})()
        self.headers = Headers({"x-forwarded-for": client_ip})


class TestPasswordResetTokenHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_migrations()

    def setUp(self):
        self.db = SessionLocal()
        self.school = School(
            name="Token Expiry Hardening School",
            code=f"EXP_{uuid.uuid4().hex[:6]}",
            school_mode="COMBINED",
            ownership_type="PRIVATE"
        )
        self.db.add(self.school)
        self.db.commit()

        role = self.db.query(Role).filter(Role.name == "teacher").first()
        if not role:
            role = Role(name="teacher")
            self.db.add(role)
            self.db.commit()

        self.user = User(
            username=f"token_user_{uuid.uuid4().hex[:6]}",
            phone_number="0244998877",
            password_hash=hash_password("OriginalPassword123!"),
            school_id=self.school.id,
            is_active=True,
            is_first_login=False,
            token_version=1
        )
        self.user.roles = [role]
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def _generate_reset_token(self, user: User, expires_in: int = 600, jti: str = None, token_version: int = None, scope: str = "password_reset"):
        jti = jti or uuid.uuid4().hex
        ver = token_version if token_version is not None else (getattr(user, "token_version", 1) or 1)
        return create_jwt(
            payload={
                "sub": str(user.id),
                "user_id": user.id,
                "username": user.username,
                "scope": scope,
                "jti": jti,
                "token_version": ver
            },
            expires_in=expires_in
        )

    def test_01_token_strict_expiry_after_ttl(self):
        """Expired tokens (past 10-min TTL) are strictly rejected with HTTP 401."""
        # Generate token with negative TTL (already expired)
        expired_token = self._generate_reset_token(self.user, expires_in=-10)

        with self.assertRaises(HTTPException) as ctx:
            reset_forgot_password(
                payload={
                    "reset_token": expired_token,
                    "new_password": "BrandNewPassword123!",
                    "confirm_password": "BrandNewPassword123!"
                },
                request=MockRequest(),
                db=self.db
            )
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("expired", ctx.exception.detail.lower())

    def test_02_token_single_use_immediate_replay_blocked(self):
        """A single reset token can only be consumed once; immediate replay is blocked."""
        token = self._generate_reset_token(self.user, expires_in=600)

        # 1. First consumption succeeds
        res = reset_forgot_password(
            payload={
                "reset_token": token,
                "new_password": "NewSecretPass123!",
                "confirm_password": "NewSecretPass123!"
            },
            request=MockRequest(),
            db=self.db
        )
        self.assertEqual(res["status"], "success")

        # 2. Immediate replay attempt fails with HTTP 401
        with self.assertRaises(HTTPException) as ctx:
            reset_forgot_password(
                payload={
                    "reset_token": token,
                    "new_password": "AttackerReplayPassword123!",
                    "confirm_password": "AttackerReplayPassword123!"
                },
                request=MockRequest(),
                db=self.db
            )
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("already been used", ctx.exception.detail.lower())

    def test_03_token_replay_blocked_across_server_reboot(self):
        """Persistent database registry prevents replay even after in-memory cache is flushed (reboot)."""
        token = self._generate_reset_token(self.user, expires_in=600)

        # 1. Consume token
        res = reset_forgot_password(
            payload={
                "reset_token": token,
                "new_password": "FirstNewPassword123!",
                "confirm_password": "FirstNewPassword123!"
            },
            request=MockRequest(),
            db=self.db
        )
        self.assertEqual(res["status"], "success")

        # 2. Simulate server restart: flush in-memory set
        _used_recovery_jtis.clear()

        # 3. Attempt replay - must be caught by persistent RevokedResetToken registry
        with self.assertRaises(HTTPException) as ctx:
            reset_forgot_password(
                payload={
                    "reset_token": token,
                    "new_password": "RebootAttackerPass123!",
                    "confirm_password": "RebootAttackerPass123!"
                },
                request=MockRequest(),
                db=self.db
            )
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("already been used", ctx.exception.detail.lower())

    def test_04_token_version_mismatch_rejects_stale_token(self):
        """Tokens issued with a prior token_version are rejected if user changed password in between."""
        stale_token = self._generate_reset_token(self.user, expires_in=600, token_version=1)

        # Advance user token_version (e.g. from password change or admin reset)
        self.user.token_version = 2
        self.db.commit()

        with self.assertRaises(HTTPException) as ctx:
            reset_forgot_password(
                payload={
                    "reset_token": stale_token,
                    "new_password": "StaleTokenNewPass123!",
                    "confirm_password": "StaleTokenNewPass123!"
                },
                request=MockRequest(),
                db=self.db
            )
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("expired due to a prior password change", ctx.exception.detail.lower())

    def test_05_invalid_scope_rejected(self):
        """Standard auth tokens (scope='access' or None) cannot be used for password reset."""
        invalid_scope_token = self._generate_reset_token(self.user, expires_in=600, scope="access")

        with self.assertRaises(HTTPException) as ctx:
            reset_forgot_password(
                payload={
                    "reset_token": invalid_scope_token,
                    "new_password": "WrongScopePass123!",
                    "confirm_password": "WrongScopePass123!"
                },
                request=MockRequest(),
                db=self.db
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("scope", ctx.exception.detail.lower())


if __name__ == "__main__":
    unittest.main()
