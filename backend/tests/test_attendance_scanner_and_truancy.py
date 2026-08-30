"""
Automated Test Suite for Barcode/QR Scanner Real-Time Check-In & Truancy Alert Dispatch Engine
Verifies scan lookups, on-time vs late status calculation, duplicate scan debouncing,
automatic Hubtel absence SMS dispatch, and attendance register PDF ledger compilation.
"""
import sys
import os
import unittest
import uuid
from datetime import datetime, date

# Setup path so tests can run standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.database import SessionLocal
from backend.app.models import (
    School, Student, User, Role, Program, AcademicYear, Semester,
    ClassSection, Attendance, Setting, MessageLog, SchoolStage
)
from backend.app.routes.attendance import (
    scan_checkin_student,
    dispatch_truancy_alerts,
    get_attendance_ledger_pdf,
    ScanCheckinPayload,
    TruancyAlertDispatchPayload
)
from fastapi import HTTPException


class TestAttendanceScannerAndTruancy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        u_suffix = uuid.uuid4().hex[:6]

        # 1. School
        cls.school = School(
            name=f"Achimota School {u_suffix}",
            code=f"ACH-{u_suffix}",
            school_mode="SHS_ONLY"
        )
        cls.db.add(cls.school)
        cls.db.commit()
        cls.db.refresh(cls.school)

        # Other School for isolation test
        cls.other_school = School(
            name=f"Prempeh College {u_suffix}",
            code=f"PC-{u_suffix}",
            school_mode="SHS_ONLY"
        )
        cls.db.add(cls.other_school)
        cls.db.commit()
        cls.db.refresh(cls.other_school)

        # 2. Roles
        cls.admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        if not cls.admin_role:
            cls.admin_role = Role(name="admin")
            cls.db.add(cls.admin_role)
            cls.db.commit()

        # 3. Admin User
        cls.admin_user = User(
            username=f"admin_att_{u_suffix}",
            email=f"admin_att_{u_suffix}@example.com",
            password_hash="mockhash",
            school_id=cls.school.id,
            roles=[cls.admin_role]
        )
        cls.db.add(cls.admin_user)
        cls.db.commit()
        cls.db.refresh(cls.admin_user)

        # 4. Program, Stage & Class Section
        cls.stage = cls.db.query(SchoolStage).filter(SchoolStage.name == f"SHS 1 {u_suffix}").first()
        if not cls.stage:
            cls.stage = SchoolStage(name=f"SHS 1 {u_suffix}", school_type="SHS")
            cls.db.add(cls.stage)
            cls.db.commit()
            cls.db.refresh(cls.stage)

        cls.program = Program(
            name=f"General Arts {u_suffix}",
            code=f"ARTS-{u_suffix}",
            school_id=cls.school.id
        )
        cls.db.add(cls.program)
        cls.db.commit()
        cls.db.refresh(cls.program)

        cls.class_sec = ClassSection(
            name=f"Arts 1B {u_suffix}",
            stage_id=cls.stage.id,
            program_id=cls.program.id
        )
        cls.db.add(cls.class_sec)
        cls.db.commit()
        cls.db.refresh(cls.class_sec)

        # 5. Students
        cls.st1 = Student(
            student_code=f"ST-ATT1-{u_suffix}",
            first_name="Kofi",
            last_name="Annan",
            full_name="Kofi Annan",
            gender="Male",
            phone="0244111222",
            guardian_name="Mrs. Annan",
            class_section_id=cls.class_sec.id,
            program_id=cls.program.id,
            school_id=cls.school.id,
            is_active=True
        )
        cls.st2 = Student(
            student_code=f"ST-ATT2-{u_suffix}",
            first_name="Abena",
            last_name="Mansah",
            full_name="Abena Mansah",
            gender="Female",
            phone="0244333444",
            guardian_name="Mr. Mansah",
            class_section_id=cls.class_sec.id,
            program_id=cls.program.id,
            school_id=cls.school.id,
            is_active=True
        )
        cls.st_other = Student(
            student_code=f"ST-OTHER-{u_suffix}",
            first_name="Yaw",
            last_name="Boateng",
            full_name="Yaw Boateng",
            gender="Male",
            school_id=cls.other_school.id,
            is_active=True
        )
        cls.db.add_all([cls.st1, cls.st2, cls.st_other])
        cls.db.commit()
        cls.db.refresh(cls.st1)
        cls.db.refresh(cls.st2)
        cls.db.refresh(cls.st_other)

    @classmethod
    def tearDownClass(cls):
        cls.db.rollback()
        cls.db.close()

    def test_01_scan_checkin_present_success(self):
        """Verify scanning a student on time records 'Present' with success audio cue."""
        # Ensure cutoff is late enough (23:59) so student is marked Present
        s = self.db.query(Setting).filter(Setting.key == "morning_attendance_cutoff").first()
        if not s:
            self.db.add(Setting(key="morning_attendance_cutoff", value="23:59"))
        else:
            s.value = "23:59"
        self.db.commit()

        payload = ScanCheckinPayload(
            student_code=self.st1.student_code,
            scan_type="Morning Roll Call"
        )
        res = scan_checkin_student(payload, db=self.db, current_user=self.admin_user)

        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "Present")
        self.assertEqual(res["audio_cue"], "success")
        self.assertEqual(res["student_code"], self.st1.student_code)
        self.assertEqual(res["full_name"], "Kofi Annan")

        # Verify DB entry
        att = self.db.query(Attendance).filter(
            Attendance.student_id == self.st1.id,
            Attendance.date == datetime.now().date()
        ).first()
        self.assertIsNotNone(att)
        self.assertEqual(att.status, "Present")

    def test_02_scan_checkin_late_status(self):
        """Verify scanning a student after cutoff time records 'Late' status."""
        s = self.db.query(Setting).filter(Setting.key == "morning_attendance_cutoff").first()
        s.value = "00:01"  # Cutoff at midnight so current time is definitely Late
        self.db.commit()

        payload = ScanCheckinPayload(
            student_code=self.st2.student_code,
            scan_type="Morning Roll Call"
        )
        res = scan_checkin_student(payload, db=self.db, current_user=self.admin_user)

        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "Late")
        self.assertEqual(res["audio_cue"], "late")

    def test_03_scan_duplicate_debounce(self):
        """Verify repeating a scan within the same day flags duplicate debounce."""
        payload = ScanCheckinPayload(
            student_code=self.st1.student_code,
            scan_type="Morning Roll Call"
        )
        res = scan_checkin_student(payload, db=self.db, current_user=self.admin_user)

        self.assertTrue(res["success"])
        self.assertTrue(res["is_duplicate"])
        self.assertEqual(res["audio_cue"], "already_scanned")

    def test_04_scan_invalid_student_code_404(self):
        """Verify that an invalid barcode / student code returns 404."""
        payload = ScanCheckinPayload(
            student_code="NON_EXISTENT_BARCODE_999",
            scan_type="Morning Roll Call"
        )
        with self.assertRaises(HTTPException) as cm:
            scan_checkin_student(payload, db=self.db, current_user=self.admin_user)
        self.assertEqual(cm.exception.status_code, 404)

    def test_05_tenant_isolation_scan_guard(self):
        """Verify that scanning a student belonging to a different school is forbidden/404."""
        payload = ScanCheckinPayload(
            student_code=self.st_other.student_code,
            scan_type="Morning Roll Call"
        )
        with self.assertRaises(HTTPException) as cm:
            scan_checkin_student(payload, db=self.db, current_user=self.admin_user)
        self.assertEqual(cm.exception.status_code, 404)

    def test_06_dispatch_truancy_alerts_sms(self):
        """Verify unexcused absences trigger personalized Hubtel SMS alerts."""
        today = datetime.now().date()
        # Mark st2 as Absent for today
        att2 = self.db.query(Attendance).filter(
            Attendance.student_id == self.st2.id,
            Attendance.date == today
        ).first()
        if att2:
            att2.status = "Absent"
        else:
            att2 = Attendance(student_id=self.st2.id, date=today, status="Absent")
            self.db.add(att2)
        self.db.commit()

        payload = TruancyAlertDispatchPayload(
            date_str=today.strftime("%Y-%m-%d"),
            class_section_id=self.class_sec.id
        )
        res = dispatch_truancy_alerts(payload, db=self.db, current_user=self.admin_user)

        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["dispatched_count"], 1)

        # Check MessageLog
        msg = self.db.query(MessageLog).filter(
            MessageLog.student_id == self.st2.id,
            MessageLog.message_type == "ABSENCE_ALERT"
        ).first()
        self.assertIsNotNone(msg)
        self.assertIn("marked ABSENT", msg.message_body)
        self.assertIn(msg.recipient_phone, ["0244333444", "233244333444"])

    def test_07_attendance_ledger_pdf_compilation(self):
        """Verify compiling the attendance register PDF ledger."""
        now = datetime.now()
        response = get_attendance_ledger_pdf(
            class_section_id=self.class_sec.id,
            month=now.month,
            year=now.year,
            db=self.db,
            current_user=self.admin_user
        )
        self.assertEqual(response.media_type, "application/pdf")
        self.assertTrue(response.body.startswith(b"%PDF-"), "Attendance ledger must be a valid PDF binary")
        self.assertIn("Attendance_Register_", response.headers["Content-Disposition"])


if __name__ == "__main__":
    unittest.main()
