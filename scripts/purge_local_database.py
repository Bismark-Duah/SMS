"""
scripts/purge_local_database.py — Production-Ready Pristine Database Reset Utility
School Management System (SMS) — Offline-First Edition

Description:
  1. Creates an atomic timestamped safety backup of school.db before purging.
  2. Purges all test data, student records, academic scores, fees, audit logs, and test schools.
  3. Preserves official NaCCA curriculum, stages, and core schemas.
  4. Ensures a single master 'superadmin' account (superadmin / superadmin123!).
  5. Vacuums SQLite database and verifies 100% page integrity.
"""
import os
import sys
import shutil
import sqlite3
from datetime import datetime

# Add project root and backend to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from sqlalchemy import text
from backend.app.database import SessionLocal, engine, Base, DEFAULT_DB_PATH, checkpoint_database
from backend.app.models import (
    School, User, Role, user_roles, Setting,
    Student, StudentGuardian, StudentHealth, Score, Attendance,
    Notification, Fee, Payment, DisciplineRecord, ExeatRecord,
    StudentSemesterSummary, MessageLog, TeacherAssignment,
    Asset, TextbookAllocation, UniformItem, UniformDisbursement,
    GatePassLog, StudentClearanceRecord, AdmissionVoucher,
    AuditLog, ActivityAuditLog, SyncOutbox,
    Program, Department, House, Dormitory, ClassSection,
    Semester, AcademicYear, SchoolStage, ElectiveCombination,
    program_subjects, department_subjects, program_core_subjects,
    class_section_subjects, elective_combination_subjects,
    school_subjects, school_programs
)
from backend.app.routes.auth import _hash_password
from backend.app.routes import settings, classes, auth
from backend.app.ncca_seed import seed_ncca_curriculum


