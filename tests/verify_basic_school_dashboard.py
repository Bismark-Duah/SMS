import sys
import os

# Set sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.database import SessionLocal
from app.models import School, Student, ClassSection, Subject, User, Score, Setting
from app.routes.academic import get_executive_analytics

def test_basic_school_dashboard_analytics():
    print("Testing Basic School Dashboard Executive Analytics Backend...")
    db = SessionLocal()
    try:
        # Create or find a test school in BASIC_ONLY mode
        basic_school = db.query(School).filter(School.name == "Test Basic School").first()
        if not basic_school:
            basic_school = School(
                name="Test Basic School",
                code="TBS-001",
                slug="test-basic-school",
                school_mode="BASIC_ONLY",
                boarding_type="DAY_ONLY"
            )
            db.add(basic_school)
            db.commit()
            db.refresh(basic_school)
        else:
            basic_school.school_mode = "BASIC_ONLY"
            basic_school.boarding_type = "DAY_ONLY"
            db.commit()

        # Mock current admin user
        admin_user = db.query(User).filter(User.username == "admin").first()

        # Execute executive analytics for this basic school
        res = get_executive_analytics(db=db, current_user=admin_user, school_id=basic_school.id)

        print("[OK] Response received from get_executive_analytics")
        assert res["school_mode"] == "BASIC_ONLY", f"Expected BASIC_ONLY, got {res['school_mode']}"

        ac = res["academic"]
        adm = res["administration"]
        dom = res["domestic"]

        print(f"  - SBA Completion Pct: {ac.get('sba_completion_pct')}%")
        print(f"  - CRF Completion Pct: {ac.get('crf_completion_pct')}%")
        print(f"  - Basic Grade Distribution: {ac.get('basic_grade_distribution')}")
        print(f"  - Proficiency Distribution: {ac.get('proficiency_distribution')}")
        print(f"  - Core Subjects Count: {len(ac.get('core_subjects_performance', []))}")
        print(f"  - Classes Matrix Count: {len(ac.get('classes_matrix', []))}")
        print(f"  - Stage Demographics: {adm.get('stage_demographics')}")

        # Assertions
        assert "classes_matrix" in ac, "classes_matrix must be present in academic payload"
        assert "basic_grade_distribution" in ac, "basic_grade_distribution must be present"
        assert "proficiency_distribution" in ac, "proficiency_distribution must be present"
        assert "crf_completion_pct" in ac, "crf_completion_pct must be present in academic payload"
        assert "crf_completion_pct" in adm, "crf_completion_pct must be present in administration payload"
        assert "stage_demographics" in adm, "stage_demographics must be present in administration payload"
        assert dom["total_boarders"] == 0, f"Expected 0 boarders in basic mode, got {dom['total_boarders']}"
        assert dom["currently_away_exeat"] == 0, f"Expected 0 exeats in basic mode, got {dom['currently_away_exeat']}"

        print("\nALL BASIC SCHOOL DASHBOARD ANALYTICS TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()

if __name__ == "__main__":
    test_basic_school_dashboard_analytics()
