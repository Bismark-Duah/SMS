"""
Automated Verification Script for One-Click Database Backup Utility
"""
import os
import sys
from sqlalchemy.orm import Session

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User, Role
from backend.app.routes.backup import run_backup, list_backups, delete_backup, BACKUPS_DIR

def run_tests():
    print("==================================================")
    print(" ONE-CLICK DATABASE BACKUP UTILITY TEST SUITE      ")
    print("==================================================")

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Setup Admin User
        print("\n[1] Setting up admin user...")
        role_admin = db.query(Role).filter(Role.name == "admin").first()
        if not role_admin:
            role_admin = Role(name="admin")
            db.add(role_admin)
            db.commit()

        user_admin = db.query(User).filter(User.username == "admin").first()
        print("   [OK] Admin user ready.")

        # 2. Run Database Backup
        print("\n[2] Triggering SQLite hot database backup...")
        res_backup = run_backup(db, user_admin)
        assert res_backup["status"] == "success", f"Backup should succeed! Got {res_backup}"
        filename = res_backup["filename"]
        backup_file_path = os.path.join(BACKUPS_DIR, filename)
        assert os.path.exists(backup_file_path), f"Backup file {filename} does not exist at {backup_file_path}!"
        print(f"   [OK] Backup successfully generated: {filename} ({os.path.getsize(backup_file_path)} bytes).")

        # 3. List Backups
        print("\n[3] Listing existing backups...")
        backups = list_backups(db, user_admin)
        assert any(b["filename"] == filename for b in backups), f"Generated backup {filename} was not returned in list_backups!"
        print(f"   [OK] Backup file found in list_backups API response.")

        # 4. Clean up / Delete Backup
        print("\n[4] Deleting generated backup file...")
        res_del = delete_backup(filename, db, user_admin)
        assert res_del["status"] == "success", f"Failed to delete backup! Got {res_del}"
        assert not os.path.exists(backup_file_path), "Backup file should be deleted from disk!"
        print(f"   [OK] Backup file successfully cleaned up from backups directory.")

        print("\n==================================================")
        print(" ALL DATABASE BACKUP VERIFICATION TESTS PASSED!    ")
        print("==================================================")

    except Exception as e:
        print(f"\n[FAIL] DATABASE BACKUP VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
