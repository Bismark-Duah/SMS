# Institutional Forensic Audit & Visibility Specification

## 1. Overview & Architectural Philosophy
The School Management System maintains an immutable, forensic audit trail of all governance, security, financial, and academic events. In offline-first school deployments, administrators (Headmasters, Bursars, Academic Heads) require full operational visibility into staff and student actions, while guaranteeing multi-tenant confidentiality and PII security.

This document details the forensic architecture implemented in **Prompt 28** across `backend/app/services/audit_service.py`, `backend/app/routes/audit.py`, and `frontend/audit-logs.html`.

---

## 2. Core Security & Forensic Controls

### 2.1 Dual-Tier Visibility & Multi-Tenant Boundary
1. **School Tenant Scope (`/api/audit/logs`, `/api/audit/school-feed`):**
   - Accessible only by authorized institutional staff (`admin`, `headmaster`, `headmistress`, `principal`, `assistant_headmaster_*`, `bursar`, `accountant`).
   - Results are strictly scoped to the authenticated caller's `school_id`. Attempting to query an external school ID returns `403 Forbidden`.
   - **Confidentiality Rule:** All Master Platform / Super Admin actions are automatically excluded (`is_super_admin_action == False`, `actor_role != 'super_admin'`, `actor_username != 'superadmin'`). School leaders never observe platform infrastructure operations.
2. **Super Admin Master Stream (`/api/super-admin/audit-stream`):**
   - Accessible strictly by platform Super Administrators.
   - Provides unified visibility across all registered schools with optional per-school filtering.

### 2.2 Sensitive Data Masking
Before any audit event is committed to storage:
- `mask_sensitive_data(details)` recursively inspects dictionaries, lists, strings, and JSON objects.
- Secret fields (`password`, `token`, `secret`, `api_key`, `access_token`, `refresh_token`, `authorization`, `pin`, `cvv`) are replaced with `"[REDACTED]"`.
- Bearer tokens and header patterns (`Bearer ...`, `eyJ...`) are scrubbed via regex.
- Cleartext credentials are never persisted in the audit ledger.

### 2.3 Comprehensive Forensic Search & Filtering
The audit feed endpoints support extensive query parameters:
| Parameter | Type | Description |
| :--- | :--- | :--- |
| `action` | `string` | Filters by exact action code (`LOGIN_SUCCESS`, `FEE_PAYMENT`, `STUDENT_CREATE`, etc.) |
| `entity_type` | `string` | Filters by target model (`Student`, `User`, `Fee`, `Score`, `System`, `Settings`) |
| `actor_username` | `string` | Filters by the username who triggered the event |
| `start_date` | `string` | ISO (`2026-09-01T00:00:00`) or Date (`2026-09-01`) lower bound |
| `end_date` | `string` | ISO or Date upper bound (defaults to 23:59:59 of that date) |
| `search` | `string` | Substring search across `details`, `action`, `username`, `entity_type`, and `ip_address` |
| `page` / `limit` | `int` | Offset-based pagination with total count and page metadata |

### 2.4 Forensic CSV Export
- Endpoint: `GET /api/audit/export`
- Exports up to 10,000 matching records formatted in standard RFC 4180 CSV.
- **Formula Injection Defense (CWE-1236):** All cells starting with `=`, `+`, `-`, `@`, `\t`, or `\r` are neutralized with `'`.
- **Filename Sanitization:** Content-Disposition uses sanitized timestamped filenames (`audit_logs_YYYYMMDD_HHMMSS.csv`).

### 2.5 Operational UI (`frontend/audit-logs.html`)
- Dedicated administrative page providing:
  - Interactive filter bar with instant query execution.
  - Color-coded action badges (`success`, `warning`, `danger`, `info`).
  - Device and client IP display (`Desktop • Chrome`, `192.168.1.50`).
  - Formatted JSON details inspection modal.
  - One-click forensic CSV download.
  - Accessible layout compliant with WCAG 2.1 AA (`skip-to-main`, semantic headers, full keyboard navigation).
