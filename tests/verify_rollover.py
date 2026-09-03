import sys
import os
import json
from sqlalchemy.orm import Session

current_dir = os.path.dirname(os.path.abspath(__file__))
sms_root = os.path.abspath(os.path.join(current_dir, ".."))
if sms_root not in sys.path:
    sys.path.insert(0, sms_root)

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User, Role, AcademicYear, Semester, Student, Fee, Setting
from backend.app.routes.rollover import get_rollover_status, execute_rollover, RolloverPayload

def run_tests():
    print("==================================================")
    print(" END-OF-TERM ROLLOVER WIZARD TEST SUITE           ")
    print("==================================================")

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Setup Admin User
        print("\n[1] Setting up users & academic years...")
        role_admin = db.query(Role).filter(Role.name == "admin").first()
        if not role_admin:
            role_admin = Role(name="admin")
            db.add(role_admin)
            db.commit()

        user_admin = db.query(User).filter(User.username == "admin").first()

        # Mark existing academic years & semesters as non-current
        db.query(Semester).update({Semester.is_current: False})
        db.query(AcademicYear).update({AcademicYear.is_current: False})
        db.commit()

        # Source Year & Sem (idempotent lookup/creation)
        yr_old = db.query(AcademicYear).filter(AcademicYear.label == "2025/2026").first()
        if not yr_old:
            yr_old = AcademicYear(label="2025/2026", is_current=True)
            db.add(yr_old)
            db.commit()
            db.refresh(yr_old)
        else:
            yr_old.is_current = True
            db.commit()

        sem_old = db.query(Semester).filter(Semester.academic_year_id == yr_old.id, Semester.name == "Term 1").first()
        if not sem_old:
            sem_old = Semester(name="Term 1", academic_year_id=yr_old.id, is_current=True)
            db.add(sem_old)
            db.commit()
            db.refresh(sem_old)
        else:
            sem_old.is_current = True
            db.commit()

        # Target Year & Sem
        sem_new = db.query(Semester).filter(Semester.academic_year_id == yr_old.id, Semester.name == "Term 2").first()
        if not sem_new:
            sem_new = Semester(name="Term 2", academic_year_id=yr_old.id, is_current=False)
            db.add(sem_new)
            db.commit()
            db.refresh(sem_new)
        else:
            sem_new.is_current = False
            db.commit()

        print(f"   [OK] Active period set to {yr_old.label} - {sem_old.name}.")
        print(f"   [OK] Target period set to {yr_old.label} - {sem_new.name}.")

        # 2. Setup Student & Fees
        print("\n[2] Setting up mock student and unpaid fees...")
        st = db.query(Student).filter(Student.student_code == "ROLL-STU-001").first()
        if not st:
            st = Student(student_code="ROLL-STU-001", full_name="Arrears Kid", gender="Male", is_active=True)
            db.add(st)
            db.commit()

        # Clean old fees
        db.query(Fee).filter(Fee.student_id == st.id).delete()
        db.commit()

        # Add unpaid fee in old term
        old_bill = Fee(
            student_id=st.id,
            fee_type="Tuition",
            description="Term 1 Fees",
            amount=500.0,
            amount_paid=200.0,  # 300 arrears
            academic_year="2025/2026",
            term="Term 1",
            status="Partial"
        )
        db.add(old_bill)
        db.commit()
        print(f"   [OK] Student billed 500, paid 200 (Arrears balance: 300).")

        # 3. Check status
        print("\n[3] Calling get_rollover_status...")
        status = get_rollover_status(db, user_admin)
        assert status["current_year_label"] == "2025/2026", "Should return active year!"
        assert status["current_semester_name"] == "Term 1", "Should return active semester!"
        assert status["unpaid_fees_count"] == 1, "Should count 1 unpaid fee!"
        assert status["total_unpaid_amount"] == 300.0, f"Outstanding sum should be 300.0, got {status['total_unpaid_amount']}"
        print("   [OK] Status check returns correct current values.")

        # 4. Execute Rollover
        print("\n[4] Executing academic term rollover...")
        payload = RolloverPayload(
            target_year_id=yr_old.id,
            target_semester_id=sem_new.id,
            carry_over_fees=True,
            archive_reports=True
        )

        res_roll = execute_rollover(payload, db, user_admin)
        assert res_roll["status"] == "success", "Rollover execution should report success status!"
        assert res_roll["fees_carried_over"] == 1, f"Should report 1 fee carried over! Got {res_roll['fees_carried_over']}"

        # 5. Assert database updates
        print("\n[5] Asserting database changes...")
        # Check active term
        db.refresh(yr_old)
        db.refresh(sem_old)
        db.refresh(sem_new)

        assert yr_old.is_current == True, "Academic Year should remain active."
        assert sem_old.is_current == False, "Old semester should no longer be active."
        assert sem_new.is_current == True, "Target semester should now be active."

        # Check Report Archive settings
        locked_setting = db.query(Setting).filter(Setting.key == "locked_semester_ids").first()
        assert locked_setting is not None, "locked_semester_ids setting should be created!"
        locked_ids = json.loads(locked_setting.value)
        assert sem_old.id in locked_ids, f"Completed semester ID {sem_old.id} should be locked!"

        # Check carried over fee
        old_bill_refreshed = db.query(Fee).filter(Fee.id == old_bill.id).first()
        assert old_bill_refreshed.status == "Carried Over", f"Old bill status should be 'Carried Over'! Got {old_bill_refreshed.status}"

        carried_fee = db.query(Fee).filter(
            Fee.student_id == st.id,
            Fee.fee_type == "Arrears",
            Fee.term == "Term 2"
        ).first()

        assert carried_fee is not None, "Arrears fee not created in Term 2!"
        assert carried_fee.amount == 300.0, f"Arrears fee should be 300.0, got {carried_fee.amount}"
        print("   [OK] Active markers, locked lists, and arrears entries asserted successfully.")

        # Cleanup
        db.query(Setting).filter(Setting.key == "locked_semester_ids").delete()
        db.query(Fee).filter(Fee.student_id == st.id).delete()
        db.commit()

        print("\n==================================================")
        print(" ALL TERM ROLLOVER VERIFICATION TESTS PASSED!     ")
        print("==================================================")

    except Exception as e:
        print(f"\n[FAIL] TERM ROLLOVER VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
