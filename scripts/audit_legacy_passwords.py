"""
scripts/audit_legacy_passwords.py

Offline CLI utility to audit user password hashes across the School Management System database.
Reports security posture (Bcrypt vs Legacy SHA-256) and safely remediates dormant legacy accounts
by arming `is_first_login = True` to mandate rotation upon authentication.

Usage:
    python scripts/audit_legacy_passwords.py                # View audit report
    python scripts/audit_legacy_passwords.py --remediate   # Flag legacy accounts for mandatory rotation
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

from backend.app.database import SessionLocal
from backend.app.services.auth import audit_password_hashes, remediate_legacy_sha256_accounts


def main():
    parser = argparse.ArgumentParser(description="Audit and remediate legacy SHA-256 password hashes.")
    parser.add_argument(
        "--remediate",
        action="store_true",
        help="Flag all legacy SHA-256 accounts for mandatory first-login password rotation."
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("\n========================================================")
        print("  EDUMANAGE 360 — PASSWORD HASH SECURITY AUDIT")
        print("========================================================\n")

        audit = audit_password_hashes(db)

        print(f"  Total Accounts Scanned : {audit['total_users']}")
        print(f"  Bcrypt-Secured ($2b$)  : {audit['bcrypt_secure']}")
        print(f"  Legacy SHA-256 Hashes  : {audit['legacy_sha256']}")
        print(f"  Unrecognized Formats   : {audit['unrecognized']}")
        print("--------------------------------------------------------")

        if audit['legacy_sha256'] == 0:
            print("  [OK] Zero legacy SHA-256 hashes detected! Database is fully secured.\n")
        else:
            print(f"  [WARN] Found {audit['legacy_sha256']} accounts with legacy SHA-256 hashes:")
            for acc in audit['legacy_accounts']:
                print(f"    - User: {acc['username']} (ID: {acc['user_id']}, School: {acc['school_id']}, FirstLogin: {acc['is_first_login']})")
            print()

            if args.remediate:
                print("  Applying remediation: arming mandatory rotation (is_first_login=True)...")
                res = remediate_legacy_sha256_accounts(db)
                print(f"  [SUCCESS] Remediated {res['remediated_count']} accounts: {', '.join(res['remediated_users']) or 'None'}\n")
            else:
                print("  To flag these accounts for mandatory rotation on next login, run:")
                print("    python scripts/audit_legacy_passwords.py --remediate\n")

    finally:
        db.close()


if __name__ == "__main__":
    main()