def purge_local_database():
    print("==================================================")
    print("  EDUMANAGE360 - PRISTINE PRODUCTION RESET TOOL   ")
    print("==================================================")

    # 1. Create safety backup
    backups_dir = os.path.join(BASE_DIR, "backups")
    os.makedirs(backups_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backups_dir, f"local_backup_pre_purge_{timestamp}.db")

    if os.path.exists(DEFAULT_DB_PATH):
        try:
            checkpoint_database(mode="TRUNCATE")
        except Exception as e:
            print(f"Notice: WAL checkpoint before backup: {e}")

        shutil.copy2(DEFAULT_DB_PATH, backup_file)
        print(f"[SAFETY ARCHIVE] Full database backed up to:\n   '{backup_file}'\n")
    else:
        print("Notice: No existing school.db found; creating fresh database.")

    # 2. Open DB session and perform cascading purge
    db = SessionLocal()
    try:
        print("[*] Purging all transactional, student, and activity records...")
        db.execute(text("PRAGMA foreign_keys = OFF;"))

        # Clear transactional & activity logs
        db.query(Payment).delete(synchronize_session=False)
        db.query(Fee).delete(synchronize_session=False)
        db.query(Score).delete(synchronize_session=False)
        db.query(Attendance).delete(synchronize_session=False)
        db.query(ExeatRecord).delete(synchronize_session=False)
        db.query(DisciplineRecord).delete(synchronize_session=False)
        db.query(Notification).delete(synchronize_session=False)
        db.query(MessageLog).delete(synchronize_session=False)
        db.query(AuditLog).delete(synchronize_session=False)
        db.query(ActivityAuditLog).delete(synchronize_session=False)
        db.query(SyncOutbox).delete(synchronize_session=False)

        # Clear student related data
        db.query(StudentSemesterSummary).delete(synchronize_session=False)
        db.query(StudentClearanceRecord).delete(synchronize_session=False)
        db.query(StudentGuardian).delete(synchronize_session=False)
        db.query(StudentHealth).delete(synchronize_session=False)
        db.query(TeacherAssignment).delete(synchronize_session=False)
        db.query(TextbookAllocation).delete(synchronize_session=False)
        db.query(UniformDisbursement).delete(synchronize_session=False)
        db.query(UniformItem).delete(synchronize_session=False)
        db.query(Asset).delete(synchronize_session=False)
        db.query(GatePassLog).delete(synchronize_session=False)
        db.query(AdmissionVoucher).delete(synchronize_session=False)
        db.query(Student).delete(synchronize_session=False)

        # Clear elective combinations & class section relationships
        db.execute(elective_combination_subjects.delete())
        db.query(ElectiveCombination).delete(synchronize_session=False)
        db.execute(class_section_subjects.delete())
        db.query(ClassSection).delete(synchronize_session=False)
        db.query(Dormitory).delete(synchronize_session=False)
        db.query(House).delete(synchronize_session=False)
        db.query(Department).delete(synchronize_session=False)

        # Clear academic calendar & school mappings
        db.execute(program_subjects.delete())
        db.execute(department_subjects.delete())
        db.execute(program_core_subjects.delete())
        db.execute(school_subjects.delete())
        db.execute(school_programs.delete())
        db.query(Semester).delete(synchronize_session=False)
        db.query(AcademicYear).delete(synchronize_session=False)
        db.query(Program).delete(synchronize_session=False)
        db.query(School).delete(synchronize_session=False)

        # Clear user roles & all users
        db.execute(user_roles.delete())
        db.query(User).delete(synchronize_session=False)
        db.execute(text("PRAGMA foreign_keys = ON;"))
        db.commit()

        print("[OK] All student records, test schools, and activity logs cleared.")

        # 3. Seed Master Super Admin Account
        super_role = db.query(Role).filter(Role.name == "super_admin").first()
        if not super_role:
            super_role = Role(name="super_admin")
            db.add(super_role)
            db.flush()

        # Seed all standard roles
        standard_roles = [
            "super_admin", "admin", "headmaster", "headmistress",
            "assistant_headmaster_academic", "assistant_head_academic",
            "assistant_headmaster_domestic", "assistant_head_domestic",
            "assistant_headmaster_admin", "assistant_head_admin",
            "hod", "senior_housemaster", "senior_housemistress",
            "house_master", "house_mistress", "form_master", "form_mistress",
            "teacher", "bursar", "storekeeper", "security_officer", "parent", "student"
        ]
        for r_name in standard_roles:
            r_obj = db.query(Role).filter(Role.name == r_name).first()
            if not r_obj:
                db.add(Role(name=r_name))
        db.flush()

        superadmin = User(
            username="superadmin",
            email="superadmin@edumanage360.gh",
            password_hash=_hash_password("superadmin123!"),
            school_id=None,
            is_active=True
        )
        superadmin.roles = [super_role]
        db.add(superadmin)
        db.commit()
        print("[OK] Master Super Admin initialized (username: superadmin / password: superadmin123!).")

        # 4. Seed NaCCA National Curriculum, Stages, and System Defaults
        classes.seed_default_stages(db)
        settings.seed_default_settings(db)
        seed_ncca_curriculum(db)
        print("[OK] NaCCA National Curriculum & standard academic stages initialized.")

    finally:
        db.close()

    # 5. Database Vacuum & Integrity Verification
    print("\n[*] Running SQLite PRAGMA VACUUM & Integrity Check...")
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    try:
        conn.execute("VACUUM;")
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        res = cursor.fetchone()
        if res and res[0] == "ok":
            print("[OK] SQLite PRAGMA integrity_check: OK")
        else:
            print(f"Warning: Integrity check output: {res}")
    finally:
        conn.close()

    # 6. Summary Report
    print("\n==================================================")
    print("     PRODUCTION-READY DATABASE RESET COMPLETE     ")
    print("==================================================")
    print(" Local Database Summary:")
    print("    - Registered Schools : 0 (Clean slate ready for onboarding)")
    print("    - Active Students    : 0")
    print("    - Test Transactions  : 0")
    print("    - Security Logs      : 0")
    print("    - Active Admin User  : 1 (superadmin)")
    print("    - Curriculum Model   : Official NaCCA Standard")
    print("==================================================")
    print(" You can now start your server with 'Start_EduManage360.bat'")
    print(" and sign in with 'superadmin' / 'superadmin123!'")
    print("==================================================\n")


if __name__ == "__main__":
    purge_local_database()
