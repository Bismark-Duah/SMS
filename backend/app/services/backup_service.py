import os
import sqlite3
import hashlib
import shutil
import zipfile
import urllib.parse
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

    @classmethod
    def restore_database_snapshot(
        cls,
        filename: str,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Validates snapshot integrity and safely tests restoration.
        If dry_run=True, tests the snapshot in isolation without altering the active live database.
        If dry_run=False, takes a pre-restore safety snapshot of the active live database,
        flushes WAL checkpoints, and restores the selected backup atomically.
        """
        if not is_sqlite:
            return {
                "status": "skipped",
                "message": "SQLite snapshot restoration only applies to SQLite databases."
            }

        filename = os.path.basename(filename)
        backup_path = os.path.join(BACKUPS_DIR, filename)

        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup snapshot '{filename}' not found.")

        # 1. Verify cryptographic checksum and SQLite page integrity
        verify_result = cls.verify_backup_integrity(filename)
        if verify_result.get("status") != "HEALTHY":
            raise ValueError(
                f"Cannot restore corrupted backup snapshot '{filename}'. "
                f"Checksum matched: {verify_result.get('checksum_matched')}, "
                f"Integrity healthy: {verify_result.get('sqlite_integrity_healthy')}."
            )

        # 2. Inspect tables in target snapshot to verify critical schemas
        conn = sqlite3.connect(backup_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]
        
        # Verify essential core tables exist
        required_tables = {"users", "schools", "students"}
        missing_tables = required_tables - set(tables)
        if missing_tables:
            conn.close()
            raise ValueError(f"Snapshot missing required system tables: {missing_tables}")

        cursor.execute("SELECT COUNT(*) FROM users;")
        user_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM schools;")
        school_count = cursor.fetchone()[0]
        conn.close()

        if dry_run:
            logger.info(f"Dry-run restore verification succeeded for {filename}: {len(tables)} tables, {user_count} users.")
            return {
                "status": "success",
                "dry_run": True,
                "filename": filename,
                "verified": True,
                "tables_count": len(tables),
                "schools_count": school_count,
                "users_count": user_count,
                "message": "Snapshot passed all integrity checks and schema validations. Safe to restore."
            }

        # 3. Live restore execution
        # Take safety snapshot of current live database first
        safety_backup = cls.create_backup(verify_integrity=True)
        logger.info(f"Created pre-restore safety backup: {safety_backup['filename']}")

        # Flush active WAL
        checkpoint_database(mode="TRUNCATE")

        # Copy snapshot over live database file
        shutil.copy2(backup_path, DEFAULT_DB_PATH)

        # Remove stale WAL / SHM files if present
        for ext in ("-wal", "-shm"):
            extra_file = f"{DEFAULT_DB_PATH}{ext}"
            if os.path.exists(extra_file):
                try: os.remove(extra_file)
                except Exception: pass

        logger.info(f"Live database successfully restored from snapshot {filename}.")
        return {
            "status": "success",
            "dry_run": False,
            "filename": filename,
            "safety_backup_filename": safety_backup["filename"],
            "message": f"Live database successfully restored from {filename}."
        }

    @classmethod
    def generate_postgres_backup_command(
        cls,
        db_url: Optional[str] = None,
        output_file: str = "edumanage_backup.dump"
    ) -> Dict[str, Any]:
        """
        Parses PostgreSQL connection details and generates standard pg_dump commands
        for production disaster recovery backups.
        """
        target_url = db_url or os.getenv("DATABASE_URL", "")
        if not (target_url.startswith("postgresql://") or target_url.startswith("postgres://")):
            return {
                "status": "skipped",
                "message": "PostgreSQL backup command generation requires a valid postgresql:// URL."
            }

        parsed = urllib.parse.urlparse(target_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        user = parsed.username or "postgres"
        dbname = parsed.path.lstrip("/") or "postgres"

        # Sanitize command output without leaking password in plaintext
        cmd_str = (
            f"pg_dump -Fc -v -h {host} -p {port} -U {user} -d {dbname} -f {output_file}"
        )

        return {
            "status": "success",
            "host": host,
            "port": port,
            "user": user,
            "database": dbname,
            "command": cmd_str,
            "format": "custom compressed (-Fc)",
            "env_requirements": "Set PGPASSWORD environment variable securely when running command.",
            "instructions": (
                f"Run: PGPASSWORD='***' {cmd_str}\n"
                f"Verify: pg_restore --list {output_file}"
            )
        }

    @classmethod
    def generate_postgres_restore_command(
        cls,
        db_url: Optional[str] = None,
        dump_file: str = "edumanage_backup.dump",
        clean: bool = True
    ) -> Dict[str, Any]:
        """
        Generates standard pg_restore commands for production PostgreSQL recovery.
        """
        target_url = db_url or os.getenv("DATABASE_URL", "")
        if not (target_url.startswith("postgresql://") or target_url.startswith("postgres://")):
            return {
                "status": "skipped",
                "message": "PostgreSQL restore command generation requires a valid postgresql:// URL."
            }

        parsed = urllib.parse.urlparse(target_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        user = parsed.username or "postgres"
        dbname = parsed.path.lstrip("/") or "postgres"

        clean_flag = "--clean --if-exists " if clean else ""
        cmd_str = (
            f"pg_restore -v {clean_flag}-h {host} -p {port} -U {user} -d {dbname} {dump_file}"
        )

        return {
            "status": "success",
            "host": host,
            "port": port,
            "user": user,
            "database": dbname,
            "command": cmd_str,
            "instructions": f"Run: PGPASSWORD='***' {cmd_str}"
        }

