# Security Policy — EduManage 360

EduManage 360 is an institutional school administration platform designed for multi-school and single-campus deployments across Ghana and West Africa. Information security, student data privacy, and multi-tenant isolation are core architectural priorities.

---

## 1. Supported Versions

We release security patches and updates for the active release line. Deployments should always run the latest patch release on the `main` branch.

| Version | Supported | Status |
|---|---|---|
| `4.2.x` | :white_check_mark: Yes | Current Active Release |
| `< 4.2.0` | :x: No | Deprecated / End of Life |

---

## 2. Reporting a Vulnerability

We appreciate responsible disclosure from security researchers, system administrators, and institutional partners.

If you identify a security vulnerability or multi-tenant boundary flaw in EduManage 360:

1. **Do not disclose publicly**: Do not create public GitHub issues or forum discussions for unpatched security vulnerabilities.
2. **Contact Security Team**: Report the vulnerability directly to the project maintainers via email or private GitHub Security Advisories:
   - Primary Security Contact: `security@edumanage360.org` (or open a private security advisory at [github.com/Bismark-Duah/SMS/security/advisories](https://github.com/Bismark-Duah/SMS/security/advisories)).
3. **Include Technical Details**:
   - Component / route affected (e.g., `/api/grades`, `/api/auth`)
   - Type of vulnerability (e.g., IDOR, multi-tenant isolation leak, session fixation, privilege escalation)
   - Step-by-step reproduction instructions or a minimal proof-of-concept
   - Impact assessment
4. **Response Timeline**:
   - Initial triage confirmation: within **48 hours**
   - Remediation and patch deployment: prioritized based on severity (Critical/High within **7 calendar days**)
   - Public release notes will credit responsible disclosures unless anonymity is requested.

---

## 3. Implemented Security Controls

EduManage 360 incorporates defense-in-depth security controls across its application, database, and operational tiers:

### Authentication & Password Security
* **Bcrypt Password Hashing**: Passwords are saved with salted Bcrypt (12 work factor rounds). A transparent upgrade hook migrates legacy SHA-256 hashes upon successful authentication.
* **Cryptographically Strong Temporary Passwords**: When accounts or resets are provisioned, credentials are generated using `secrets.token_urlsafe()` with mandatory entropy requirements (uppercase, lowercase, digits, special symbols).
* **Single-Use Reset Tokens & Nonce Revocation**: Password reset tokens contain unique cryptographic nonces stored in the `revoked_tokens` database table. Once used or expired, tokens are immediately and irreversibly revoked.

### Role-Based Access Control & Multi-Tenancy
* **26 Granular Institutional Roles**: Enforces strict separation of duties (e.g., `superadmin`, `school_admin`, `headmaster`, `accountant`, `teacher`, `student`, `parent`).
* **Multi-Tenant Boundary Isolation**: All school data tables enforce a foreign key `school_id`. Requests validate that the active session's school ID matches the requested resource. Super Admin operations require explicit multi-school context or cross-tenant elevation.
* **Anti-Spoofing Headers**: Tenant override headers (`X-School-Id`) are strictly restricted to authenticated `superadmin` sessions; any unauthenticated or unauthorized tenant tampering is rejected with HTTP 403 Forbidden.

### API & Transport Protection
* **Tiered Rate Limiting**: Powered by SlowAPI (e.g., 5 requests/minute on `/api/auth/login` to prevent brute force; 30 requests/minute on general endpoints).
* **Strict CORS Whitelisting**: Production configurations require explicit origin declarations. Wildcard origins (`*`) are disallowed when credentialed cookies/headers are supported.
* **Security Headers**: Production endpoints emit defensive HTTP response headers including `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy`.

### Cryptography & Data Integrity
* **AES-256-GCM Backup Encryption**: Database backups can be encrypted at rest using envelope encryption (`cryptography.fernet` / AES-256) with integrity checks.
* **SHA-256 Integrity Verification**: Every backup archive generates a companion `.sha256` checksum to detect tampering or storage corruption prior to restoration.
* **URI Credential Masking**: Database connection strings logged by operational tools or health checks automatically mask username and password credentials.
* **CSV Formula Injection Mitigation (CWE-1236)**: Student and financial CSV/Excel export routines sanitize cell inputs prefixed with `=`, `+`, `-`, or `@` to prevent remote spreadsheet execution.

---

## 4. Security Documentation & Audits

For detailed forensic analysis, audit checklists, and architectural matrices, consult:

* [Frontend Security Audit](docs/FRONTEND_SECURITY_AUDIT.md) — XSS defense, CSP, and client-side sanitization.
* [CORS Hardening Guide](docs/CORS_HARDENING.md) — Cross-origin resource sharing policy specification.
* [Audit & Forensic Visibility](docs/AUDIT_AND_FORENSIC_VISIBILITY.md) — Audit logging architecture and event schemas.
* [Backup & Recovery Specification](docs/BACKUP_AND_RECOVERY.md) — Cryptographic backup and recovery verification.
