"""
EduManage 360 — Disaster Recovery & Backup Management CLI
Task 22: Offline SQLite snapshot management, integrity verification,
and production PostgreSQL disaster recovery command generator.
"""

import sys
import os
import json
import argparse

# Ensure parent path resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from backend.app.database import DEFAULT_DB_PATH, is_sqlite, is_postgres, mask_database_url
from backend.app.services.backup_service import BackupService


def cmd_status(args):
    """Reports status of live database and stored backups."""
    print("=" * 60)
    print(" EDUMANAGE 360 — DATABASE DISASTER RECOVERY STATUS")
    print("=" * 60)
    print(f"Database Engine : {'SQLite (Local WAL)' if is_sqlite else 'PostgreSQL'}")
    print(f"Database Target : {DEFAULT_DB_PATH if is_sqlite else mask_database_url(os.getenv('DATABASE_URL', ''))}")

    if is_sqlite:
        if os.path.exists(DEFAULT_DB_PATH):
            size_mb = round(os.path.getsize(DEFAULT_DB_PATH) / (1024 * 1024), 2)
            print(f"Live DB Size    : {size_mb} MB")
        else:
            print("Live DB Size    : NOT FOUND")

        backups = BackupService.list_backups()
        print(f"Stored Backups  : {len(backups)}")
        if backups:
            latest = backups[0]
            print(f"Latest Backup   : {latest['filename']} ({latest['created_at']})")
    print("=" * 60)


def cmd_backup(args):
    """Executes a hot backup of the database."""
    print("[*] Initiating hot backup...")
    try:
        res = BackupService.create_backup(verify_integrity=True)
        print(f"[+] Backup succeeded: {res.get('filename')}")
        print(f"    Size: {res.get('size_bytes')} bytes")
        print(f"    SHA-256: {res.get('sha256')}")
        print(f"    Integrity Check: {'PASSED' if res.get('integrity_verified') else 'FAILED'}")
    except Exception as e:
        print(f"[-] Backup failed: {e}")
        sys.exit(1)


def cmd_verify(args):
    """Verifies integrity and executes dry-run restore validation."""
    backups = BackupService.list_backups()
    if not backups:
        print("[-] No backups found to verify.")
        return

    filename = args.filename or backups[0]["filename"]
    print(f"[*] Verifying backup snapshot: {filename}")
    try:
        res = BackupService.restore_database_snapshot(filename, dry_run=True)
        print(f"[+] Integrity & Dry-Run Restore: SUCCESS")
        print(f"    Tables verified: {res.get('tables_count')}")
        print(f"    Schools count  : {res.get('schools_count')}")
        print(f"    Users count    : {res.get('users_count')}")
        print(f"    Status: {res.get('message')}")
    except Exception as e:
        print(f"[-] Verification failed: {e}")
        sys.exit(1)


def cmd_postgres(args):
    """Generates production PostgreSQL disaster recovery commands."""
    db_url = os.getenv("DATABASE_URL", "")
    print("=" * 60)
    print(" POSTGRESQL PRODUCTION RECOVERY COMMANDS")
    print("=" * 60)
    dump_info = BackupService.generate_postgres_backup_command(db_url=db_url)
    restore_info = BackupService.generate_postgres_restore_command(db_url=db_url)

    print("\n1. BACKUP (pg_dump custom compressed format):")
    print(f"   Command: {dump_info.get('command')}")
    print(f"   Note   : {dump_info.get('env_requirements')}")

    print("\n2. RESTORE (pg_restore with clean replace):")
    print(f"   Command: {restore_info.get('command')}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="EduManage 360 Disaster Recovery Utility")
    subparsers = parser.add_subparsers(dest="action", help="Action to execute")

    subparsers.add_parser("status", help="Display backup and database status")
    subparsers.add_parser("backup", help="Create an immediate hot backup")
    
    verify_parser = subparsers.add_parser("verify", help="Verify backup integrity and test dry-run restore")
    verify_parser.add_argument("--filename", "-f", help="Specific backup file to verify")

    subparsers.add_parser("postgres-commands", help="Generate production PostgreSQL pg_dump/restore commands")

    args = parser.parse_args()
    if not args.action or args.action == "status":
        cmd_status(args)
    elif args.action == "backup":
        cmd_backup(args)
    elif args.action == "verify":
        cmd_verify(args)
    elif args.action == "postgres-commands":
        cmd_postgres(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
