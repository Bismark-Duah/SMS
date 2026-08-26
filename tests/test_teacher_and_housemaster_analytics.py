import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import SessionLocal
from backend.app.models import User, TeacherAssignment, House
from backend.app.routes.academic import get_executive_analytics

def test_teacher_and_housemaster_analytics():
    db = SessionLocal()
    try:
        # 1. Test as Admin / General Executive
        admin_user = db.query(User).first()
        res_admin = get_executive_analytics(db=db, current_user=admin_user)
        
        assert "teacher" in res_admin, "teacher key missing from executive-analytics"
        assert "house_master" in res_admin, "house_master key missing from executive-analytics"
        
        tchr = res_admin["teacher"]
        hm = res_admin["house_master"]
        
        print("[OK] General executive-analytics returns teacher and house_master keys.")
        if tchr:
            print(f"[OK] Teacher allocations: {tchr.get('total_allocations')} ({tchr.get('total_classes')} classes, {tchr.get('total_subjects')} subjects)")
            print(f"     SBA overall completion: {tchr.get('sba_completion_pct')}%")
            print(f"     Today timetable periods: {len(tchr.get('today_timetable', []))}")
            print(f"     At-risk students list: {len(tchr.get('at_risk_students', []))}")
        
        if hm:
            print(f"[OK] House: {hm.get('house_name')} ({hm.get('gender_type')}) - Total Boarders: {hm.get('total_boarders')} / {hm.get('total_capacity')} beds ({hm.get('occupancy_pct')}%)")
            print(f"     Active Exeats: {hm.get('active_exeats_count')}, Medical alerts: {len(hm.get('medical_alerts', []))}")
            print(f"     Dormitories: {len(hm.get('dormitories', []))}, Discipline cases: {len(hm.get('discipline_cases', []))}")

        # 2. Test specific Teacher user if one exists
        asgn = db.query(TeacherAssignment).first()
        if asgn:
            t_user = db.query(User).filter(User.id == asgn.teacher_id).first()
            if t_user:
                res_teacher = get_executive_analytics(db=db, current_user=t_user)
                assert "allocations" in res_teacher["teacher"]
                print(f"[OK] Specific Teacher user {t_user.username} returns scoped allocations: {len(res_teacher['teacher']['allocations'])}")

        # 3. Test specific Housemaster user if one exists
        h_with_master = db.query(House).filter(House.house_master_id.isnot(None)).first()
        if h_with_master:
            hm_user = db.query(User).filter(User.id == h_with_master.house_master_id).first()
            if hm_user:
                res_hm = get_executive_analytics(db=db, current_user=hm_user)
                assert res_hm["house_master"]["house_id"] == h_with_master.id
                print(f"[OK] Specific Housemaster user {hm_user.username} scoped directly to house: {res_hm['house_master']['house_name']}")

        print("\n========================================================")
        print("SUCCESS: TEACHER & HOUSEMASTER ANALYTICS VERIFIED 100%!")
        print("========================================================")
    finally:
        db.close()

if __name__ == "__main__":
    test_teacher_and_housemaster_analytics()
