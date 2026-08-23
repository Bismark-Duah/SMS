"""
Production Client Hand-off System Reset Script
School Management System (SMS)
"""
import os
import sys
import shutil
from datetime import datetime

# Ensure backend imports work
sys.path.insert(0, os.path.abspath("backend"))

from app.database import SessionLocal, engine
from app.models import (
    School, User, Role, user_roles, Setting,
    Student, StudentGuardian, StudentHealth, Score, Attendance,
    Notification, Fee, Payment, DisciplineRecord, ExeatRecord,
    StudentSemesterSummary, MessageLog, TeacherAssignment,
    Asset, TextbookAllocation, UniformItem, UniformDisbursement,
    GatePassLog, StudentClearanceRecord, AdmissionVoucher
)
from app.routes.auth import _hash_password

def prepare_client_handoff():
    db = SessionLocal()
    try:
        # 1. Create a timestamped backup before reset
        os.makedirs("backups", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if os.path.exists("school.db"):
            backup_path = f"backups/school_pre_handoff_{timestamp}.db"
            shutil.copy2("school.db", backup_path)
            print(f"[OK] Pre-handoff database backup created at: '{backup_path}'.")

        print("\nPurging all test users, transactional data, and student records for production hand-off...")

        # 2. Clear activity, transactional, and student tables
        db.query(Payment).delete(synchronize_session=False)
        db.query(Fee).delete(synchronize_session=False)
        db.query(Score).delete(synchronize_session=False)
        db.query(Attendance).delete(synchronize_session=False)
        db.query(ExeatRecord).delete(synchronize_session=False)
        db.query(DisciplineRecord).delete(synchronize_session=False)
        db.query(Notification).delete(synchronize_session=False)
        db.query(MessageLog).delete(synchronize_session=False)
        db.query(StudentSemesterSummary).delete(synchronize_session=False)
        db.query(StudentClearanceRecord).delete(synchronize_session=False)
        db.query(StudentGuardian).delete(synchronize_session=False)
        db.query(StudentHealth).delete(synchronize_session=False)
        db.query(TeacherAssignment).delete(synchronize_session=False)
        db.query(TextbookAllocation).delete(synchronize_session=False)
        db.query(UniformDisbursement).delete(synchronize_session=False)
        db.query(GatePassLog).delete(synchronize_session=False)
        db.query(AdmissionVoucher).delete(synchronize_session=False)
        db.query(Student).delete(synchronize_session=False)

        # 3. Purge all test users except superadmin and admin
        test_users = db.query(User).filter(~User.username.in_(["superadmin", "admin"])).all()
        test_user_ids = [u.id for u in test_users]

        if test_user_ids:
            db.execute(user_roles.delete().where(user_roles.c.user_id.in_(test_user_ids)))
            db.query(User).filter(User.id.in_(test_user_ids)).delete(synchronize_session=False)
            print(f"   [CLEARED] Purged {len(test_user_ids)} test user account(s).")
        else:
            print("   [CLEARED] No test user accounts found.")

        # 4. Enforce clean core admin accounts
        super_role = db.query(Role).filter(Role.name == "super_admin").first()
        admin_role = db.query(Role).filter(Role.name == "admin").first()

        if not super_role:
            super_role = Role(name="super_admin")
            db.add(super_role)
            db.flush()
        if not admin_role:
            admin_role = Role(name="admin")
            db.add(admin_role)
            db.flush()

        # Ensure superadmin exists & configured
        superadmin = db.query(User).filter(User.username == "superadmin").first()
        if not superadmin:
            superadmin = User(
                username="superadmin",
                email="superadmin@system.local",
                password_hash=_hash_password("superadmin123!"),
                school_id=None,
                is_active=True
            )
            db.add(superadmin)
            db.flush()
        else:
            superadmin.password_hash = _hash_password("superadmin123!")
            superadmin.school_id = None
            superadmin.is_active = True
        superadmin.roles = [super_role]

        # Ensure primary school admin exists & configured
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@school.local",
                password_hash=_hash_password("admin123!"),
                school_id=1,
                is_active=True
            )
            db.add(admin)
            db.flush()
        else:
            admin.password_hash = _hash_password("admin123!")
            admin.school_id = 1
            admin.is_active = True
        admin.roles = [admin_role]

        db.commit()

        # 5. Print Production Hand-Off Summary
        print("\n==================================================")
        print("         PRODUCTION CLIENT HAND-OFF SUMMARY       ")
        print("==================================================")
        print(f"  • Total Registered Users : {db.query(User).count()} (superadmin, admin)")
        print(f"  • Total Students         : {db.query(Student).count()} (Clean for Client)")
        print(f"  • Total Score Records    : {db.query(Score).count()} (Clean for Client)")
        print(f"  • Total Attendance Logs  : {db.query(Attendance).count()} (Clean for Client)")
        print(f"  • Total Fee Records      : {db.query(Fee).count()} (Clean for Client)")
        print(f"  • Total Exeat Logs       : {db.query(ExeatRecord).count()} (Clean for Client)")
        print("==================================================")
        print("[SUCCESS] System database is 100% clean and ready for production client deployment!")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Handoff preparation failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    prepare_client_handoff()
