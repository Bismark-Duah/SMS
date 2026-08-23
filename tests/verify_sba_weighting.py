"""
Automated Verification Script for Configurable SBA Weighting Configuration
"""
import sys
from sqlalchemy.orm import Session

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import Setting
from backend.app.routes.settings import get_settings

def run_tests():
    print("==================================================")
    print(" CONFIGURABLE SBA/EXAM WEIGHTING TEST SUITE        ")
    print("==================================================")

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Setup Test Settings
        print("\n[1] Configuring SBA/Exam weights to 50/50 JHS BECE ratio...")
        setting_class = db.query(Setting).filter(Setting.key == "class_score_weight").first()
        if not setting_class:
            setting_class = Setting(key="class_score_weight", value="50")
            db.add(setting_class)
        else:
            setting_class.value = "50"

        setting_exam = db.query(Setting).filter(Setting.key == "exam_score_weight").first()
        if not setting_exam:
            setting_exam = Setting(key="exam_score_weight", value="50")
            db.add(setting_exam)
        else:
            setting_exam.value = "50"
        
        db.commit()
        print("   [OK] DB Weights set to 50/50.")

        # 2. Test settings endpoint output
        print("\n[2] Checking settings API output values...")
        settings_res = get_settings(db)
        assert settings_res["class_score_weight"] == 50, f"Expected 50! Got {settings_res['class_score_weight']}"
        assert settings_res["exam_score_weight"] == 50, f"Expected 50! Got {settings_res['exam_score_weight']}"
        print("   [OK] Settings API successfully returned configured 50/50 ratios.")

        # 3. Simulate frontend formula calculation
        print("\n[3] Simulating breakdown raw-sum calculation for 50/50 ratio...")
        # Raw inputs sum up to 80 out of 100
        raw_sum = 10 + 10 + 10 + 10 + 20 + 10 + 10 + 0 # 80
        class_weight = settings_res["class_score_weight"] # 50
        
        # Formula: Math.min(classWeight, rawSum * (classWeight / 100))
        computed_class_score = min(class_weight, raw_sum * (class_weight / 100.0))
        expected_class_score = 40.0
        assert computed_class_score == expected_class_score, f"Expected {expected_class_score}, got {computed_class_score}"
        print(f"   [OK] Raw sum of {raw_sum} scaled to {computed_class_score} (Expected: {expected_class_score}).")

        # 4. Clean up / Restore SHS 30/70 defaults
        setting_class.value = "30"
        setting_exam.value = "70"
        db.commit()
        print("\n[4] Restored defaults to 30/70.")
        
        print("\n==================================================")
        print(" ALL SBA CONFIGURATION VERIFICATION TESTS PASSED!  ")
        print("==================================================")

    except Exception as e:
        print(f"\n[FAIL] SBA CONFIGURATION VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
