import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath("backend"))

from app.database import SessionLocal
from app.models import Student, User, School
from app.routes.reports import get_parent_ward_summary

def test_parent_portal():
    db = SessionLocal()
    print("Testing Parent Ward Summary Endpoint...")

    # Fetch admin user and a student from the SAME school
    admin_user = db.query(User).filter(User.username == "admin").first()

    if not admin_user:
        print("[FAIL] admin user not found in database.")
        db.close()
        sys.exit(1)

    # Get a student that belongs to admin's school (or any student if admin has no school_id)
    admin_school_id = getattr(admin_user, "school_id", None)
    if admin_school_id:
        student = db.query(Student).filter(Student.school_id == admin_school_id).first()
    else:
        student = db.query(Student).first()

    if not student:
        # Create a minimal student for testing
        print("[INFO] No student found — creating a test student for this verification...")
        school = db.query(School).first()
        if not school:
            print("[FAIL] No school found in database.")
            db.close()
            sys.exit(1)
        import time
        student = Student(
            full_name=f"Test Student {int(time.time())}",
            student_code=f"TST{int(time.time())}",
            school_id=school.id,
            gender="M",
            residential_status="D",
        )
        db.add(student)
        db.commit()
        db.refresh(student)
        print(f"   [OK] Created test student ID {student.id}: {student.full_name}")

    print(f"Testing for Student ID {student.id} ({student.full_name})...")

    summary = get_parent_ward_summary(student_id=student.id, db=db, current_user=admin_user)

    print("[OK] Parent Ward Summary Payload Retrieved:")
    print(f"  - Student: {summary['student_info']['full_name']} ({summary['student_info']['student_code']})")
    print(f"  - Class: {summary['student_info']['class_name']} | House: {summary['student_info']['house_name']}")
    print(f"  - Attendance: {summary['attendance']['percentage']}% ({summary['attendance']['present_days']}/{summary['attendance']['total_days']} days)")
    print(f"  - Fees: Outstanding Balance GHS {summary['financial']['outstanding_balance']} (Total Billed: GHS {summary['financial']['total_billed']})")
    print(f"  - Recent Payments: {len(summary['financial']['payments'])} payment record(s)")
    print(f"  - Active Exeat Pass: {summary['exeat']['has_active_exeat']}")
    print(f"  - Discipline Records: {len(summary['discipline'])} incident(s)")

    db.close()
    print("\nALL PARENT DASHBOARD PORTAL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_parent_portal()
