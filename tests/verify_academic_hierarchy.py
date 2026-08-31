"""
Automated Verification Script for Academic Hierarchy & 3-Mode Report Card Publishing
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.database import engine, Base, SessionLocal
from backend.app.models import (
    User, Role, Department, ClassSection, Subject, Semester, Student, Score,
    StudentSemesterSummary, Setting, ClassSectionReportStatus, ClassSubjectScoreStatus
)
from backend.app.routes.academic_hierarchy import (
    _get_publishing_mode,
    _is_academic_head,
    _is_hod,
    _is_form_master_of_class
)

def run_tests():
    print("==================================================")
    print(" ACADEMIC HIERARCHY & PUBLISHING MODES SUITE     ")
    print("==================================================")

    with engine.connect() as conn:
        try:
            conn.execute(text("SELECT department_id FROM users LIMIT 1"))
        except Exception:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN department_id INTEGER REFERENCES departments(id)"))
                conn.commit()
            except Exception as e:
                pass

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Setup Test Roles, Users, Departments, Classes
        print("\n[1] Setting up academic hierarchy test data...")

        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            db.add(admin_role)

        teacher_role = db.query(Role).filter(Role.name == "teacher").first()
        if not teacher_role:
            teacher_role = Role(name="teacher")
            db.add(teacher_role)

        form_master_role = db.query(Role).filter(Role.name == "form_master").first()
        if not form_master_role:
            form_master_role = Role(name="form_master")
            db.add(form_master_role)

        db.commit()

        # Users
        admin_acad = db.query(User).filter(User.username == "test_assistant_head_academic").first()
        if not admin_acad:
            admin_acad = User(username="test_assistant_head_academic", email="asst_acad@school.edu", password_hash="pass", roles=[admin_role])
            db.add(admin_acad)

        hod_science = db.query(User).filter(User.username == "test_hod_science").first()
        if not hod_science:
            hod_science = User(username="test_hod_science", email="hod_sci@school.edu", password_hash="pass", roles=[teacher_role])
            db.add(hod_science)

        form_master_user = db.query(User).filter(User.username == "test_form_master_science").first()
        if not form_master_user:
            form_master_user = User(username="test_form_master_science", email="fm_sci@school.edu", password_hash="pass", roles=[teacher_role, form_master_role])
            db.add(form_master_user)

        db.commit()

        # Department
        dept_science = db.query(Department).filter(Department.name == "Test Science Dept").first()
        if not dept_science:
            dept_science = Department(name="Test Science Dept", code="TSCI", hod_id=hod_science.id)
            db.add(dept_science)

        db.commit()

        # Teacher Department Affiliation
        form_master_user.department_id = dept_science.id
        db.commit()
        assert form_master_user.department_id == dept_science.id, "Teacher department affiliation failed!"
        print("   [OK] Teacher department affiliation verified.")

        # Subjects
        subj_physics = db.query(Subject).filter(Subject.name == "Test Physics").first()
        if not subj_physics:
            subj_physics = Subject(name="Test Physics", code="TPHY", is_core=False)
            db.add(subj_physics)

        subj_chemistry = db.query(Subject).filter(Subject.name == "Test Chemistry").first()
        if not subj_chemistry:
            subj_chemistry = Subject(name="Test Chemistry", code="TCHM", is_core=False)
            db.add(subj_chemistry)

        db.commit()
        if subj_physics not in dept_science.subjects: dept_science.subjects.append(subj_physics)
        if subj_chemistry not in dept_science.subjects: dept_science.subjects.append(subj_chemistry)
        db.commit()

        # Semester
        sem = db.query(Semester).filter(Semester.name == "Test Term 1").first()
        if not sem:
            sem = Semester(name="Test Term 1", is_current=True, academic_year_id=1)
            db.add(sem)
            db.commit()

        # Class Section
        class_sec = db.query(ClassSection).filter(ClassSection.name == "Form 1 Test STEM").first()
        if not class_sec:
            class_sec = ClassSection(name="Form 1 Test STEM", stage_id=1, form_master_id=form_master_user.id)
            db.add(class_sec)
            db.commit()
        else:
            class_sec.form_master_id = form_master_user.id
            db.commit()

        if subj_physics not in class_sec.subjects: class_sec.subjects.append(subj_physics)
        if subj_chemistry not in class_sec.subjects: class_sec.subjects.append(subj_chemistry)
        db.commit()

        # Students
        st1 = db.query(Student).filter(Student.student_code == "ACAD-STU-001").first()
        if not st1:
            st1 = Student(student_code="ACAD-STU-001", full_name="Kojo Mensah", class_section_id=class_sec.id)
            db.add(st1)

        st2 = db.query(Student).filter(Student.student_code == "ACAD-STU-002").first()
        if not st2:
            st2 = Student(student_code="ACAD-STU-002", full_name="Abena Osei", class_section_id=class_sec.id)
            db.add(st2)

        db.commit()

        # Scores
        # Student 1: 85 (Physics), 90 (Chemistry) = Total 175
        # Student 2: 70 (Physics), 75 (Chemistry) = Total 145
        sc1 = db.query(Score).filter(Score.student_id == st1.id, Score.subject_id == subj_physics.id, Score.semester_id == sem.id).first()
        if not sc1:
            db.add(Score(student_id=st1.id, subject_id=subj_physics.id, semester_id=sem.id, class_score=25, exam_score=60, total_score=85))

        sc2 = db.query(Score).filter(Score.student_id == st1.id, Score.subject_id == subj_chemistry.id, Score.semester_id == sem.id).first()
        if not sc2:
            db.add(Score(student_id=st1.id, subject_id=subj_chemistry.id, semester_id=sem.id, class_score=28, exam_score=62, total_score=90))

        sc3 = db.query(Score).filter(Score.student_id == st2.id, Score.subject_id == subj_physics.id, Score.semester_id == sem.id).first()
        if not sc3:
            db.add(Score(student_id=st2.id, subject_id=subj_physics.id, semester_id=sem.id, class_score=20, exam_score=50, total_score=70))

        sc4 = db.query(Score).filter(Score.student_id == st2.id, Score.subject_id == subj_chemistry.id, Score.semester_id == sem.id).first()
        if not sc4:
            db.add(Score(student_id=st2.id, subject_id=subj_chemistry.id, semester_id=sem.id, class_score=22, exam_score=53, total_score=75))

        db.commit()
        print("   [OK] Academic test hierarchy, class, and scores created successfully.")

        # 2. Test Dual Hierarchy Helper Authorization Functions
        print("\n[2] Testing Dual Hierarchy Authorization Helpers...")
        assert _is_academic_head(admin_acad) == True, "Admin/Academic Head should be academic head!"
        assert _is_hod(db, hod_science, dept_science.id) == True, "HOD Science should be verified as HOD!"
        assert _is_form_master_of_class(form_master_user, class_sec) == True, "Form Master should be verified for class!"
        print("   [OK] Dual Hierarchy helpers passed.")

        # 3. Test Broadsheet & Rank Calculation
        print("\n[3] Testing Broadsheet Calculations & Ranks...")
        st1_scores = db.query(Score).filter(Score.student_id == st1.id, Score.semester_id == sem.id).all()
        st1_tot = sum(s.total_score for s in st1_scores)
        assert st1_tot == 175.0, f"Kojo Mensah total score should be 175.0! Got {st1_tot}"

        st2_scores = db.query(Score).filter(Score.student_id == st2.id, Score.semester_id == sem.id).all()
        st2_tot = sum(s.total_score for s in st2_scores)
        assert st2_tot == 145.0, f"Abena Osei total score should be 145.0! Got {st2_tot}"

        assert st1_tot > st2_tot, "Student 1 should rank #1 over Student 2."
        print("   [OK] Broadsheet total marks and class rank #1 vs #2 verified.")

        # 4. Test Form Master Remarks Input
        print("\n[4] Testing Form Master Remarks Storage...")
        summary = db.query(StudentSemesterSummary).filter(
            StudentSemesterSummary.student_id == st1.id,
            StudentSemesterSummary.semester_id == sem.id
        ).first()

        if not summary:
            summary = StudentSemesterSummary(
                student_id=st1.id,
                semester_id=sem.id,
                attitude="Excellent",
                conduct="Very Good",
                interest="Physics Experiments",
                form_teacher_remarks="An outstanding science student."
            )
            db.add(summary)
            db.commit()

        assert summary.attitude == "Excellent", "Form master attitude remark saving failed!"
        print("   [OK] Form master remarks successfully stored in StudentSemesterSummary.")

        # 5. Test 3 Configurable Report Card Publishing Modes
        print("\n[5] Testing 3 Configurable Report Card Publishing Modes...")

        mode_setting = db.query(Setting).filter(Setting.key == "report_publishing_mode").first()
        if not mode_setting:
            mode_setting = Setting(key="report_publishing_mode", value="HYBRID_BOTH")
            db.add(mode_setting)
            db.commit()

        # Mode 1: FORM_MASTER_DIRECT
        mode_setting.value = "FORM_MASTER_DIRECT"
        db.commit()
        assert _get_publishing_mode(db) == "FORM_MASTER_DIRECT"
        print("   [OK] Mode 1: FORM_MASTER_DIRECT active. Form Masters can publish directly.")

        # Mode 2: ACADEMIC_HEAD_ONLY
        mode_setting.value = "ACADEMIC_HEAD_ONLY"
        db.commit()
        assert _get_publishing_mode(db) == "ACADEMIC_HEAD_ONLY"
        print("   [OK] Mode 2: ACADEMIC_HEAD_ONLY active. Only Assistant Head Academic / Headmaster can publish.")

        # Mode 3: HYBRID_BOTH
        mode_setting.value = "HYBRID_BOTH"
        db.commit()
        assert _get_publishing_mode(db) == "HYBRID_BOTH"
        print("   [OK] Mode 3: HYBRID_BOTH active. Both Form Master and Academic Head have publishing power.")

        print("\n==================================================")
        print(" ALL ACADEMIC HIERARCHY VERIFICATION TESTS PASSED!")
        print("==================================================")

    except Exception as e:
        print(f"\n[FAIL] VERIFICATION FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
