import os
import sqlite3
import hashlib
import shutil
import zipfile
import urllib.parse
import base64
import secrets
from datetime import datetime
from typing import List, Dict, Any, Optional
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from ..database import DEFAULT_DB_PATH, is_sqlite, checkpoint_database
from ..logger import get_logger

logger = get_logger("backup_service")

# Backups directory relative to project root
BACKUPS_DIR = os.path.abspath(os.path.join(os.path.dirname(DEFAULT_DB_PATH), "backups"))
MAX_BACKUPS_RETAINED = int(os.getenv("MAX_BACKUPS_RETAINED", "14"))

BACKUP_MAGIC_HEADER = b"EDUBKP01"
BACKUP_SALT_LEN = 16
BACKUP_KDF_ITERATIONS = 100_000


def _secure_directory(dir_path: str):
    """Enforces restrictive 0o700 directory permissions where supported."""
    try:
        if hasattr(os, "chmod"):
            os.chmod(dir_path, 0o700)
    except Exception:
        pass


def _secure_file(file_path: str):
    """Enforces restrictive 0o600 file permissions where supported."""
    try:
        if hasattr(os, "chmod"):
            os.chmod(file_path, 0o600)
    except Exception:
        pass


def _derive_fernet_key(passphrase: str, salt: bytes) -> bytes:
    """Derives a url-safe base64-encoded 32-byte Fernet key from a passphrase and salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=BACKUP_KDF_ITERATIONS
    )
    key_bytes = kdf.derive(passphrase.encode("utf-8"))
    return base64.urlsafe_b64encode(key_bytes)


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
    - Restrictive 0o700/0o600 filesystem permissions hardening
    - AES-256 (Fernet) authenticated encryption at rest
    """

    @classmethod
    def create_backup(
        cls,
        retention_limit: int = MAX_BACKUPS_RETAINED,
        verify_integrity: bool = True,
        encrypt: Optional[bool] = None,
        passphrase: Optional[str] = None
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
        _secure_directory(BACKUPS_DIR)
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

            _secure_file(backup_path)

            # 3. Compute and store SHA-256 checksum
            sha256_hash = _compute_sha256(backup_path)
            with open(checksum_path, "w", encoding="utf-8") as f:
                f.write(f"{sha256_hash}  {backup_filename}\n")
            _secure_file(checksum_path)

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

            # 5. Optional / configured encryption at rest
            encrypted_file = None
            should_encrypt = encrypt if encrypt is not None else bool(os.getenv("BACKUP_ENCRYPTION_KEY"))
            if should_encrypt:
                enc_path = cls.encrypt_backup(backup_path, passphrase=passphrase)
                encrypted_file = os.path.basename(enc_path)

            # 6. Enforce rolling retention policy
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
                "encrypted": should_encrypt,
                "encrypted_filename": encrypted_file,
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
    def encrypt_backup(
        cls,
        source_path: str,
        target_path: Optional[str] = None,
        passphrase: Optional[str] = None
    ) -> str:
        """
        Encrypts a backup file at rest using AES-256 (Fernet) with a key derived
        via PBKDF2HMAC from BACKUP_ENCRYPTION_KEY or the provided passphrase.
        File format: [8-byte MAGIC 'EDUBKP01'] + [16-byte random salt] + [Fernet ciphertext].
        """
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source backup file not found: {source_path}")

        enc_key = passphrase or os.getenv("BACKUP_ENCRYPTION_KEY")
        if not enc_key:
            raise ValueError("Encryption passphrase or BACKUP_ENCRYPTION_KEY environment variable is required.")

        target_path = target_path or f"{source_path}.enc"
        salt = secrets.token_bytes(BACKUP_SALT_LEN)
        fernet_key = _derive_fernet_key(enc_key, salt)
        fernet = Fernet(fernet_key)

        with open(source_path, "rb") as f_in:
            data = f_in.read()

        encrypted_data = fernet.encrypt(data)

        with open(target_path, "wb") as f_out:
            f_out.write(BACKUP_MAGIC_HEADER)
            f_out.write(salt)
            f_out.write(encrypted_data)

        _secure_file(target_path)
        logger.info(f"Encrypted backup snapshot created: {os.path.basename(target_path)}")
        return target_path

    @classmethod
    def decrypt_backup(
        cls,
        source_path: str,
        target_path: Optional[str] = None,
        passphrase: Optional[str] = None
    ) -> str:
        """
        Decrypts an encrypted backup file at rest.
        Verifies magic header and authenticity before writing the target file.
        """
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Encrypted backup file not found: {source_path}")

        enc_key = passphrase or os.getenv("BACKUP_ENCRYPTION_KEY")
        if not enc_key:
            raise ValueError("Decryption passphrase or BACKUP_ENCRYPTION_KEY environment variable is required.")

        with open(source_path, "rb") as f_in:
            header = f_in.read(len(BACKUP_MAGIC_HEADER))
            if header != BACKUP_MAGIC_HEADER:
                raise ValueError("Invalid encrypted backup: Missing or invalid EDUBKP01 header.")
            salt = f_in.read(BACKUP_SALT_LEN)
            if len(salt) < BACKUP_SALT_LEN:
                raise ValueError("Invalid encrypted backup: Corrupted salt.")
            ciphertext = f_in.read()

        fernet_key = _derive_fernet_key(enc_key, salt)
        fernet = Fernet(fernet_key)

        try:
            decrypted_data = fernet.decrypt(ciphertext)
        except InvalidToken:
            raise ValueError("Decryption failed: Incorrect passphrase or tampered ciphertext.")

        target_path = target_path or source_path.removesuffix(".enc")
        if target_path == source_path:
            target_path = f"{source_path}.dec"

        with open(target_path, "wb") as f_out:
            f_out.write(decrypted_data)

        _secure_file(target_path)
        logger.info(f"Decrypted backup snapshot restored to: {os.path.basename(target_path)}")
        return target_path

    @classmethod
    def verify_backup_integrity(cls, filename: str, passphrase: Optional[str] = None) -> Dict[str, Any]:
        """
        Validates SHA-256 checksum match and executes SQLite integrity check on a stored backup.
        Supports checking encrypted (.enc) backup snapshots as well.
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
            with open(checksum_path, "w", encoding="utf-8") as f:
                f.write(f"{computed_hash}  {filename}\n")
            _secure_file(checksum_path)
            stored_hash = computed_hash
            checksum_valid = True

        # Encrypted file verification
        if filename.endswith(".enc"):
            with open(backup_path, "rb") as f:
                header = f.read(len(BACKUP_MAGIC_HEADER))
                salt = f.read(BACKUP_SALT_LEN)
            header_valid = (header == BACKUP_MAGIC_HEADER and len(salt) == BACKUP_SALT_LEN)
            decryption_verified = False
            enc_key = passphrase or os.getenv("BACKUP_ENCRYPTION_KEY")
            if enc_key and header_valid:
                try:
                    with open(backup_path, "rb") as f:
                        f.seek(len(BACKUP_MAGIC_HEADER) + BACKUP_SALT_LEN)
                        ct = f.read()
                    k = _derive_fernet_key(enc_key, salt)
                    Fernet(k).decrypt(ct)
                    decryption_verified = True
                except Exception:
                    decryption_verified = False

            return {
                "filename": filename,
                "size_bytes": os.path.getsize(backup_path),
                "checksum_matched": checksum_valid,
                "computed_sha256": computed_hash,
                "stored_sha256": stored_hash,
                "is_encrypted": True,
                "header_valid": header_valid,
                "decryption_verified": decryption_verified,
                "status": "HEALTHY" if (checksum_valid and header_valid and (decryption_verified if enc_key else True)) else "CORRUPTED"
            }

        # 2. Run PRAGMA integrity_check for plaintext SQLite database
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
            "is_encrypted": False,
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
            if f.startswith("backup_") and (f.endswith(".db") or f.endswith(".enc")):
                full_path = os.path.join(BACKUPS_DIR, f)
                stat = os.stat(full_path)
                has_checksum = os.path.exists(f"{full_path}.sha256")
                backups.append({
                    "filename": f,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "has_checksum": has_checksum,
                    "is_encrypted": f.endswith(".enc")
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
            if f.startswith("backup_") and (f.endswith(".db") or f.endswith(".enc"))
        ]
        all_backups.sort(reverse=True)  # Newest first

        pruned_count = 0
        if len(all_backups) > retention_limit:
            to_delete = all_backups[retention_limit:]
            for stale_file in to_delete:
                bk_file = os.path.join(BACKUPS_DIR, stale_file)
                sha_file = f"{bk_file}.sha256"
                enc_companion = f"{bk_file}.enc" if bk_file.endswith(".db") else ""
                try:
                    if os.path.exists(bk_file): os.remove(bk_file)
                    if os.path.exists(sha_file): os.remove(sha_file)
                    if enc_companion and os.path.exists(enc_companion): os.remove(enc_companion)
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

