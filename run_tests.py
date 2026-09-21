#!/usr/bin/env python3
"""
run_tests.py — Enterprise Unified Test Runner & Sterile Test Orchestrator
EduManage 360 School Management System

Usage:
  python run_tests.py                 # Runs core security & stability test suites
  python run_tests.py --security      # Runs all 8 core security hardening suites
  python run_tests.py --tenant        # Runs multi-tenant isolation suites
  python run_tests.py --fast          # Runs fast unit checks
  python run_tests.py --all           # Discovers and runs all 80+ test suites
  python run_tests.py tests/test_x.py # Runs specific test file(s)

Guarantees:
  1. Sterile execution: sets ENVIRONMENT=testing and prevents live database pollution.
  2. 100% offline-first: no external network calls required.
  3. Clean reporting: timing benchmarks, failure summaries, and standard exit codes.
"""

import os
import sys
import time
import glob
import argparse
import unittest
from typing import List, Tuple

# Ensure project root and backend are on PYTHONPATH
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
backend_path = os.path.join(PROJECT_ROOT, "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Enforce sterile test environment
os.environ["ENVIRONMENT"] = "testing"
os.environ.setdefault("ALEMBIC_DISABLE_CONSOLE_LOGGING", "1")

# Predefined curated test suites
SECURITY_SUITES = [
    "tests/test_system_telemetry_hardening.py",
    "tests/test_predictable_passwords_elimination.py",
    "tests/test_sha256_migration_hardening.py",
    "tests/test_password_reset_token_hardening.py",
    "tests/test_cloud_db_credential_hardening.py",
    "tests/test_multi_tenant_isolation_hardening.py",
    "tests/test_backup_security_hardening.py",
    "tests/test_render_config_and_cors_hardening.py",
]

TENANT_SUITES = [
    "tests/test_multi_tenant_isolation_hardening.py",
    "tests/test_tenant_isolation_comprehensive.py",
    "tests/test_tenant_isolation_idor.py",
    "tests/test_tenant_user_authorization.py",
    "tests/test_assignments_super_admin_tenant_scoping.py",
]

FAST_SUITES = [
    "tests/test_render_config_and_cors_hardening.py",
    "tests/test_cloud_db_credential_hardening.py",
    "tests/test_reproducible_test_environment.py",
    "tests/test_password_reset_token_hardening.py",
    "tests/test_system_telemetry_hardening.py",
]

DATABASE_SUITES = [
    "tests/test_alembic_migrations.py",
    "tests/test_database_constraints_integrity.py",
    "tests/test_database_query_and_performance.py",
    "tests/test_sqlite_wal_and_concurrency.py",
]


def discover_all_tests() -> List[str]:
    """Discovers all test files matching tests/test_*.py."""
    pattern = os.path.join(PROJECT_ROOT, "tests", "test_*.py")
    files = glob.glob(pattern)
    rel_files = [os.path.relpath(f, PROJECT_ROOT).replace("\\", "/") for f in files]
    rel_files.sort()
    return rel_files


def run_test_files(test_files: List[str], verbosity: int = 1) -> Tuple[bool, int, int, int, float]:
    """
    Executes the specified test files using unittest TestLoader and TextTestRunner.
    Returns (success_bool, total_tests, failures_count, errors_count, elapsed_seconds).
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for file_rel in test_files:
        file_path = os.path.join(PROJECT_ROOT, file_rel)
        if not os.path.exists(file_path):
            print(f"Warning: Test file not found: {file_rel}")
            continue

        # Convert file path to module name
        rel_no_ext = os.path.splitext(file_rel)[0].replace("\\", "/").replace("/", ".")
        try:
            mod_suite = loader.loadTestsFromName(rel_no_ext)
            suite.addTests(mod_suite)
        except Exception as e:
            print(f"Error loading {rel_no_ext}: {e}")

    start_time = time.time()
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    elapsed = time.time() - start_time

    total_tests = result.testsRun
    failures_count = len(result.failures)
    errors_count = len(result.errors)
    success = result.wasSuccessful()

    return success, total_tests, failures_count, errors_count, elapsed


def main():
    parser = argparse.ArgumentParser(
        description="EduManage 360 Unified Test Runner & Sterile Test Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py --security     # Run all 8 security hardening suites
  python run_tests.py --tenant       # Run multi-tenant isolation suites
  python run_tests.py --all          # Discover and run all 80+ suites
  python run_tests.py tests/test_backup_security_hardening.py
        """
    )
    parser.add_argument("--security", action="store_true", help="Run core security hardening test suites")
    parser.add_argument("--tenant", action="store_true", help="Run multi-tenant isolation test suites")
    parser.add_argument("--database", action="store_true", help="Run database migrations and schema integrity suites")
    parser.add_argument("--fast", action="store_true", help="Run fast unit & configuration test suites")
    parser.add_argument("--all", action="store_true", help="Discover and execute all test suites in tests/")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed test progress")
    parser.add_argument("files", nargs="*", help="Specific test file paths to execute")

    args = parser.parse_args()

    # Determine which tests to run
    if args.files:
        test_files = args.files
        category = "Custom Selection"
    elif args.security:
        test_files = SECURITY_SUITES
        category = "Security Hardening"
    elif args.tenant:
        test_files = TENANT_SUITES
        category = "Multi-Tenant Isolation"
    elif args.database:
        test_files = DATABASE_SUITES
        category = "Database & Migration Integrity"
    elif args.fast:
        test_files = FAST_SUITES
        category = "Fast Unit Checks"
    elif args.all:
        test_files = discover_all_tests()
        category = f"All Discovered Suites ({len(test_files)} files)"
    else:
        # Default: run the security hardening suites as the baseline gate
        test_files = SECURITY_SUITES
        category = "Security Hardening (Default)"

    verbosity = 2 if args.verbose else 1

    print("=" * 70)
    print(f" EduManage 360 Test Orchestrator — {category}")
    print(f" Target suites: {len(test_files)} file(s)")
    print(f" Environment:   {os.environ.get('ENVIRONMENT', 'testing')}")
    print("=" * 70)

    success, total, failures, errors, elapsed = run_test_files(test_files, verbosity=verbosity)

    print("\n" + "=" * 70)
    print(" Execution Summary")
    print("=" * 70)
    print(f" Total Tests Run: {total}")
    print(f" Passed:          {total - failures - errors}")
    print(f" Failures:        {failures}")
    print(f" Errors:          {errors}")
    print(f" Duration:        {elapsed:.2f}s")
    status_str = "SUCCESS (ALL TESTS PASSED)" if success else "FAILED"
    print(f" Final Status:    {status_str}")
    print("=" * 70)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
