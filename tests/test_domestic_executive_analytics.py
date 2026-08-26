import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import SessionLocal
from backend.app.models import User, Student, House, Dormitory, ExeatRecord, DisciplineRecord, StudentHealth
from backend.app.routes.academic import get_executive_analytics

def test_domestic_executive_analytics_payload():
    db = SessionLocal()
    try:
        user = db.query(User).first()
        res = get_executive_analytics(db=db, current_user=user)
        assert "domestic" in res, "Domestic analytics key missing"
        dom = res["domestic"]
        
        # Verify required keys
        expected_keys = [
            "total_boarders", "total_day_students", "currently_away_exeat",
            "overdue_exeat_count", "active_discipline_incidents", "medical_flags_count",
            "total_houses", "houses_matrix", "overdue_exeats_roster",
            "active_exeats_breakdown", "critical_medical_roster", "pending_discipline_cases"
        ]
        for k in expected_keys:
            assert k in dom, f"Key {k} missing from domestic analytics"
            
        print("[OK] Domestic analytics structure verified.")
        print(f"[OK] Total Boarders: {dom['total_boarders']}")
        print(f"[OK] Currently Away Exeats: {dom['currently_away_exeat']}")
        print(f"[OK] Overdue Exeats Count: {dom['overdue_exeat_count']}")
        print(f"[OK] Medical Flags Count: {dom['medical_flags_count']}")
        print(f"[OK] Houses Matrix Count: {len(dom['houses_matrix'])}")
        print(f"[OK] Exeat Breakdown: {dom['active_exeats_breakdown']}")
        print(f"[OK] Critical Medical Roster Count: {len(dom['critical_medical_roster'])}")
    finally:
        db.close()

if __name__ == "__main__":
    test_domestic_executive_analytics_payload()
