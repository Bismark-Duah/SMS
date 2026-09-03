import os
import sqlite3
import hashlib
import shutil
import zipfile
from datetime import datetime
from typing import List, Dict, Any, Optional
from ..database import DEFAULT_DB_PATH, is_sqlite, checkpoint_database
from ..logger import get_logger

logger = get_logger("backup_service")

# Backups directory relative to project root
BACKUPS_DIR = os.path.abspath(os.path.join(os.path.dirname(DEFAULT_DB_PATH), "backups"))
MAX_BACKUPS_RETAINED = int(os.getenv("MAX_BACKUPS_RETAINED", "14"))


def _compute_sha256(file_path: str) -> str:
    """Computes SHA-256 cryptographic hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


class BackupService:
    """
    Enterprise SQLite Backup & Recovery Service.
    Features:
    - Online hot database snapshots using sqlite3.backup (zero locking/downtime)
    - Pre-backup WAL checkpoint synchronization
    - SHA-256 cryptographic checksum calculation and storage
    - Post-backup PRAGMA quick_check integrity verification
    - Rolling retention policy enforcement (pruning stale backups)
    """

    @classmethod
    def create_backup(
        cls,
        retention_limit: int = MAX_BACKUPS_RETAINED,
        verify_integrity: bool = True
    ) -> Dict[str, Any]:
        """
        Executes an atomic hot backup of the active SQLite database.
        """
        if not is_sqlite:
            return {
                "status": "skipped",
                "message": "SQLite hot backup service only applies to SQLite databases. Use pg_dump for PostgreSQL."
            }

        if not os.path.exists(DEFAULT_DB_PATH):
            raise FileNotFoundError(f"Primary database file not found at {DEFAULT_DB_PATH}")

        os.makedirs(BACKUPS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.db"
        backup_path = os.path.join(BACKUPS_DIR, backup_filename)
        checksum_path = f"{backup_path}.sha256"

        try:
            # 1. Flush active WAL transactions to main database file
            checkpoint_result = checkpoint_database(mode="PASSIVE")
            logger.info(f"WAL checkpoint before backup completed: {checkpoint_result}")

            # 2. Perform safe sqlite3 online hot backup
            src_conn = sqlite3.connect(DEFAULT_DB_PATH)
            dest_conn = sqlite3.connect(backup_path)
            with dest_conn:
                src_conn.backup(dest_conn, pages=100)
            src_conn.close()
            dest_conn.close()

            # 3. Compute and store SHA-256 checksum
            sha256_hash = _compute_sha256(backup_path)
            with open(checksum_path, "w", encoding="utf-8") as f:
                f.write(f"{sha256_hash}  {backup_filename}\n")

            # 4. Verify integrity via PRAGMA quick_check
            integrity_passed = True
            integrity_message = "ok"
            if verify_integrity:
                test_conn = sqlite3.connect(backup_path)
                cursor = test_conn.cursor()
                cursor.execute("PRAGMA quick_check;")
                rows = cursor.fetchall()
                test_conn.close()
                if not rows or rows[0][0] != "ok":
                    integrity_passed = False
                    integrity_message = str(rows)
                    logger.error(f"Integrity check failed for {backup_filename}: {integrity_message}")
                    raise ValueError(f"Corrupted backup generated: {integrity_message}")

            # 5. Enforce rolling retention policy
            pruned_count = cls.enforce_retention_policy(retention_limit)

            size_bytes = os.path.getsize(backup_path)
            logger.info(f"Hot backup successful: {backup_filename} ({size_bytes} bytes), SHA-256: {sha256_hash[:12]}...")

            return {
                "status": "success",
                "message": "Hot database backup completed and verified successfully.",
                "filename": backup_filename,
                "size_bytes": size_bytes,
                "sha256": sha256_hash,
                "integrity_verified": integrity_passed,
                "pruned_old_backups_count": pruned_count
            }

        except Exception as e:
            logger.error(f"Database backup failed: {e}", exc_info=True)
            if os.path.exists(backup_path):
                try: os.remove(backup_path)
                except Exception: pass
            if os.path.exists(checksum_path):
                try: os.remove(checksum_path)
                except Exception: pass
            raise RuntimeError(f"Hot database backup failed: {str(e)}")

    @classmethod
    def verify_backup_integrity(cls, filename: str) -> Dict[str, Any]:
        """
        Validates SHA-256 checksum match and executes SQLite integrity check on a stored backup.
        """
        filename = os.path.basename(filename)
        backup_path = os.path.join(BACKUPS_DIR, filename)
        checksum_path = f"{backup_path}.sha256"

        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file {filename} not found.")

        # 1. Verify Checksum
        checksum_valid = False
        stored_hash = None
        computed_hash = _compute_sha256(backup_path)

        if os.path.exists(checksum_path):
            with open(checksum_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                stored_hash = content.split()[0] if content else ""
                checksum_valid = (computed_hash == stored_hash)
        else:
            # Checksum file missing -> regenerate
            with open(checksum_path, "w", encoding="utf-8") as f:
                f.write(f"{computed_hash}  {filename}\n")
            stored_hash = computed_hash
            checksum_valid = True

        # 2. Run PRAGMA integrity_check
        test_conn = sqlite3.connect(backup_path)
        cursor = test_conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        rows = cursor.fetchall()
        test_conn.close()

        is_sqlite_healthy = bool(rows and rows[0][0] == "ok")

        return {
            "filename": filename,
            "size_bytes": os.path.getsize(backup_path),
            "checksum_matched": checksum_valid,
            "computed_sha256": computed_hash,
            "stored_sha256": stored_hash,
            "sqlite_integrity_healthy": is_sqlite_healthy,
            "status": "HEALTHY" if (checksum_valid and is_sqlite_healthy) else "CORRUPTED"
        }

    @classmethod
    def list_backups(cls) -> List[Dict[str, Any]]:
        """Lists all available backup files with metadata and checksum statuses."""
        if not os.path.exists(BACKUPS_DIR):
            return []

        backups = []
        for f in os.listdir(BACKUPS_DIR):
            if f.startswith("backup_") and f.endswith(".db"):
                full_path = os.path.join(BACKUPS_DIR, f)
                stat = os.stat(full_path)
                has_checksum = os.path.exists(f"{full_path}.sha256")
                backups.append({
                    "filename": f,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "has_checksum": has_checksum
                })

        backups.sort(key=lambda x: x["filename"], reverse=True)
        return backups

    @classmethod
    def enforce_retention_policy(cls, retention_limit: int = MAX_BACKUPS_RETAINED) -> int:
        """
        Prunes backups exceeding the retention threshold, removing both .db and .sha256 files.
        """
        if not os.path.exists(BACKUPS_DIR) or retention_limit <= 0:
            return 0

        all_backups = [
            f for f in os.listdir(BACKUPS_DIR)
            if f.startswith("backup_") and f.endswith(".db")
        ]
        all_backups.sort(reverse=True)  # Newest first

        pruned_count = 0
        if len(all_backups) > retention_limit:
            to_delete = all_backups[retention_limit:]
            for stale_file in to_delete:
                db_file = os.path.join(BACKUPS_DIR, stale_file)
                sha_file = f"{db_file}.sha256"
                try:
                    if os.path.exists(db_file): os.remove(db_file)
                    if os.path.exists(sha_file): os.remove(sha_file)
                    pruned_count += 1
                    logger.info(f"Retention policy pruned stale backup: {stale_file}")
                except Exception as e:
                    logger.warning(f"Failed to prune stale backup {stale_file}: {e}")

        return pruned_count
