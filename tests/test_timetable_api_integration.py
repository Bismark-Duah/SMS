import sys
import os
import requests
sys.path.insert(0, os.path.abspath('.'))

from backend.app.database import SessionLocal
from backend.app.models import User, Role, School

def test_api_integration():
    db = SessionLocal()
    # Find an admin user
    admin = db.query(User).join(User.roles).filter(Role.name == "admin").first()
    if not admin:
        admin = db.query(User).first()
    print("Testing with User:", admin.username if admin else "None")
    
    # Generate token and register session
    from backend.app.services.auth import create_jwt
    from backend.app.middleware.device_session_guard import register_device_session
    token = create_jwt({"user_id": admin.id, "sub": admin.username, "roles": [r.name for r in admin.roles]})
    register_device_session(
        user_id=admin.id,
        user_role="admin",
        user_agent="PythonTest/1.0",
        client_ip="127.0.0.1",
        token=token,
        db=db
    )
    db.commit()
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Profile config
    r = requests.get("http://127.0.0.1:8000/api/timetable/profile-config", headers=headers)
    print("Profile Config API:", r.status_code, r.json())
    assert r.status_code == 200

    # 2. Auto generate
    r = requests.post("http://127.0.0.1:8000/api/timetable/auto-generate", headers=headers, json={
        "periods_per_day": 8,
        "friday_periods": 6
    })
    print("Auto-Generate API:", r.status_code, r.text)
    assert r.status_code == 200

    # 3. Campus Radar
    r = requests.get("http://127.0.0.1:8000/api/timetable/campus-radar", headers=headers)
    print("Campus Radar API:", r.status_code, r.json())
    assert r.status_code == 200

    # 4. Teacher Workloads
    r = requests.get("http://127.0.0.1:8000/api/timetable/teacher-workloads", headers=headers)
    print("Teacher Workloads API:", r.status_code, len(r.json()), "teachers")
    assert r.status_code == 200

    print("ALL API INTEGRATION TESTS PASSED 100%!")

if __name__ == '__main__':
    test_api_integration()
