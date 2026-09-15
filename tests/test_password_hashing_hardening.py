"""
Tests for Prompt 5: Password Hashing Hardening & Legacy Migration
Validates modern bcrypt enforcement, removal of weak fallbacks,
and transparent upgrade of legacy SHA-256 password hashes upon authentication.
"""
import unittest
import hashlib
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import Request

from backend.app.database import Base
from backend.app.models import User, Role, School, Student
from backend.app.services.auth import hash_password, verify_password
from backend.app.routes.auth import _hash_password, _verify_password, login
from backend.app.services.guardian_service import auto_link_guardian_for_student

class TestPasswordHashingHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.Session()
        # Ensure base roles exist
        for role_name in ["super_admin", "admin", "teacher", "student", "parent"]:
            if not self.db.query(Role).filter(Role.name == role_name).first():
                self.db.add(Role(name=role_name))
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_hash_password_produces_modern_bcrypt(self):
        """Newly created passwords must always be modern bcrypt hashes."""
        password = "SecurePassword2026!"
        h = hash_password(password)
        self.assertTrue(h.startswith("$2b$") or h.startswith("$2a$"), f"Expected bcrypt hash, got: {h}")
        self.assertGreaterEqual(len(h), 59)

        # Re-verify through auth.py alias
        h2 = _hash_password(password)
        self.assertTrue(h2.startswith("$2b$") or h2.startswith("$2a$"))

    def test_hash_password_rejects_invalid_inputs(self):
        """Empty or invalid passwords must be rejected."""
        with self.assertRaises(ValueError):
            hash_password("")
        with self.assertRaises(ValueError):
            hash_password(None)

    def test_verify_password_bcrypt_flow(self):
        """Valid bcrypt passwords verify successfully without needing rehash."""
        password = "CorrectHorseBatteryStaple!"
        h = hash_password(password)
        
        is_valid, needs_rehash = verify_password(password, h)
        self.assertTrue(is_valid)
        self.assertFalse(needs_rehash, "Modern bcrypt should not request a rehash")

        # Invalid password check
        is_valid, needs_rehash = verify_password("WrongPassword!", h)
        self.assertFalse(is_valid)
        self.assertFalse(needs_rehash)

    def test_legacy_sha256_detection_and_rehash_flag(self):
        """Legacy 64-char SHA-256 hashes must be verified and flagged for upgrade."""
        raw_password = "LegacyUserSecret123"
        legacy_hash = hashlib.sha256(raw_password.encode("utf-8")).hexdigest()
        self.assertEqual(len(legacy_hash), 64)

        # Correct password on legacy hash
        is_valid, needs_rehash = verify_password(raw_password, legacy_hash)
        self.assertTrue(is_valid, "Legacy hash should verify successfully")
        self.assertTrue(needs_rehash, "Legacy hash MUST trigger needs_rehash for upgrade")

        # Wrong password on legacy hash
        is_valid, needs_rehash = verify_password("WrongPassword!", legacy_hash)
        self.assertFalse(is_valid)
        self.assertFalse(needs_rehash)

    def test_login_transparently_upgrades_legacy_hash_to_bcrypt(self):
        """When a legacy SHA-256 user logs in, their stored hash is transparently upgraded to bcrypt."""
        # 1. Create a school and legacy user
        school = School(name="Migration Academy", code="MIG001", school_mode="BASIC")
        self.db.add(school)
        self.db.flush()

        raw_password = "MyOldLegacyPassword999!"
        legacy_sha256 = hashlib.sha256(raw_password.encode("utf-8")).hexdigest()

        teacher_role = self.db.query(Role).filter(Role.name == "teacher").first()
        user = User(
            username="legacy_teacher",
            email="legacy@migration.local",
            password_hash=legacy_sha256,
            school_id=school.id,
            is_active=True,
        )
        user.roles.append(teacher_role)
        self.db.add(user)
        self.db.commit()

        # Verify initial database state has the 64-character SHA-256 hash
        db_user = self.db.query(User).filter(User.username == "legacy_teacher").first()
        self.assertEqual(db_user.password_hash, legacy_sha256)

        # 2. Perform login
        req = MagicMock(spec=Request)
        req.client = MagicMock(host="127.0.0.1")
        req.headers = {}
        
        login_res = login(
            payload={"username": "legacy_teacher", "password": raw_password},
            request=req,
            db=self.db
        )

        # If JSONResponse or dict returned, verify it's not a 401
        if hasattr(login_res, "status_code"):
            self.assertEqual(login_res.status_code, 200)

        # 3. Verify user's hash in database was automatically upgraded to bcrypt!
        self.db.refresh(db_user)
        self.assertNotEqual(db_user.password_hash, legacy_sha256)
        self.assertTrue(
            db_user.password_hash.startswith("$2b$") or db_user.password_hash.startswith("$2a$"),
            f"Stored hash was not upgraded to bcrypt: {db_user.password_hash}"
        )

        # 4. Perform a second login with the newly upgraded bcrypt hash
        second_login_res = login(
            payload={"username": "legacy_teacher", "password": raw_password},
            request=req,
            db=self.db
        )
        if hasattr(second_login_res, "status_code"):
            self.assertEqual(second_login_res.status_code, 200)

    def test_guardian_service_creates_bcrypt_passwords(self):
        """Parent accounts auto-provisioned by guardian_service must use bcrypt hashes."""
        school = School(name="Guardian Test School", code="GRD001", school_mode="BASIC")
        self.db.add(school)
        self.db.flush()

        student = Student(
            student_code="STD001",
            full_name="Kwame Mensah",
            first_name="Kwame",
            last_name="Mensah",
            school_id=school.id,
            guardian_name="Kofi Mensah",
            phone="0241234567"
        )
        self.db.add(student)
        self.db.commit()

        parent_user = auto_link_guardian_for_student(self.db, student, auto_create=True)
        self.assertIsNotNone(parent_user)
        self.assertTrue(
            parent_user.password_hash.startswith("$2b$") or parent_user.password_hash.startswith("$2a$"),
            f"Guardian password should be bcrypt, got: {parent_user.password_hash}"
        )
        # Verify parent can authenticate with default password "Parent123"
        is_valid, needs_rehash = verify_password("Parent123", parent_user.password_hash)
        self.assertTrue(is_valid)
        self.assertFalse(needs_rehash)

if __name__ == "__main__":
    unittest.main()
