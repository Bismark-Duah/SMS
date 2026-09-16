# EduManage 360 — Production Observability, Structured Logging & Security Audit Specification

## Overview
EduManage 360 implements an enterprise observability stack designed for high-availability cloud deployments (Docker, Render, AWS, Kubernetes) while preserving complete offline-first capability and data privacy.

---

## 1. Structured JSON Logging Architecture
- **Centralized Format**: Every log record emitted to file (`logs/sms_app.log`) is formatted as a single-line structured JSON document by `StructuredJsonFormatter`.
- **Fields**:
  - `timestamp`: UTC ISO-8601 formatted timestamp.
  - `level`: Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
  - `logger`: Subsystem logger hierarchy (`edumanage`, `edumanage.access`, `edumanage.security`, `edumanage.audit`, `edumanage.startup`).
  - `message`: Scrubbed, human-readable log message.
  - `request_id`: Tracing correlation ID (sourced from `X-Request-ID` or randomly generated per request).
  - `client_ip`: Verified client IP (extracted via Cloudflare perimeter guard).
  - `method`, `path`, `status_code`, `duration_ms`: HTTP transaction metrics.
  - `school_id`: Multi-tenant boundary isolation identifier.
  - `exception`: Sanitized stack trace (scrubbed of connection strings and secrets).
- **Log Rotation**: Built-in `RotatingFileHandler` with 10 MB file bounds and 5 rolling generation archives.

---

## 2. Zero-Leakage Credential & PII Redaction
All log streams pass through `sanitize_log_text()` and `sanitize_dict_payload()`:
- **Passwords**: Any JSON key (`"password"`, `"admin_password"`, `"new_password"`) or URI query param is scrubbed to `***REDACTED***`.
- **JWTs & Session Tokens**: Bearer tokens (`Bearer eyJ...`) and JSON fields (`"access_token"`, `"token"`) are scrubbed to `***REDACTED_JWT***`.
- **API Secret Keys**: Paystack, Hubtel, and generic API keys (`sk_live_...`, `sk_test_...`, `pk_live_...`) are replaced with `***REDACTED_KEY***`.
- **Database Connection Strings**: PostgreSQL connection strings containing embedded credentials (`postgresql://user:secret@host:5432/db`) have their password segments masked to `postgresql://user:***REDACTED***@host:5432/db`.

---

## 3. Dedicated Security & Administrative Audit Streams
- **Security Events (`edumanage.security`)**:
  - Emitted via `log_security_event(event_type, severity, details, ...)`
  - Tracks: `LOGIN_FAILED`, `RATE_LIMIT_EXCEEDED`, `UNAUTHORIZED_ACCESS`, `IDOR_ATTEMPT`, `SUSPENDED_USER_LOGIN`, `PASSWORD_RESET_TRIGGERED`.
- **Admin Audit Trail (`edumanage.audit`)**:
  - Emitted via `log_admin_audit_event(action, target_type, target_id, actor_user_id, ...)`
  - Tracks high-privilege configuration and financial actions (`SCHOOL_CREATED`, `USER_SUSPENDED`, `FEES_VOIDED`, `STUDENT_DELETED`).

---

## 4. Health Checks & Database Connectivity Monitoring
- **Endpoints**:
  - `GET /health` / `GET /api/health` / `GET /api/system/health`:
    Returns HTTP 200 (or 503 if database down) with database telemetry, latency in milliseconds, and environment status.
  - `GET /api/system/telemetry`:
    Returns metrics, entity counts (schools, users, students), and storage engine metrics for Prometheus/Grafana scrapers.
- **Replication Monitoring**:
  - Primary nodes report connected standby replica count and WAL replication lag in bytes.
  - Standby nodes report replication lag in seconds (`lag_seconds`) and LSN markers.
- **Noise Reduction**: High-frequency orchestrator poll pings to `/health` are filtered from access logs unless an error (HTTP >= 400) occurs.
