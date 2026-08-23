import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database import SessionLocal, engine
from sqlalchemy import text

def swap_admin_ids():
    db = SessionLocal()
    try:
        # Check current IDs
        superadmin = db.execute(text("SELECT id, username FROM users WHERE username = 'superadmin'")).fetchone()
        admin = db.execute(text("SELECT id, username FROM users WHERE username = 'admin'")).fetchone()

        if not superadmin or not admin:
            print("[ERROR] Could not find both 'superadmin' and 'admin' users.")
            return

        print(f"Current IDs: superadmin={superadmin.id}, admin={admin.id}")

        old_super_id = superadmin.id
        old_admin_id = admin.id
        temp_id = 9999

        # STEP 1: Move admin (ID 1) -> temp_id (9999)
        db.execute(text("UPDATE user_roles SET user_id = :temp_id WHERE user_id = :old_id"), {"temp_id": temp_id, "old_id": old_admin_id})
        db.execute(text("UPDATE teacher_assignments SET teacher_id = :temp_id WHERE teacher_id = :old_id"), {"temp_id": temp_id, "old_id": old_admin_id})
        db.execute(text("UPDATE exeat_records SET created_by_id = :temp_id WHERE created_by_id = :old_id"), {"temp_id": temp_id, "old_id": old_admin_id})
        db.execute(text("UPDATE exeat_records SET approved_by_id = :temp_id WHERE approved_by_id = :old_id"), {"temp_id": temp_id, "old_id": old_admin_id})
        db.execute(text("UPDATE discipline_records SET recorded_by = :temp_id WHERE recorded_by = :old_id"), {"temp_id": temp_id, "old_id": old_admin_id})
        db.execute(text("UPDATE message_logs SET sender_id = :temp_id WHERE sender_id = :old_id"), {"temp_id": temp_id, "old_id": old_admin_id})
        db.execute(text("UPDATE users SET id = :temp_id WHERE id = :old_id"), {"temp_id": temp_id, "old_id": old_admin_id})

        # STEP 2: Move superadmin (old_super_id) -> ID 1
        db.execute(text("UPDATE user_roles SET user_id = 1 WHERE user_id = :old_id"), {"old_id": old_super_id})
        db.execute(text("UPDATE teacher_assignments SET teacher_id = 1 WHERE teacher_id = :old_id"), {"old_id": old_super_id})
        db.execute(text("UPDATE exeat_records SET created_by_id = 1 WHERE created_by_id = :old_id"), {"old_id": old_super_id})
        db.execute(text("UPDATE exeat_records SET approved_by_id = 1 WHERE approved_by_id = :old_id"), {"old_id": old_super_id})
        db.execute(text("UPDATE discipline_records SET recorded_by = 1 WHERE recorded_by = :old_id"), {"old_id": old_super_id})
        db.execute(text("UPDATE message_logs SET sender_id = 1 WHERE sender_id = :old_id"), {"old_id": old_super_id})
        db.execute(text("UPDATE users SET id = 1 WHERE id = :old_id"), {"old_id": old_super_id})

        # STEP 3: Move admin (temp_id 9999) -> ID 2
        db.execute(text("UPDATE user_roles SET user_id = 2 WHERE user_id = :temp_id"), {"temp_id": temp_id})
        db.execute(text("UPDATE teacher_assignments SET teacher_id = 2 WHERE teacher_id = :temp_id"), {"temp_id": temp_id})
        db.execute(text("UPDATE exeat_records SET created_by_id = 2 WHERE created_by_id = :temp_id"), {"temp_id": temp_id})
        db.execute(text("UPDATE exeat_records SET approved_by_id = 2 WHERE approved_by_id = :temp_id"), {"temp_id": temp_id})
        db.execute(text("UPDATE discipline_records SET recorded_by = 2 WHERE recorded_by = :temp_id"), {"temp_id": temp_id})
        db.execute(text("UPDATE message_logs SET sender_id = 2 WHERE sender_id = :temp_id"), {"temp_id": temp_id})
        db.execute(text("UPDATE users SET id = 2 WHERE id = :temp_id"), {"temp_id": temp_id})

        db.commit()

        # Verify
        new_users = db.execute(text("SELECT id, username, email FROM users ORDER BY id ASC")).fetchall()
        print("\n[SUCCESS] User IDs swapped successfully!")
        print("Updated User List:")
        for u in new_users:
            print(f"  • ID {u.id}: {u.username} ({u.email})")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Failed to swap user IDs: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    swap_admin_ids()
