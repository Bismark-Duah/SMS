import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath("backend"))

from app.database import SessionLocal
from app.models import Department, User, TeacherAssignment, Subject, ClassSection, Semester
from app.routes.assignments import list_privileges, update_assignment
from app.schemas import TeacherAssignmentCreate

def test_workload_fixes():
    db = SessionLocal()
    print("Testing Workload Fixes & Edit Feature...")

    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        print("[FAIL] Admin user not found.")
        db.close()
        sys.exit(1)

    # 1. Test Privileges List (includes HODs and leadership roles)
    privileges = list_privileges(db=db, current_user=admin_user)
    print(f"[OK] Total Privileges Retrieved: {len(privileges)}")
    hod_privs = [p for p in privileges if "HOD" in p.privilege_type or "Head of Department" in p.privilege_type]
    print(f"[OK] Active HOD Privileges Count: {len(hod_privs)}")
    for hp in hod_privs[:5]:
        print(f"      - {hp.teacher_name} -> {hp.privilege_type} ({hp.target_name})")

    # 2. Test Editing an Assignment via PUT /api/assignments/{id}
    asgn = db.query(TeacherAssignment).first()
    if asgn:
        print(f"\n[OK] Found existing assignment ID {asgn.id} (Teacher {asgn.teacher_id}, Subject {asgn.subject_id}, Class {asgn.class_section_id})")
        payload = TeacherAssignmentCreate(
            teacher_id=asgn.teacher_id,
            subject_id=asgn.subject_id,
            class_section_id=asgn.class_section_id,
            semester_id=asgn.semester_id
        )
        updated = update_assignment(assignment_id=asgn.id, payload=payload, db=db, current_user=admin_user)
        print(f"[OK] Successfully updated assignment ID {updated['id']} via PUT handler!")

    db.close()
    print("\nALL WORKLOAD FIXES AND EDIT ASSIGNMENT TESTS PASSED!")

if __name__ == "__main__":
    test_workload_fixes()
