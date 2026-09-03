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

def _is_admin(user: User):
    roles = [r.name.lower() for r in user.roles]
    admin_allowed = {
        "admin", "super_admin", "headmaster", "headmistress",
        "assistant_headmaster_admin", "assistant_head_admin",
        "assistant_headmaster_academic", "assistant_head_academic",
        "assistant_headmaster_domestic", "assistant_head_domestic",
        "bursar", "storekeeper"
    }
    if not any(r in admin_allowed for r in roles):
        raise HTTPException(status_code=403, detail="Access Denied: Administrative privileges required.")

@router.post("/run")
def run_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _is_admin(current_user)
    try:
        res = BackupService.create_backup(verify_integrity=True)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Verifies SHA-256 hash match and SQLite page integrity of a backup snapshot."""
    _is_admin(current_user)
    try:
        return BackupService.verify_backup_integrity(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Backup file {filename} not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Integrity verification failed: {str(e)}")

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
        return {"status": "success", "message": f"Backup file {filename} successfully deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete backup: {str(e)}")

@router.get("/download/{filename}")
def download_backup(
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _is_admin(current_user)
    filename = os.path.basename(filename)
    backup_path = os.path.join(BACKUPS_DIR, filename)

    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="Backup file not found.")

    from fastapi.responses import FileResponse
    return FileResponse(backup_path, filename=filename, media_type="application/x-sqlite3")


@router.get("/export-full-zip")
def export_full_system_zip(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Bundles the latest SQLite hot database snapshot and school assets into a single downloadable .zip archive.
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
        return FileResponse(zip_path, filename=zip_filename, media_type="application/zip")
    except Exception as e:
        if os.path.exists(db_temp_path):
            os.remove(db_temp_path)
        raise HTTPException(status_code=500, detail=f"System zip packaging failed: {str(e)}")


@router.post("/copy-to-path")
def copy_backup_to_path(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Copies the latest SQLite database backup to a custom local drive/partition or LAN network path.
    """
    _is_admin(current_user)
    target_dir = payload.get("target_path", "").strip()
    if not target_dir:
        raise HTTPException(status_code=400, detail="Target local/network directory path is required.")

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

        size_kb = (os.path.getsize(target_file) / 1024)
        return {
            "status": "success",
            "message": f"Successfully backed up database to custom location: {target_file}",
            "target_file": target_file,
            "size_kb": round(size_kb, 1)
        }
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
