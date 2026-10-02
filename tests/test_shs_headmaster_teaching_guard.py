import sys
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath('.'))

from backend.app.database import Base
from backend.app.models import (
    School, ClassSection, Subject, User, Role, Program, TeacherAssignment,
    Timetable, TimetableConfig, SchoolStage, Semester, AcademicYear
)
from backend.app.services.timetable_generator import TimetableSolver
from backend.app.routes.assignments import create_assignment, update_assignment
from backend.app.schemas import TeacherAssignmentCreate

def test_shs_headmaster_teaching_guard():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    # 1. Setup SHS School
    shs_school = School(
        name="Opoku Ware Senior High School",
        code="OWASS",
        school_mode="SHS_ONLY",
        ownership_type="PUBLIC"
    )
    db.add(shs_school)
    db.commit()
    db.refresh(shs_school)

    # 2. Roles
    r_teacher = Role(name="teacher")
    r_head = Role(name="headmaster")
    r_admin = Role(name="admin")
    db.add_all([r_teacher, r_head, r_admin])
    db.commit()

    # 3. Headmaster user & regular teacher user
    headmaster_user = User(
        username="Rev. Fr. Headmaster",
        email="headmaster@owass.edu.gh",
        password_hash="fakehash",
        school_id=shs_school.id,
        responsibility_role="HEADMASTER",
        is_teaching_exempt=True,
        roles=[r_teacher, r_head]  # even if granted teacher role
    )
    regular_teacher = User(
        username="Mr. Mensah Science",
        email="mensah@owass.edu.gh",
        password_hash="fakehash",
        school_id=shs_school.id,
        responsibility_role="REGULAR_TEACHER",
        max_weekly_periods=24,
        is_teaching_exempt=False,
        roles=[r_teacher]
    )
    admin_caller = User(
        username="System Administrator",
        email="admin@owass.edu.gh",
        password_hash="fakehash",
        school_id=shs_school.id,
        roles=[r_admin]
    )
    db.add_all([headmaster_user, regular_teacher, admin_caller])
    db.commit()

    # 4. Academic structure
    acad_year = AcademicYear(label="2025/2026", is_current=True, school_id=shs_school.id)
    db.add(acad_year)
    db.commit()

    semester = Semester(name="Semester 1", academic_year_id=acad_year.id, is_current=True, school_id=shs_school.id)
    db.add(semester)
    db.commit()

    stage_shs = SchoolStage(name="SHS 2", school_type="SHS", school_id=shs_school.id)
    db.add(stage_shs)
    db.commit()

    class_2sci = ClassSection(name="2 Science 1", stage_id=stage_shs.id, school_id=shs_school.id)
    db.add(class_2sci)
    db.commit()

    subj_physics = Subject(name="Physics", code="PHY-SHS", is_core=False, school_id=shs_school.id)
    db.add(subj_physics)
    db.commit()

    # TEST 1: Attempting to assign Headmaster to class in SHS must be rejected with HTTP 400
    payload_head = TeacherAssignmentCreate(
        teacher_id=headmaster_user.id,
        subject_id=subj_physics.id,
        class_section_id=class_2sci.id,
        semester_id=semester.id
    )

    with pytest.raises(HTTPException) as exc_info:
        create_assignment(
            payload=payload_head,
            db=db,
            current_user=admin_caller,
            school_id=shs_school.id
        )
    assert exc_info.value.status_code == 400
    assert "Headmasters and Headmistresses are 100% duty-exempt" in exc_info.value.detail
    print("SUCCESS: create_assignment blocked assigning Headmaster in SHS.")

    # TEST 2: Assigning regular teacher succeeds
    payload_regular = TeacherAssignmentCreate(
        teacher_id=regular_teacher.id,
        subject_id=subj_physics.id,
        class_section_id=class_2sci.id,
        semester_id=semester.id
    )
    res = create_assignment(
        payload=payload_regular,
        db=db,
        current_user=admin_caller,
        school_id=shs_school.id
    )
    assert res["teacher_id"] == regular_teacher.id
    print("SUCCESS: create_assignment succeeded for regular teacher.")

    # TEST 3: Updating assignment to Headmaster in SHS must be rejected with HTTP 400
    with pytest.raises(HTTPException) as exc_info2:
        update_assignment(
            assignment_id=res["id"],
            payload=payload_head,
            db=db,
            current_user=admin_caller
        )
    assert exc_info2.value.status_code == 400
    assert "Headmasters and Headmistresses are 100% duty-exempt" in exc_info2.value.detail
    print("SUCCESS: update_assignment blocked switching teacher to Headmaster in SHS.")

    # TEST 4: Timetable Solver strictly skips Headmaster even if a legacy assignment somehow exists
    legacy_asgn = TeacherAssignment(
        teacher_id=headmaster_user.id,
        subject_id=subj_physics.id,
        class_section_id=class_2sci.id,
        semester_id=semester.id
    )
    db.add(legacy_asgn)
    db.commit()

    solver = TimetableSolver(
        db=db,
        school_id=shs_school.id,
        semester_id=semester.id,
        school_profile="SHS",
        periods_per_day=8,
        friday_periods=6
    )
    solve_result = solver.solve()
    assert solve_result["status"] in ["SUCCESS", "OPTIMAL", "FEASIBLE", "PARTIAL"]

    # Verify Headmaster has ZERO scheduled slots
    headmaster_slots = db.query(Timetable).filter(Timetable.teacher_id == headmaster_user.id).all()
    assert len(headmaster_slots) == 0, f"Expected 0 slots for Headmaster, got {len(headmaster_slots)}"
    print("SUCCESS: Timetable Solver placed 0 slots for Headmaster in SHS.")

if __name__ == "__main__":
    test_shs_headmaster_teaching_guard()
    print("\nALL SHS HEADMASTER TEACHING GUARD TESTS PASSED!")
