import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath("backend"))

from app.database import SessionLocal, engine, Base
from app.routes.academic import get_executive_analytics

def test_executive_analytics():
    db = SessionLocal()
    print("Testing Executive Analytics Endpoint...")
    
    data = get_executive_analytics(db=db)
    
    print("[OK] Executive Analytics Data Retrieved:")
    print("  - Academic Metrics:")
    print(f"      SBA Entry Completion: {data['academic']['sba_completion_pct']}%")
    print(f"      Pending HOD Approvals: {data['academic']['pending_hod_approvals']}")
    print(f"      Published Class Reports: {data['academic']['published_classes_count']} / {data['academic']['total_classes']}")
    print(f"      Total Teachers: {data['academic']['total_teachers']}")
    print(f"      Total Departments: {data['academic']['total_departments']}")
    
    print("  - Domestic Metrics:")
    print(f"      Active Boarders: {data['domestic']['total_boarders']} across {data['domestic']['total_houses']} Houses")
    print(f"      Currently Away on Exeat: {data['domestic']['currently_away_exeat']}")
    print(f"      Overdue Exeat Count: {data['domestic']['overdue_exeat_count']}")
    print(f"      Active Discipline Incidents: {data['domestic']['active_discipline_incidents']}")
    
    db.close()
    print("\nALL EXECUTIVE ANALYTICS TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_executive_analytics()
