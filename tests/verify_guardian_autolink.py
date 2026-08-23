import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.database import SessionLocal, engine, Base
from app.models import Student, User, Role, ClassSection, SchoolStage
from app.services.guardian_service import (
    auto_link_guardian_for_student,
    auto_link_all_guardians,
    link_students_for_parent_user,
    get_or_create_parent_role
)
from app.routes.students import create_student, StudentCreate

import time

def run_tests():
    db = SessionLocal()
    print("=== STARTING GUARDIAN AUTO-LINKING VERIFICATION TESTS ===")

    # Clean up prior test records if any
    db.query(Student).filter(Student.student_code.like("TEST-AUTOLINK-%")).delete(synchronize_session=False)
    db.commit()

    ts = str(int(time.time()))
    code1 = f"TEST-AUTOLINK-{ts}-1"
    code2 = f"TEST-AUTOLINK-{ts}-2"
    code3 = f"TEST-AUTOLINK-{ts}-3"
    
    # 0. Ensure a dummy class section exists
    stage = db.query(SchoolStage).first()
    if not stage:
        stage = SchoolStage(name="Test Stage", school_type="Basic")
        db.add(stage)
        db.flush()
    
    csec = db.query(ClassSection).first()
    if not csec:
        csec = ClassSection(name="Basic 1 Test", stage_id=stage.id)
        db.add(csec)
        db.flush()
    db.commit()
    class_id = csec.id

    admin_user = db.query(User).filter(User.username == "admin").first()

    # Test 1: Single student creation triggers automatic guardian creation & linking
    s1_data = StudentCreate(
        student_code=code1,
        full_name="Ama Serwaa",
        class_section_id=class_id,
        phone="0249998877",
        guardian_name="Kofi Serwaa"
    )
    s1 = create_student(s1_data, db, admin_user)
    print(f"Test 1 - Student 1 created: ID={s1['id']}, parent_id={s1['parent_id']}, parent_username={s1['parent_username']}")
    assert s1['parent_id'] is not None, "Student 1 should have parent_id auto-assigned"
    assert s1['parent_username'] == "parent_0249998877", f"Unexpected parent username: {s1['parent_username']}"

    parent1_id = s1['parent_id']

    # Test 2: Second student created with matching phone number links to the SAME parent User (1-to-many)
    s2_data = StudentCreate(
        student_code=code2,
        full_name="Kwaku Serwaa",
        class_section_id=class_id,
        phone="0249998877",
        guardian_name="Kofi Serwaa"
    )
    s2 = create_student(s2_data, db, admin_user)
    print(f"Test 2 - Student 2 created with same phone: ID={s2['id']}, parent_id={s2['parent_id']}, parent_username={s2['parent_username']}")
    assert s2['parent_id'] == parent1_id, "Student 2 should be linked to the same parent User as Student 1"

    # Verify parent user has 2 children
    parent1_user = db.query(User).filter(User.id == parent1_id).first()
    linked_children = db.query(Student).filter(Student.parent_id == parent1_id).all()
    print(f"Verified Guardian '{parent1_user.username}' has {len(linked_children)} linked children: {[c.full_name for c in linked_children]}")
    assert len(linked_children) >= 2, f"Expected at least 2 children for guardian {parent1_user.username}"

    # Test 3: Pre-existing Parent User created, then student added with matching guardian name/phone
    parent_role = get_or_create_parent_role(db)
    p2_username = f"parent_john_doe_{ts}"
    p3_phone = f"020{ts[-7:]}"
    p2_user = User(
        username=p2_username,
        email=f"{p2_username}@example.com",
        password_hash="dummyhash",
        is_active=True
    )
    p2_user.roles.append(parent_role)
    db.add(p2_user)
    db.commit()

    s3_data = StudentCreate(
        student_code=code3,
        full_name="Abena Doe",
        class_section_id=class_id,
        phone=p3_phone,
        guardian_name=p2_username
    )
    s3 = create_student(s3_data, db, admin_user)
    print(f"Test 3 - Student created matching pre-existing guardian: ID={s3['id']}, parent_id={s3['parent_id']}, parent_username={s3['parent_username']}")
    assert s3['parent_id'] == p2_user.id, "Student 3 should be linked to pre-existing parent_john_doe User"

    # Test 4: Unlink a student, run bulk auto-link service function
    student_obj = db.query(Student).filter(Student.id == s3['id']).first()
    student_obj.parent_id = None
    db.commit()

    stats = auto_link_all_guardians(db)
    print(f"Test 4 - Bulk Auto-Link Stats: {stats}")
    db.refresh(student_obj)
    assert student_obj.parent_id == p2_user.id, "Unlinked student should be re-linked during bulk auto-linking"

    print("\n[SUCCESS] ALL GUARDIAN AUTO-LINKING VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
