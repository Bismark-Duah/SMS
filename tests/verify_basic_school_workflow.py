import sys
import os

# Ensure backend is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.database import SessionLocal
from app.models import School, User, Role, ClassSection, SchoolStage, Subject, Semester, AcademicYear, Student, Score, TeacherAssignment
from app.routes.classes import provision_ges_basic_streams, ProvisionBasicStreamsRequest
from app.routes.assignments import assign_primary_class_teacher, batch_jhs_matrix_assignment, AssignPrimaryClassRequest, BatchJHSMatrixRequest
from app.routes.results import save_batch_class_matrix, BatchClassMatrixRequest, ClassMatrixScoreItem
from app.ncca_seed import seed_ncca_curriculum

def run_basic_school_workflow_suite():
    print("=" * 60)
    print(" GHANAIAN BASIC SCHOOL SPECIALIZED WORKFLOW TEST SUITE")
    print("=" * 60)

    db = SessionLocal()
    try:
        # 0. Ensure NaCCA Curriculum is seeded
        seed_ncca_curriculum(db)

        # 1. Setup Test Basic School
        basic_sch = db.query(School).filter(School.name == "Workflow Test Basic School").first()
        if not basic_sch:
            basic_sch = School(
                name="Workflow Test Basic School",
                code="WTBS-001",
                slug="workflow-test-basic-school",
                school_mode="BASIC_ONLY",
                boarding_type="DAY_ONLY"
            )
            db.add(basic_sch)
            db.commit()
            db.refresh(basic_sch)

        # Mock Admin User
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(username="admin", email="admin@test.com", password_hash="hash", school_id=basic_sch.id)
            admin_role = db.query(Role).filter(Role.name == "admin").first()
            if not admin_role:
                admin_role = Role(name="admin")
                db.add(admin_role)
                db.commit()
            admin_user.roles.append(admin_role)
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

        # Mock Teachers
        primary_teacher = db.query(User).filter(User.username == "mr_mensah_primary").first()
        if not primary_teacher:
            primary_teacher = User(
                username="mr_mensah_primary",
                email="kwame@test.com",
                password_hash="hash",
                school_id=basic_sch.id
            )
            t_role = db.query(Role).filter(Role.name == "teacher").first()
            if not t_role:
                t_role = Role(name="teacher")
                db.add(t_role)
                db.commit()
            primary_teacher.roles.append(t_role)
            db.add(primary_teacher)
            db.commit()
            db.refresh(primary_teacher)

        jhs_teacher = db.query(User).filter(User.username == "madam_fatima_jhs").first()
        if not jhs_teacher:
            jhs_teacher = User(
                username="madam_fatima_jhs",
                email="fatima@test.com",
                password_hash="hash",
                school_id=basic_sch.id
            )
            t_role = db.query(Role).filter(Role.name == "teacher").first()
            jhs_teacher.roles.append(t_role)
            db.add(jhs_teacher)
            db.commit()
            db.refresh(jhs_teacher)

        # Mock Academic Year & Semester
        acad_yr = db.query(AcademicYear).first()
        if not acad_yr:
            acad_yr = AcademicYear(label="2025/2026", is_active=True)
            db.add(acad_yr)
            db.commit()
            db.refresh(acad_yr)

        sem = db.query(Semester).first()
        if not sem:
            sem = Semester(name="Term 1", academic_year_id=acad_yr.id, is_active=True)
            db.add(sem)
            db.commit()
            db.refresh(sem)

        print("\n[1] Testing 1-Click GES Basic School Stream Auto-Provisioner...")
        # A) Provision 2-Stream setup (A & B arms)
        prov_req = ProvisionBasicStreamsRequest(
            stream_mode="TWO_ARMS_AB",
            include_creche=True,
            include_nursery=True,
            include_kg=True,
            include_primary=True,
            include_jhs=True,
            school_id=basic_sch.id
        )
        res_prov = provision_ges_basic_streams(payload=prov_req, db=db, current_user=admin_user)
        print(f"   [OK] Provisioned {res_prov['created_count']} streams (Skipped {len(res_prov['skipped_existing'])} existing).")
        
        # Verify Class 3A and JHS 1A exist with subjects
        class_3a = db.query(ClassSection).filter(ClassSection.name == "Class 3 A", ClassSection.school_id == basic_sch.id).first()
        if not class_3a:
            class_3a = db.query(ClassSection).filter(ClassSection.name == "Class 3A", ClassSection.school_id == basic_sch.id).first()
        assert class_3a is not None, "Class 3 A stream was not created!"
        print(f"   [OK] Class 3 Stream verified: {class_3a.name} ({len(class_3a.subjects)} NaCCA subjects linked)")

        jhs_1a = db.query(ClassSection).filter(ClassSection.name == "JHS 1 A", ClassSection.school_id == basic_sch.id).first()
        if not jhs_1a:
            jhs_1a = db.query(ClassSection).filter(ClassSection.name == "JHS 1A", ClassSection.school_id == basic_sch.id).first()
        assert jhs_1a is not None, "JHS 1 A stream was not created!"

        print("\n[2] Testing 1-Click Primary Class Teacher (All-Subject) Fast Allocation...")
        assign_req = AssignPrimaryClassRequest(
            teacher_id=primary_teacher.id,
            class_section_id=class_3a.id,
            semester_id=sem.id
        )
        res_assign = assign_primary_class_teacher(payload=assign_req, db=db, current_user=admin_user)
        print(f"   [OK] {res_assign['message']}")
        assert res_assign["subjects_assigned_count"] >= 5, "Fewer subjects assigned than expected!"

        # Verify class form_master is updated
        db.refresh(class_3a)
        assert class_3a.form_master_id == primary_teacher.id, "Form master was not set to primary teacher!"
        print(f"   [OK] Form Master correctly verified as {primary_teacher.username}")

        print("\n[3] Testing JHS Multi-Subject Matrix Workload Allocation...")
        # Get Math and Computing subjects
        math_sub = db.query(Subject).filter(Subject.name.ilike("%Mathematics%")).first()
        comp_sub = db.query(Subject).filter(Subject.name.ilike("%Computing%")).first()
        assert math_sub and comp_sub, "Math and Computing subjects missing!"

        jhs_classes = db.query(ClassSection).filter(
            ClassSection.name.ilike("JHS%"),
            ClassSection.school_id == basic_sch.id
        ).all()
        jhs_class_ids = [c.id for c in jhs_classes[:3]]

        jhs_req = BatchJHSMatrixRequest(
            teacher_id=jhs_teacher.id,
            subject_ids=[math_sub.id, comp_sub.id],
            class_section_ids=jhs_class_ids,
            semester_id=sem.id
        )
        res_jhs = batch_jhs_matrix_assignment(payload=jhs_req, db=db, current_user=admin_user)
        print(f"   [OK] {res_jhs['message']}")
        assert res_jhs["assigned_count"] > 0, "No assignments created for JHS matrix!"

        print("\n[4] Testing Primary All-in-One Class Marks Matrix Batch Persistence...")
        # Create 2 test students in Class 3A
        st1 = db.query(Student).filter(Student.student_code == "ST-TEST-001").first()
        if not st1:
            st1 = Student(
                student_code="ST-TEST-001",
                full_name="Kofi Annan",
                first_name="Kofi",
                last_name="Annan",
                class_section_id=class_3a.id,
                school_id=basic_sch.id,
                is_active=True
            )
            db.add(st1)

        st2 = db.query(Student).filter(Student.student_code == "ST-TEST-002").first()
        if not st2:
            st2 = Student(
                student_code="ST-TEST-002",
                full_name="Abena Osei",
                first_name="Abena",
                last_name="Osei",
                class_section_id=class_3a.id,
                school_id=basic_sch.id,
                is_active=True
            )
            db.add(st2)
        db.commit()
        db.refresh(st1)
        db.refresh(st2)

        # Batch submit scores for st1 and st2 across math and computing
        matrix_req = BatchClassMatrixRequest(
            class_section_id=class_3a.id,
            semester_id=sem.id,
            records=[
                ClassMatrixScoreItem(student_id=st1.id, subject_id=math_sub.id, class_score=38.0, exam_score=45.0),
                ClassMatrixScoreItem(student_id=st1.id, subject_id=comp_sub.id, class_score=40.0, exam_score=48.0),
                ClassMatrixScoreItem(student_id=st2.id, subject_id=math_sub.id, class_score=45.0, exam_score=50.0),
                ClassMatrixScoreItem(student_id=st2.id, subject_id=comp_sub.id, class_score=44.0, exam_score=49.0),
            ]
        )
        res_matrix = save_batch_class_matrix(payload=matrix_req, db=db, current_user=admin_user)
        print(f"   [OK] {res_matrix['message']}")
        assert res_matrix["saved_count"] == 4, f"Expected 4 saved scores, got {res_matrix['saved_count']}"

        # Verify saved score and grade in database
        st1_math_score = db.query(Score).filter(
            Score.student_id == st1.id,
            Score.subject_id == math_sub.id,
            Score.semester_id == sem.id
        ).first()
        assert st1_math_score is not None, "Score was not persisted in database!"
        assert st1_math_score.total_score == 83.0, f"Expected 83.0, got {st1_math_score.total_score}"
        print(f"   [OK] Verified student score: {st1_math_score.total_score} (Grade: {st1_math_score.grade})")

        print("\n" + "=" * 60)
        print(" ALL GHANAIAN BASIC SCHOOL WORKFLOW TESTS PASSED SUCCESSFULLY!")
        print("=" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    run_basic_school_workflow_suite()
