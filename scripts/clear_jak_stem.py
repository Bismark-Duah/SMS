import os
import sys
import json
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database import SessionLocal
from backend.app.models import (
    School, Student, StudentGuardian, StudentHealth, Score,
    Attendance, ExeatRecord, DisciplineRecord,
    StudentSemesterSummary, MessageLog, User, user_roles, TeacherAssignment
)

def clear_jak_stem():
    db = SessionLocal()
    try:
        school = db.query(School).filter(School.id == 1).first()
        if not school:
            print("[ERROR] JAK STEM (School ID 1) not found in database.")
            return

        print(f"Starting data purge for: {school.name} (ID: {school.id}, Code: {school.code})")

        # 1. Create timestamped JSON backup before deletion
        os.makedirs("backups", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join("backups", f"jak_stem_pre_clear_{timestamp}.json")

        students = db.query(Student).filter(Student.school_id == 1).all()
        student_ids = [s.id for s in students]

        users_to_delete = db.query(User).filter(
            User.school_id == 1,
            ~User.username.in_(["admin", "superadmin"]),
            User.id != 1,
            User.id != 57
        ).all()
        user_ids = [u.id for u in users_to_delete]

        backup_data = {
            "school_id": school.id,
            "school_name": school.name,
            "purged_at": timestamp,
            "student_count": len(student_ids),
            "test_user_count": len(user_ids),
            "test_usernames": [u.username for u in users_to_delete],
            "students": [
                {
                    "id": s.id,
                    "student_code": s.student_code,
                    "full_name": s.full_name,
                    "gender": s.gender,
                    "class_name": s.class_name
                } for s in students
            ]
        }

        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2)
        print(f"[OK] Pre-purge backup created at: {backup_file}")

        # 2. Delete student dependent records
        if student_ids:
            db.query(StudentGuardian).filter(StudentGuardian.student_id.in_(student_ids)).delete(synchronize_session=False)
            db.query(StudentHealth).filter(StudentHealth.student_id.in_(student_ids)).delete(synchronize_session=False)
            db.query(Score).filter(Score.student_id.in_(student_ids)).delete(synchronize_session=False)
            db.query(Attendance).filter(Attendance.student_id.in_(student_ids)).delete(synchronize_session=False)
            db.query(ExeatRecord).filter(ExeatRecord.student_id.in_(student_ids)).delete(synchronize_session=False)
            db.query(DisciplineRecord).filter(DisciplineRecord.student_id.in_(student_ids)).delete(synchronize_session=False)
            db.query(StudentSemesterSummary).filter(StudentSemesterSummary.student_id.in_(student_ids)).delete(synchronize_session=False)
            db.query(MessageLog).filter(MessageLog.student_id.in_(student_ids)).delete(synchronize_session=False)

        # 3. Delete Student rows
        deleted_students = db.query(Student).filter(Student.school_id == 1).delete(synchronize_session=False)

        # 4. Delete 37 Test User rows (preserving primary admin & superadmin)
        deleted_users = 0
        if user_ids:
            db.execute(user_roles.delete().where(user_roles.c.user_id.in_(user_ids)))
            db.query(TeacherAssignment).filter(TeacherAssignment.teacher_id.in_(user_ids)).delete(synchronize_session=False)
            deleted_users = db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)

        db.commit()
        print(f"[SUCCESS] Successfully purged {deleted_students} student records and {deleted_users} test user accounts for {school.name}!")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Failed to clear JAK STEM data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_jak_stem()
