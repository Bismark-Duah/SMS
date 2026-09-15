"""
tests/test_tenant_user_authorization.py
Regression tests for Prompt 1: Cross-Tenant User Authorization Hardening.

Covers:
1. Same-school admin operations (role update, status toggle, password reset, deletion).
2. Cross-school admin operations denial (404 Not Found to prevent tenant user enumeration).
3. Super-admin cross-school management access.
4. Ordinary admin blocked from managing or deleting super-admin accounts (403 Forbidden).
5. X-School-Id / school_id query parameter spoofing immunity for ordinary admins.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models import Base, School, User, Role
from backend.app.routes.auth import (
    update_user_roles,
    delete_user,
    admin_reset_password,
    set_user_status,
    list_users,
    create_user,
)


class TestTenantUserAuthorization(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Seed Schools
        self.sch1 = School(id=1, name="School Alpha", code="SA", status="ACTIVE")
        self.sch2 = School(id=2, name="School Beta", code="SB", status="ACTIVE")
        self.session.add_all([self.sch1, self.sch2])

        # Seed Roles
        self.admin_role = Role(id=1, name="admin")
        self.super_role = Role(id=2, name="super_admin")
        self.teacher_role = Role(id=3, name="teacher")
        self.session.add_all([self.admin_role, self.super_role, self.teacher_role])
        self.session.commit()

        # Seed Users
        # Super Admin (no school restriction)
        self.super_admin = User(
            id=1,
            username="superadmin",
            email="super@sms.local",
            password_hash="mock_hash",
            school_id=None,
            is_active=True,
        )
        self.super_admin.roles.append(self.super_role)

        # Admin 1 (School 1)
        self.admin1 = User(
            id=10,
            username="admin_alpha",
            email="admin@alpha.edu",
            password_hash="mock_hash",
            school_id=1,
            is_active=True,
        )
        self.admin1.roles.append(self.admin_role)

        # Teacher 1 (School 1)
        self.teacher1 = User(
            id=11,
            username="teacher_alpha",
            email="teacher@alpha.edu",
            password_hash="mock_hash",
            school_id=1,
            is_active=True,
        )
        self.teacher1.roles.append(self.teacher_role)

        # Admin 2 (School 2)
        self.admin2 = User(
            id=20,
            username="admin_beta",
            email="admin@beta.edu",
            password_hash="mock_hash",
            school_id=2,
            is_active=True,
        )
        self.admin2.roles.append(self.admin_role)

        # Teacher 2 (School 2)
        self.teacher2 = User(
            id=21,
            username="teacher_beta",
            email="teacher@beta.edu",
            password_hash="mock_hash",
            school_id=2,
            is_active=True,
        )
        self.teacher2.roles.append(self.teacher_role)

        self.session.add_all([
            self.super_admin, self.admin1, self.teacher1, self.admin2, self.teacher2
        ])
        self.session.commit()

    def tearDown(self):
        self.session.close()

    # ── 1. Same-School Authorization (Must Succeed) ───────────────────────────

    def test_same_school_admin_can_update_roles(self):
        res = update_user_roles(
            user_id=self.teacher1.id,
            payload={"roles": ["teacher"]},
            db=self.session,
            current_user=self.admin1,
        )
        self.assertEqual(res["status"], "success")

    def test_same_school_admin_can_reset_password(self):
        res = admin_reset_password(
            user_id=self.teacher1.id,
            payload={"new_password": "NewSecurePassword123!"},
            db=self.session,
            current_user=self.admin1,
        )
        self.assertEqual(res["status"], "success")

    def test_same_school_admin_can_change_status(self):
        res = set_user_status(
            user_id=self.teacher1.id,
            payload={"is_active": False},
            db=self.session,
            current_user=self.admin1,
        )
        self.assertEqual(res["status"], "success")
        self.assertFalse(self.teacher1.is_active)

    def test_same_school_admin_can_delete_user(self):
        res = delete_user(
            user_id=self.teacher1.id,
            db=self.session,
            current_user=self.admin1,
        )
        self.assertEqual(res["status"], "success")
        deleted = self.session.query(User).filter(User.id == self.teacher1.id).first()
        self.assertIsNone(deleted)

    # ── 2. Cross-School Authorization (Must Be Denied with 404) ───────────────

    def test_cross_school_admin_cannot_update_roles(self):
        # Admin 1 (School 1) tries to update roles of Teacher 2 (School 2)
        with self.assertRaises(HTTPException) as ctx:
            update_user_roles(
                user_id=self.teacher2.id,
                payload={"roles": ["admin"]},
                db=self.session,
                current_user=self.admin1,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_cross_school_admin_cannot_reset_password(self):
        # Admin 1 (School 1) tries to reset password of Teacher 2 (School 2)
        with self.assertRaises(HTTPException) as ctx:
            admin_reset_password(
                user_id=self.teacher2.id,
                payload={"new_password": "HackedPassword123!"},
                db=self.session,
                current_user=self.admin1,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_cross_school_admin_cannot_deactivate_user(self):
        # Admin 1 (School 1) tries to deactivate Teacher 2 (School 2)
        with self.assertRaises(HTTPException) as ctx:
            set_user_status(
                user_id=self.teacher2.id,
                payload={"is_active": False},
                db=self.session,
                current_user=self.admin1,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_cross_school_admin_cannot_delete_user(self):
        # Admin 1 (School 1) tries to delete Teacher 2 (School 2)
        with self.assertRaises(HTTPException) as ctx:
            delete_user(
                user_id=self.teacher2.id,
                db=self.session,
                current_user=self.admin1,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    # ── 3. Ordinary Admin Cannot Manage Super Admin (403 Forbidden) ───────────

    def test_ordinary_admin_cannot_delete_super_admin(self):
        with self.assertRaises(HTTPException) as ctx:
            delete_user(
                user_id=self.super_admin.id,
                db=self.session,
                current_user=self.admin1,
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_ordinary_admin_cannot_reset_super_admin_password(self):
        with self.assertRaises(HTTPException) as ctx:
            admin_reset_password(
                user_id=self.super_admin.id,
                payload={"new_password": "HackedPassword123!"},
                db=self.session,
                current_user=self.admin1,
            )
        self.assertEqual(ctx.exception.status_code, 403)

    # ── 4. Super-Admin Cross-School Access (Must Succeed) ─────────────────────

    def test_super_admin_can_manage_any_school_user(self):
        # Super Admin updates Teacher 2 (School 2)
        res = update_user_roles(
            user_id=self.teacher2.id,
            payload={"roles": ["teacher"]},
            db=self.session,
            current_user=self.super_admin,
        )
        self.assertEqual(res["status"], "success")

        # Super Admin resets Teacher 1 (School 1) password
        res2 = admin_reset_password(
            user_id=self.teacher1.id,
            payload={"new_password": "SuperReset123!"},
            db=self.session,
            current_user=self.super_admin,
        )
        self.assertEqual(res2["status"], "success")

    # ── 5. Anti-Spoofing: X-School-Id Header Immunity ─────────────────────────

    def test_ordinary_admin_cannot_spoof_x_school_id_to_list_other_users(self):
        # Admin 1 belongs to School 1, but sends X-School-Id: 2
        users = list_users(
            db=self.session,
            current_user=self.admin1,
            school_id=None,
            x_school_id="2",
        )
        # Must only receive School 1 users, ignoring the spoofed header
        school_ids = {u.school_id for u in users}
        self.assertEqual(school_ids, {1})
        self.assertNotIn(self.teacher2.id, [u.id for u in users])

    def test_ordinary_admin_cannot_spoof_school_in_create_user(self):
        # Admin 1 belongs to School 1, tries to create a user in School 2
        new_u = create_user(
            payload={
                "username": "intruder_user",
                "email": "intruder@alpha.edu",
                "password": "Password123!",
                "roles": ["teacher"],
                "school_id": 2,
            },
            db=self.session,
            current_user=self.admin1,
            school_id=2,
            x_school_id="2",
        )
        # Must be locked to Admin 1's school (School 1)
        self.assertEqual(new_u.school_id, 1)


if __name__ == "__main__":
    unittest.main()
