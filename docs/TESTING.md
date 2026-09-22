# EduManage 360 — Test Environment & Quality Engineering Guide

This guide describes how to reproduce the complete test environment, execute unit and integration test suites, and maintain zero regression standards across all 68+ verification modules.

---

## 1. Prerequisites & Environment Setup

EduManage 360 requires **Python 3.10+** (verified through Python 3.14) and supports **offline-first local operation** using local SQLite WAL or cloud PostgreSQL.

### 1.1 Create & Activate Virtual Environment
```bash
# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 1.2 Install Test & Runtime Dependencies
```bash
pip install --upgrade pip
pip install -r requirements-test.txt
```

---

## 2. Test Execution

### 2.1 Unified Full-System Verification (Recommended)
EduManage 360 includes a unified test orchestrator that validates all security, academic, database, and financial suites sequentially:

```bash
python verify_all.py
```
This script automatically:
1. Bootstraps clean in-memory or WAL test database tables.
2. Runs all 68+ test suites across `tests/`, `backend/tests/`, and `scripts/`.
3. Verifies zero regressions before exit code 0.

### 2.2 Running Individual Test Suites
You can run any test module independently using Python's standard `unittest` or `pytest`:

```bash
# Using standard unittest
python -m unittest tests/test_standardized_api_error_handling.py
python -m unittest tests/test_promotion_rules_and_transcripts.py
python -m unittest tests/test_grading_edge_cases_and_sba.py

# Using pytest
pytest tests/test_standardized_api_error_handling.py
pytest tests/ -k "tenant"
```

---

## 3. Test Categories & Architecture

| Category | Directories | Key Focus |
|---|---|---|
| **Security & Auth** | `tests/test_*security*.py`, `tests/test_tenant*.py` | Cross-tenant isolation, IDOR/BOLA prevention, password hashing, JWT expiry, rate limiting |
| **Academic & Grading** | `tests/test_grading*.py`, `tests/test_promotion*.py` | SBA continuous assessment, WAEC boundaries, promotion idempotency, transcript scoping |
| **Database & Migration** | `tests/test_alembic*.py`, `tests/test_database*.py` | SQLite WAL concurrency, Alembic schema migrations, composite indexes, cascades |
| **API & Error Handling** | `tests/test_standardized_api_error_handling.py` | Sanitized 4xx/5xx responses, zero SQL/stack trace leakage, correlation `X-Request-ID` |
| **Offline & Sync** | `tests/test_sync*.py`, `tests/verify_enterprise_sync*.py` | Offline PWA outbox, delta syncing, conflict resolution |

---

## 4. Failure Categorization Guide

When inspecting test failures during development:
1. **Application Defect**: The system logic produces an incorrect result or violates an invariant (e.g. leaking School B data to School A). Fix the backend code.
2. **Test Defect**: The test expects obsolete schema attributes or asserts incorrect assumptions. Update test assertions while preserving security contracts.
3. **Environment / Dependency Issue**: Missing package (e.g. `httpx`, `xhtml2pdf`) or unsupported Python version. Check `requirements-test.txt`.
4. **Database / Setup Issue**: SQLite busy lock, missing table, or uncommitted transaction in `setUp()`. Use in-memory SQLite fixtures (`sqlite:///:memory:`) or WAL mode.
