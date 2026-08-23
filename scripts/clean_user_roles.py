import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database import SessionLocal
from backend.app.models import User, Role

def clean_user_roles():
    db = SessionLocal()
    try:
        super_admin_role = db.query(Role).filter(Role.name == "super_admin").first()
        admin_role = db.query(Role).filter(Role.name == "admin").first()

        if not super_admin_role or not admin_role:
            print("[ERROR] Roles 'super_admin' or 'admin' not found in database.")
            return

        user1 = db.query(User).filter(User.id == 1).first()
        user2 = db.query(User).filter(User.id == 2).first()

        if user1:
            # User 1 (superadmin) -> super_admin role ONLY
            user1.roles = [super_admin_role]
            print(f"[OK] User ID 1 ({user1.username}) set to role: {[r.name for r in user1.roles]}")

        if user2:
            # User 2 (admin) -> admin role ONLY
            user2.roles = [admin_role]
            print(f"[OK] User ID 2 ({user2.username}) set to role: {[r.name for r in user2.roles]}")

        db.commit()

        # Verification
        print("\nUpdated System User List & Roles:")
        all_users = db.query(User).order_by(User.id).all()
        for u in all_users:
            print(f"  • User ID {u.id}: {u.username} (School ID: {u.school_id}) -> Roles: {[r.name for r in u.roles]}")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Failed to update user roles: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clean_user_roles()
