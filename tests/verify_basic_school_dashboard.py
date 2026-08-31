import sys
import os

# Set sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.database import SessionLocal
from app.models import School, Student, ClassSection, Subject, User, Score, Setting, SchoolStage
from app.routes.academic import get_executive_analytics

def test_basic_school_dashboard_analytics():
    print("Testing Basic School Dashboard Executive Analytics Backend & Isolation...")
    db = SessionLocal()
    try:
        # 1. Create or find Basic School
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

        # 2. Create or find SHS School
        shs_school = db.query(School).filter(School.name == "Test SHS School").first()
        if not shs_school:
            shs_school = School(
                name="Test SHS School",
                code="TSHS-001",
                slug="test-shs-school",
                school_mode="SHS_ONLY",
                boarding_type="BOARDING_AND_DAY"
            )
            db.add(shs_school)
            db.commit()
            db.refresh(shs_school)

        # 3. Create stages and classes
        basic_stage = db.query(SchoolStage).filter(SchoolStage.name == "Primary School Stage").first()
        if not basic_stage:
            basic_stage = SchoolStage(name="Primary School Stage", school_type="Basic", school_id=basic_school.id)
            db.add(basic_stage)
            db.commit()
            db.refresh(basic_stage)

        shs_stage = db.query(SchoolStage).filter(SchoolStage.name == "SHS Form 1 Stage").first()
        if not shs_stage:
            shs_stage = SchoolStage(name="SHS Form 1 Stage", school_type="SHS", school_id=shs_school.id)
            db.add(shs_stage)
            db.commit()
            db.refresh(shs_stage)

        # Basic class for Basic School
        basic_class = db.query(ClassSection).filter(ClassSection.name == "Class 4 Excellence").first()
        if not basic_class:
            basic_class = ClassSection(name="Class 4 Excellence", stage_id=basic_stage.id, school_id=basic_school.id)
            db.add(basic_class)
            db.commit()

        # SHS class for SHS School
        shs_class = db.query(ClassSection).filter(ClassSection.name == "Form 1 Science A").first()
        if not shs_class:
            shs_class = ClassSection(name="Form 1 Science A", stage_id=shs_stage.id, school_id=shs_school.id)
            db.add(shs_class)
            db.commit()

        # Mock current admin user
        admin_user = db.query(User).filter(User.username == "admin").first()

        # Execute executive analytics for BASIC School
        res = get_executive_analytics(db=db, current_user=admin_user, school_id=basic_school.id)

        print("[OK] Response received for Basic School")
        assert res["school_mode"] == "BASIC_ONLY"

        ac = res["academic"]
        adm = res["administration"]
        dom = res["domestic"]

        classes_matrix = ac.get("classes_matrix", [])
        class_names = [c["name"] for c in classes_matrix]
        print("  - Basic School classes returned in matrix:", class_names)

        # Verify NO SHS classes leaked into Basic school matrix
        for name in class_names:
            assert "Form 1" not in name, f"SHS class {name} leaked into Basic School matrix!"
            assert "Form 2" not in name, f"SHS class {name} leaked into Basic School matrix!"
            assert "Form 3" not in name, f"SHS class {name} leaked into Basic School matrix!"
            assert "STEM" not in name, f"SHS class {name} leaked into Basic School matrix!"

        assert "Class 4 Excellence" in class_names, "Basic class was not returned in Basic School matrix!"

        # Execute executive analytics for SHS School
        res_shs = get_executive_analytics(db=db, current_user=admin_user, school_id=shs_school.id)
        assert res_shs["school_mode"] == "SHS_ONLY"

        print("\nALL BASIC SCHOOL DASHBOARD ANALYTICS & ISOLATION TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()

if __name__ == "__main__":
    test_basic_school_dashboard_analytics()
