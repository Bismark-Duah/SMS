import os
import sys
sys.path.insert(0, os.path.abspath("backend"))

from app.database import SessionLocal
from app.models import User
from app.routes.auth import list_users

def inspect_users():
    db = SessionLocal()
    users = list_users(db=db)
    
    print("Total users from list_users endpoint:", len(users))
    for u in users:
        if "owusu" in u.username.lower() or (u.email and "owusu" in u.email.lower()):
            print(f"\nUser: id={u.id}, username='{u.username}', email='{u.email}'")
            print(f"  roles type: {type(u.roles)}")
            print(f"  roles content: {u.roles}")
            for r in u.roles:
                print(f"    role item: type={type(r)}, val={r}")

    db.close()

if __name__ == "__main__":
    inspect_users()
