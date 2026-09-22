# Testing Guide — EduManage 360

This guide documents the testing architecture, runner options, test categories, and offline verification workflows for the **EduManage 360** School Management System.

---

## 1. Quickstart & Test Commands

The repository includes a unified test runner, [`run_tests.py`](file:///run_tests.py), which automates test discovery, environment isolation, and reporting:

```bash
# 1. Run the core security hardening test suite (8 suites, 39+ tests)
python run_tests.py --security

# 2. Run multi-tenant data isolation and boundary verification
python run_tests.py --tenant

# 3. Run fast unit and configuration tests
python run_tests.py --fast

# 4. Run all 80+ test suites across the entire repository
python run_tests.py --all

# 5. Run a specific test file
python run_tests.py tests/test_backup_security_hardening.py

# 6. Run with detailed verbose output
python run_tests.py --security -v
```

Alternatively, standard `unittest` and `pytest` commands remain fully supported:

```bash
# Using standard Python unittest
python -m unittest tests/test_system_telemetry_hardening.py

# Using pytest
pytest tests/test_system_telemetry_hardening.py
```

---

## 2. Core Testing Principles

1. **Offline Test Execution**:
   - All tests execute strictly against local SQLite or in-memory fixtures.
   - Zero tests require internet access, third-party APIs, or external payment gateways.
2. **Database Isolation & Cleanliness**:
   - Tests execute in `ENVIRONMENT=testing` mode.
   - Active development databases (`school.db`) are protected from test mutations.
3. **Fail-Secure Security Assertions**:
   - Security suites explicitly test adversarial inputs: privilege escalations, cross-school IDOR attacks, SQL injection attempts, expired or replayed tokens, and parameter tampering.
4. **Deterministic & Idempotent**:
   - Tests clean up temporary files, rollback sessions, and run predictably on any operating system (Windows, Linux, macOS).

---

## 3. Test Suites Taxonomy

| Category | Primary Test Suites | Focus & Verification |
|---|---|---|
| **Security Hardening** | `test_system_telemetry_hardening.py`<br>`test_predictable_passwords_elimination.py`<br>`test_sha256_migration_hardening.py`<br>`test_password_reset_token_hardening.py`<br>`test_cloud_db_credential_hardening.py`<br>`test_multi_tenant_isolation_hardening.py`<br>`test_backup_security_hardening.py`<br>`test_render_config_and_cors_hardening.py` | Information leak prevention, credential safety, SHA-256 migration, token nonces & TTLs, credential scrubbing, tenant isolation, AES-256 backup encryption, and production CORS lockdown. |
| **Multi-Tenancy** | `test_multi_tenant_isolation_hardening.py`<br>`test_tenant_isolation_comprehensive.py`<br>`test_tenant_isolation_idor.py`<br>`test_tenant_user_authorization.py` | Cross-school BOLA/IDOR prevention, school-id spoofing protection, and scoped role access across multiple schools. |
| **Database & Migrations** | `test_alembic_migrations.py`<br>`test_database_constraints_integrity.py`<br>`test_database_query_and_performance.py`<br>`test_sqlite_wal_and_concurrency.py` | Schema integrity, WAL mode checkpoints, foreign keys, transaction rollback, and migration execution. |
| **Academic & SBA** | `test_grading_edge_cases_and_sba.py`<br>`test_promotion_rules_and_transcripts.py`<br>`test_timetable_csp_engine.py` | WASSCE/BECE grading formulas, class broadsheets, constraint satisfaction timetabling, and transcripts. |
| **Finance & Fees** | `test_fee_financial_audit.py`<br>`test_fees_subaccount_split.py`<br>`test_payment_orchestrator.py` | Fee balances, subaccount revenue allocations, and receipt generation. |
| **Deployment & Infra** | `test_render_config_and_cors_hardening.py`<br>`test_devops_and_infrastructure.py`<br>`test_reproducible_test_environment.py` | Managed PostgreSQL configuration, zero-data-loss verification, automated migrations on deploy, and dependency validation. |

---

## 4. Dependencies & Environment Setup

To prepare a sterile testing environment:

```bash
# Install core and test dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt

# Verify environment imports
python -m unittest tests/test_reproducible_test_environment.py
```
