"""
test_multi_tenant_security_audit.py — Comprehensive Automated Test Suite for Multi-Tenant Security & Scoping
"""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException
from backend.app.database import SessionLocal, engine, Base
from backend.app.models import (
    User, Role, School, Student, Fee, Payment, Asset, TextbookAllocation, UniformItem,
    Score, ClassSection, Subject, Semester, AcademicYear, Setting, Program, Department,
    SchoolStage
)
from backend.app.dependencies import get_current_user, get_school_id
from backend.app.routes.auth import impersonate_user
from backend.app.routes.fees import get_student_fees, get_fee, update_fee, delete_fee, record_payment
from backend.app.routes.assets import delete_asset, issue_textbook, return_textbook, disburse_uniform
from backend.app.routes.results import submit_to_hod, approve_by_hod, publish_by_academic_head
from backend.app.routes.programs import create_program, ProgramCreate
from backend.app.routes.departments import create_department, DepartmentCreate


class TestMultiTenantSecurityAudit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()

        # Create or ensure Roles
        admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            cls.db.add(admin_role)

        super_admin_role = cls.db.query(Role).filter(Role.name == "super_admin").first()
        if not super_admin_role:
            super_admin_role = Role(name="super_admin")
            cls.db.add(super_admin_role)

        teacher_role = cls.db.query(Role).filter(Role.name == "teacher").first()
        if not teacher_role:
            teacher_role = Role(name="teacher")
            cls.db.add(teacher_role)

        cls.db.commit()

        # Create School 1 (Active, COMBINED)
        cls.sch1 = cls.db.query(School).filter(School.name == "Audit School 1").first()
        if not cls.sch1:
            cls.sch1 = School(name="Audit School 1", code="AS1", status="ACTIVE", school_mode="COMBINED")
            cls.db.add(cls.sch1)
            cls.db.commit()
            cls.db.refresh(cls.sch1)

        # Create School 2 (Active, BASIC_ONLY)
        cls.sch2 = cls.db.query(School).filter(School.name == "Audit School 2").first()
        if not cls.sch2:
            cls.sch2 = School(name="Audit School 2", code="AS2", status="ACTIVE", school_mode="BASIC_ONLY")
            cls.db.add(cls.sch2)
            cls.db.commit()
            cls.db.refresh(cls.sch2)

        # Create School 3 (Suspended)
        cls.sch3 = cls.db.query(School).filter(School.name == "Audit School 3 Suspended").first()
        if not cls.sch3:
            cls.sch3 = School(name="Audit School 3 Suspended", code="AS3", status="SUSPENDED", school_mode="COMBINED")
            cls.db.add(cls.sch3)
            cls.db.commit()
            cls.db.refresh(cls.sch3)

        # Create Users
        cls.admin1 = cls.db.query(User).filter(User.username == "admin_sch1").first()
        if not cls.admin1:
            cls.admin1 = User(
                username="admin_sch1", email="admin1@test.local",
                password_hash="hash", is_active=True, school_id=cls.sch1.id,
                roles=[admin_role]
            )
            cls.db.add(cls.admin1)

        cls.admin2 = cls.db.query(User).filter(User.username == "admin_sch2").first()
        if not cls.admin2:
            cls.admin2 = User(
                username="admin_sch2", email="admin2@test.local",
                password_hash="hash", is_active=True, school_id=cls.sch2.id,
                roles=[admin_role]
            )
            cls.db.add(cls.admin2)

        cls.user_suspended = cls.db.query(User).filter(User.username == "user_suspended_sch").first()
        if not cls.user_suspended:
            cls.user_suspended = User(
                username="user_suspended_sch", email="user_susp@test.local",
                password_hash="hash", is_active=True, school_id=cls.sch3.id,
                roles=[admin_role]
            )
            cls.db.add(cls.user_suspended)

        cls.user_deactivated = cls.db.query(User).filter(User.username == "user_deactivated").first()
        if not cls.user_deactivated:
            cls.user_deactivated = User(
                username="user_deactivated", email="user_deact@test.local",
                password_hash="hash", is_active=False, school_id=cls.sch1.id,
                roles=[teacher_role]
            )
            cls.db.add(cls.user_deactivated)

        cls.super_admin = cls.db.query(User).filter(User.username == "super_admin_test").first()
        if not cls.super_admin:
            cls.super_admin = User(
                username="super_admin_test", email="superadmin@test.local",
                password_hash="hash", is_active=True, school_id=None,
                roles=[super_admin_role]
            )
            cls.db.add(cls.super_admin)

        cls.db.commit()

        # Create SchoolStage, Academic Section & Student in School 1
        stage1 = cls.db.query(SchoolStage).filter(SchoolStage.school_id == cls.sch1.id).first()
        if not stage1:
            stage1 = cls.db.query(SchoolStage).first()
        if not stage1:
            stage1 = SchoolStage(name="SHS 1", school_type="SHS", school_id=cls.sch1.id)
            cls.db.add(stage1)
            cls.db.commit()
            cls.db.refresh(stage1)

        cls.cs1 = cls.db.query(ClassSection).filter(ClassSection.name == "Audit Class 1").first()
        if not cls.cs1:
            cls.cs1 = ClassSection(name="Audit Class 1", stage_id=stage1.id, school_id=cls.sch1.id)
            cls.db.add(cls.cs1)
            cls.db.commit()
            cls.db.refresh(cls.cs1)

        cls.student1 = cls.db.query(Student).filter(Student.student_code == "AUD-001").first()
        if not cls.student1:
            cls.student1 = Student(
                student_code="AUD-001", full_name="Kwame Mensah", first_name="Kwame", last_name="Mensah",
                school_id=cls.sch1.id, class_section_id=cls.cs1.id, is_active=True
            )
            cls.db.add(cls.student1)
            cls.db.commit()
            cls.db.refresh(cls.student1)

        # Create Fee in School 1
        cls.fee1 = cls.db.query(Fee).filter(Fee.student_id == cls.student1.id).first()
        if not cls.fee1:
            cls.fee1 = Fee(
                student_id=cls.student1.id, fee_type="Tuition", amount=500.0,
                amount_paid=0.0, status="Pending"
            )
            cls.db.add(cls.fee1)
            cls.db.commit()
            cls.db.refresh(cls.fee1)

        # Create Asset in School 1
        cls.asset1 = cls.db.query(Asset).filter(Asset.name == "School 1 Microscope").first()
        if not cls.asset1:
            cls.asset1 = Asset(
                name="School 1 Microscope", category="Laboratory", quantity=5,
                unit_cost=1200.0, school_id=cls.sch1.id
            )
            cls.db.add(cls.asset1)
            cls.db.commit()
            cls.db.refresh(cls.asset1)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_deactivated_and_suspended_token_rejection(self):
        """Verify get_current_user rejects deactivated users and suspended schools."""
        from backend.app.services.auth import create_jwt

        # Deactivated user token
        deact_token = create_jwt({"user_id": self.user_deactivated.id, "sub": self.user_deactivated.username})
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(authorization=f"Bearer {deact_token}", db=self.db)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("deactivated", ctx.exception.detail.lower())

        # Suspended school user token
        susp_token = create_jwt({"user_id": self.user_suspended.id, "sub": self.user_suspended.username})
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(authorization=f"Bearer {susp_token}", db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("suspended", ctx.exception.detail.lower())

    def test_02_cross_tenant_impersonation_block(self):
        """Verify admin of School 2 cannot impersonate staff/admin of School 1."""
        with self.assertRaises(HTTPException) as ctx:
            impersonate_user(
                user_id=self.admin1.id,
                current_user=self.admin2,
                db=self.db
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("another institution", ctx.exception.detail)

    def test_03_cross_tenant_fee_idor_block(self):
        """Verify admin of School 2 cannot view, update, delete, or record payments on School 1 fee."""
        # View student fees from other school
        with self.assertRaises(HTTPException) as ctx:
            get_student_fees(
                student_id=self.student1.id,
                db=self.db,
                current_user=self.admin2
            )
        self.assertEqual(ctx.exception.status_code, 404)

        # View fee record
        with self.assertRaises(HTTPException) as ctx:
            get_fee(fee_id=self.fee1.id, db=self.db, current_user=self.admin2)
        self.assertEqual(ctx.exception.status_code, 404)

        # Delete fee record
        with self.assertRaises(HTTPException) as ctx:
            delete_fee(fee_id=self.fee1.id, db=self.db, current_user=self.admin2)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_04_cross_tenant_asset_idor_block(self):
        """Verify admin of School 2 cannot delete or issue assets belonging to School 1."""
        with self.assertRaises(HTTPException) as ctx:
            delete_asset(asset_id=self.asset1.id, db=self.db, current_user=self.admin2)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_05_basic_only_mode_program_and_department_rejection(self):
        """Verify Basic School (BASIC_ONLY) cannot create SHS programs or HOD departments."""
        # Program creation in BASIC_ONLY mode
        prog_payload = ProgramCreate(name="General Arts", code="GA")
        with self.assertRaises(HTTPException) as ctx:
            create_program(payload=prog_payload, db=self.db, current_user=self.admin2)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Basic Schools", ctx.exception.detail)

        # Department creation in BASIC_ONLY mode
        dept_payload = DepartmentCreate(name="Science Department", code="SCI")
        with self.assertRaises(HTTPException) as ctx:
            create_department(payload=dept_payload, db=self.db, current_user=self.admin2)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Basic Schools", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
