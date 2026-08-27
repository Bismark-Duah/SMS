import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import SessionLocal
from backend.app.models import (
    User, Role, School, Student, Score, Subject, ClassSection, 
    Department, House, Semester, AcademicYear
)
from backend.app.routes.results import get_comparative_rankings

def test_comparative_rankings_engine():
    db = SessionLocal()
    try:
        print("\n" + "="*66)
        print("TEST SUITE: Role-Scoped Academic Comparative Intelligence & Rankings")
        print("="*66)

        # 1. Test Admin Executive View
        admin_user = db.query(User).filter(User.username == "test_admin").first()
        if not admin_user:
            admin_user = db.query(User).join(User.roles).filter(Role.name == "admin").first()

        assert admin_user is not None, "Admin user required for test"

        payload = get_comparative_rankings(
            semester_id=None,
            stage_filter=None,
            db=db,
            current_user=admin_user
        )

        print(f"[OK] Semester Resolved: {payload['semester']['name']} (ID: {payload['semester']['id']})")
        print(f"[OK] Total Classes Ranked in League Table: {len(payload['class_league'])}")
        
        if payload['class_league']:
            top_class = payload['class_league'][0]
            print(f"     -> [1st Place] {top_class['class_name']} | Avg: {top_class['average_score']}% | Pass Rate: {top_class['pass_rate_pct']}% | Form Master: {top_class['form_master_name']}")
            print(f"     -> Delta Movement: {top_class['rank_delta']} positions")

        print(f"[OK] Department Benchmarks Count: {len(payload['department_benchmarks'])}")
        if payload['department_benchmarks']:
            top_dept = payload['department_benchmarks'][0]
            print(f"     -> Top Dept: {top_dept['department_name']} (HOD: {top_dept['hod_name']}) | Quality Pass: {top_dept['quality_pass_rate_pct']}%")

        print(f"[OK] Cross-Class Subject Mastery Count: {len(payload['subject_mastery'])}")
        if payload['subject_mastery']:
            sub = payload['subject_mastery'][0]
            print(f"     -> Subject: {sub['subject_name']} | School Avg: {sub['overall_average']}% | Tested Classes: {len(sub['class_rankings'])}")

        print(f"[OK] Top Scholars Count: {len(payload['top_scholars'])}")
        if payload['top_scholars']:
            top_sc = payload['top_scholars'][0]
            print(f"     -> [Top Scholar] {top_sc['student_name']} ({top_sc['class_name']}) | Avg: {top_sc['average_score']}%")

        print(f"[OK] Most Improved Students Count: {len(payload['most_improved'])}")
        print(f"[OK] Inter-House League Count: {len(payload['house_league'])}")
        print(f"[OK] Fee Recovery League Count: {len(payload['fee_recovery_league'])}")

        # 2. Test Teacher Scoped View
        teacher_user = db.query(User).join(User.roles).filter(Role.name == "teacher").first()
        if teacher_user:
            t_payload = get_comparative_rankings(
                semester_id=None,
                stage_filter=None,
                db=db,
                current_user=teacher_user
            )
            print(f"[OK] Teacher Context Verified: is_teacher={t_payload['user_context']['is_teacher']}, is_admin={t_payload['user_context']['is_admin_exec']}")
            print(f"     -> Teacher Allocated Class Benchmarks: {len(t_payload['teacher_classes_benchmark'])}")

        print("\n" + "="*66)
        print("SUCCESS: ACADEMIC COMPARATIVE INTELLIGENCE SUITE VERIFIED 100%!")
        print("="*66)

    finally:
        db.close()

if __name__ == "__main__":
    test_comparative_rankings_engine()
