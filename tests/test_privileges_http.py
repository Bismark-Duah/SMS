import os
import sys
sys.path.insert(0, os.path.abspath("backend"))

from app.database import SessionLocal
from app.models import User
from app.routes.assignments import list_privileges

def test_api():
    db = SessionLocal()
    
    # Test with admin user (user_id=1, school_id=1)
    admin = db.query(User).filter(User.username == "admin").first()
    print("Admin school_id:", getattr(admin, 'school_id', None))

    data = list_privileges(db=db, current_user=admin)
    print("Total privileges returned:", len(data))
    
    found = False
    for item in data:
        print(f"ID: {item.id} | teacher_id: {item.teacher_id} ({item.teacher_name}) | type: {item.privilege_type} | target: {item.target_name}")
        if item.teacher_id == 4:
            found = True
            print("  ==> OWUSU TITUS HAS PRIVILEGE:", item)

    if not found:
        print("  ==> OWUSU TITUS (ID 4) HAS NO PRIVILEGES RETURNED!")

    db.close()

if __name__ == "__main__":
    test_api()
