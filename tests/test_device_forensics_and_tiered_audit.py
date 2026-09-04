"""
tests/test_device_forensics_and_tiered_audit.py
Verification suite for Pure-Python Device Forensics & Tiered Audit Logging Engine.
Tests mobile phone brand detection, browser/OS extraction, tiered scoping, pagination, purge, and privacy isolation.
"""
import os
import sys
import unittest

# Add backend directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.database import SessionLocal, engine, Base
from app.models import School, User, Role, AuditLog, ActivityAuditLog
from app.services.device_parser import parse_device_forensics, get_client_ip
from app.services.audit_service import record_audit_event
from app.routes.super_admin import get_super_admin_audit_stream, purge_super_admin_audit_stream


class TestDeviceForensicsAndTieredAudit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        self.db = SessionLocal()
        # Seed test schools
        self.sch1 = self.db.query(School).filter(School.code == "AUDIT_SCH_1").first()
        if not self.sch1:
            self.sch1 = School(name="Audit Test Academy A", code="AUDIT_SCH_1", school_mode="SHS_ONLY", status="ACTIVE")
            self.db.add(self.sch1)

        self.sch2 = self.db.query(School).filter(School.code == "AUDIT_SCH_2").first()
        if not self.sch2:
            self.sch2 = School(name="Audit Test Academy B", code="AUDIT_SCH_2", school_mode="BASIC_ONLY", status="ACTIVE")
            self.db.add(self.sch2)

        self.db.commit()

        # Seed roles
        self.teacher_role = self.db.query(Role).filter(Role.name == "teacher").first()
        if not self.teacher_role:
            self.teacher_role = Role(name="teacher")
            self.db.add(self.teacher_role)
            self.db.commit()

        self.super_role = self.db.query(Role).filter(Role.name == "super_admin").first()
        if not self.super_role:
            self.super_role = Role(name="super_admin")
            self.db.add(self.super_role)
            self.db.commit()

        # Seed teacher user
        self.teacher = self.db.query(User).filter(User.username == "test_audit_teacher").first()
        if not self.teacher:
            self.teacher = User(
                username="test_audit_teacher",
                email="teacher@audit.edu.gh",
                password_hash="test_hash",
                school_id=self.sch1.id,
                is_active=True
            )
            self.teacher.roles = [self.teacher_role]
            self.db.add(self.teacher)
            self.db.commit()

        # Seed superadmin
        self.superadmin = self.db.query(User).filter(User.username == "superadmin").first()
        if not self.superadmin:
            self.superadmin = User(
                username="superadmin",
                email="superadmin@edumanage360.gh",
                password_hash="test_hash",
                is_active=True
            )
            self.superadmin.roles = [self.super_role]
            self.db.add(self.superadmin)
            self.db.commit()

    def tearDown(self):
        self.db.close()

    # ── 1. Mobile Phone Brand & Model Forensics ──────────────────────────────

    def test_mobile_phone_detection(self):
        # TECNO with model name
        tecno_ua = "Mozilla/5.0 (Linux; Android 13; TECNO KI7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36"
        res1 = parse_device_forensics(tecno_ua)
        self.assertEqual(res1["device_category"], "Mobile")
        self.assertIn("TECNO", res1["device_brand"].upper())
        self.assertIn("Android 13", res1["os_name"])
        self.assertIn("Chrome Mobile", res1["browser_name"])

        # TECNO with model code CK7n (Camon 20 Pro)
        tecno_code_ua = "Mozilla/5.0 (Linux; Android 13; CK7n) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36"
        res1_code = parse_device_forensics(tecno_code_ua)
        self.assertEqual(res1_code["device_category"], "Mobile")
        self.assertIn("TECNO", res1_code["device_brand"].upper())

        # Infinix
        infinix_ua = "Mozilla/5.0 (Linux; Android 12; Infinix X6816C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36"
        res2 = parse_device_forensics(infinix_ua)
        self.assertEqual(res2["device_category"], "Mobile")
        self.assertIn("INFINIX", res2["device_brand"].upper())
        self.assertIn("Android 12", res2["os_name"])

        # Itel
        itel_ua = "Mozilla/5.0 (Linux; Android 11; itel W6501) AppleWebKit/537.36 Chrome/100.0 Mobile Safari/537.36"
        res_itel = parse_device_forensics(itel_ua)
        self.assertEqual(res_itel["device_category"], "Mobile")
        self.assertIn("ITEL", res_itel["device_brand"].upper())

        # Samsung Galaxy
        samsung_ua = "Mozilla/5.0 (Linux; Android 14; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36"
        res3 = parse_device_forensics(samsung_ua)
        self.assertEqual(res3["device_category"], "Mobile")
        self.assertIn("Samsung Galaxy", res3["device_brand"])

        # Apple iPhone
        iphone_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1"
        res4 = parse_device_forensics(iphone_ua)
        self.assertEqual(res4["device_category"], "Mobile")
        self.assertEqual(res4["device_brand"], "Apple iPhone")
        self.assertIn("iOS", res4["os_name"])
        self.assertIn("Safari", res4["browser_name"])

    # ── 2. Client Hints & Desktop Mode on Android Recovery ───────────────────

    def test_client_hints_and_desktop_mode_recovery(self):
        # Android Chrome with User-Agent Reduction and Desktop site mode active
        desktop_ua_on_phone = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        headers = {
            "sec-ch-ua-model": "TECNO Spark 10 Pro",
            "sec-ch-ua-platform": "Android",
            "sec-ch-ua-mobile": "?1",
            "x-client-touch": "true"
        }
        res = parse_device_forensics(desktop_ua_on_phone, headers)
        self.assertEqual(res["device_category"], "Mobile")
        self.assertIn("TECNO", res["device_brand"].upper())
        self.assertEqual(res["os_name"], "Android")

    def test_gpu_hardware_fallback(self):
        # Android Chrome where model was reduced to "K" but WebGL GPU reveals MediaTek / Mali GPU
        frozen_ua = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36"
        gpu_headers = {
            "x-client-gpu": "Mali-G57 MC2",
            "x-client-touch": "true"
        }
        res = parse_device_forensics(frozen_ua, gpu_headers)
        self.assertEqual(res["device_category"], "Mobile")
        self.assertIn("TECNO / Infinix", res["device_brand"])
        self.assertIn("Mali-G57", res["device_brand"])
        self.assertIn("Android", res["os_name"])

    # ── 3. Desktop OS & Browser Forensics ────────────────────────────────────

    def test_desktop_forensics_detection(self):
        # Windows with Edge
        win_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
        res1 = parse_device_forensics(win_ua)
        self.assertEqual(res1["device_category"], "Desktop")
        self.assertIn("Windows", res1["device_brand"])
        self.assertIn("Windows 10 / 11", res1["os_name"])
        self.assertIn("Microsoft Edge", res1["browser_name"])

        # Mac with Safari
        mac_ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15"
        res2 = parse_device_forensics(mac_ua)
        self.assertEqual(res2["device_category"], "Desktop")
        self.assertEqual(res2["device_brand"], "Apple Mac")
        self.assertIn("macOS", res2["os_name"])
        self.assertIn("Safari", res2["browser_name"])

    # ── 4. Client IP Extraction ─────────────────────────────────────────────

    def test_client_ip_extraction(self):
        headers1 = {"x-forwarded-for": "102.176.94.12, 192.168.1.1"}
        self.assertEqual(get_client_ip(headers1), "102.176.94.12")

        headers2 = {"cf-connecting-ip": "154.160.25.80"}
        self.assertEqual(get_client_ip(headers2), "154.160.25.80")

        headers3 = {}
        self.assertEqual(get_client_ip(headers3, fallback_ip="192.168.0.50"), "192.168.0.50")

    # ── 5. Audit Event Recording & Database Persistence ──────────────────────

    def test_audit_event_recording(self):
        tecno_ua = "Mozilla/5.0 (Linux; Android 13; TECNO Spark 10 Pro) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36"

        entry = record_audit_event(
            db=self.db,
            actor=self.teacher,
            action="SCORE_UPDATE",
            details="Updated Elective Mathematics mark for Student #104 from 55 to 88",
            entity_type="Score",
            entity_id="104",
            school_id=self.sch1.id,
            ip_override="102.176.65.20",
            user_agent_override=tecno_ua
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry.actor_username, "test_audit_teacher")
        self.assertEqual(entry.action, "SCORE_UPDATE")
        self.assertEqual(entry.device_category, "Mobile")
        self.assertIn("TECNO", entry.device_brand.upper())
        self.assertEqual(entry.ip_address, "102.176.65.20")
        self.assertFalse(entry.is_super_admin_action)

    # ── 6. Super-Admin Action Tagging & Isolation ────────────────────────────

    def test_super_admin_action_tagging_and_isolation(self):
        entry = record_audit_event(
            db=self.db,
            actor=self.superadmin,
            action="SCHOOL_PROFILE_UPDATE",
            details="Super-Admin updated school profile settings",
            entity_type="School",
            entity_id=str(self.sch1.id),
            school_id=self.sch1.id,
            ip_override="127.0.0.1",
            user_agent_override="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0",
            is_super_admin_action=True
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry.actor_username, "superadmin")
        self.assertTrue(entry.is_super_admin_action)

        # Ensure School Admin query strictly hides this superadmin entry
        school_feed = self.db.query(AuditLog).filter(
            AuditLog.school_id == self.sch1.id,
            AuditLog.is_super_admin_action == False,
            AuditLog.actor_role != "super_admin",
            AuditLog.actor_username != "superadmin"
        ).all()

        actions = [l.action for l in school_feed]
        self.assertNotIn("SCHOOL_PROFILE_UPDATE", actions)

    # ── 7. Pagination and Purge ──────────────────────────────────────────────

    def test_audit_pagination_and_purge(self):
        # Generate 20 test records
        for i in range(20):
            record_audit_event(
                db=self.db,
                actor=self.teacher,
                action=f"TEST_ACTION_{i}",
                details=f"Test action #{i}",
                entity_type="Test",
                school_id=self.sch1.id
            )

        # Test Page 1 (limit 15)
        res_p1 = get_super_admin_audit_stream(page=1, limit=15, db=self.db, current_user=self.superadmin)
        self.assertGreaterEqual(res_p1["total"], 20)
        self.assertEqual(res_p1["page"], 1)
        self.assertEqual(res_p1["limit"], 15)
        self.assertEqual(len(res_p1["logs"]), 15)
        self.assertGreaterEqual(res_p1["total_pages"], 2)

        # Test Purge
        purge_res = purge_super_admin_audit_stream(db=self.db, current_user=self.superadmin)
        self.assertEqual(purge_res["status"], "success")

        # After purge, only the AUDIT_LOG_PURGED marker remains
        res_after = get_super_admin_audit_stream(page=1, limit=15, db=self.db, current_user=self.superadmin)
        self.assertEqual(res_after["total"], 1)
        self.assertEqual(res_after["logs"][0]["action"], "AUDIT_LOG_PURGED")


if __name__ == "__main__":
    unittest.main()
