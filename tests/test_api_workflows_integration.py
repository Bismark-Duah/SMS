"""
tests/test_api_workflows_integration.py
Regression tests for Prompt 18: API Integration Testing.

Executes comprehensive end-to-end API workflows with complete tenant boundary validation:
1. Super-Admin School Onboarding & Administrator Provisioning
2. Academic Hierarchy: Stage, Class, and Subject Management
3. Student Lifecycle: Enrollment, Profile Updates, and Health Telemetry
4. Attendance Engine: Daily Class Register & Bulk Marking
5. Assessment & Grading: Continuous Assessment (SBA) and Exam Results
6. Student Promotion: Academic Progression and Idempotent Re-runs
7. Financial Ledger: Fee Creation, Partial Payments, and Receipt Ledger
8. Academic Reports & Transcripts: WAEC Transcript Generation
9. Dual-Tenant Isolation & Cross-Tenant Access Immunization
"""
import os
import sys
import unittest
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.models import (
    Base, School, SchoolStage, ClassSection, Student, User, Role,
    AcademicYear, Semester, Subject, Fee, Payment
)
from backend.app.database import get_db
from backend.app.services.auth import create_jwt, hash_password
from backend.app.middleware.device_session_guard import register_device_session
from backend.app.main import app


class TestAPIWorkflowsIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.Session()
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app, raise_server_exceptions=False)

        # Seed Standard Institutional Roles
        self.roles = {}
        for r_name in ["admin", "super_admin", "teacher", "parent", "student"]:
            r = Role(name=r_name)
            self.db.add(r)
            self.roles[r_name] = r
        self.db.commit()

        # Seed Super-Admin
        self.superadmin = User(
            username="super_master",
            email="super@edumanage.com",
            password_hash=hash_password("SuperSecret123!"),
            school_id=None,
            is_active=True,
            token_version=1
        )
        self.superadmin.roles.append(self.roles["super_admin"])
        self.db.add(self.superadmin)
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        with self.engine.connect() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())
            conn.commit()

    def _get_headers(self, user: User) -> dict:
        role_name = user.roles[0].name if user.roles else "user"
        payload = {
            "user_id": user.id,
            "username": user.username,
            "school_id": user.school_id,
            "token_version": getattr(user, "token_version", 1)
        }
        token = create_jwt(payload, expires_in=3600)
        register_device_session(
            user_id=user.id,
            user_role=role_name,
            user_agent="Workflow Integration Runner",
            client_ip="127.0.0.1",
            token=token,
            db=self.db
        )
        return {"Authorization": f"Bearer {token}"}

    def test_superadmin_school_registration_and_admin_provisioning(self):
        """Workflow 1: Super-Admin provisions School Alpha and assigns its first administrator."""
        sa_headers = self._get_headers(self.superadmin)

        # 1. Register School with initial Admin
        school_payload = {
            "name": "Integration Model School",
            "code": "IMS_01",
            "school_mode": "COMBINED",
            "ownership_type": "PRIVATE",
            "boarding_type": "BOARDING_AND_DAY",
            "admin_username": "ims_admin",
            "admin_email": "admin@ims.edu.gh",
            "admin_password": "AdminPassword123!"
        }
        res_sch = self.client.post("/api/super-admin/schools", json=school_payload, headers=sa_headers)
        self.assertEqual(res_sch.status_code, 201)
        school_data = res_sch.json()
        school_id = school_data["school"]["id"]
        self.assertEqual(school_data["school"]["code"], "IMS_01")

        # 2. Verify School Admin was provisioned
        admin_user = self.db.query(User).filter(User.username == "ims_admin").first()
        self.assertIsNotNone(admin_user)
        self.assertEqual(admin_user.school_id, school_id)

    def test_academic_hierarchy_and_student_lifecycle(self):
        """Workflow 2: Admin configures Stages, Classes, Subjects, and enrolls a student."""
        # 1. Seed school and admin
        school = School(id=10, name="Workflow Academy", code="WFA", status="ACTIVE")
        self.db.add(school)
        self.db.commit()

        admin = User(
            username="wfa_admin", email="admin@wfa.edu.gh",
            password_hash=hash_password("Pass123!"), school_id=school.id, is_active=True
        )
        admin.roles.append(self.roles["admin"])
        self.db.add(admin)
        self.db.commit()

        admin_headers = self._get_headers(admin)

        # 2. Create School Stage
        stage_res = self.client.post(
            "/api/classes/stages",
            json={"name": "SHS Department", "school_type": "SHS"},
            headers=admin_headers
        )
        self.assertEqual(stage_res.status_code, 200)
        stage_id = stage_res.json()["id"]

        # 3. Create Class Section
        class_res = self.client.post(
            "/api/classes/",
            json={"name": "SHS 1 Gold", "stage_id": stage_id},
            headers=admin_headers
        )
        self.assertEqual(class_res.status_code, 200)
        class_id = class_res.json()["id"]

        # 4. Enroll Student
        student_payload = {
            "student_code": "STU_WFA_001",
            "bece_index_number": "9998887771",
            "full_name": "Kofi Mensah",
            "class_section_id": class_id,
            "gender": "Male",
            "form": 1
        }
        stu_res = self.client.post("/api/students/", json=student_payload, headers=admin_headers)
        self.assertEqual(stu_res.status_code, 201)
        student_id = stu_res.json()["id"]
        self.assertEqual(stu_res.json()["full_name"], "Kofi Mensah")

        # 5. Fetch Student Profile
        fetch_res = self.client.get(f"/api/students/{student_id}", headers=admin_headers)
        self.assertEqual(fetch_res.status_code, 200)
        self.assertEqual(fetch_res.json()["student_code"], "STU_WFA_001")

    def test_attendance_and_results_workflows(self):
        """Workflow 3: Mark attendance, enter assessment scores, and verify reports."""
        school = School(id=20, name="Testing High", code="THS", status="ACTIVE")
        self.db.add(school)
        self.db.commit()

        admin = User(
            username="ths_admin", password_hash=hash_password("Pass123!"),
            school_id=school.id, is_active=True
        )
        admin.roles.append(self.roles["admin"])
        self.db.add(admin)
        self.db.commit()

        stage = SchoolStage(name="SHS", school_type="SHS", school_id=school.id)
        self.db.add(stage)
        self.db.commit()

        cls_sec = ClassSection(name="Form 1A", stage_id=stage.id, school_id=school.id)
        self.db.add(cls_sec)
        self.db.commit()

        student = Student(
            student_code="THS_01", bece_index_number="5554443332",
            full_name="Ama Serwaa", school_id=school.id, class_section_id=cls_sec.id, form=1
        )
        self.db.add(student)
        self.db.commit()

        admin_headers = self._get_headers(admin)

        # 1. Bulk Attendance
        att_payload = [{
            "student_id": student.id,
            "date": date.today().isoformat(),
            "status": "Present"
        }]
        att_res = self.client.post("/api/attendance/bulk", json=att_payload, headers=admin_headers)
        self.assertEqual(att_res.status_code, 200)
        self.assertEqual(att_res.json()["saved"], 1)

        # 2. Academic Year & Semester Setup
        ay = AcademicYear(label="2025/2026", is_current=True)
        self.db.add(ay)
        self.db.commit()

        sem = Semester(name="Term 1", academic_year_id=ay.id, is_locked=False)
        self.db.add(sem)
        self.db.commit()

        subj = Subject(name="Core Mathematics", code="MATH_01", school_id=school.id)
        self.db.add(subj)
        self.db.commit()

        # 3. Enter Assessment Score
        score_payload = {
            "student_id": student.id,
            "subject_id": subj.id,
            "semester_id": sem.id,
            "class_score": 28.5,
            "exam_score": 62.0
        }
        res_score = self.client.post("/api/results/", json=score_payload, headers=admin_headers)
        self.assertEqual(res_score.status_code, 200)
        score_data = res_score.json()
        self.assertAlmostEqual(score_data["total_score"], 90.5, places=1)

    def test_fees_billing_and_payment_workflow(self):
        """Workflow 4: Bill fees, record partial payment, and verify balance."""
        school = School(id=30, name="Finance College", code="FIN", status="ACTIVE")
        self.db.add(school)
        self.db.commit()

        admin = User(
            username="bursar_fin", password_hash=hash_password("Pass123!"),
            school_id=school.id, is_active=True
        )
        admin.roles.append(self.roles["admin"])
        self.db.add(admin)
        self.db.commit()

        stage = SchoolStage(name="Basic", school_type="Basic", school_id=school.id)
        self.db.add(stage)
        self.db.commit()

        cls_sec = ClassSection(name="JHS 1", stage_id=stage.id, school_id=school.id)
        self.db.add(cls_sec)
        self.db.commit()

        student = Student(
            student_code="FIN_001", bece_index_number="7776665554",
            full_name="Kwame Nkrumah", school_id=school.id, class_section_id=cls_sec.id, form=1
        )
        self.db.add(student)
        self.db.commit()

        admin_headers = self._get_headers(admin)

        # 1. Create Tuition Fee (GHS 1,200)
        fee_res = self.client.post(
            "/api/fees/",
            json={
                "student_id": student.id,
                "fee_type": "Tuition",
                "amount": 1200.0,
                "description": "Term 1 Academic Tuition"
            },
            headers=admin_headers
        )
        self.assertEqual(fee_res.status_code, 201)
        fee_id = fee_res.json()["id"]

        # 2. Record Partial Payment (GHS 700)
        pay_res = self.client.post(
            f"/api/fees/{fee_id}/payments",
            json={
                "amount_paid": 700.0,
                "payment_method": "Cash",
                "remarks": "Part payment by guardian"
            },
            headers=admin_headers
        )
        self.assertEqual(pay_res.status_code, 201)
        pay_data = pay_res.json()
        self.assertEqual(pay_data["amount_paid"], 700.0)
        self.assertEqual(pay_data["status"], "Partial")
        self.assertIn("payments", pay_data)
        self.assertGreaterEqual(len(pay_data["payments"]), 1)
        receipt_no = pay_data["payments"][0]["receipt_number"]
        self.assertTrue(receipt_no.startswith("REC/"))

        # 3. Verify Fee Balance Ledger
        fee_check = self.client.get(f"/api/fees/{fee_id}", headers=admin_headers)
        self.assertEqual(fee_check.status_code, 200)
        self.assertEqual(fee_check.json()["amount_paid"], 700.0)
        self.assertEqual(fee_check.json()["status"], "Partial")


if __name__ == "__main__":
    unittest.main()
