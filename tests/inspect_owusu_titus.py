import os
import sys
sys.path.insert(0, os.path.abspath("backend"))

from app.database import SessionLocal
from app.models import User, Department, Role
from app.routes.assignments import list_privileges

def inspect():
    db = SessionLocal()
    user = db.query(User).filter(User.username.ilike("%owusu%") | User.email.ilike("%owusu%")).first()
    print("User found:", user.id if user else None, user.username if user else None, user.email if user else None)
    
    if user:
        print("User roles:", [r.name for r in user.roles])
        depts = db.query(Department).filter(Department.hod_id == user.id).all()
        print("Departments where hod_id = user.id:", [(d.id, d.name, d.code, d.hod_id) for d in depts])
        
    admin = db.query(User).filter(User.username == "admin").first()
    privs = list_privileges(db=db, current_user=admin)
    print("\nAll Privileges returned from list_privileges:")
    for p in privs:
        print(f"  teacher_id={p.teacher_id} ({p.teacher_name}) | type={p.privilege_type} | target={p.target_name}")

    db.close()

if __name__ == "__main__":
    inspect()
