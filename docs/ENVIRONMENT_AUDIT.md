# EduManage 360 — Production Environment Variable Audit & Security Specification

## Overview
This specification audits every environment variable utilized by the EduManage 360 School Management System. It establishes rigorous classifications, sensitivity boundaries, and automated fail-secure validation criteria to prevent insecure operational deployment.

---

## Variable Classification Scheme
Each variable belongs to one or more of the following categories:
- **Required**: Critical setting mandatory for system operation in production. Missing values trigger an immediate fail-secure startup abort.
- **Optional**: Configuration with sensible, safe defaults that can be omitted or tuned as needed.
- **Development-Only**: Variables intended strictly for local development or test runners; prohibited in production.
- **Secret**: Confidential cryptographic keys, database passwords, API tokens, or webhook secrets. Must never be logged, exposed via APIs, or committed to version control.
- **Deprecated**: Legacy configuration flags slated for retirement.

---

## Master Environment Variable Matrix

| Variable | Classifications | Default Value | Description / Production Rules |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | **Required** | `development` | Operational mode (`development`, `test`, `staging`, `production`). In production, triggers strict fail-secure auditing. |
| `SECRET_KEY` | **Required**, **Secret** | *None* | 256-bit cryptographically secure key used to sign JWTs and session tokens. Must be >= 32 characters and cannot be a default or placeholder. |
| `DATABASE_URL` | **Required** | `sqlite:///./school.db` | Target database URI. Must be a PostgreSQL connection (`postgresql://`) in production. SQLite is rejected in production. |
| `CORS_ORIGINS` | **Optional** | *None* | Comma-separated list of allowed frontend origins. Wildcard `*` is strictly forbidden in production. Defaults to verified HTTPS origins if omitted. |
| `LOG_LEVEL` | **Optional** | `INFO` | Application log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). `INFO` recommended for production. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | **Optional** | `1440` (24h) | Lifespan of JWT authentication tokens. |
| `INITIAL_SUPERADMIN_PASSWORD` | **Optional**, **Secret** | *None* | Initial bootstrap password for the root super-admin account on first run. Must be rotated after setup. |
| `DB_POOL_SIZE` | **Optional** | `20` | PostgreSQL connection pool size for SQLAlchemy. |
| `DB_MAX_OVERFLOW` | **Optional** | `10` | Maximum overflow connections allowed during traffic surges. |
| `DB_POOL_TIMEOUT` | **Optional** | `30` | Connection pool checkout timeout (seconds). |
| `DB_POOL_RECYCLE` | **Optional** | `1800` | Connection recycling period (seconds) to prevent stale connections. |
| `MAX_BACKUPS_RETAINED` | **Optional** | `14` | Rolling retention count for automated snapshot backups. |
| `AUTH_RATE_LIMIT_MAX_REQUESTS`| **Optional** | `5` | Maximum failed authentication attempts allowed within the rate limit window. |
| `AUTH_RATE_LIMIT_WINDOW_SECONDS`| **Optional** | `60` | Duration (seconds) of the rate limit sliding window. |
| `PAYSTACK_ENABLED` | **Optional** | `false` | Enables Paystack Ghana payment processing (`true`/`false`). |
| `PAYSTACK_SECRET_KEY` | **Optional**, **Secret** | *None* | Mandatory if `PAYSTACK_ENABLED=true`. Production requires a valid `sk_live_` key. |
| `PAYSTACK_PUBLIC_KEY` | **Optional** | *None* | Public key for frontend checkout widgets. |
| `HUBTEL_ENABLED` | **Optional** | `false` | Enables Hubtel Ghana SMS gateway (`true`/`false`). |
| `HUBTEL_CLIENT_ID` | **Optional** | *None* | Mandatory if `HUBTEL_ENABLED=true`. Hubtel API Client ID. |
| `HUBTEL_CLIENT_SECRET` | **Optional**, **Secret** | *None* | Mandatory if `HUBTEL_ENABLED=true`. Hubtel API Client Secret. |
| `MNOTIFY_API_KEY` | **Optional**, **Secret** | *None* | Alternative Ghana SMS gateway API key. |
| `CLOUDFLARE_TURNSTILE_SECRET_KEY` | **Optional**, **Secret** | *None* | Cloudflare Turnstile bot protection server secret key. |
| `DB_ALLOW_SQLITE_FALLBACK` | **Development-Only** | `false` | Allows fallback to SQLite if PostgreSQL fails. **Strictly rejected in production.** |
| `SKIP_DB_INIT` | **Development-Only** | `false` | Bypass database initialization in specific test fixtures. |
| `ENV` | **Deprecated** | *None* | Superseded by `ENVIRONMENT`. |
| `PG_DATABASE_URL` | **Deprecated** | *None* | Superseded by `DATABASE_URL`. |

---

## Automated Fail-Secure Startup Guard
The application invokes `validate_production_environment_or_exit()` during module startup. When `ENVIRONMENT=production`:
1. **SECRET_KEY Validation**: Verifies existence, minimum 32-character entropy, and absence of known insecure placeholders.
2. **DATABASE_URL Validation**: Confirms URI begins with `postgresql://` or `postgres://`. Any `sqlite://` URI aborts startup immediately.
3. **CORS Security**: Ensures `CORS_ORIGINS` does not contain wildcard `*`.
4. **Third-Party Integrations**: If payment or SMS gateways are enabled, their respective API secret keys must be present and valid.
5. **Fail-Secure Output**: Detailed diagnostic messages are emitted explaining the exact violation and remediation steps before raising a `RuntimeError` to prevent container boot.
