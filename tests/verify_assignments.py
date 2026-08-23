"""
Automated Verification Script for Teacher Subject Assignments
"""
import sys
from sqlalchemy.orm import Session

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User, Role, ClassSection, SchoolStage, Subject, Semester, AcademicYear, TeacherAssignment
from backend.app.schemas import TeacherAssignmentCreate
from backend.app.routes.assignments import create_assignment, list_assignments

def run_tests():
    print("==================================================")
    print(" TEACHER ASSIGNMENTS VERIFICATION SUITE          ")
    print("==================================================")

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Setup Test Data
        print("\n[1] Setting up assignment test environment...")

        role_teacher = db.query(Role).filter(Role.name == "teacher").first()
        if not role_teacher:
            role_teacher = Role(name="teacher")
            db.add(role_teacher)
            db.commit()

        role_admin = db.query(Role).filter(Role.name == "admin").first()
        if not role_admin:
            role_admin = Role(name="admin")
            db.add(role_admin)
            db.commit()

        user_admin = db.query(User).filter(User.username == "test_asgn_admin").first()
        if not user_admin:
            user_admin = User(username="test_asgn_admin", email="asgn_admin@school.edu", password_hash="pass", roles=[role_admin])
            db.add(user_admin)
            db.commit()

        teacher_user = db.query(User).filter(User.username == "test_asgn_teacher").first()
        if not teacher_user:
            teacher_user = User(username="test_asgn_teacher", email="asgn_teacher@school.edu", password_hash="pass", roles=[role_teacher])
            db.add(teacher_user)
            db.commit()

        from backend.app.routes.assignments import _get_school_mode
        active_mode = _get_school_mode(db)
        stype = "SHS" if active_mode == "SHS_ONLY" else "Basic"

        stage = db.query(SchoolStage).filter(SchoolStage.name == "Asgn Stage").first()
        if not stage:
            stage = SchoolStage(name="Asgn Stage", school_type=stype)
            db.add(stage)
            db.commit()
        else:
            stage.school_type = stype
            db.commit()

        class_sec = db.query(ClassSection).filter(ClassSection.name == "Form 1 Asgn Test").first()
        if not class_sec:
            class_sec = ClassSection(name="Form 1 Asgn Test", stage_id=stage.id)
            db.add(class_sec)
            db.commit()

        subj = db.query(Subject).filter(Subject.name == "Asgn Science").first()
        if not subj:
            subj = Subject(name="Asgn Science", code="ASCI", is_core=True)
            db.add(subj)
            db.commit()

        ay = db.query(AcademicYear).filter(AcademicYear.label == "2025/2026 Asgn").first()
        if not ay:
            ay = AcademicYear(label="2025/2026 Asgn", is_current=True)
            db.add(ay)
            db.commit()

        sem = db.query(Semester).filter(Semester.name == "Term 1 Asgn").first()
        if not sem:
            sem = Semester(name="Term 1 Asgn", academic_year_id=ay.id, is_current=True)
            db.add(sem)
            db.commit()

        # Idempotency cleanup
        db.query(TeacherAssignment).filter(
            TeacherAssignment.teacher_id == teacher_user.id,
            TeacherAssignment.class_section_id == class_sec.id,
            TeacherAssignment.subject_id == subj.id,
            TeacherAssignment.semester_id == sem.id
        ).delete(synchronize_session=False)
        db.commit()

        print("   [OK] Test teacher, class section, subject, and semester established.")

        # 2. Test Assignment Creation
        print("\n[2] Creating Teacher Assignment...")
        asgn_req = TeacherAssignmentCreate(
            teacher_id=teacher_user.id,
            subject_id=subj.id,
            class_section_id=class_sec.id,
            semester_id=sem.id
        )
        asgn_res = create_assignment(asgn_req, db=db, current_user=user_admin)
        assert asgn_res["teacher_id"] == teacher_user.id, "Teacher ID mismatch!"
        assert asgn_res["subject_id"] == subj.id, "Subject ID mismatch!"
        print(f"   [OK] Created assignment #{asgn_res['id']} for {asgn_res['teacher_name']} -> {asgn_res['subject_name']} ({asgn_res['class_section_name']}).")

        # 3. Test Querying Assignments List
        print("\n[3] Querying Assignments List...")
        asgns_list = list_assignments(
            db=db,
            current_user=user_admin
        )
        matching_asgn = next((a for a in asgns_list if a["id"] == asgn_res["id"]), None)
        assert matching_asgn is not None, "Created assignment should be present in assignments list!"
        print(f"   [OK] Retrieved {len(asgns_list)} assignment record(s).")

        print("\n==================================================")
        print(" ALL TEACHER ASSIGNMENT TESTS PASSED SUCCESSFULLY!")
        print("==================================================")

    except Exception as e:
        print(f"\n[FAIL] VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
