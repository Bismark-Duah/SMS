import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import SessionLocal
from backend.app.models import User, Student, Department, TeacherAssignment, ActivityAuditLog
from backend.app.routes.academic import get_executive_analytics

def test_administration_executive_analytics_payload():
    db = SessionLocal()
    try:
        user = db.query(User).first()
        res = get_executive_analytics(db=db, current_user=user)
        assert "administration" in res, "Administration analytics key missing"
        adm = res["administration"]
        
        expected_keys = [
            "total_staff", "teaching_staff_count", "non_teaching_staff_count",
            "unassigned_teachers_count", "active_users_count", "inactive_users_count",
            "total_students_enrolled", "admissions_funnel", "form_demographics",
            "departments_staffing", "total_broadcast_messages", "recent_audit_logs",
            "total_classes", "total_departments"
        ]
        for k in expected_keys:
            assert k in adm, f"Key {k} missing from administration analytics"
            
        assert "placed" in adm["admissions_funnel"]
        assert "form_completed" in adm["admissions_funnel"]
        assert "fully_registered" in adm["admissions_funnel"]
        
        print("[OK] Administration analytics payload verified successfully.")
        print(f"[OK] Total Staff: {adm['total_staff']} ({adm['teaching_staff_count']} teaching, {adm['non_teaching_staff_count']} non-teaching)")
        print(f"[OK] Unassigned Teachers: {adm['unassigned_teachers_count']}")
        print(f"[OK] Active Users: {adm['active_users_count']}")
        print(f"[OK] Total Students Enrolled: {adm['total_students_enrolled']}")
        print(f"[OK] Admissions Funnel: {adm['admissions_funnel']}")
        print(f"[OK] Form Demographics: {adm['form_demographics']}")
        print(f"[OK] Departments Staffing Count: {len(adm['departments_staffing'])}")
        print(f"[OK] Recent Audit Logs Count: {len(adm['recent_audit_logs'])}")
    finally:
        db.close()

if __name__ == "__main__":
    test_administration_executive_analytics_payload()
