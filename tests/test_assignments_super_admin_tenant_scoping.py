import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database import SessionLocal, run_migrations
from backend.app.models import User, Role, School, SchoolStage, ClassSection, Subject, TeacherAssignment
from backend.app.routes.auth import _hash_password
from backend.app.routes.classes import list_sections, list_stages
from backend.app.routes.assignments import list_assignments, list_privileges
from backend.app.dependencies import get_school_id

def test_assignments_super_admin_tenant_scoping():
    print("=" * 66)
    print("TEST SUITE: Super Admin Multi-Tenant Scoping & Class Filtering Audit")
    print("=" * 66)

    run_migrations()
    db = SessionLocal()
    try:
        # 1. Setup Roles
        super_admin_role = db.query(Role).filter(Role.name == "super_admin").first()
        if not super_admin_role:
            super_admin_role = Role(name="super_admin")
            db.add(super_admin_role)
            db.flush()

        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            db.add(admin_role)
            db.flush()

        teacher_role = db.query(Role).filter(Role.name == "teacher").first()
        if not teacher_role:
            teacher_role = Role(name="teacher")
            db.add(teacher_role)
            db.flush()

        # 2. Setup Super Admin User
        super_user = db.query(User).filter(User.username == "superadmin_asgn_test").first()
        if not super_user:
            super_user = User(
                username="superadmin_asgn_test",
                email="super_asgn@sms.test",
                password_hash=_hash_password("SuperSecret123!"),
                is_active=True,
                school_id=None
            )
            super_user.roles.append(super_admin_role)
            db.add(super_user)
            db.flush()
        elif super_admin_role not in super_user.roles:
            super_user.roles.append(super_admin_role)
            db.flush()

        # 3. Setup SHS School (JAK STEM) and Basic School
        jak_school = db.query(School).filter(School.code == "JAK-STEM-SHS-TEST").first()
        if not jak_school:
            jak_school = School(
                name="JAK STEM Senior High School",
                code="JAK-STEM-SHS-TEST",
                school_mode="SHS_ONLY",
                ownership_type="PUBLIC",
                status="ACTIVE"
            )
            db.add(jak_school)
            db.flush()

        basic_school = db.query(School).filter(School.code == "BASIC-SCH-TEST").first()
        if not basic_school:
            basic_school = School(
                name="Accra Model Basic School",
                code="BASIC-SCH-TEST",
                school_mode="BASIC_ONLY",
                ownership_type="PUBLIC",
                status="ACTIVE"
            )
            db.add(basic_school)
            db.flush()

        # 4. Setup Stages & Classes for JAK STEM (SHS)
        shs_stage = db.query(SchoolStage).filter(SchoolStage.name == "SHS 1 Form Test").first()
        if not shs_stage:
            shs_stage = SchoolStage(
                name="SHS 1 Form Test",
                school_type="SHS",
                school_id=jak_school.id
            )
            db.add(shs_stage)
            db.flush()

        shs_class = db.query(ClassSection).filter(ClassSection.school_id == jak_school.id, ClassSection.name == "SHS 1 Science A").first()
        if not shs_class:
            shs_class = ClassSection(
                name="SHS 1 Science A",
                stage_id=shs_stage.id,
                school_id=jak_school.id
            )
            db.add(shs_class)
            db.flush()

        # 5. Setup Stages & Classes for Basic School
        basic_stage = db.query(SchoolStage).filter(SchoolStage.name == "Primary 4 Stage Test").first()
        if not basic_stage:
            basic_stage = SchoolStage(
                name="Primary 4 Stage Test",
                school_type="Basic",
                school_id=basic_school.id
            )
            db.add(basic_stage)
            db.flush()

        basic_class = db.query(ClassSection).filter(ClassSection.school_id == basic_school.id, ClassSection.name == "Primary 4 Emerald").first()
        if not basic_class:
            basic_class = ClassSection(
                name="Primary 4 Emerald",
                stage_id=basic_stage.id,
                school_id=basic_school.id
            )
            db.add(basic_class)
            db.flush()

        db.commit()

        # 6. Test dependency resolution for get_school_id with Super Admin
        resolved_jak_id = get_school_id(current_user=super_user, x_school_id=str(jak_school.id))
        assert resolved_jak_id == jak_school.id, f"Expected {jak_school.id}, got {resolved_jak_id}"

        resolved_basic_id = get_school_id(current_user=super_user, x_school_id=str(basic_school.id))
        assert resolved_basic_id == basic_school.id, f"Expected {basic_school.id}, got {resolved_basic_id}"

        print("\n[Step 1] Dependency get_school_id correctly resolved tenant IDs for Super Admin.")

        # 7. Query classes scoped to JAK STEM (SHS_ONLY)
        print(f"\n[Step 2] Testing list_sections scoped to JAK STEM (school_id={jak_school.id}, SHS_ONLY)...")
        shs_classes = list_sections(db=db, current_user=super_user, school_id=jak_school.id)
        print(f"  * Retrieved {len(shs_classes)} classes for JAK STEM SHS.")
        assert len(shs_classes) > 0, "Expected at least 1 SHS class"
        for c in shs_classes:
            school_type = c.get("school_type") or ""
            class_name = c.get("name") or ""
            c_sch_id = c.get("school_id")
            print(f"    - Class: {class_name} | School Type: {school_type} | School ID: {c_sch_id}")
            assert school_type == "SHS", f"Basic class '{class_name}' leaked into SHS scope!"
            assert c_sch_id == jak_school.id, f"Cross-tenant class leak: expected school_id {jak_school.id}, got {c_sch_id}"
            assert not any(b in class_name.upper() for b in ["KG ", "PRIMARY", "CRECHE", "NURSERY", "JHS "]), f"Found basic class '{class_name}' in SHS scope!"
        print("[PASS] Only SHS classes returned for SHS school scope; zero Basic school classes leaked.")

        # 8. Query classes scoped to Basic School (BASIC_ONLY)
        print(f"\n[Step 3] Testing list_sections scoped to Basic School (school_id={basic_school.id}, BASIC_ONLY)...")
        basic_classes = list_sections(db=db, current_user=super_user, school_id=basic_school.id)
        print(f"  * Retrieved {len(basic_classes)} classes for Basic school.")
        assert len(basic_classes) > 0, "Expected at least 1 Basic class"
        for c in basic_classes:
            school_type = c.get("school_type") or ""
            class_name = c.get("name") or ""
            c_sch_id = c.get("school_id")
            print(f"    - Class: {class_name} | School Type: {school_type} | School ID: {c_sch_id}")
            assert school_type == "Basic", f"SHS class '{class_name}' leaked into Basic scope!"
            assert c_sch_id == basic_school.id, f"Cross-tenant class leak: expected school_id {basic_school.id}, got {c_sch_id}"
        print("[PASS] Only Basic classes returned for Basic school scope.")

        # 9. Query list_assignments and list_privileges
        print(f"\n[Step 4] Testing list_assignments with school_id={jak_school.id}...")
        asgns = list_assignments(db=db, current_user=super_user, school_id=jak_school.id)
        assert isinstance(asgns, list), "Expected list response"
        print(f"[PASS] Assignments returned successfully ({len(asgns)} items).")

        print(f"\n[Step 5] Testing list_privileges with school_id={jak_school.id}...")
        privs = list_privileges(db=db, current_user=super_user, school_id=jak_school.id)
        assert isinstance(privs, list), "Expected list response"
        print(f"[PASS] Privileges returned successfully ({len(privs)} items).")

        # 10. Audit frontend files for header and UI cleanliness
        print("\n[Step 6] Auditing frontend/assignments.html and frontend/js/assignments.js...")
        with open("frontend/assignments.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        assert "assignmentSchoolFilterContainer" in html_content, "Missing assignmentSchoolFilterContainer in assignments.html"
        assert "activeSchoolModeBadge" in html_content, "Missing activeSchoolModeBadge in assignments.html"
        assert "Select Target Class Section(s)" in html_content, "Target class header mismatch"
        assert "➕" not in html_content, "Found decorative ➕ emoji in assignments.html"
        assert "🏫" not in html_content, "Found decorative 🏫 emoji in assignments.html"
        assert "📘" not in html_content, "Found decorative 📘 emoji in assignments.html"

        with open("frontend/js/assignments.js", "r", encoding="utf-8") as f:
            js_content = f.read()
        assert "selectedSchoolFilter" in js_content, "Missing selectedSchoolFilter in assignments.js"
        assert "setupSuperAdminSchoolFilter" in js_content, "Missing setupSuperAdminSchoolFilter in assignments.js"
        assert "onAssignmentSchoolFilterChange" in js_content, "Missing onAssignmentSchoolFilterChange in assignments.js"
        assert "X-School-Id" in js_content, "Missing X-School-Id header handling in assignments.js"
        print("[PASS] Frontend files successfully verified.")

        print("\n" + "=" * 66)
        print("ALL TESTS PASSED SUCCESSFULLY (100% VERIFIED)")
        print("=" * 66)

    finally:
        db.close()

if __name__ == "__main__":
    test_assignments_super_admin_tenant_scoping()
