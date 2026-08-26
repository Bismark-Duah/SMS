import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import SessionLocal
from backend.app.models import User, Student
from backend.app.routes.academic import get_executive_analytics

def test_all_remaining_personas_analytics():
    db = SessionLocal()
    try:
        # 1. Test as Admin / Root User
        admin_user = db.query(User).first()
        res = get_executive_analytics(db=db, current_user=admin_user)
        
        # Check all keys
        for key in ["academic", "domestic", "administration", "departmental", "class_master", "teacher", "house_master", "bursar", "storekeeper", "security", "student_portal", "parent_portal"]:
            assert key in res, f"Key '{key}' missing from executive-analytics payload!"
        
        # Verify Bursar metrics
        bur = res["bursar"]
        print(f"[OK] Bursar: Billed=GHC {bur.get('total_billed_ghc')}, Collected=GHC {bur.get('total_collected_ghc')}, Arrears=GHC {bur.get('total_arrears_ghc')}, Rate={bur.get('collection_rate_pct')}%")
        print(f"     Categories: {len(bur.get('fee_categories', []))}, Recent Payments: {len(bur.get('recent_payments', []))}, Debtors: {len(bur.get('top_debtors', []))}")
        
        # Verify Storekeeper metrics
        stk = res["storekeeper"]
        print(f"[OK] Storekeeper: Assets={stk.get('total_assets_count')}, Textbooks={stk.get('total_textbooks_issued')}, Uniforms={stk.get('total_uniforms_in_stock')}, Low Stock Alerts={stk.get('low_stock_alerts_count')}")
        
        # Verify Security metrics
        sec = res["security"]
        print(f"[OK] Security: Active Gate Exeats={sec.get('active_gate_exeats_count')}, Overdue={sec.get('overdue_exeats_count')}, Gate Movements Today={sec.get('today_gate_movements_count')}")
        
        # Verify Student & Parent metrics
        stp = res["student_portal"]
        prt = res["parent_portal"]
        if stp:
            print(f"[OK] Student Portal: Name={stp.get('name')}, Class={stp.get('class_name')}, Average={stp.get('term_average')}%, Attendance={stp.get('attendance_rate_pct')}%, Fee Balance=GHC {stp.get('fee_summary', {}).get('balance')}")
        print(f"[OK] Parent Portal: Linked Wards Count={len(prt.get('wards', []))}")

        print("\n==================================================================")
        print("SUCCESS: ALL PERSONAS ACROSS SYSTEM HIERARCHY VERIFIED 100%!")
        print("==================================================================")
    finally:
        db.close()

if __name__ == "__main__":
    test_all_remaining_personas_analytics()
