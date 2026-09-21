import unittest
import os
import sys
import uuid
import time
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

# Ensure backend imports work
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

from backend.app.database import engine, Base, SessionLocal, run_migrations
from backend.app.models import School, User, Role, Student, UserDeviceSession
from backend.app.routes.auth import (
    verify_forgot_password_identity,
    reset_forgot_password,
    _hash_password,
    _verify_password,
    _recovery_rate_limit,
    _used_recovery_jtis
)
from backend.app.services.auth import decode_jwt

class MockRequest:
    def __init__(self, client_ip="127.0.0.1"):
        self.client = type("Client", (), {"host": client_ip})()
        self.headers = Headers({})

class TestPasswordRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_migrations()
        cls.db: Session = SessionLocal()
        cls.suffix = uuid.uuid4().hex[:6]

        # 1. Ensure School
        cls.school = School(
            name=f"Recovery Test School {cls.suffix}",
            code=f"RTS-{cls.suffix}",
            school_mode="COMBINED"
        )
        cls.db.add(cls.school)
        cls.db.commit()
        cls.db.refresh(cls.school)

        # 2. Roles
        teacher_role = cls.db.query(Role).filter(Role.name == "teacher").first()
        student_role = cls.db.query(Role).filter(Role.name == "student").first()
        admin_role = cls.db.query(Role).filter(Role.name == "admin").first()

        # 3. Create Teacher User
        cls.teacher_user = User(
            username=f"teacher_{cls.suffix}",
            email=f"teacher_{cls.suffix}@school.local",
            phone_number="0244123456",
            staff_id=f"STF-{cls.suffix}",
            password_hash=_hash_password("OldPassword123!"),
            school_id=cls.school.id,
            roles=[teacher_role] if teacher_role else []
        )
        cls.db.add(cls.teacher_user)

        # 4. Create Student User & Profile
        cls.student_user = User(
            username=f"student_{cls.suffix}",
            email=f"student_{cls.suffix}@school.local",
            phone_number="0209998888",
            password_hash=_hash_password("StudentOldPass123!"),
            school_id=cls.school.id,
            roles=[student_role] if student_role else []
        )
        cls.db.add(cls.student_user)
        cls.db.flush()

        from datetime import datetime
        cls.student_profile = Student(
            student_code=cls.student_user.username,
            full_name="Kwame Mensah",
            first_name="Kwame",
            last_name="Mensah",
            date_of_birth=datetime(2008, 4, 15),
            phone="0209998888",
            parent_id=cls.student_user.id,
            school_id=cls.school.id
        )
        cls.db.add(cls.student_profile)

        # 5. Create Admin with Recovery PIN
        cls.admin_user = User(
            username=f"admin_rec_{cls.suffix}",
            email=f"admin_rec_{cls.suffix}@school.local",
            phone_number="0551122334",
            staff_id=f"ADM-{cls.suffix}",
            password_hash=_hash_password("AdminOldPass123!"),
            recovery_pin_hash=_hash_password("884422"),
            school_id=cls.school.id,
            roles=[admin_role] if admin_role else []
        )
        cls.db.add(cls.admin_user)

        # 6. Create SuperAdmin User
        super_admin_role = cls.db.query(Role).filter(Role.name == "super_admin").first()
        if not super_admin_role:
            super_admin_role = Role(name="super_admin", description="Super Admin")
            cls.db.add(super_admin_role)
            cls.db.flush()

        cls.super_admin_user = User(
            username=f"superadmin_{cls.suffix}",
            email=f"super_{cls.suffix}@platform.local",
            phone_number="0240000000",
            staff_id=f"ROOT-{cls.suffix}",
            password_hash=_hash_password("SuperSecret123!"),
            roles=[super_admin_role]
        )
        cls.db.add(cls.super_admin_user)
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_teacher_recovery_success(self):
        """Verify teacher can verify identity with username + phone + staff_id and reset password."""
        req = MockRequest(client_ip="192.168.1.50")
        
        # Step 1: Verify
        payload = {
            "username": self.teacher_user.username,
            "phone_number": "0244123456",
            "identifier": self.teacher_user.staff_id
        }
        res = verify_forgot_password_identity(payload, req, self.db)
        self.assertEqual(res["status"], "success")
        self.assertIn("reset_token", res)
        reset_token = res["reset_token"]

        # Step 2: Reset
        reset_payload = {
            "reset_token": reset_token,
            "new_password": "NewTeacherPass456!",
            "confirm_password": "NewTeacherPass456!"
        }
        reset_res = reset_forgot_password(reset_payload, req, self.db)
        self.assertEqual(reset_res["status"], "success")

        # Step 3: Verify new password matches in DB
        self.db.refresh(self.teacher_user)
        valid, _ = _verify_password("NewTeacherPass456!", self.teacher_user.password_hash)
        self.assertTrue(valid, "Teacher password was not updated to new password.")

    def test_02_student_recovery_success(self):
        """Verify student can verify identity with username + phone + DOB and reset password."""
        req = MockRequest(client_ip="192.168.1.51")

        payload = {
            "username": self.student_user.username,
            "phone_number": "0209998888",
            "identifier": "2008-04-15"
        }
        res = verify_forgot_password_identity(payload, req, self.db)
        self.assertEqual(res["status"], "success")
        reset_token = res["reset_token"]

        reset_payload = {
            "reset_token": reset_token,
            "new_password": "NewStudentPass789!",
            "confirm_password": "NewStudentPass789!"
        }
        reset_res = reset_forgot_password(reset_payload, req, self.db)
        self.assertEqual(reset_res["status"], "success")

        self.db.refresh(self.student_user)
        valid, _ = _verify_password("NewStudentPass789!", self.student_user.password_hash)
        self.assertTrue(valid, "Student password was not updated to new password.")

    def test_03_admin_recovery_with_pin(self):
        """Verify admin role verifies identity using secret Recovery PIN."""
        req = MockRequest(client_ip="192.168.1.52")

        payload = {
            "username": self.admin_user.username,
            "phone_number": "0551122334",
            "recovery_pin": "884422"
        }
        res = verify_forgot_password_identity(payload, req, self.db)
        self.assertEqual(res["status"], "success")
        reset_token = res["reset_token"]

        reset_payload = {
            "reset_token": reset_token,
            "new_password": "NewAdminPass999!",
            "confirm_password": "NewAdminPass999!"
        }
        reset_res = reset_forgot_password(reset_payload, req, self.db)
        self.assertEqual(reset_res["status"], "success")

        self.db.refresh(self.admin_user)
        valid, _ = _verify_password("NewAdminPass999!", self.admin_user.password_hash)
        self.assertTrue(valid)

    def test_04_wrong_phone_rejected(self):
        """Verify recovery is rejected when phone number does not match registered records."""
        from fastapi import HTTPException
        req = MockRequest(client_ip="192.168.1.53")

        payload = {
            "username": self.teacher_user.username,
            "phone_number": "0249999999",  # Wrong phone
            "identifier": self.teacher_user.staff_id
        }
        with self.assertRaises(HTTPException) as ctx:
            verify_forgot_password_identity(payload, req, self.db)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_05_token_replay_attack_rejected(self):
        """Verify that a consumed reset token cannot be replayed (single-use JTI)."""
        from fastapi import HTTPException
        req = MockRequest(client_ip="192.168.1.54")

        payload = {
            "username": self.teacher_user.username,
            "phone_number": "0244123456",
            "identifier": self.teacher_user.staff_id
        }
        res = verify_forgot_password_identity(payload, req, self.db)
        reset_token = res["reset_token"]

        # First use -> Success
        reset_payload = {
            "reset_token": reset_token,
            "new_password": "AnotherNewPass1!",
            "confirm_password": "AnotherNewPass1!"
        }
        reset_forgot_password(reset_payload, req, self.db)

        # Second use -> Must fail (HTTP 401 Replay Attack)
        with self.assertRaises(HTTPException) as ctx:
            reset_forgot_password(reset_payload, req, self.db)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_06_brute_force_lockout(self):
        """Verify rate limiting locks out attacker after 5 consecutive failed attempts."""
        from fastapi import HTTPException
        req = MockRequest(client_ip=f"10.0.0.{uuid.uuid4().int % 250}")
        victim_user = f"victim_{self.suffix}"

        # 5 failed attempts
        for _ in range(5):
            try:
                verify_forgot_password_identity({
                    "username": victim_user,
                    "phone_number": "0000000000",
                    "identifier": "bad_guess"
                }, req, self.db)
            except HTTPException:
                pass

        # 6th attempt must trigger HTTP 429 Too Many Requests (Lockout)
        with self.assertRaises(HTTPException) as ctx:
            verify_forgot_password_identity({
                "username": victim_user,
                "phone_number": "0000000000",
                "identifier": "bad_guess"
            }, req, self.db)
        self.assertEqual(ctx.exception.status_code, 429)

    def test_07_superadmin_recovery_forbidden(self):
        """Verify that SuperAdmin recovery is strictly forbidden via the web API."""
        from fastapi import HTTPException
        req = MockRequest(client_ip="192.168.1.99")
        payload = {
            "username": self.super_admin_user.username,
            "phone_number": self.super_admin_user.phone_number,
            "identifier": self.super_admin_user.staff_id
        }
        with self.assertRaises(HTTPException) as ctx:
            verify_forgot_password_identity(payload, req, self.db)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("SuperAdmin accounts cannot be reset via the web portal", ctx.exception.detail)

    def test_08_superadmin_reset_token_forbidden(self):
        """Verify that even with a forged or valid reset token, SuperAdmin cannot reset password via web API."""
        from fastapi import HTTPException
        from backend.app.services.auth import create_jwt
        req = MockRequest(client_ip="192.168.1.99")
        
        # Forge a password reset token for the super admin
        token = create_jwt(
            payload={
                "sub": str(self.super_admin_user.id),
                "user_id": self.super_admin_user.id,
                "username": self.super_admin_user.username,
                "scope": "password_reset",
                "jti": uuid.uuid4().hex,
                "token_version": 1
            },
            expires_in=600
        )
        reset_payload = {
            "reset_token": token,
            "new_password": "NewSuperAdminPass123!",
            "confirm_password": "NewSuperAdminPass123!"
        }
        with self.assertRaises(HTTPException) as ctx:
            reset_forgot_password(reset_payload, req, self.db)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("SuperAdmin accounts cannot be reset via the web portal", ctx.exception.detail)

if __name__ == "__main__":
    unittest.main()
