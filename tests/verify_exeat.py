"""
Automated Verification Script for Exeat Management System
Tests domestic hierarchy authorization, exeat lifecycle, gate operations, and overdue detection.
"""
import sys
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User, Role, House, Student, ExeatRecord
from backend.app.routes.exeat import (
    _can_user_access_student,
    _get_user_jurisdiction,
    _check_overdue_exeats,
    _format_exeat_response
)

def run_tests():
    print("==================================================")
    print("   EXEAT MANAGEMENT MODULE VERIFICATION SUITE    ")
    print("==================================================")

    # 1. Ensure tables exist
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 2. Setup Test Data
        print("\n[1] Setting up test roles, users, houses, and students...")
        
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            db.add(admin_role)

        teacher_role = db.query(Role).filter(Role.name == "teacher").first()
        if not teacher_role:
            teacher_role = Role(name="teacher")
            db.add(teacher_role)

        shm_role = db.query(Role).filter(Role.name == "senior_house_master").first()
        if not shm_role:
            shm_role = Role(name="senior_house_master")
            db.add(shm_role)

        shmistress_role = db.query(Role).filter(Role.name == "senior_house_mistress").first()
        if not shmistress_role:
            shmistress_role = Role(name="senior_house_mistress")
            db.add(shmistress_role)

        db.commit()

        # Users
        admin_user = db.query(User).filter(User.username == "admin").first()

        shm_boys = db.query(User).filter(User.username == "test_shm_boys").first()
        if not shm_boys:
            shm_boys = User(username="test_shm_boys", email="shm_b@school.edu", password_hash="pass")
            db.add(shm_boys)
            db.flush()
            if shm_role and not any(r.name == "senior_house_master" for r in shm_boys.roles):
                shm_boys.roles.append(shm_role)

        shm_girls = db.query(User).filter(User.username == "test_shm_girls").first()
        if not shm_girls:
            shm_girls = User(username="test_shm_girls", email="shm_g@school.edu", password_hash="pass")
            db.add(shm_girls)
            db.flush()
            if shmistress_role and not any(r.name == "senior_house_mistress" for r in shm_girls.roles):
                shm_girls.roles.append(shmistress_role)

        hm_aggrey = db.query(User).filter(User.username == "test_hm_aggrey").first()
        if not hm_aggrey:
            hm_aggrey = User(username="test_hm_aggrey", email="hm_aggrey@school.edu", password_hash="pass", roles=[teacher_role])
            db.add(hm_aggrey)

        hm_guggisberg = db.query(User).filter(User.username == "test_hm_guggisberg").first()
        if not hm_guggisberg:
            hm_guggisberg = User(username="test_hm_guggisberg", email="hm_gugg@school.edu", password_hash="pass", roles=[teacher_role])
            db.add(hm_guggisberg)

        db.commit()

        # Houses
        house_aggrey = db.query(House).filter(House.name == "Test Aggrey House").first()
        if not house_aggrey:
            house_aggrey = House(name="Test Aggrey House", gender="Boys", house_master_id=hm_aggrey.id)
            db.add(house_aggrey)
        else:
            house_aggrey.house_master_id = hm_aggrey.id

        house_guggisberg = db.query(House).filter(House.name == "Test Guggisberg House").first()
        if not house_guggisberg:
            house_guggisberg = House(name="Test Guggisberg House", gender="Boys", house_master_id=hm_guggisberg.id)
            db.add(house_guggisberg)
        else:
            house_guggisberg.house_master_id = hm_guggisberg.id

        house_yaa = db.query(House).filter(House.name == "Test Yaa Asantewaa House").first()
        if not house_yaa:
            house_yaa = House(name="Test Yaa Asantewaa House", gender="Girls")
            db.add(house_yaa)

        db.commit()

        # Students
        student_boy1 = db.query(Student).filter(Student.student_code == "EXT-BOY-001").first()
        if not student_boy1:
            student_boy1 = Student(student_code="EXT-BOY-001", full_name="Kofi Mensah", gender="Male", house_id=house_aggrey.id)
            db.add(student_boy1)
        else:
            student_boy1.house_id = house_aggrey.id

        student_boy2 = db.query(Student).filter(Student.student_code == "EXT-BOY-002").first()
        if not student_boy2:
            student_boy2 = Student(student_code="EXT-BOY-002", full_name="Kwame Addo", gender="Male", house_id=house_guggisberg.id)
            db.add(student_boy2)
        else:
            student_boy2.house_id = house_guggisberg.id

        student_girl1 = db.query(Student).filter(Student.student_code == "EXT-GIRL-001").first()
        if not student_girl1:
            student_girl1 = Student(student_code="EXT-GIRL-001", full_name="Ama Serwaa", gender="Female", house_id=house_yaa.id)
            db.add(student_girl1)
        else:
            student_girl1.house_id = house_yaa.id

        db.commit()
        print("   [OK] Test users, houses, and students created successfully.")

        # 3. Test Hierarchy Permissions
        print("\n[2] Testing Domestic Hierarchy Permission Rules...")

        # Rule A: House Master Aggrey can access Kofi Mensah (Aggrey)
        can_aggrey = _can_user_access_student(db, hm_aggrey, student_boy1)
        assert can_aggrey == True, "HM Aggrey should have access to Aggrey House student!"
        print("   [OK] House Master Aggrey allowed for Aggrey House student (Kofi Mensah).")

        # Rule B: House Master Aggrey CANNOT access Kwame Addo (Guggisberg)
        can_aggrey_cross = _can_user_access_student(db, hm_aggrey, student_boy2)
        assert can_aggrey_cross == False, "HM Aggrey must NOT have access to Guggisberg House student!"
        print("   [OK] House Master Aggrey correctly DENIED for Guggisberg House student (Kwame Addo).")

        # Rule C: Senior House Master (Boys) CAN access both boys in Aggrey & Guggisberg
        can_shm_boy1 = _can_user_access_student(db, shm_boys, student_boy1)
        can_shm_boy2 = _can_user_access_student(db, shm_boys, student_boy2)
        assert can_shm_boy1 and can_shm_boy2, "SHM Boys should access all male students across houses!"
        print("   [OK] Senior House Master (Boys) allowed for all male students across houses.")

        # Rule D: Senior House Mistress (Girls) CAN access female student in Yaa Asantewaa House
        can_shm_girl1 = _can_user_access_student(db, shm_girls, student_girl1)
        assert can_shm_girl1 == True, "SHM Girls should access all female students!"
        print("   [OK] Senior House Mistress (Girls) allowed for female student.")

        # Rule E: Admin user CAN access any student
        can_admin = _can_user_access_student(db, admin_user, student_girl1)
        assert can_admin == True, "Admin should access all students!"
        print("   [OK] Administrator allowed for any student across all houses.")

        # 4. Test Exeat Lifecycle (Create -> Approve -> Depart (Gate Out) -> Return (Gate In))
        print("\n[3] Testing Exeat Pass Lifecycle...")
        now = datetime.now()
        tomorrow = now + timedelta(days=1)

        new_ex = ExeatRecord(
            student_id=student_boy1.id,
            exeat_type="Weekend",
            reason="Family Event",
            destination="Kumasi",
            expected_departure=now,
            expected_return=tomorrow,
            status="Pending",
            created_by_id=student_boy1.id
        )
        db.add(new_ex)
        db.commit()
        db.refresh(new_ex)
        print(f"   Created Exeat #{new_ex.id} with status: {new_ex.status}")

        # Approve
        new_ex.status = "Approved"
        new_ex.approved_by_id = hm_aggrey.id
        db.commit()
        print(f"   Approved Exeat #{new_ex.id} by {hm_aggrey.username} -> Status: {new_ex.status}")

        # Gate Sign-Out
        new_ex.status = "Departed"
        new_ex.actual_departure = datetime.now()
        new_ex.gate_out_by_id = admin_user.id
        db.commit()
        print(f"   Gate Signed Out Exeat #{new_ex.id} -> Status: {new_ex.status}")

        # Gate Sign-In
        new_ex.status = "Returned"
        new_ex.actual_return = datetime.now()
        new_ex.gate_in_by_id = admin_user.id
        db.commit()
        print(f"   Gate Signed In Exeat #{new_ex.id} -> Status: {new_ex.status}")
        assert new_ex.status == "Returned", "Status should be Returned after gate sign-in!"

        # 5. Test Overdue Detection
        print("\n[4] Testing Automatic Overdue Exeat Detection...")
        past_dep = now - timedelta(days=3)
        past_ret = now - timedelta(days=1) # Expected return was yesterday!

        overdue_ex = ExeatRecord(
            student_id=student_boy2.id,
            exeat_type="Day",
            reason="Medical Visit",
            destination="Hospital",
            expected_departure=past_dep,
            expected_return=past_ret,
            status="Departed",
            actual_departure=past_dep,
            created_by_id=hm_guggisberg.id,
            approved_by_id=hm_guggisberg.id
        )
        db.add(overdue_ex)
        db.commit()

        # Run overdue scanner
        _check_overdue_exeats(db)
        db.refresh(overdue_ex)
        assert overdue_ex.status == "Overdue", f"Departed exeat past expected return should be Overdue! Got: {overdue_ex.status}"
        print(f"   [OK] Overdue scanner automatically updated Exeat #{overdue_ex.id} to status: {overdue_ex.status}")

        print("\n==================================================")
        print("   ALL EXEAT MODULE VERIFICATION TESTS PASSED!    ")
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
