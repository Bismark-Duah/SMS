"""
Verification Script for Departments & HOD Management API
"""
import sys
from backend.app.database import SessionLocal
from backend.app.models import Department, Subject, User

def test_departments():
    print("--- Verifying Departments & HOD Management ---")
    db = SessionLocal()
    try:
        # Create test subject if needed
        subject = db.query(Subject).first()
        if not subject:
            subject = Subject(name="Test Dept Subject", code="TDS01", is_core=True)
            db.add(subject)
            db.flush()

        # Find or create admin user for HOD test
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(username="admin_dept_test", email="adept@test.com", password_hash="hash", is_active=True)
            db.add(admin_user)
            db.flush()

        # Test Department Creation
        dept_name = "Department of Science Test"
        dept_code = "DEPT_SCI_TEST"
        existing = db.query(Department).filter(Department.code == dept_code).first()
        if existing:
            db.delete(existing)
            db.commit()

        dept = Department(
            name=dept_name,
            code=dept_code,
            hod_id=admin_user.id,
            subjects=[subject]
        )
        db.add(dept)
        db.commit()
        db.refresh(dept)

        assert dept.id is not None, "Department creation failed: Missing ID"
        assert dept.name == dept_name, f"Expected {dept_name}, got {dept.name}"
        assert dept.code == dept_code, f"Expected {dept_code}, got {dept.code}"
        assert dept.hod_id == admin_user.id, "HOD assignment failed"
        assert len(dept.subjects) == 1, "Department subject mapping failed"

        # Test Department Query & Update
        queried = db.query(Department).filter(Department.id == dept.id).first()
        assert queried is not None, "Failed to query created department"
        queried.name = "Department of Science Updated"
        db.commit()

        updated = db.query(Department).filter(Department.id == dept.id).first()
        assert updated.name == "Department of Science Updated", "Department update failed"

        # Cleanup test dept
        db.delete(updated)
        db.commit()

        print("[OK] Departments & HOD Management verified successfully!")
    except Exception as e:
        print(f"[FAIL] Verification failed: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    test_departments()
