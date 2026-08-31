import sys
import os

# Ensure backend is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.database import SessionLocal, run_migrations
from app.models import School, User, Role, ClassSection, Subject, Student, TeacherAssignment, Score
from app.routes.academic import get_executive_analytics

def run_basic_dashboards_test_suite():
    print("=" * 60)
    print(" GHANAIAN BASIC SCHOOL ENTERPRISE DASHBOARDS TEST SUITE")
    print("=" * 60)

    run_migrations()
    db = SessionLocal()

    try:
        # 1. Setup Test Basic School
        sch = db.query(School).filter(School.name == "Dashboards Test Basic School").first()
        if not sch:
            sch = School(
                name="Dashboards Test Basic School",
                code="DTBS-001",
                slug="dashboards-test-basic-school",
                school_mode="BASIC_ONLY",
                boarding_type="DAY_ONLY"
            )
            db.add(sch)
            db.commit()
            db.refresh(sch)

        # 2. Setup Headteacher User
        head_user = db.query(User).filter(User.username == "headteacher_test_dash").first()
        if not head_user:
            head_user = User(
                username="headteacher_test_dash",
                email="head_dash@test.com",
                password_hash="hash",
                school_id=sch.id,
                is_first_login=False
            )
            admin_role = db.query(Role).filter(Role.name == "admin").first()
            if not admin_role:
                admin_role = Role(name="admin")
                db.add(admin_role)
                db.commit()
            head_user.roles.append(admin_role)
            db.add(head_user)
            db.commit()
            db.refresh(head_user)

        # Stages
        from app.models import SchoolStage
        pri_stage = db.query(SchoolStage).filter(SchoolStage.name == "Primary School", SchoolStage.school_id == sch.id).first()
        if not pri_stage:
            pri_stage = SchoolStage(name="Primary School", school_type="Basic", school_id=sch.id)
            db.add(pri_stage)
            db.commit()
            db.refresh(pri_stage)

        jhs_stage = db.query(SchoolStage).filter(SchoolStage.name == "Junior High School", SchoolStage.school_id == sch.id).first()
        if not jhs_stage:
            jhs_stage = SchoolStage(name="Junior High School", school_type="Basic", school_id=sch.id)
            db.add(jhs_stage)
            db.commit()
            db.refresh(jhs_stage)

        # 3. Setup Primary Class & Primary Teacher (Mr. Mensah)
        primary_cls = db.query(ClassSection).filter(ClassSection.name == "Class 4 A", ClassSection.school_id == sch.id).first()
        if not primary_cls:
            primary_cls = ClassSection(name="Class 4 A", stage_id=pri_stage.id, school_id=sch.id)
            db.add(primary_cls)
            db.commit()
            db.refresh(primary_cls)

        teacher_primary = db.query(User).filter(User.username == "teacher_primary_mensah").first()
        if not teacher_primary:
            teacher_primary = User(
                username="teacher_primary_mensah",
                email="mensah_pri@test.com",
                password_hash="hash",
                school_id=sch.id,
                is_first_login=False
            )
            teacher_role = db.query(Role).filter(Role.name == "teacher").first()
            if not teacher_role:
                teacher_role = Role(name="teacher")
                db.add(teacher_role)
                db.commit()
            teacher_primary.roles.append(teacher_role)
            db.add(teacher_primary)
            db.commit()
            db.refresh(teacher_primary)

        # Assign as Form Master for Class 4 A
        primary_cls.form_master_id = teacher_primary.id
        db.commit()

        # Add 2 pupils to Class 4 A
        for idx in range(1, 3):
            st = db.query(Student).filter(Student.student_code == f"P4-ST-{idx}", Student.school_id == sch.id).first()
            if not st:
                st = Student(
                    full_name=f"Primary Pupil {idx}",
                    student_code=f"P4-ST-{idx}",
                    gender="M" if idx == 1 else "F",
                    class_section_id=primary_cls.id,
                    school_id=sch.id,
                    is_active=True
                )
                db.add(st)
                db.commit()

        # 4. Setup JHS 3 Class & JHS Multi-Subject Teacher (Madam Fatima - JHS Form Mistress + Science & Computing Teacher)
        jhs3_cls = db.query(ClassSection).filter(ClassSection.name == "JHS 3 A", ClassSection.school_id == sch.id).first()
        if not jhs3_cls:
            jhs3_cls = ClassSection(name="JHS 3 A", stage_id=jhs_stage.id, school_id=sch.id)
            db.add(jhs3_cls)
            db.commit()
            db.refresh(jhs3_cls)

        jhs2_cls = db.query(ClassSection).filter(ClassSection.name == "JHS 2 A", ClassSection.school_id == sch.id).first()
        if not jhs2_cls:
            jhs2_cls = ClassSection(name="JHS 2 A", stage_id=jhs_stage.id, school_id=sch.id)
            db.add(jhs2_cls)
            db.commit()
            db.refresh(jhs2_cls)

        teacher_jhs = db.query(User).filter(User.username == "teacher_jhs_fatima").first()
        if not teacher_jhs:
            teacher_jhs = User(
                username="teacher_jhs_fatima",
                email="fatima_jhs@test.com",
                password_hash="hash",
                school_id=sch.id,
                is_first_login=False
            )
            teacher_jhs.roles.append(teacher_role)
            db.add(teacher_jhs)
            db.commit()
            db.refresh(teacher_jhs)

        # Fatima is Form Mistress for JHS 3 A
        jhs3_cls.form_master_id = teacher_jhs.id
        db.commit()

        # Add JHS 3 candidate pupils with BECE index
        st_cand = db.query(Student).filter(Student.student_code == "BECE-CAND-01", Student.school_id == sch.id).first()
        if not st_cand:
            st_cand = Student(
                full_name="Kofi Mensah BECE Candidate",
                student_code="BECE-CAND-01",
                bece_index_number="0101001001",
                gender="M",
                class_section_id=jhs3_cls.id,
                school_id=sch.id,
                is_active=True
            )
            db.add(st_cand)
            db.commit()

        # Subjects
        sci_subj = db.query(Subject).filter(Subject.name == "Basic Integrated Science (Dash Test)").first()
        if not sci_subj:
            sci_subj = Subject(name="Basic Integrated Science (Dash Test)", code="SCI-JHS-DASH", school_id=sch.id)
            db.add(sci_subj)
            db.commit()
            db.refresh(sci_subj)

        ict_subj = db.query(Subject).filter(Subject.name == "Basic Computing / ICT (Dash Test)").first()
        if not ict_subj:
            ict_subj = Subject(name="Basic Computing / ICT (Dash Test)", code="ICT-JHS-DASH", school_id=sch.id)
            db.add(ict_subj)
            db.commit()
            db.refresh(ict_subj)

        # Academic Year & Term
        from app.models import AcademicYear, Semester
        ay = db.query(AcademicYear).filter(AcademicYear.is_current == True).first()
        if not ay:
            ay = db.query(AcademicYear).first()
        if not ay:
            ay = AcademicYear(label="2026/2027 Academic Year", is_current=True)
            db.add(ay)
            db.commit()
            db.refresh(ay)

        term = db.query(Semester).filter(Semester.academic_year_id == ay.id, Semester.is_current == True).first()
        if not term:
            term = db.query(Semester).filter(Semester.academic_year_id == ay.id).first()
        if not term:
            term = Semester(name="Term 2", academic_year_id=ay.id, is_current=True)
            db.add(term)
            db.commit()
            db.refresh(term)

        # Allocate Fatima to teach Science in JHS 2A & JHS 3A, and Computing in JHS 3A
        for c_obj, s_obj in [(jhs2_cls, sci_subj), (jhs3_cls, sci_subj), (jhs3_cls, ict_subj)]:
            asgn = db.query(TeacherAssignment).filter(
                TeacherAssignment.teacher_id == teacher_jhs.id,
                TeacherAssignment.class_section_id == c_obj.id,
                TeacherAssignment.subject_id == s_obj.id,
                TeacherAssignment.semester_id == term.id
            ).first()
            if not asgn:
                asgn = TeacherAssignment(
                    teacher_id=teacher_jhs.id,
                    class_section_id=c_obj.id,
                    subject_id=s_obj.id,
                    semester_id=term.id
                )
                db.add(asgn)
                db.commit()

        # Record a test score for JHS 3 candidate
        sc = db.query(Score).filter(Score.student_id == st_cand.id, Score.subject_id == sci_subj.id, Score.semester_id == term.id).first()
        if not sc:
            sc = Score(
                student_id=st_cand.id,
                subject_id=sci_subj.id,
                semester_id=term.id,
                class_score=42.0,
                exam_score=44.0,
                total_score=86.0
            )
            db.add(sc)
            db.commit()

        print("\n[1] Testing Headteacher Executive Analytics API...")
        exec_data = get_executive_analytics(
            db=db,
            current_user=head_user,
            school_id=sch.id
        )

        assert exec_data["school_mode"] == "BASIC_ONLY"
        assert "academic" in exec_data
        assert "bece_candidate_tracker" in exec_data["academic"]
        
        bece_info = exec_data["academic"]["bece_candidate_tracker"]
        assert bece_info is not None, "BECE candidate tracker must be populated for basic schools with JHS 3"
        assert bece_info["total_candidates"] >= 1
        assert bece_info["index_assigned_count"] >= 1
        print(f"   [OK] Headteacher Analytics verified: Mode={exec_data['school_mode']}, BECE Candidates={bece_info['total_candidates']}, IndexAssigned={bece_info['index_assigned_count']}")

        print("\n[2] Testing Primary Class Teacher Workspace Data...")
        pri_data = get_executive_analytics(
            db=db,
            current_user=teacher_primary,
            school_id=sch.id
        )

        t_pri = pri_data["teacher"]
        assert t_pri["is_primary_teacher"] is True, "Expected is_primary_teacher=True for Class 4 Form Master"
        assert t_pri["form_class"] is not None
        assert t_pri["form_class"]["name"] == "Class 4 A"
        print(f"   [OK] Primary Class Teacher Workspace verified: FormClass={t_pri['form_class']['name']}, is_primary={t_pri['is_primary_teacher']}")

        print("\n[3] Testing JHS Multi-Subject Teacher & Form Mistress Workspace Data...")
        jhs_data = get_executive_analytics(
            db=db,
            current_user=teacher_jhs,
            school_id=sch.id
        )

        t_jhs = jhs_data["teacher"]
        assert t_jhs["is_jhs_teacher"] is True, "Expected is_jhs_teacher=True for JHS 3 Form Mistress"
        assert t_jhs["form_class"]["name"] == "JHS 3 A"
        assert len(t_jhs["allocations"]) >= 3, f"Expected 3 subject allocations, got {len(t_jhs['allocations'])}"
        print(f"   [OK] JHS Multi-Subject Workspace verified: FormClass={t_jhs['form_class']['name']}, Allocations={len(t_jhs['allocations'])}")

        print("\n[4] Testing Assistant Headteacher Multi-Role Designation...")
        asst_role = db.query(Role).filter(Role.name == "assistant_head_academic").first()
        if not asst_role:
            asst_role = Role(name="assistant_head_academic")
            db.add(asst_role)
            db.commit()
        teacher_jhs.roles.append(asst_role)
        db.commit()

        asst_data = get_executive_analytics(
            db=db,
            current_user=teacher_jhs,
            school_id=sch.id
        )
        assert asst_data["teacher"]["is_assistant_head"] is True, "Expected is_assistant_head=True"
        print(f"   [OK] Assistant Headteacher designation verified: is_assistant_head={asst_data['teacher']['is_assistant_head']}")

        print("\n" + "=" * 60)
        print(" ALL BASIC SCHOOL ENTERPRISE DASHBOARDS TESTS PASSED!")
        print("=" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    run_basic_dashboards_test_suite()
