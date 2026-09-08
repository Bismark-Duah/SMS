import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.database import Base
from backend.app.models import (
    School, ClassSection, Subject, User, Role, Program, TeacherAssignment,
    Timetable, TimetableConfig
)
from backend.app.services.timetable_generator import TimetableSolver, smart_surgical_swap
from backend.app.services.curriculum_presets import ROLE_WORKLOAD_LIMITS, get_subject_config

def test_timetable_csp_solver_and_rules():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    # 1. Create School
    school = School(
        name="Prempeh Senior High School",
        code="PREMPEH-SHS",
        school_mode="SHS_ONLY",
        ownership_type="PUBLIC"
    )
    db.add(school)
    db.commit()
    db.refresh(school)

    # 2. Create Roles
    r_teacher = Role(name="teacher")
    r_admin = Role(name="admin")
    r_superadmin = Role(name="super_admin")
    r_secretary = Role(name="secretary")
    db.add_all([r_teacher, r_admin, r_superadmin, r_secretary])
    db.commit()

    # 3. Create Users with Responsibilities
    super_admin_user = User(
        username="Super System Executive",
        email="super@sms.com",
        password_hash="fakehash",
        roles=[r_superadmin]
    )
    school_admin = User(
        username="Mr. Addo School Admin",
        email="admin@school.com",
        password_hash="fakehash",
        school_id=school.id,
        responsibility_role="SCHOOL_ADMINISTRATOR",
        roles=[r_admin]
    )
    school_sec = User(
        username="Mrs. Mensah Secretary",
        email="secretary@school.com",
        password_hash="fakehash",
        school_id=school.id,
        responsibility_role="SECRETARY",
        roles=[r_secretary]
    )
    assist_head_admin = User(
        username="Mr. Osei Assistant Head Admin",
        email="asstheadadmin@school.com",
        password_hash="fakehash",
        school_id=school.id,
        responsibility_role="ASSISTANT_HEAD_ADMIN",
        roles=[r_teacher]
    )
    assist_head_acad = User(
        username="Mrs. Appiah Assistant Head Academic",
        email="asstheadacad@school.com",
        password_hash="fakehash",
        school_id=school.id,
        responsibility_role="ASSISTANT_HEAD_ACADEMIC",
        roles=[r_teacher]
    )
    hod_science = User(
        username="Dr. Mensah HOD Science",
        email="hodsci@school.com",
        password_hash="fakehash",
        school_id=school.id,
        responsibility_role="HOD",
        max_weekly_periods=16,
        is_teaching_exempt=False,
        roles=[r_teacher]
    )
    teacher_maths = User(
        username="Mr. Boateng Maths",
        email="maths@school.com",
        password_hash="fakehash",
        school_id=school.id,
        responsibility_role="REGULAR_TEACHER",
        max_weekly_periods=28,
        is_teaching_exempt=False,
        roles=[r_teacher]
    )
    db.add_all([super_admin_user, school_admin, school_sec, assist_head_admin, assist_head_acad, hod_science, teacher_maths])
    db.commit()

    # 4. Create Subjects
    sub_maths = Subject(name="Core Mathematics", code="CMATH-SHS", is_core=True, school_id=school.id)
    sub_physics = Subject(name="Physics", code="PHYS-SHS", is_core=False, school_id=school.id)
    sub_english = Subject(name="English Language", code="ENG-SHS", is_core=True, school_id=school.id)
    db.add_all([sub_maths, sub_physics, sub_english])
    db.commit()

    from backend.app.models import SchoolStage
    stage = SchoolStage(name="SHS 1", school_type="SHS", school_id=school.id)
    db.add(stage)
    db.commit()

    # 5. Create Classes
    class_sci_1 = ClassSection(name="Form 1 Science 1", stage_id=stage.id, school_id=school.id)
    class_sci_2 = ClassSection(name="Form 1 Science 2", stage_id=stage.id, school_id=school.id)
    class_arts_1 = ClassSection(name="Form 1 Arts 1", stage_id=stage.id, school_id=school.id)
    db.add_all([class_sci_1, class_sci_2, class_arts_1])
    db.commit()

    class_sci_1.subjects.extend([sub_maths, sub_physics, sub_english])
    class_sci_2.subjects.extend([sub_maths, sub_physics, sub_english])
    class_arts_1.subjects.extend([sub_maths, sub_english])
    db.commit()

    # 6. Assign Teachers to Subjects
    a1 = TeacherAssignment(teacher_id=teacher_maths.id, subject_id=sub_maths.id, class_section_id=class_sci_1.id, semester_id=1)
    a2 = TeacherAssignment(teacher_id=teacher_maths.id, subject_id=sub_maths.id, class_section_id=class_sci_2.id, semester_id=1)
    a3 = TeacherAssignment(teacher_id=teacher_maths.id, subject_id=sub_maths.id, class_section_id=class_arts_1.id, semester_id=1)
    a4 = TeacherAssignment(teacher_id=hod_science.id, subject_id=sub_physics.id, class_section_id=class_sci_1.id, semester_id=1)
    a5 = TeacherAssignment(teacher_id=hod_science.id, subject_id=sub_physics.id, class_section_id=class_sci_2.id, semester_id=1)
    # Even if accidentally assigned to school admin or secretary, solver should exempt them
    a6 = TeacherAssignment(teacher_id=school_admin.id, subject_id=sub_english.id, class_section_id=class_sci_1.id, semester_id=1)
    db.add_all([a1, a2, a3, a4, a5, a6])
    db.commit()

    # 7. Run Solver
    solver = TimetableSolver(
        db=db,
        school_id=school.id,
        semester_id=1,
        school_profile="SHS",
        periods_per_day=8,
        friday_periods=6
    )

    result = solver.solve()
    print("Solver Result:", result)

    assert result["status"] == "SUCCESS", f"Expected SUCCESS but got {result}"
    assert result["total_slots"] > 0, "Slots should be generated"

    # Verify zero teacher double-bookings
    all_slots = db.query(Timetable).all()
    teacher_schedule = {}
    class_schedule = {}
    room_schedule = {}

    for s in all_slots:
        # Class collision check
        c_key = (s.class_section_id, s.day_of_week, s.period_number)
        assert c_key not in class_schedule, f"Class collision at {c_key}"
        class_schedule[c_key] = s

        # Teacher collision check
        if s.teacher_id:
            t_key = (s.teacher_id, s.day_of_week, s.period_number)
            assert t_key not in teacher_schedule, f"Teacher collision at {t_key}"
            teacher_schedule[t_key] = s

        # Room/Lab collision check
        if s.room and s.room.strip():
            r_key = (s.room.strip().lower(), s.day_of_week, s.period_number)
            assert r_key not in room_schedule, f"Room collision at {r_key}"
            room_schedule[r_key] = s

    # Verify Superadmin, School Admin, Secretary, and Assistant Heads received 0 slots
    assert db.query(Timetable).filter(Timetable.teacher_id == super_admin_user.id).count() == 0
    assert db.query(Timetable).filter(Timetable.teacher_id == school_admin.id).count() == 0
    assert db.query(Timetable).filter(Timetable.teacher_id == school_sec.id).count() == 0
    assert db.query(Timetable).filter(Timetable.teacher_id == assist_head_admin.id).count() == 0
    assert db.query(Timetable).filter(Timetable.teacher_id == assist_head_acad.id).count() == 0

    # Verify HOD Science does not exceed max cap (16)
    hod_slots = db.query(Timetable).filter(Timetable.teacher_id == hod_science.id).count()
    assert hod_slots <= 16, f"HOD Science exceeded max cap: {hod_slots} > 16"

    # Test Surgical Staff Handover / Auto-Swap
    new_maths_teacher = User(
        username="Mr. Mensah Newly Arrived Maths",
        email="newmaths@school.com",
        password_hash="fakehash",
        school_id=school.id,
        roles=[r_teacher]
    )
    db.add(new_maths_teacher)
    db.commit()

    swap_res = smart_surgical_swap(
        db=db,
        school_id=school.id,
        outgoing_teacher_id=teacher_maths.id,
        incoming_teacher_id=new_maths_teacher.id
    )
    print("Surgical Handover Result:", swap_res)
    assert swap_res["status"] == "SUCCESS"
    assert swap_res["slots_transferred"] > 0

    # Verify all slots transferred
    old_slots = db.query(Timetable).filter(Timetable.teacher_id == teacher_maths.id).count()
    new_slots_count = db.query(Timetable).filter(Timetable.teacher_id == new_maths_teacher.id).count()
    assert old_slots == 0
    assert new_slots_count > 0

    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    test_timetable_csp_solver_and_rules()
