import sys
import os
import json

# Ensure backend is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.database import SessionLocal
from app.models import School, User, Role, Setting
from app.routes.settings import get_settings, update_settings

def run_basic_settings_suite():
    print("=" * 60)
    print(" GHANAIAN BASIC SCHOOL SETTINGS VERIFICATION SUITE")
    print("=" * 60)

    db = SessionLocal()
    try:
        # 1. Setup Test Basic School
        basic_sch = db.query(School).filter(School.name == "Settings Test Basic School").first()
        if not basic_sch:
            basic_sch = School(
                name="Settings Test Basic School",
                code="STBS-001",
                slug="settings-test-basic-school",
                school_mode="BASIC_ONLY",
                boarding_type="DAY_ONLY"
            )
            db.add(basic_sch)
            db.commit()
            db.refresh(basic_sch)

        # Mock Admin User
        admin_user = db.query(User).filter(User.username == "admin_settings").first()
        if not admin_user:
            admin_user = User(
                username="admin_settings",
                email="admin_settings@test.com",
                password_hash="hash",
                school_id=basic_sch.id
            )
            admin_role = db.query(Role).filter(Role.name == "admin").first()
            if not admin_role:
                admin_role = Role(name="admin")
                db.add(admin_role)
                db.commit()
            admin_user.roles.append(admin_role)
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

        print("\n[1] Testing GET /api/settings for Basic School Mode...")
        settings_res = get_settings(db=db, current_user=admin_user, school_id=basic_sch.id)
        assert settings_res["school_mode"] == "BASIC_ONLY", f"Expected BASIC_ONLY, got {settings_res['school_mode']}"
        assert settings_res["boarding_hierarchy_mode"] == "BASIC_TWO_TIER", f"Expected BASIC_TWO_TIER, got {settings_res['boarding_hierarchy_mode']}"
        print(f"   [OK] School mode verified: {settings_res['school_mode']}")
        print(f"   [OK] Hierarchy mode verified: {settings_res['boarding_hierarchy_mode']}")
        print(f"   [OK] Grading standard: {settings_res.get('grading_standard')}")

        print("\n[2] Testing PUT /api/settings with NaCCA 50/50 SBA and Core Competencies...")
        nacca_competencies = {
            "critical_thinking": True,
            "creativity": True,
            "collaboration": True,
            "cultural_identity": True,
            "personal_dev": True,
            "conduct_punctuality": True
        }

        update_payload = {
            "class_score_weight": 50,
            "exam_score_weight": 50,
            "grading_standard": "BECE",
            "report_title": "TERMINAL PROGRESS REPORT",
            "report_motto": "Knowledge, Discipline and Truth",
            "nacca_core_competencies": json.dumps(nacca_competencies)
        }

        res_update = update_settings(payload=update_payload, db=db, current_user=admin_user, school_id=basic_sch.id)
        print(f"   [OK] Settings update executed: {res_update['status']}")

        print("\n[3] Verifying Persisted NaCCA Settings from Database...")
        refetched = get_settings(db=db, current_user=admin_user, school_id=basic_sch.id)
        assert int(refetched["class_score_weight"]) == 50, f"Expected 50, got {refetched['class_score_weight']}"
        assert int(refetched["exam_score_weight"]) == 50, f"Expected 50, got {refetched['exam_score_weight']}"
        assert "nacca_core_competencies" in refetched, "nacca_core_competencies missing from settings!"
        
        parsed_comps = json.loads(refetched["nacca_core_competencies"])
        assert parsed_comps["critical_thinking"] is True, "Critical thinking toggle not saved!"
        assert parsed_comps["creativity"] is True, "Creativity toggle not saved!"
        print(f"   [OK] Continuous Assessment Weights: {refetched['class_score_weight']}% SBA / {refetched['exam_score_weight']}% Exam")
        print(f"   [OK] NaCCA Core Competencies verified in store: {list(parsed_comps.keys())}")

        print("\n" + "=" * 60)
        print(" ALL BASIC SCHOOL SETTINGS TESTS PASSED SUCCESSFULLY!")
        print("=" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    run_basic_settings_suite()
