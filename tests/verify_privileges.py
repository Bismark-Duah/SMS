"""
Automated Verification Script for Administrative Privileges & Gender Role Mapping
"""
import sys
import time
from sqlalchemy.orm import Session

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User, Role, ClassSection, SchoolStage, House
from backend.app.schemas import TeacherPrivilegeCreate
from backend.app.routes.assignments import create_privilege, delete_privilege

def run_tests():
    print("==================================================")
    print(" ADMINISTRATIVE PRIVILEGES VERIFICATION SUITE    ")
    print("==================================================")

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        ts = int(time.time())

        # 1. Setup Test Data
        print("\n[1] Setting up privileges test environment...")

        role_admin = db.query(Role).filter(Role.name == "admin").first()
        if not role_admin:
            role_admin = Role(name="admin")
            db.add(role_admin)
            db.commit()

        user_admin = db.query(User).filter(User.username == "test_priv_admin").first()
        if not user_admin:
            user_admin = User(username="test_priv_admin", email="priv_admin@school.edu", password_hash="pass", roles=[role_admin])
            db.add(user_admin)
            db.commit()

        role_teacher = db.query(Role).filter(Role.name == "teacher").first()
        if not role_teacher:
            role_teacher = Role(name="teacher")
            db.add(role_teacher)
            db.commit()

        female_teacher = db.query(User).filter(User.username == f"test_female_teacher_{ts}").first()
        if not female_teacher:
            female_teacher = User(
                username=f"test_female_teacher_{ts}",
                email=f"female_{ts}@school.edu",
                password_hash="pass",
                gender="Female",
                roles=[role_teacher]
            )
            db.add(female_teacher)
            db.commit()

        stage = db.query(SchoolStage).first()
        if not stage:
            stage = SchoolStage(name="Priv Stage", school_type="Basic")
            db.add(stage)
            db.commit()

        csec = db.query(ClassSection).filter(ClassSection.name == f"Priv Class {ts}").first()
        if not csec:
            csec = ClassSection(name=f"Priv Class {ts}", stage_id=stage.id)
            db.add(csec)
            db.commit()

        house = db.query(House).filter(House.name == f"Priv House {ts}").first()
        if not house:
            house = House(name=f"Priv House {ts}", gender="Both")
            db.add(house)
            db.commit()

        print(f"   [OK] Test environment initialized: Female Teacher {female_teacher.username}, Class #{csec.id}, House #{house.id}.")

        # 2. Test Form Master Privilege -> Auto Assigns form_mistress Role
        print("\n[2] Assigning Form Master privilege to Female Teacher...")
        req_fm = TeacherPrivilegeCreate(
            teacher_id=female_teacher.id,
            privilege_type="form_master",
            target_id=csec.id
        )
        res_fm = create_privilege(req_fm, db=db, current_user=user_admin)
        assert res_fm.teacher_id == female_teacher.id, "Teacher ID mismatch!"

        db.refresh(female_teacher)
        roles_list = [r.name for r in female_teacher.roles]
        print(f"   [OK] Assigned Form Master privilege. Female teacher roles: {roles_list}")
        assert "form_mistress" in roles_list, "Expected role 'form_mistress' to be assigned!"

        # 3. Test House Master Privilege -> Auto Assigns house_mistress Role
        print("\n[3] Assigning House Master privilege to Female Teacher...")
        req_hm = TeacherPrivilegeCreate(
            teacher_id=female_teacher.id,
            privilege_type="house_master",
            target_id=house.id
        )
        res_hm = create_privilege(req_hm, db=db, current_user=user_admin)
        assert res_hm.teacher_id == female_teacher.id, "Teacher ID mismatch!"

        db.refresh(female_teacher)
        roles_list = [r.name for r in female_teacher.roles]
        print(f"   [OK] Assigned House Master privilege. Female teacher roles: {roles_list}")
        assert "house_mistress" in roles_list, "Expected role 'house_mistress' to be assigned!"

        # 4. Test Unassign Form Master Privilege -> Auto Removes form_mistress Role
        print("\n[4] Unassigning Form Master privilege...")
        delete_privilege(priv_type="form_master", target_id=csec.id, db=db, current_user=user_admin)

        db.refresh(female_teacher)
        roles_list = [r.name for r in female_teacher.roles]
        print(f"   [OK] Unassigned Form Master. Female teacher roles: {roles_list}")
        assert "form_mistress" not in roles_list, "Expected role 'form_mistress' to be removed!"

        # 5. Test Unassign House Master Privilege -> Auto Removes house_mistress Role
        print("\n[5] Unassigning House Master privilege...")
        delete_privilege(priv_type="house_master", target_id=house.id, teacher_id=female_teacher.id, db=db, current_user=user_admin)

        db.refresh(female_teacher)
        roles_list = [r.name for r in female_teacher.roles]
        print(f"   [OK] Unassigned House Master. Female teacher roles: {roles_list}")
        assert "house_mistress" not in roles_list, "Expected role 'house_mistress' to be removed!"

        print("\n==================================================")
        print(" ALL ADMINISTRATIVE PRIVILEGES TESTS PASSED!      ")
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
