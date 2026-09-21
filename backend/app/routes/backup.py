import os
import sqlite3
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db, DEFAULT_DB_PATH
from ..models import User
from ..dependencies import get_current_user

router = APIRouter()

# Get backups directory path relative to project root
BACKUPS_DIR = os.path.join(os.path.dirname(DEFAULT_DB_PATH), "backups")

import zipfile
import shutil

from ..services.backup_service import BackupService

BACKUP_PRIVILEGED_ROLES = {
    "super_admin", "admin", "headmaster", "headmistress"
}

def _is_admin(user: User):
    roles = [r.name.lower() for r in user.roles]
    if not any(r in BACKUP_PRIVILEGED_ROLES for r in roles):
        raise HTTPException(
            status_code=403,
            detail="Access Denied: High-level administrative privileges required for backup operations."
        )


def _validate_safe_backup_path(target_path: str) -> str:
    """Validates that target_path is not a dangerous system directory or application source directory."""
    if not target_path or not target_path.strip():
        raise HTTPException(status_code=400, detail="Target directory path is required.")

    # Disallow path traversal patterns in relative paths
    if ".." in target_path.replace("\\", "/").split("/"):
        raise HTTPException(status_code=400, detail="Directory traversal patterns ('..') are forbidden in target path.")

    clean_target = os.path.abspath(os.path.realpath(target_path.strip()))

    # Prohibit root directory overwrites
    forbidden_roots = {"/", "\\", "c:\\", "c:/", "d:\\", "d:/"}
    if clean_target.lower().rstrip("\\/") in forbidden_roots or len(clean_target) <= 3:
        raise HTTPException(status_code=400, detail="Direct backup to drive or system root is forbidden.")

    # Prohibit operating system critical directories
    dangerous_substrs = [
        "windows", "system32", "program files", "bin", "sbin", "usr", "etc", "boot"
    ]
    path_parts = [p.lower() for p in clean_target.replace("\\", "/").split("/") if p]
    if any(dang in path_parts for dang in dangerous_substrs):
        raise HTTPException(status_code=400, detail="Target path cannot reside within protected system directories.")

    # Prohibit writing directly into the active application source code directory
    app_root = os.path.abspath(os.path.realpath(os.path.join(os.path.dirname(DEFAULT_DB_PATH), "..")))
    if clean_target.lower() == app_root.lower() or clean_target.lower().startswith(os.path.join(app_root, "backend").lower()):
        raise HTTPException(status_code=400, detail="Target path cannot target application source code.")

    return clean_target


