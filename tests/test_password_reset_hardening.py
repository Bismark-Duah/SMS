"""
Tests for Prompt 6: Password Reset & Session Invalidation Hardening
Audits administrative password reset, self-service recovery, token expiration,
single-use JTI burning, cross-tenant isolation, and immediate session invalidation.
"""
import unittest
import uuid
import time
from unittest.mock import MagicMock
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import User, Role, School, UserDeviceSession
from backend.app.services.auth import hash_password, create_jwt
from backend.app.routes.auth import (
    admin_reset_password,
    change_password,
    set_user_status,
    reset_forgot_password,
    _used_recovery_jtis,
    _verify_password
)
from backend.app.dependencies import get_current_user

class TestPasswordResetHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        self.db = self.Session()

        # Seed core roles
        self.roles = {}
        for r_name in ["super_admin", "admin", "teacher", "student"]:
            r = self.db.query(Role).filter(Role.name == r_name).first()
            if not r:
                r = Role(name=r_name)
                self.db.add(r)
                self.db.flush()
            self.roles[r_name] = r

        # Seed schools
        self.school_a = School(name="Reset School A", code=f"RSA-{uuid.uuid4().hex[:4]}", school_mode="BASIC")
        self.school_b = School(name="Reset School B", code=f"RSB-{uuid.uuid4().hex[:4]}", school_mode="BASIC")
        self.db.add_all([self.school_a, self.school_b])
        self.db.commit()

        # Seed users
        self.superadmin = User(
            username="super_reset",
            email="super_reset@system.local",
            password_hash=hash_password("SuperSecret123!"),
            school_id=None,
            is_active=True,
            token_version=1
        )
        self.admin_a = User(
            username="admin_a",
            email="admin_a@schoola.local",
            password_hash=hash_password("AdminPass123!"),
            school_id=self.school_a.id,
            is_active=True,
            token_version=1
        )

        self.teacher_a = User(
            username="teacher_a",
            email="teacher_a@schoola.local",
            password_hash=hash_password("TeacherPass123!"),
            school_id=self.school_a.id,
            is_active=True,
            token_version=1
        )

        self.teacher_b = User(
            username="teacher_b",
            email="teacher_b@schoolb.local",
            password_hash=hash_password("TeacherBPass123!"),
            school_id=self.school_b.id,
            is_active=True,
            token_version=1
        )

        self.db.add_all([self.superadmin, self.admin_a, self.teacher_a, self.teacher_b])
        self.superadmin.roles = [self.roles["super_admin"]]
        self.admin_a.roles = [self.roles["admin"]]
        self.teacher_a.roles = [self.roles["teacher"]]
        self.teacher_b.roles = [self.roles["teacher"]]
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_unauthorized_user_cannot_invoke_admin_reset(self):
        """Ordinary non-admin users must be rejected with 403 Forbidden."""
        with self.assertRaises(HTTPException) as ctx:
            admin_reset_password(
                user_id=self.teacher_a.id,
                payload={"new_password": "NewSecret123!"},
                db=self.db,
                current_user=self.teacher_a
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_cross_tenant_admin_reset_prevented(self):
        """School A admin resetting School B user must return 404 to prevent user enumeration."""
        with self.assertRaises(HTTPException) as ctx:
            admin_reset_password(
                user_id=self.teacher_b.id,
                payload={"new_password": "HackedPass123!"},
                db=self.db,
                current_user=self.admin_a
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_school_admin_cannot_reset_superadmin(self):
        """School admin attempting to reset super_admin must return 403 Forbidden."""
        with self.assertRaises(HTTPException) as ctx:
            admin_reset_password(
                user_id=self.superadmin.id,
                payload={"new_password": "HackedSuperPass!"},
                db=self.db,
                current_user=self.admin_a
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_admin_reset_invalidates_sessions_and_increments_token_version(self):
        """Admin resetting password must advance token_version and invalidate old sessions."""
        # 1. Create active device session and token for teacher_a
        old_token = create_jwt({
            "user_id": self.teacher_a.id,
            "username": self.teacher_a.username,
            "school_id": self.school_a.id,
            "roles": ["teacher"],
            "token_version": 1
        })
        import hashlib
        old_token_hash = hashlib.sha256(old_token.encode("utf-8")).hexdigest()
        session_rec = UserDeviceSession(
            user_id=self.teacher_a.id,
            device_fingerprint="fp-test-1",
            session_token_hash=old_token_hash,
            device_name="Chrome on Windows PC",
            is_active=True
        )
        self.db.add(session_rec)
        self.db.commit()

        # Verify old token works before reset
        authed_user = get_current_user(f"Bearer {old_token}", self.db)
        self.assertEqual(authed_user.id, self.teacher_a.id)

        # 2. Admin resets teacher_a password
        initial_version = self.teacher_a.token_version
        res = admin_reset_password(
            user_id=self.teacher_a.id,
            payload={"new_password": "BrandNewSecret123!"},
            db=self.db,
            current_user=self.admin_a
        )
        self.assertEqual(res["status"], "success")

        # 3. Assert database updates
        self.db.refresh(self.teacher_a)
        self.db.refresh(session_rec)
        self.assertGreater(self.teacher_a.token_version, initial_version)
        self.assertFalse(session_rec.is_active, "Device session must be deactivated")

        # 4. Old JWT token must now be rejected with 401
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(f"Bearer {old_token}", self.db)
        self.assertEqual(ctx.exception.status_code, 401)

        # 5. New password works
        valid, _ = _verify_password("BrandNewSecret123!", self.teacher_a.password_hash)
        self.assertTrue(valid)

    def test_change_password_invalidates_previous_sessions(self):
        """User changing their own password advances token_version and invalidates previous token."""
        old_token = create_jwt({
            "user_id": self.teacher_a.id,
            "username": self.teacher_a.username,
            "school_id": self.school_a.id,
            "roles": ["teacher"],
            "token_version": 1
        })
        import hashlib
        old_token_hash = hashlib.sha256(old_token.encode("utf-8")).hexdigest()
        session_rec = UserDeviceSession(
            user_id=self.teacher_a.id,
            device_fingerprint="fp-test-2",
            session_token_hash=old_token_hash,
            device_name="Firefox on Desktop",
            is_active=True
        )
        self.db.add(session_rec)
        self.db.commit()

        initial_ver = self.teacher_a.token_version
        res = change_password(
            payload={"old_password": "TeacherPass123!", "new_password": "ChangedTeacherPass99!"},
            db=self.db,
            current_user=self.teacher_a
        )
        self.assertEqual(res["status"], "success")

        self.db.refresh(self.teacher_a)
        self.db.refresh(session_rec)
        self.assertGreater(self.teacher_a.token_version, initial_ver)
        self.assertFalse(session_rec.is_active)

        # Old token fails
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(f"Bearer {old_token}", self.db)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_user_deactivation_invalidates_sessions_immediately(self):
        """Deactivating an account immediately invalidates active sessions and raises 401."""
        old_token = create_jwt({
            "user_id": self.teacher_a.id,
            "username": self.teacher_a.username,
            "school_id": self.school_a.id,
            "roles": ["teacher"],
            "token_version": 1
        })
        import hashlib
        session_rec = UserDeviceSession(
            user_id=self.teacher_a.id,
            device_fingerprint="fp-test-3",
            session_token_hash=hashlib.sha256(old_token.encode("utf-8")).hexdigest(),
            device_name="Safari on iPhone",
            is_active=True
        )
        self.db.add(session_rec)
        self.db.commit()

        # Admin deactivates user
        res = set_user_status(
            user_id=self.teacher_a.id,
            payload={"is_active": False},
            db=self.db,
            current_user=self.admin_a
        )
        self.assertEqual(res["status"], "success")

        self.db.refresh(self.teacher_a)
        self.db.refresh(session_rec)
        self.assertFalse(self.teacher_a.is_active)
        self.assertFalse(session_rec.is_active)

        # Access with old token fails with 401 deactivated
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(f"Bearer {old_token}", self.db)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_self_service_reset_token_expiration_and_single_use(self):
        """Self-service recovery token cannot be reused and expired token is rejected."""
        req = MagicMock()
        
        # 1. Expired token check
        expired_token = create_jwt(
            payload={
                "sub": str(self.teacher_a.id),
                "user_id": self.teacher_a.id,
                "username": self.teacher_a.username,
                "scope": "password_reset",
                "jti": uuid.uuid4().hex,
            },
            expires_in=-60  # Already expired
        )
        with self.assertRaises(HTTPException) as ctx:
            reset_forgot_password(
                payload={"reset_token": expired_token, "new_password": "NewExpiredPass123!"},
                request=req,
                db=self.db
            )
        self.assertEqual(ctx.exception.status_code, 401)

        # 2. Legitimate reset token
        fresh_jti = uuid.uuid4().hex
        valid_token = create_jwt(
            payload={
                "sub": str(self.teacher_a.id),
                "user_id": self.teacher_a.id,
                "username": self.teacher_a.username,
                "scope": "password_reset",
                "jti": fresh_jti,
            },
            expires_in=600
        )

        res = reset_forgot_password(
            payload={
                "reset_token": valid_token,
                "new_password": "SelfServicePass2026!",
                "confirm_password": "SelfServicePass2026!"
            },
            request=req,
            db=self.db
        )
        self.assertEqual(res["status"], "success")
        self.assertIn(fresh_jti, _used_recovery_jtis)

        # 3. Replay attack: Reusing the same token must be rejected with 401
        with self.assertRaises(HTTPException) as ctx:
            reset_forgot_password(
                payload={
                    "reset_token": valid_token,
                    "new_password": "ReplayAttackerPass!",
                    "confirm_password": "ReplayAttackerPass!"
                },
                request=req,
                db=self.db
            )
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("already been used", ctx.exception.detail)

if __name__ == "__main__":
    unittest.main()
