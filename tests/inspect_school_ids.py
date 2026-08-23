import os
import sys
sys.path.insert(0, os.path.abspath("backend"))

from app.database import SessionLocal
from app.models import User, Department, School

def inspect_schools():
    db = SessionLocal()
    users = db.query(User).all()
    print("Users count:", len(users))
    for u in users:
        if "owusu" in u.username.lower() or (u.email and "owusu" in u.email.lower()):
            print(f"User ID {u.id}: {u.username} | email: {u.email} | school_id: {u.school_id}")

    depts = db.query(Department).all()
    print("\nDepartments count:", len(depts))
    for d in depts:
        print(f"Dept ID {d.id}: {d.name} | hod_id: {d.hod_id} | school_id: {d.school_id}")

    schools = db.query(School).all()
    print("\nSchools count:", len(schools))
    for s in schools:
        print(f"School ID {s.id}: {s.name}")

    db.close()

if __name__ == "__main__":
    inspect_schools()
