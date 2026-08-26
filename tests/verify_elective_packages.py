import os
import sys

# Ensure backend path is available
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import (
    School, Program, Subject, ClassSection, SchoolStage,
    ElectiveCombination, Student, StudentHealth, StudentGuardian
)
from backend.app.routes.cssps_enrollment import complete_admission_form, CandidateAdmissionForm

def run_tests():
    print("================================================================")
    print("TEST SUITE: Phase 1 Curriculum Track & Elective Package Builder")
    print("================================================================")

    # 1. Initialize Tables
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Create or find School
        school = db.query(School).first()
        if not school:
            school = School(name="J.A. Kufuor STEM School", code="JAK-STEM", school_mode="SHS_ONLY")
            db.add(school)
            db.commit()
            db.refresh(school)
        print(f"[OK] School loaded: {school.name} (ID: {school.id})")

        # Create or find Stage
        stage = db.query(SchoolStage).filter(SchoolStage.name == "SHS Form 1").first()
        if not stage:
            stage = SchoolStage(name="SHS Form 1", school_type="SHS")
            db.add(stage)
            db.commit()
            db.refresh(stage)

        # Create or find Class Sections
        sec_sci_1 = db.query(ClassSection).filter(ClassSection.name == "Form 1 Science 1").first()
        if not sec_sci_1:
            sec_sci_1 = ClassSection(name="Form 1 Science 1", stage_id=stage.id)
            db.add(sec_sci_1)

        sec_sci_2 = db.query(ClassSection).filter(ClassSection.name == "Form 1 Science 2").first()
        if not sec_sci_2:
            sec_sci_2 = ClassSection(name="Form 1 Science 2", stage_id=stage.id)
            db.add(sec_sci_2)
        db.commit()
        db.refresh(sec_sci_1)
        db.refresh(sec_sci_2)
        print(f"[OK] Class Sections ready: '{sec_sci_1.name}' (ID: {sec_sci_1.id}), '{sec_sci_2.name}' (ID: {sec_sci_2.id})")

        # Create or find Subjects
        subject_data = [
            ("English Language", "ENG", True, "Core"),
            ("Core Mathematics", "CMATH", True, "Core"),
            ("Social Studies", "SOC", True, "Core"),
            ("Integrated Science", "INTSCI", True, "Core"),
            ("Physics", "PHYS", False, "Elective"),
            ("Chemistry", "CHEM", False, "Elective"),
            ("Biology", "BIO", False, "Elective"),
            ("Elective Mathematics", "EMATH", False, "Elective"),
            ("Applied Electricity", "APPELEC", False, "Elective"),
            ("Technical Drawing", "TD", False, "Elective"),
        ]
        subjects_map = {}
        for name, code, is_core, cat in subject_data:
            s = db.query(Subject).filter(Subject.name == name).first()
            if not s:
                s = Subject(name=name, code=code, is_core=is_core, category=cat)
                db.add(s)
                db.commit()
                db.refresh(s)
            subjects_map[name] = s
        print(f"[OK] Prepared {len(subjects_map)} Subjects (Core & Electives)")

        # Create or find STEM Pure Science Program
        prog_name = "JAK STEM Pure Science Track"
        program = db.query(Program).filter(Program.name == prog_name).first()
        if not program:
            program = Program(name=prog_name, code="STEM-SCI", school_id=school.id)
            db.add(program)
            db.commit()
            db.refresh(program)
        print(f"[OK] Program Track created: '{program.name}' (ID: {program.id})")

        # 2. Test Custom Core Subjects Configuration (Dropping Integrated Science)
        custom_cores = [
            subjects_map["English Language"],
            subjects_map["Core Mathematics"],
            subjects_map["Social Studies"]
        ]
        program.core_subjects = custom_cores
        db.commit()
        db.refresh(program)

        core_names = [s.name for s in program.core_subjects]
        assert "Integrated Science" not in core_names, "Integrated Science should be excluded from Pure Science track"
        assert len(program.core_subjects) == 3, f"Expected 3 core subjects, got {len(program.core_subjects)}"
        print(f"[OK] Step 1: Program Core Subjects configured: {core_names} (Integrated Science excluded as required!)")

        # 3. Test Elective Package Builder (Option A: 4 electives, Option B: 5 electives)
        # Clear existing test combos
        for c in program.elective_combinations:
            db.delete(c)
        db.commit()

        # Package A: Pure Bio Science (4 electives) -> Form 1 Science 1
        pkg_a = ElectiveCombination(
            name="Option A: Pure Biological Science",
            code="SCI-OPT-A",
            program_id=program.id,
            class_section_id=sec_sci_1.id,
            capacity=45,
            is_active=True,
            school_id=school.id
        )
        pkg_a.subjects = [
            subjects_map["Physics"],
            subjects_map["Chemistry"],
            subjects_map["Biology"],
            subjects_map["Elective Mathematics"],
        ]
        db.add(pkg_a)

        # Package B: Physical & Technical Science (5 electives) -> Form 1 Science 2
        pkg_b = ElectiveCombination(
            name="Option B: Physical & Engineering Science",
            code="SCI-OPT-B",
            program_id=program.id,
            class_section_id=sec_sci_2.id,
            capacity=40,
            is_active=True,
            school_id=school.id
        )
        pkg_b.subjects = [
            subjects_map["Physics"],
            subjects_map["Chemistry"],
            subjects_map["Elective Mathematics"],
            subjects_map["Applied Electricity"],
            subjects_map["Technical Drawing"],
        ]
        db.add(pkg_b)
        db.commit()
        db.refresh(pkg_a)
        db.refresh(pkg_b)

        assert len(pkg_a.subjects) == 4, f"Option A should have 4 subjects, got {len(pkg_a.subjects)}"
        assert len(pkg_b.subjects) == 5, f"Option B should have 5 subjects, got {len(pkg_b.subjects)}"
        print(f"[OK] Step 2: Elective Packages created:")
        print(f"   - {pkg_a.name} -> {len(pkg_a.subjects)} subjects -> Routes to '{sec_sci_1.name}'")
        print(f"   - {pkg_b.name} -> {len(pkg_b.subjects)} subjects -> Routes to '{sec_sci_2.name}'")

        # 4. Test Student Placement & Candidate Form Auto-Routing
        test_bece_index = "101045999926"
        student = db.query(Student).filter(Student.bece_index_number == test_bece_index).first()
        if not student:
            student = Student(
                student_code="STU-TEST-9999",
                full_name="Kwabena Mensah Boateng",
                first_name="Kwabena",
                last_name="Boateng",
                bece_index_number=test_bece_index,
                enrolment_code="CSSPS-2026-T9999",
                program_id=program.id,
                residential_status="B",
                school_id=school.id,
                enrollment_status="PLACED"
            )
            db.add(student)
            db.commit()
            db.refresh(student)

        print(f"[OK] Step 3: Candidate verified on portal: {student.full_name} (Index: {student.bece_index_number})")

        # Candidate submits admission form choosing Package B (Option B)
        form_payload = CandidateAdmissionForm(
            student_id=student.id,
            elective_combination_id=pkg_b.id,
            elective_combination=pkg_b.name,
            guardian_name="Dr. Osei Boateng",
            primary_phone="0244123456",
            residential_address="Block D, Ridge Residential, Kumasi",
            blood_group="O+",
            allergies="None",
            medical_conditions="None"
        )

        result = complete_admission_form(data=form_payload, db=db)
        db.refresh(student)

        # 5. Assertions
        assert result["success"] == True, "Form completion should succeed"
        assert student.class_section_id == sec_sci_2.id, f"Student should be routed to '{sec_sci_2.name}', got ID {student.class_section_id}"
        assert student.elective_combination_id == pkg_b.id, "Student elective_combination_id should match Option B"
        assert student.enrollment_status == "FORM_COMPLETED", f"Status should be FORM_COMPLETED, got {student.enrollment_status}"
        assert student.class_section.name == "Form 1 Science 2", f"Class name should be 'Form 1 Science 2', got '{student.class_section.name}'"

        print(f"[OK] Step 4: Admission Form processed successfully!")
        print(f"   - Assigned Class Stream: '{student.class_section.name}' (Stream 2)")
        print(f"   - Enrolled Package: '{student.elective_combination_rel.name}'")
        print(f"   - Total Electives in Package: {len(student.elective_combination_rel.subjects)} subjects")
        print(f"   - Track Core Subjects: {len(student.program.core_subjects)} subjects")
        print(f"   - Total Student Subjects: {len(student.program.core_subjects) + len(student.elective_combination_rel.subjects)} subjects (3 Core + 5 Electives = 8 Subjects)")
        print(f"   - Enrollment Status: {student.enrollment_status}")

        # 6. Test Bi-Directional Auto-Sync from Class Section Subjects -> Program Elective Package
        from backend.app.routes.classes import set_class_subjects, get_class_subjects
        from backend.app.routes.programs import list_programs
        from backend.app.models import User

        test_admin = User(id=99966, username="test_bidirect_admin", school_id=school.id)
        sec_sci_1.program_id = program.id
        db.commit()

        assigned_sub_ids = [
            subjects_map["English Language"].id,
            subjects_map["Core Mathematics"].id,
            subjects_map["Social Studies"].id,
            subjects_map["Physics"].id,
            subjects_map["Chemistry"].id,
            subjects_map["Biology"].id,
            subjects_map["Elective Mathematics"].id,
        ]

        set_res = set_class_subjects(section_id=sec_sci_1.id, payload=assigned_sub_ids, db=db, current_user=test_admin)
        assert "synchronized" in set_res["message"].lower(), "Response should confirm program synchronization"

        # Verify elective package auto-created / updated for this stream
        auto_combo = db.query(ElectiveCombination).filter(
            ElectiveCombination.program_id == program.id,
            ElectiveCombination.class_section_id == sec_sci_1.id
        ).first()

        assert auto_combo is not None, "ElectiveCombination should be auto-created for this stream"
        auto_combo_names = [s.name for s in auto_combo.subjects]
        assert "Physics" in auto_combo_names
        assert "Chemistry" in auto_combo_names
        assert "Biology" in auto_combo_names
        assert "Elective Mathematics" in auto_combo_names
        assert "Core Mathematics" not in auto_combo_names, "Core subjects should not be in elective package"

        # Verify rich program summary list
        progs_summary = list_programs(db=db, current_user=test_admin)
        matched_p = next((p for p in progs_summary if p["id"] == program.id), None)
        assert matched_p is not None
        assert matched_p["core_count"] == 3
        assert matched_p["package_count"] >= 2
        assert len(matched_p["packages_summary"]) >= 2

        print(f"[OK] Step 5: Bi-Directional Auto-Sync verified 100%! Class Section '{sec_sci_1.name}' created Elective Package '{auto_combo.name}' with {len(auto_combo.subjects)} electives.")

        print("\n================================================================")
        print("SUCCESS: ALL PHASE 1 CURRICULUM & ELECTIVE BUILDER TESTS PASSED 100%!")
        print("================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()

