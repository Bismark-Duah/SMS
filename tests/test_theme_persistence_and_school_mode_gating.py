"""
Test Suite: Theme Persistence & School Mode Student Import Gating Verification
Verifies:
1. Tenant-specific system_theme persistence via Settings API (GET & PUT /api/settings/).
2. HTML toolbar gating attributes in students.html (basic-only-feature vs shs-only-feature).
3. Data Tools cleanup (obsolete student CSV import removed in favor of Student Directory).
"""
import sys
import os
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database import SessionLocal
from backend.app.models import User, Role, School, Setting
from backend.app.routes.settings import get_settings, update_settings

def test_theme_persistence_and_student_import_gating():
    db = SessionLocal()
    try:
        print("\n==================================================================")
        print("TEST SUITE: Theme Persistence & School Mode Toolbar Gating Audit")
        print("==================================================================")

        # 1. Setup Admin Role and JAKSTEM School
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            db.add(admin_role)
            db.flush()

        jakstem = db.query(School).filter(School.code == "JAKSTEM-TEST").first()
        if not jakstem:
            jakstem = School(
                name="JAKSTEM Senior High Technical School",
                code="JAKSTEM-TEST",
                school_mode="SHS_ONLY",
                status="ACTIVE"
            )
            db.add(jakstem)
            db.flush()

        jak_admin = db.query(User).filter(User.username == "jakstem_admin_tester").first()
        if not jak_admin:
            jak_admin = User(
                username="jakstem_admin_tester",
                email="jak_admin@jakstem.edu.gh",
                password_hash="test_pw_hash",
                school_id=jakstem.id,
                is_active=True
            )
            jak_admin.roles.append(admin_role)
            db.add(jak_admin)
            db.flush()

        db.commit()

        # 2. Test Theme Update & Persistence
        print("\n[Step 1] Changing theme to 'light' (Clean Light) for JAKSTEM...")
        res = update_settings(
            payload={"system_theme": "light"},
            db=db,
            current_user=jak_admin,
            school_id=jakstem.id
        )
        assert res["status"] == "success"

        # Verify in DB
        db_theme_setting = db.query(Setting).filter(
            Setting.school_id == jakstem.id,
            Setting.key == "system_theme"
        ).first()
        assert db_theme_setting is not None, "Theme setting must exist in DB for school"
        assert db_theme_setting.value == "light", f"Expected 'light', got '{db_theme_setting.value}'"
        print("  [OK] Theme 'light' successfully written and committed to database for JAKSTEM.")

        # Verify get_settings returns 'light'
        fetched_settings = get_settings(db=db, current_user=jak_admin, school_id=jakstem.id)
        assert fetched_settings.get("system_theme") == "light", f"Expected 'light', got '{fetched_settings.get('system_theme')}'"
        print("  [OK] GET /api/settings/ returns 'light' - theme will not revert on refresh!")

        # Test switching to another theme (e.g. 'emerald')
        update_settings(
            payload={"system_theme": "emerald"},
            db=db,
            current_user=jak_admin,
            school_id=jakstem.id
        )
        fetched_settings2 = get_settings(db=db, current_user=jak_admin, school_id=jakstem.id)
        assert fetched_settings2.get("system_theme") == "emerald"
        print("  [OK] Switching to 'emerald' verified and persistent.")

        # 3. Verify students.html Toolbar Gating Markup
        print("\n[Step 2] Auditing students.html import toolbar buttons...")
        students_html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'students.html'))
        with open(students_html_path, 'r', encoding='utf-8') as f:
            students_content = f.read()

        # Check basicTemplateBtn & basicImportBtn have basic-only-feature
        assert re.search(r'id="basicTemplateBtn"[^>]*class="[^"]*basic-only-feature', students_content) or \
               re.search(r'class="[^"]*basic-only-feature[^"]*"[^>]*id="basicTemplateBtn"', students_content), \
               "basicTemplateBtn must have basic-only-feature class"

        assert re.search(r'id="basicImportBtn"[^>]*class="[^"]*basic-only-feature', students_content) or \
               re.search(r'class="[^"]*basic-only-feature[^"]*"[^>]*id="basicImportBtn"', students_content), \
               "basicImportBtn must have basic-only-feature class"

        # Check continuingTemplateBtn & csspsTemplateBtn have shs-only-feature
        assert re.search(r'id="continuingTemplateBtn"[^>]*class="[^"]*shs-only-feature', students_content) or \
               re.search(r'class="[^"]*shs-only-feature[^"]*"[^>]*id="continuingTemplateBtn"', students_content), \
               "continuingTemplateBtn must have shs-only-feature class"

        assert re.search(r'id="csspsTemplateBtn"[^>]*class="[^"]*shs-only-feature', students_content) or \
               re.search(r'class="[^"]*shs-only-feature[^"]*"[^>]*id="csspsTemplateBtn"', students_content), \
               "csspsTemplateBtn must have shs-only-feature class"

        print("  [OK] students.html import toolbar buttons properly tagged for adaptive school mode rendering.")

        # 4. Verify data-tools.html cleanup
        print("\n[Step 3] Auditing data-tools.html cleanup...")
        data_tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'data-tools.html'))
        with open(data_tools_path, 'r', encoding='utf-8') as f:
            dt_content = f.read()

        assert "id=\"studentCsvFile\"" not in dt_content, "Legacy studentCsvFile input should be removed from data-tools.html"
        assert "importStudentCSV()" not in dt_content, "Legacy importStudentCSV call should be removed from data-tools.html"
        assert "Student Admissions &amp; Batch Enrollment Desk" in dt_content or "Student Admissions & Batch Enrollment Desk" in dt_content, \
            "Data tools should contain the informative banner pointing to Student Directory"

        print("  [OK] data-tools.html streamlined; duplicate legacy student import removed.")

        # 5. Verify settings.html cleanup & conductSection gating
        print("\n[Step 4] Auditing settings.html conductSection gating & payment removal...")
        settings_html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'settings.html'))
        with open(settings_html_path, 'r', encoding='utf-8') as f:
            st_content = f.read()

        assert "data-feature=\"showConductHub\"" in st_content, "conductSection must have data-feature='showConductHub'"
        assert "shs-only-feature" in st_content, "conductSection must have shs-only-feature class"
        assert "id=\"paystackSection\"" not in st_content, "paystackSection should be completely removed from settings.html"
        assert "id=\"voucherSection\"" not in st_content, "voucherSection should be completely removed from settings.html"
        assert "PAYSTACK SPLIT READY" not in st_content, "PAYSTACK SPLIT card should be removed from settings.html"

        print("  [OK] settings.html verified: conductSection gated to SHS-only, and all payment/settlement cards removed.")

        print("\n==================================================================")
        print("ALL TESTS PASSED: Theme Persistence, Conduct Hub & School Mode Gating Verified!")
        print("==================================================================\n")

    finally:
        db.close()

if __name__ == "__main__":
    test_theme_persistence_and_student_import_gating()

