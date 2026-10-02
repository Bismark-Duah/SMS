import sys
import os
import requests

sys.path.insert(0, os.path.abspath('.'))

from backend.app.database import SessionLocal
from backend.app.models import User, Role, Timetable, TimetableSnapshot
from backend.app.services.auth import create_jwt
from backend.app.middleware.device_session_guard import register_device_session

def test_clear_and_discard():
    db = SessionLocal()
    admin = db.query(User).join(User.roles).filter(Role.name == "admin").first()
    assert admin is not None
    
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
    
    # Check slots before test
    initial_slots = db.query(Timetable).count()
    print(f"Initial slots in DB: {initial_slots}")
    
    # 1. Test DELETE /clear
    print("\n--- Testing DELETE /clear ---")
    r = requests.delete(f"{base}/clear", headers=headers)
    assert r.status_code == 200, f"clear returned {r.status_code}: {r.text}"
    data = r.json()
    print("Clear response:", data)
    assert data["status"] == "SUCCESS"
    
    slots_after_clear = db.query(Timetable).count()
    print(f"Slots after clear: {slots_after_clear}")
    assert slots_after_clear == 0, f"Expected 0 slots, got {slots_after_clear}"
    
    # 2. Test auto-generate on a clean slate
    print("\n--- Testing auto-generate on clean slate ---")
    r = requests.post(f"{base}/auto-generate", headers=headers, json={
        "periods_per_day": 8,
        "friday_periods": 6
    })
    assert r.status_code == 200
    gen_data = r.json()
    print("Auto-generate total slots:", gen_data.get("total_slots"))
    assert gen_data.get("total_slots", 0) > 0
    
    # Verify snapshot status exists
    r_snap = requests.get(f"{base}/snapshot-status", headers=headers)
    assert r_snap.status_code == 200
    snap_data = r_snap.json()
    print("Snapshot status after generate:", snap_data)
    assert snap_data.get("has_snapshot") is True
    assert snap_data.get("slot_count") == 0  # previous slot count was 0!
    
    # 3. Test POST /discard (Discard draft & clear to blank)
    print("\n--- Testing POST /discard (Discard draft & clear to blank) ---")
    r_discard = requests.post(f"{base}/discard", headers=headers)
    assert r_discard.status_code == 200, f"discard returned {r_discard.status_code}: {r_discard.text}"
    discard_data = r_discard.json()
    print("Discard response:", discard_data)
    assert discard_data["status"] == "SUCCESS"
    
    slots_after_discard = db.query(Timetable).count()
    print(f"Slots after discard: {slots_after_discard}")
    assert slots_after_discard == 0, f"Expected 0 slots, got {slots_after_discard}"
    
    # Verify snapshot is also gone
    r_snap2 = requests.get(f"{base}/snapshot-status", headers=headers)
    snap_data2 = r_snap2.json()
    print("Snapshot status after discard:", snap_data2)
    assert snap_data2.get("has_snapshot") is False
    
    print("\n[OK] ALL CLEAR AND DISCARD TESTS PASSED 100%!")
    db.close()

if __name__ == "__main__":
    test_clear_and_discard()
