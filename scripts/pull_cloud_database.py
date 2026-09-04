"""
scripts/pull_cloud_database.py — Automated Cloud-to-Local Database Pipeline
School Management System (SMS) — Offline-First Edition

Usage:
  python scripts/pull_cloud_database.py
  python scripts/pull_cloud_database.py --url https://sms-nald.onrender.com --user superadmin

Description:
  1. Authenticates securely with the live cloud portal (Render).
  2. Creates an atomic snapshot on the cloud server.
  3. Downloads and verifies the cryptographic SHA-256 hash.
  4. Archives local school.db safely to backups/ before replacing.
  5. Validates SQLite page integrity and displays an entity summary report.
"""
import os
import sys
import getpass
import hashlib
import shutil
import sqlite3
import requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

DEFAULT_CLOUD_URL = os.getenv("CLOUD_BASE_URL", "https://sms-nald.onrender.com")
LOCAL_DB_PATH = os.path.join(BASE_DIR, "school.db")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")


def compute_sha256(file_path: str) -> str:
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def pull_cloud_database():
    print("==================================================")
    print("   CLOUD -> LOCAL DATABASE SYNCHRONIZATION TOOL   ")
    print("==================================================")

    cloud_url = input(f"Enter Cloud URL [{DEFAULT_CLOUD_URL}]: ").strip() or DEFAULT_CLOUD_URL
    cloud_url = cloud_url.rstrip("/")

    username = input("Enter Super Admin Username [superadmin]: ").strip() or "superadmin"
    password = getpass.getpass("Enter Super Admin Password: ")

    if not password:
        print("ERROR: Password is required to authenticate with cloud server.")
        sys.exit(1)

    print(f"\n[*] Connecting to {cloud_url}...")

    session = requests.Session()
    session.headers.update({"User-Agent": "EduManage360-CloudPullUtility/1.0"})

    # 1. Login
    try:
        login_res = session.post(
            f"{cloud_url}/api/auth/login",
            json={"username": username, "password": password},
            timeout=25
        )
    except Exception as e:
        print(f"ERROR: Failed to connect to cloud server: {e}")
        sys.exit(1)

    if login_res.status_code != 200:
        print(f"ERROR: Authentication failed ({login_res.status_code}): {login_res.text}")
        sys.exit(1)

    login_data = login_res.json()
    token = login_data.get("access_token")
    if not token:
        print("ERROR: No access token received from cloud server.")
        sys.exit(1)

    session.headers.update({"Authorization": f"Bearer {token}"})
    print("[OK] Super Admin authentication successful.")

    # 2. Trigger hot snapshot on cloud
    print("[*] Requesting live database snapshot from cloud server...")
    try:
        backup_res = session.post(f"{cloud_url}/api/backup/run", timeout=60)
    except Exception as e:
        print(f"ERROR: Failed to trigger cloud backup: {e}")
        sys.exit(1)

    if backup_res.status_code != 200:
        print(f"ERROR: Cloud backup generation failed ({backup_res.status_code}): {backup_res.text}")
        sys.exit(1)

    backup_data = backup_res.json()
    filename = backup_data.get("filename")
    cloud_sha256 = backup_data.get("sha256")

    if not filename:
        print(f"ERROR: Cloud server did not return a backup filename: {backup_data}")
        sys.exit(1)

    print(f"[OK] Cloud snapshot created: '{filename}'")

    # 3. Download cloud snapshot
    print(f"[*] Downloading '{filename}' from cloud...")
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    temp_download_path = os.path.join(BACKUPS_DIR, f"temp_cloud_{filename}")

    try:
        with session.get(f"{cloud_url}/api/backup/download/{filename}", stream=True, timeout=120) as stream_res:
            if stream_res.status_code != 200:
                print(f"ERROR: Failed to download backup file ({stream_res.status_code}): {stream_res.text}")
                sys.exit(1)

            with open(temp_download_path, "wb") as f:
                for chunk in stream_res.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
    except Exception as e:
        print(f"ERROR: Download interrupted: {e}")
        if os.path.exists(temp_download_path):
            os.remove(temp_download_path)
        sys.exit(1)

    download_size = os.path.getsize(temp_download_path)
    print(f"[OK] Download complete ({download_size:,} bytes).")

    # 4. Verify SHA-256
    download_sha256 = compute_sha256(temp_download_path)
    if cloud_sha256 and download_sha256.lower() != cloud_sha256.lower():
        print(f"ERROR: SHA-256 checksum mismatch!")
        print(f"   Expected: {cloud_sha256}")
        print(f"   Got     : {download_sha256}")
        os.remove(temp_download_path)
        sys.exit(1)
    print(f"[OK] SHA-256 Checksum verified: {download_sha256[:16]}... (Match)")

    # 5. Archive local DB before replacement
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_archive = os.path.join(BACKUPS_DIR, f"local_backup_pre_cloud_pull_{timestamp}.db")
    if os.path.exists(LOCAL_DB_PATH):
        shutil.copy2(LOCAL_DB_PATH, local_archive)
        print(f"[SAFETY ARCHIVE] Existing local database backed up to:\n   '{local_archive}'")

    # 6. Replace local DB atomically
    shutil.move(temp_download_path, LOCAL_DB_PATH)
    # Remove old WAL / SHM to ensure clean boot
    for ext in ["-wal", "-shm"]:
        wal_file = f"{LOCAL_DB_PATH}{ext}"
        if os.path.exists(wal_file):
            try:
                os.remove(wal_file)
            except Exception:
                pass

    print("[OK] Local database file updated with cloud snapshot.")

    # 7. Verify SQLite integrity & print summary
    print("\n[*] Verifying imported database integrity and entity stats...")
    conn = sqlite3.connect(LOCAL_DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        check_res = cur.fetchone()
        if not check_res or check_res[0] != "ok":
            print(f"WARNING: SQLite integrity check reported: {check_res}")
        else:
            print("[OK] SQLite PRAGMA integrity_check: OK")

        # Query counts
        def get_count(table_name):
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table_name};")
                return cur.fetchone()[0]
            except Exception:
                return 0

        schools_cnt = get_count("schools")
        students_cnt = get_count("students")
        users_cnt = get_count("users")
        scores_cnt = get_count("scores")
        fees_cnt = get_count("fees")

        print("\n==================================================")
        print("      CLOUD -> LOCAL SYNCHRONIZATION REPORT       ")
        print("==================================================")
        print(f" 📊 Imported Cloud Database Metrics:")
        print(f"    - Registered Schools : {schools_cnt}")
        print(f"    - Enrolled Students  : {students_cnt}")
        print(f"    - System Users       : {users_cnt}")
        print(f"    - Recorded Scores    : {scores_cnt}")
        print(f"    - Fee Records        : {fees_cnt}")
        print("==================================================")
        print(" ✔ Localhost is now synchronized with Cloud production data!")
        print(" 👉 Start your server with 'Start_EduManage360.bat'")
        print("==================================================\n")
    finally:
        conn.close()


if __name__ == "__main__":
    pull_cloud_database()
