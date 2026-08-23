"""
Automated Verification Script for Flexible Boarding Configuration & Hierarchy Modes
"""
import sys
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User, Role, ClassSection, Student, ExeatRecord, House, Setting
from backend.app.routes.exeat import create_exeat, approve_exeat, _get_user_jurisdiction
from backend.app.schemas import ExeatCreate

def run_tests():
    print("==================================================")
    print(" FLEXIBLE BOARDING CONFIGURATION TEST SUITE       ")
    print("==================================================")

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Setup Test Data
        print("\n[1] Setting up users & student assignment...")

        role_admin = db.query(Role).filter(Role.name == "admin").first()
        if not role_admin:
            role_admin = Role(name="admin")
            db.add(role_admin)

        role_teacher = db.query(Role).filter(Role.name == "teacher").first()
        if not role_teacher:
            role_teacher = Role(name="teacher")
            db.add(role_teacher)
        db.commit()

        user_admin = db.query(User).filter(User.username == "admin").first()
        user_housemaster = db.query(User).filter(User.username == "test_boarding_hm").first()
        if not user_housemaster:
            user_housemaster = User(username="test_boarding_hm", email="hm@school.edu", password_hash="pass")
            db.add(user_housemaster)
            db.flush()
        user_housemaster.roles = [role_teacher]
        db.commit()

        # Boarding House
        house = db.query(House).filter(House.name == "Boarding Test House").first()
        if not house:
            house = House(name="Boarding Test House", gender="Boys", house_master_id=user_housemaster.id)
            db.add(house)
            db.commit()
        else:
            house.house_master_id = user_housemaster.id
            db.commit()

        # Student
        st = db.query(Student).filter(Student.student_code == "BOARD-STU-001").first()
        if not st:
            st = Student(
                student_code="BOARD-STU-001",
                full_name="Mensah JHS Boarder",
                gender="Male",
                house_id=house.id,
                is_active=True
            )
            db.add(st)
            db.commit()
        else:
            st.house_id = house.id
            st.gender = "Male"
            db.commit()

        # Initialize setting values
        setting_status = db.query(Setting).filter(Setting.key == "boarding_status").first()
        if not setting_status:
            setting_status = Setting(key="boarding_status", value="BOARDING_AND_DAY")
            db.add(setting_status)
        else:
            setting_status.value = "BOARDING_AND_DAY"

        setting_hierarchy = db.query(Setting).filter(Setting.key == "boarding_hierarchy_mode").first()
        if not setting_hierarchy:
            setting_hierarchy = Setting(key="boarding_hierarchy_mode", value="BASIC_TWO_TIER")
            db.add(setting_hierarchy)
        else:
            setting_hierarchy.value = "BASIC_TWO_TIER"
        db.commit()

        print("   [OK] Test environment initialized with BASIC_TWO_TIER hierarchy.")

        # 2. Test Exeat Creation under JHS/Basic Simple Mode
        print("\n[2] Testing Exeat Creation by Housemaster in BASIC_TWO_TIER...")
        # Since hierarchy is BASIC_TWO_TIER, exeat created by housemaster should remain Pending
        payload = ExeatCreate(
            student_id=st.id,
            exeat_type="Weekend",
            reason="Visiting family",
            destination="Kumasi",
            expected_departure=datetime.now(),
            expected_return=datetime.now()
        )

        res_ex = create_exeat(payload, db, user_housemaster)
        assert res_ex.status == "Pending", f"Exeat should be created as Pending! Got {res_ex.status}"
        print(f"   [OK] Exeat successfully created as Pending (Status: {res_ex.status}).")

        # 3. Test Regular Housemaster Approval Block
        print("\n[3] Testing Housemaster approval block in BASIC_TWO_TIER...")
        try:
            approve_exeat(res_ex.id, "HM Approval Attempt", db, user_housemaster)
            print("   [FAIL] Housemaster should not be allowed to approve in JHS mode!")
            sys.exit(1)
        except HTTPException as he:
            assert he.status_code == 403, "Should return HTTP 403 Forbidden!"
            print(f"   [OK] Housemaster approval correctly blocked (Message: {he.detail}).")

        # 4. Test Master Admin Approval Success
        print("\n[4] Testing Headmaster/Admin approval in BASIC_TWO_TIER...")
        res_approved = approve_exeat(res_ex.id, "Headmaster final approval", db, user_admin)
        assert res_approved.status == "Approved", f"Status should be Approved! Got {res_approved.status}"
        print(f"   [OK] Headmaster/Admin approved exeat directly (Status: {res_approved.status}).")

        # 5. Clean up settings to default
        setting_hierarchy.value = "SHS_THREE_TIER"
        db.commit()
        print("\n==================================================")
        print(" ALL FLEXIBLE BOARDING VERIFICATION TESTS PASSED! ")
        print("==================================================")

    except Exception as e:
        print(f"\n[FAIL] FLEXIBLE BOARDING VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