@router.post("/run")
def run_backup(
    payload: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _is_admin(current_user)
    encrypt = (payload or {}).get("encrypt")
    passphrase = (payload or {}).get("passphrase")
    try:
        res = BackupService.create_backup(verify_integrity=True, encrypt=encrypt, passphrase=passphrase)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database backup failed: {str(e)}")

@router.get("/list")
def list_backups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _is_admin(current_user)
    return BackupService.list_backups()

@router.post("/verify/{filename}")
def verify_backup(
    filename: str,
    payload: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Verifies SHA-256 hash match and SQLite page integrity of a backup snapshot."""
    _is_admin(current_user)
    passphrase = (payload or {}).get("passphrase")
    try:
        return BackupService.verify_backup_integrity(filename, passphrase=passphrase)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Backup file {filename} not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Integrity verification failed: {str(e)}")

@router.post("/restore-test/{filename}")
def test_restore_backup(
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Executes a dry-run restoration verification on a backup snapshot, validating table schemas
    and queryability without altering the active live database.
    """
    _is_admin(current_user)
    try:
        return BackupService.restore_database_snapshot(filename, dry_run=True)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Backup snapshot '{filename}' not found.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore verification failed: {str(e)}")

@router.delete("/{filename}")
def delete_backup(
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _is_admin(current_user)

    # Sanitize path to prevent directory traversal
    filename = os.path.basename(filename)
    backup_path = os.path.join(BACKUPS_DIR, filename)

    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="Backup file not found.")

    try:
        os.remove(backup_path)
        sha_file = f"{backup_path}.sha256"
        if os.path.exists(sha_file):
            try: os.remove(sha_file)
            except Exception: pass
        return {"status": "success", "message": f"Backup file {filename} successfully deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete backup: {str(e)}")

@router.get("/download/{filename}")
def download_backup(
    filename: str,
    passphrase: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _is_admin(current_user)
    filename = os.path.basename(filename)
    backup_path = os.path.join(BACKUPS_DIR, filename)

    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="Backup file not found.")

    from fastapi.responses import FileResponse
    if passphrase and filename.endswith(".db"):
        enc_path = BackupService.encrypt_backup(backup_path, passphrase=passphrase)
        return FileResponse(enc_path, filename=os.path.basename(enc_path), media_type="application/octet-stream")

    media_type = "application/x-sqlite3"
    if filename.endswith(".enc"):
        media_type = "application/octet-stream"
    elif filename.endswith(".sha256"):
        media_type = "text/plain"

    return FileResponse(backup_path, filename=filename, media_type=media_type)


@router.get("/export-full-zip")
def export_full_system_zip(
    passphrase: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Bundles the latest SQLite hot database snapshot and school assets into a single downloadable .zip archive.
    If a passphrase is provided, the zip archive is encrypted with AES-256 before download.
    """
    _is_admin(current_user)
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    zip_filename = f"SMS_Full_Offline_Backup_{timestamp}.zip"
    zip_path = os.path.join(BACKUPS_DIR, zip_filename)

    db_temp_path = os.path.join(BACKUPS_DIR, f"temp_{timestamp}.db")
    try:
        src_conn = sqlite3.connect(DEFAULT_DB_PATH)
        dest_conn = sqlite3.connect(db_temp_path)
        with dest_conn:
            src_conn.backup(dest_conn)
        src_conn.close()
        dest_conn.close()

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(db_temp_path, arcname="sms_app.db")
            uploads_dir = os.path.join(os.path.dirname(DEFAULT_DB_PATH), "static", "uploads")
            if os.path.exists(uploads_dir):
                for root, _, files in os.walk(uploads_dir):
                    for file in files:
                        full_f = os.path.join(root, file)
                        rel_f = os.path.relpath(full_f, uploads_dir)
                        zipf.write(full_f, arcname=os.path.join("uploads", rel_f))

        if os.path.exists(db_temp_path):
            os.remove(db_temp_path)

        from fastapi.responses import FileResponse
        if passphrase or os.getenv("BACKUP_ENCRYPTION_KEY"):
            enc_zip = BackupService.encrypt_backup(zip_path, passphrase=passphrase)
            if os.path.exists(zip_path):
                try: os.remove(zip_path)
                except Exception: pass
            return FileResponse(enc_zip, filename=f"{zip_filename}.enc", media_type="application/octet-stream")

        return FileResponse(zip_path, filename=zip_filename, media_type="application/zip")
    except Exception as e:
        if os.path.exists(db_temp_path):
            os.remove(db_temp_path)
        raise HTTPException(status_code=500, detail=f"System zip packaging failed: {str(e)}")


@router.post("/encrypt/{filename}")
def encrypt_backup_file(
    filename: str,
    payload: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Encrypts an existing database snapshot at rest using AES-256 (Fernet)."""
    _is_admin(current_user)
    filename = os.path.basename(filename)
    source_path = os.path.join(BACKUPS_DIR, filename)
    passphrase = (payload or {}).get("passphrase")

    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="Backup file not found.")

    try:
        enc_file = BackupService.encrypt_backup(source_path, passphrase=passphrase)
        return {
            "status": "success",
            "message": "Backup encrypted successfully.",
            "encrypted_filename": os.path.basename(enc_file)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decrypt/{filename}")
def decrypt_backup_file(
    filename: str,
    payload: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Decrypts an encrypted backup snapshot at rest."""
    _is_admin(current_user)
    filename = os.path.basename(filename)
    source_path = os.path.join(BACKUPS_DIR, filename)
    passphrase = (payload or {}).get("passphrase")

    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="Encrypted backup file not found.")

    try:
        dec_file = BackupService.decrypt_backup(source_path, passphrase=passphrase)
        return {
            "status": "success",
            "message": "Backup decrypted successfully.",
            "decrypted_filename": os.path.basename(dec_file)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/copy-to-path")
def copy_backup_to_path(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Copies the latest SQLite database backup to a custom validated local drive/partition or LAN network path.
    """
    _is_admin(current_user)
    raw_target = payload.get("target_path", "")
    target_dir = _validate_safe_backup_path(raw_target)
    passphrase = payload.get("passphrase")

    if not os.path.exists(DEFAULT_DB_PATH):
        raise HTTPException(status_code=404, detail="Primary database file not found.")

    try:
        os.makedirs(target_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        target_file = os.path.join(target_dir, f"SMS_Offline_Backup_{timestamp}.db")

        src_conn = sqlite3.connect(DEFAULT_DB_PATH)
        dest_conn = sqlite3.connect(target_file)
        with dest_conn:
            src_conn.backup(dest_conn)
        src_conn.close()
        dest_conn.close()

        encrypted_target = None
        if passphrase or os.getenv("BACKUP_ENCRYPTION_KEY"):
            enc_path = BackupService.encrypt_backup(target_file, passphrase=passphrase)
            if os.path.exists(target_file):
                try: os.remove(target_file)
                except Exception: pass
            target_file = enc_path
            encrypted_target = True

        size_kb = (os.path.getsize(target_file) / 1024)
        return {
            "status": "success",
            "message": f"Successfully backed up database to custom location: {target_file}",
            "target_file": target_file,
            "size_kb": round(size_kb, 1),
            "encrypted": bool(encrypted_target)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write backup to custom path: {str(e)}")


@router.post("/checkpoint")
def trigger_wal_checkpoint(
    payload: dict = None,
    current_user: User = Depends(get_current_user)
):
    """
    Triggers an immediate SQLite WAL checkpoint to flush log frames into the main database.
    """
    _is_admin(current_user)
    from ..database import checkpoint_database
    mode = (payload or {}).get("mode", "TRUNCATE")
    res = checkpoint_database(mode)
    return res


@router.post("/optimize")
def trigger_database_optimize(
    current_user: User = Depends(get_current_user)
):
    """
    Executes a WAL TRUNCATE checkpoint followed by VACUUM to reclaim disk space and defragment.
    """
    _is_admin(current_user)
    from ..database import checkpoint_database, vacuum_database
    chk_res = checkpoint_database("TRUNCATE")
    vac_res = vacuum_database()
    return {
        "status": "success",
        "checkpoint": chk_res,
        "vacuum": vac_res,
        "message": "Database optimized, checkpointed, and compacted successfully."
    }
