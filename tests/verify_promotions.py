"""
Automated Verification Script for Student Promotion & Graduation Workflow
"""
import sys
from sqlalchemy.orm import Session

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User, Role, ClassSection, Student, StudentSemesterSummary, Semester
from backend.app.routes.promotions import (
    promote_students, graduate_students, check_promotion_permission,
    PromoteRequest, GraduateRequest
)

def run_tests():
    print("==================================================")
    print(" STUDENT PROMOTION & GRADUATION VERIFICATION SUITE")
    print("==================================================")

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Setup Test Data
        print("\n[1] Setting up promotion test data...")

        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            db.add(admin_role)
            db.commit()

        admin_user = db.query(User).filter(User.username == "test_assistant_head_academic").first()
        if not admin_user:
            admin_user = User(username="test_assistant_head_academic", email="asst_head@school.edu", password_hash="pass", roles=[admin_role])
            db.add(admin_user)
            db.commit()

        class_src = db.query(ClassSection).filter(ClassSection.name == "Form 1 STEM A").first()
        if not class_src:
            class_src = ClassSection(name="Form 1 STEM A", stage_id=1)
            db.add(class_src)
            db.commit()

        class_tgt = db.query(ClassSection).filter(ClassSection.name == "Form 2 STEM A").first()
        if not class_tgt:
            class_tgt = ClassSection(name="Form 2 STEM A", stage_id=1)
            db.add(class_tgt)
            db.commit()

        # Students
        st_p1 = db.query(Student).filter(Student.student_code == "PROM-STU-001").first()
        if not st_p1:
            st_p1 = Student(student_code="PROM-STU-001", full_name="Kwame Nkrumah", form=1, class_section_id=class_src.id, is_active=True, status="ACTIVE")
            db.add(st_p1)
        else:
            st_p1.form = 1
            st_p1.class_section_id = class_src.id
            st_p1.is_active = True
            st_p1.status = "ACTIVE"

        st_p2 = db.query(Student).filter(Student.student_code == "PROM-STU-002").first()
        if not st_p2:
            st_p2 = Student(student_code="PROM-STU-002", full_name="Yaa Asantewaa", form=1, class_section_id=class_src.id, is_active=True, status="ACTIVE")
            db.add(st_p2)
        else:
            st_p2.form = 1
            st_p2.class_section_id = class_src.id
            st_p2.is_active = True
            st_p2.status = "ACTIVE"

        db.commit()
        print("   [OK] Source Class (Form 1 STEM A), Target Class (Form 2 STEM A), and Students created.")

        # 2. Test Role Authorization Helper
        print("\n[2] Testing Promotion Authorization Helper...")
        check_promotion_permission(admin_user)
        print("   [OK] Authorization check passed.")

        # 3. Test Batch Student Promotion
        print("\n[3] Testing Batch Promotion Execution...")
        payload_prom = PromoteRequest(
            student_ids=[st_p1.id, st_p2.id],
            target_class_section_id=class_tgt.id,
            increment_form=True
        )

        res_prom = promote_students(payload_prom, db, admin_user)
        print(f"   [OK] {res_prom['message']}")

        # Verify database updates
        db.refresh(st_p1)
        db.refresh(st_p2)

        assert st_p1.class_section_id == class_tgt.id, "Student 1 class_section_id failed to update!"
        assert st_p1.form == 2, f"Student 1 form level should be 2! Got {st_p1.form}"
        assert st_p2.class_section_id == class_tgt.id, "Student 2 class_section_id failed to update!"
        assert st_p2.form == 2, f"Student 2 form level should be 2! Got {st_p2.form}"
        print("   [OK] Class section transfer and Form level increment (1 -> 2) verified.")

        # 4. Test Batch Graduation Execution
        print("\n[4] Testing Batch Graduation Execution...")
        payload_grad = GraduateRequest(
            student_ids=[st_p1.id]
        )

        res_grad = graduate_students(payload_grad, db, admin_user)
        print(f"   [OK] {res_grad['message']}")

        # Verify database updates
        db.expire_all()
        st_check = db.query(Student).filter(Student.id == st_p1.id).first()
        assert st_check.class_section_id == None, "Graduated student should have no class section!"
        assert st_check.status == "GRADUATED", f"Status should be GRADUATED! Got {st_check.status}"
        print("   [OK] Graduation status update and class detachment verified.")

        print("\n==================================================")
        print(" ALL PROMOTION & GRADUATION VERIFICATION TESTS PASSED!")
        print("==================================================")

    except Exception as e:
        print(f"\n[FAIL] PROMOTION VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
