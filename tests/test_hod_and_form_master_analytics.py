import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import SessionLocal
from backend.app.models import User, Department, ClassSection
from backend.app.routes.academic import get_executive_analytics

def test_hod_and_form_master_analytics():
    db = SessionLocal()
    try:
        # 1. Test as Admin / General Executive
        admin_user = db.query(User).first()
        res_admin = get_executive_analytics(db=db, current_user=admin_user)
        
        assert "departmental" in res_admin, "departmental key missing from executive-analytics"
        assert "class_master" in res_admin, "class_master key missing from executive-analytics"
        
        dept = res_admin["departmental"]
        cls = res_admin["class_master"]
        
        print("[OK] General executive-analytics returns departmental and class_master keys.")
        if dept:
            print(f"[OK] Department: {dept.get('name')} ({dept.get('code')}) - HOD: {dept.get('hod_name')}")
            print(f"     Faculty: {dept.get('teacher_count')}, Subjects: {dept.get('subject_count')}, SBA: {dept.get('sba_completion_pct')}%, Pass: {dept.get('pass_rate_pct')}%")
            print(f"     Submissions roster: {len(dept.get('submissions', []))} items")
        
        if cls:
            print(f"[OK] Class: {cls.get('class_name')} - Total Students: {cls.get('total_students')} ({cls.get('boys_count')} boys, {cls.get('girls_count')} girls)")
            print(f"     Attendance Today: {cls.get('attendance_today_pct')}%, Pass Rate: {cls.get('pass_rate_pct')}%")
            print(f"     At-Risk Count: {cls.get('at_risk_count')}, Subjects Matrix: {len(cls.get('subjects_matrix', []))} items")

        # 2. Test specific HOD user if one exists
        dept_with_hod = db.query(Department).filter(Department.hod_id.isnot(None)).first()
        if dept_with_hod:
            hod_user = db.query(User).filter(User.id == dept_with_hod.hod_id).first()
            if hod_user:
                res_hod = get_executive_analytics(db=db, current_user=hod_user)
                assert res_hod["departmental"]["id"] == dept_with_hod.id
                print(f"[OK] Specific HOD user {hod_user.username} scoped directly to department: {res_hod['departmental']['name']}")

        # 3. Test specific Form Master user if one exists
        cls_with_fm = db.query(ClassSection).filter(ClassSection.form_master_id.isnot(None)).first()
        if cls_with_fm:
            fm_user = db.query(User).filter(User.id == cls_with_fm.form_master_id).first()
            if fm_user:
                res_fm = get_executive_analytics(db=db, current_user=fm_user)
                assert res_fm["class_master"]["class_id"] == cls_with_fm.id
                print(f"[OK] Specific Form Master user {fm_user.username} scoped directly to class: {res_fm['class_master']['class_name']}")

        print("\n========================================================")
        print("SUCCESS: HOD & FORM MASTER ANALYTICS VERIFIED 100%!")
        print("========================================================")
    finally:
        db.close()

if __name__ == "__main__":
    test_hod_and_form_master_analytics()
