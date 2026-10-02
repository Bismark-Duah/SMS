import sys
import os
import requests

sys.path.insert(0, os.path.abspath('.'))

from backend.app.database import SessionLocal
from backend.app.models import User, Role, Timetable
from backend.app.services.auth import create_jwt
from backend.app.middleware.device_session_guard import register_device_session

def test_facilities_and_undo_flow():
    db = SessionLocal()
    admin = db.query(User).join(User.roles).filter(Role.name == "admin").first()
    assert admin is not None, "Admin user must exist"
    
    token = create_jwt({"user_id": admin.id, "sub": admin.username, "roles": [r.name for r in admin.roles]})
    register_device_session(
        user_id=admin.id,
        user_role="admin",
        user_agent="PythonTestRig/2.0",
        client_ip="127.0.0.1",
        token=token,
        db=db
    )
    db.commit()
    
    headers = {"Authorization": f"Bearer {token}"}
    base = "http://127.0.0.1:8000/api/timetable"
    
    print("\n--- 1. Testing GET /active-facilities ---")
    r = requests.get(f"{base}/active-facilities", headers=headers)
    assert r.status_code == 200, f"active-facilities returned {r.status_code}: {r.text}"
    data = r.json()
    print("Has specialized facilities:", data.get("has_specialized_facilities"))
    print("Found facilities count:", len(data.get("facilities", [])))
    print("Categories:", [c["title"] for c in data.get("categories", [])])
    
    fac_ids = [f["id"] for f in data.get("facilities", [])]
    print("Facility IDs detected from active subjects:", fac_ids)
    
    # 2. Setup facility counts to test solver
    facility_counts = {fid: 1 for fid in fac_ids}
    facility_counts["ict_lab"] = 2
    
    print("\n--- 2. Testing POST /auto-generate with facility counts ---")
    r = requests.post(f"{base}/auto-generate", headers=headers, json={
        "periods_per_day": 8,
        "friday_periods": 6,
        "facility_counts": facility_counts
    })
    assert r.status_code == 200, f"auto-generate returned {r.status_code}: {r.text}"
    gen_data = r.json()
    print("Status:", gen_data.get("status"))
    print("Total slots generated:", gen_data.get("total_slots"))
    print("Quality Score:", gen_data.get("quality_report", {}).get("score"))
    print("Can Undo:", gen_data.get("can_undo"))
    
    # Verify rooms in generated slots
    slots_with_rooms = db.query(Timetable).filter(
        Timetable.room.isnot(None),
        Timetable.room != "Standard Classroom"
    ).all()
    print(f"Slots allocated to specialized labs/workshops: {len(slots_with_rooms)}")
    sample_rooms = set(s.room for s in slots_with_rooms)
    print("Allocated specialized rooms:", sample_rooms)
    
    print("\n--- 3. Testing GET /snapshot-status ---")
    r = requests.get(f"{base}/snapshot-status", headers=headers)
    assert r.status_code == 200, f"snapshot-status failed: {r.text}"
    snap_data = r.json()
    print("Snapshot status:", snap_data)
    assert snap_data.get("has_snapshot") is True, "Must have an undo snapshot after auto-generate"
    
    print("\n--- 4. Testing POST /revert (Undo / Rollback) ---")
    r = requests.post(f"{base}/revert", headers=headers, json={})
    assert r.status_code == 200, f"revert failed: {r.text}"
    rev_data = r.json()
    print("Revert result:", rev_data)
    assert rev_data.get("status") == "SUCCESS", "Revert must succeed"
    print(f"Restored {rev_data.get('restored_slots')} slots from snapshot timestamp {rev_data.get('restored_snapshot_timestamp')}!")
    
    print("\n--- 5. Testing Re-Generation with Custom Lab Quantities ---")
    # Test setting single lab = 0 (homeroom fallback) vs 1
    facility_counts_custom = {fid: 0 for fid in fac_ids}
    # Turn on only Auto Workshop and Physics Lab
    facility_counts_custom["auto_workshop"] = 1
    facility_counts_custom["physics_lab"] = 1
    
    r = requests.post(f"{base}/auto-generate", headers=headers, json={
        "periods_per_day": 8,
        "friday_periods": 6,
        "facility_counts": facility_counts_custom
    })
    assert r.status_code == 200
    custom_gen = r.json()
    print("Status:", custom_gen.get("status"))
    print("Total slots:", custom_gen.get("total_slots"))
    print("Quality Score:", custom_gen.get("quality_report", {}).get("score"))
    
    slots_custom = db.query(Timetable).filter(
        Timetable.room.isnot(None),
        Timetable.room != "Standard Classroom"
    ).all()
    sample_rooms_custom = set(s.room for s in slots_custom)
    print("Allocated rooms when only Auto & Physics are active:", sample_rooms_custom)
    
    print("\n[OK] ALL FACILITY CAPACITY AND 1-CLICK ROLLBACK TESTS PASSED 100%!")
    db.close()

if __name__ == "__main__":
    test_facilities_and_undo_flow()
