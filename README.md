# EduManage 360

<div align="center">

![EduManage 360 Institutional Crest](frontend/assets/logo_primary.png)

**Unified Multi-School Administration & Academic Management Platform**

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Database Architecture](https://img.shields.io/badge/Database-PostgreSQL%20%7C%20SQLite%20WAL-4169E1?logo=postgresql&logoColor=white)](DATABASE_MIGRATIONS.md)
[![Deployment](https://img.shields.io/badge/Deployment-Render-46E3B7?logo=render&logoColor=white)](https://sms-nald.onrender.com)
[![Testing Suite](https://img.shields.io/badge/Tests-81%20Suites%20Passing-brightgreen?logo=pytest&logoColor=white)](TESTING.md)
[![Security Policy](https://img.shields.io/badge/Security-Policy%20Enforced-red?logo=shield)](SECURITY.md)
[![Curriculum Standards](https://img.shields.io/badge/Curriculum-NaCCA%20%2F%20WAEC%20Aligned-gold)](#2-academic-management--dual-curricula)

</div>

---

## Overview

**EduManage 360** is an institutional School Management System (SMS) and academic administration platform engineered specifically for Basic Schools, Senior High Schools (SHS), Technical/Vocational Institutes (TVET), and Multi-Campus Educational Networks across Ghana and the broader West African region.

### The Problem It Solves
Educational institutions in the region often face severe operational challenges:
* **Connectivity Barriers**: Critical campus administrative operations (attendance, grading, admissions, cashier payments) often halt when regional internet connectivity fails.
* **Complex Regional Curricula**: Off-the-shelf international systems lack native support for Ghanaian educational structures, including the National Council for Curriculum and Assessment (**NaCCA**) Common Core Programme and the West African Examinations Council (**WAEC**) SHS grading standards.
* **Disjointed Multi-School Governance**: Educational directorates, dioceses, and school groups struggle to aggregate metrics across remote campuses while maintaining strict data isolation between individual schools.

### Architectural Solution
EduManage 360 addresses these challenges through:
1. **Offline/Local Campus Operation**: EduManage 360 supports offline/local operation for supported workflows (roll call, gradebook entry, report card generation, cashier receipting, and gate security) using its local database mode over a campus Wi-Fi or Local Area Network (LAN). Workflows that depend on third-party internet services (such as external SMS alerts) queue until connectivity is restored.
2. **Cloud Scalability**: Centralized multi-campus governance hosted on managed PostgreSQL, allowing regional synchronization and consolidated analytics.
3. **Deep Curricular Alignment**: Automated grading engines tailored to NaCCA and WAEC standards, Computerized School Selection & Placement System (**CSSPS**) intake processing, automated constraint-satisfaction timetabling, and biometric/QR gate security.

---

## Live System

EduManage 360 is actively deployed and running in a live production environment:

* **Production URL**: [https://sms-nald.onrender.com](https://sms-nald.onrender.com)
* **API Documentation**: [https://sms-nald.onrender.com/docs](https://sms-nald.onrender.com/docs) (OpenAPI / Swagger UI)
* **System Health Check**: [https://sms-nald.onrender.com/api/system/health](https://sms-nald.onrender.com/api/system/health)

> [!NOTE]
> Public demo credentials are intentionally not published in this repository to safeguard running instances. Access to live administrative environments is restricted to authorized personnel. To evaluate the platform locally, follow the [Local Development](#local-development) guide.

---

## Key Capabilities

EduManage 360 organizes school operations into integrated, security-scoped operational modules:

### 1. School Administration & Governance
* **Multi-Tenant Administration**: Centralized Super Admin portal to onboard, configure, inspect, and manage multiple independent schools from a single installation.
* **Institutional Branding**: Per-school configuration of crests, color themes, grading boundaries, operational terms, and semester schedules.
* **Staff Directory & Workload**: Comprehensive staff profiling, subject/class allocation, role assignments, and departmental oversight.

### 2. Academic Management & Dual Curricula
* **NaCCA Standards-Based Grading**: Native support for Basic School and Junior High School (JHS) 7–9 Continuous Assessment (Class Assessment Tasks, Project Work, End-of-Term Examinations).
* **WAEC SHS Grading Scheme**: Rigorous 30% Continuous Assessment (Class Tests, Assignments, Mid-Term) + 70% Terminal Exam calculations generating standard WAEC letter grades (A1 to F9) and GPA metrics.
* **Bulk Gradebook Entry**: Real-time tabular gradebook input with out-of-range value validation, automatic score tallying, and class ranking algorithms.
* **Institutional Report Cards**: One-click generation of PDF terminal reports, transcripts, and broadsheets with dynamic headmaster signature blocks.

### 3. Admissions & CSSPS Intake
* **CSSPS Bulk Ingestion**: Import national Computerized School Selection & Placement System CSV/Excel exports with automated data cleansing and deduplication.
* **Auto-Enrollment Pipeline**: Automated conversion of placed applicants into active student records, assigning index numbers, programme streams, and class sections.
* **House & Track Assignment**: Intelligent distribution of boarding students into residential houses and academic tracks (Green, Gold, Single Track).

### 4. Boarding House & QR Gate Security
* **Exeat & Leave Authorization**: Multi-stage exeat approval workflows (Housemaster -> Senior Housemaster) with digital passes.
* **QR Security Verification**: Security gate scanning interface to validate exeat passes, track student departures, and flag overdue returns in real time.
* **Residential Capacity Management**: Real-time room and bed allocation monitoring across male and female boarding facilities.

### 5. Automated Timetabling Engine
* **Constraint Satisfaction Solver (CSP)**: Heuristic scheduling engine that builds conflict-free school timetables.
* **Hard Constraint Enforcement**: Prevents teacher double-booking, room capacity violations, and overlapping class periods.
* **Soft Constraint Optimization**: Balances teacher daily workloads, distributes difficult subjects into morning blocks, and reserves departmental planning periods.

### 6. Financial Management & Ledgers
* **Configurable Fee Schedules**: Define mandatory, optional, boarding, and day fees broken down by class, programme, or term.
* **Student Ledger Accounting**: Real-time balance tracking, credit/debit transaction history, and automated invoice generation.
* **Hybrid Payment Recording**: Supports cash desk transactions, bank deposits, and mobile money payment reconciliations.
* **Defaulter Tracking & Statements**: Filterable debt recovery lists and printable financial clearance statements for exam admittance.

### 7. Attendance & Truancy Tracking
* **Daily Class Roll Call**: Quick-toggle interface for homeroom teachers (Present, Absent, Late, Excused).
* **Subject-Level Attendance**: Track period attendance to identify subject-specific truancy.
* **Automated Guardian Alerts**: Immediate trigger of alert dispatches when unexcused absences are logged.

### 8. Omnichannel Communication
* **Regional SMS Gateway**: Native integration with Hubtel SMS API for instant parent notifications (terminal results, fee balances, urgent notices).
* **Direct WhatsApp Messaging**: Web-based WhatsApp template dispatching for paperless digital report card links.
* **Internal Notice Board**: Role-scoped campus announcements broadcasted directly to student, teacher, or parent portal dashboards.

### 9. Forensic Audit Trail & Data Tools
* **Immutable Audit Logging**: Automatic recording of user, IP address, timestamp, action type, and exact state diffs for financial, grading, and authentication events.
* **Data Export & Archiving**: Comprehensive data exports to Excel, CSV, and encrypted JSON formats with formula-injection defenses.

---

## User Roles & Access Control

EduManage 360 implements a **26-Role Role-Based Access Control (RBAC)** architecture enforcing the principle of least privilege:

```
                                  ┌─────────────────────────┐
                                  │       Super Admin       │
                                  │ (Cross-Tenant Platform) │
                                  └────────────┬────────────┘
                                               │
             ┌─────────────────────────────────┴─────────────────────────────────┐
             ▼                                                                   ▼
┌─────────────────────────┐                                         ┌─────────────────────────┐
│     School Admin A      │                                         │     School Admin B      │
│ (Tenant-Isolated Scope) │                                         │ (Tenant-Isolated Scope) │
└────────────┬────────────┘                                         └────────────┬────────────┘
             │                                                                   │
    ┌────────┴────────┬─────────────────┬────────────────┐                      ...
    ▼                 ▼                 ▼                ▼
Headmaster      Accountant           Teacher          Student / Parent
```

### Role Matrix & Permissions Overview

| Role Group | Roles | Can Manage | Access Restrictions |
|---|---|---|---|
| **Platform Governance** | `superadmin` | All schools, platform settings, global database maintenance, cross-tenant auditing | Cannot modify individual school academic grades without administrative audit logging |
| **School Leadership** | `school_admin`, `headmaster`, `assistant_headmaster` | School configuration, staff accounts, term dates, fee policies, final report approvals | Restricted strictly to own school (`school_id`); cannot access other school records |
| **Academic Oversight** | `academic_head`, `senior_housemaster`, `hod` | Department curricula, class allocations, timetable approvals, exeat workflows | Cannot alter fee structures or perform cash reconciliations |
| **Teaching Faculty** | `teacher`, `form_master`, `subject_master` | Class roll call, gradebook entry for assigned subjects, terminal comments | Cannot modify grades outside assigned subjects or terms; read-only access to student fees |
| **Financial Operations** | `accountant`, `cashier`, `bursar` | Fee schedule setup, payment entry, receipt issuance, financial ledger reporting | No access to edit student grades, curriculum, or exeat passes |
| **Campus Support** | `librarian`, `nurse`, `security_officer`, `storekeeper` | Library loans, infirmary visits, exeat gate validation, asset inventory | Read-only directory access; strictly scoped operational views |
| **End Users** | `student`, `parent`, `alumni` | Personal academic reports, fee balance statements, attendance records, school notices | Strict self-service isolation; zero write access to school records |

### Multi-Tenant Isolation Mechanism
* Every query involving school-scoped data is parameterized with `WHERE school_id = :school_id`.
* The `current_user` dependency extracts the authenticated user's `school_id` directly from cryptographically signed JWT claims.
* School administrators cannot read or write data belonging to another institution.
* The `X-School-Id` tenant override header is reserved exclusively for authenticated `superadmin` sessions to switch administrative contexts safely.

---

## System Architecture

EduManage 360 uses a decoupled, layered service architecture designed to operate seamlessly across both cloud hosting and offline local campus servers.

```
                  ┌─────────────────────────────────────────────────┐
                  │           Client Layer (Browser / PWA)          │
                  │  Modern Vanilla JS, HTML5, CSS3, Responsive UI  │
                  └────────────────────────┬────────────────────────┘
                                           │ HTTP / HTTPS (REST API)
                                           ▼
                  ┌─────────────────────────────────────────────────┐
                  │            API Gateway & Security Layer         │
                  │   FastAPI Routing, CORS, SlowAPI Rate Limiting  │
                  │       JWT Nonce Revocation, Auth Dependency     │
                  └────────────────────────┬────────────────────────┘
                                           │
             ┌─────────────────────────────┴─────────────────────────────┐
             ▼                                                           ▼
┌───────────────────────────────┐                       ┌───────────────────────────────┐
│     Core Business Engines     │                       │    External Gateway Adapters  │
│  - Grading & Assessment       │                       │  - Hubtel SMS Client          │
│  - CSP Timetable Solver       │                       │  - WhatsApp Deep-Link Engine  │
│  - CSSPS Intake Processor     │                       │  - Cloud Storage / File Upload│
│  - Forensic Audit Logging     │                       │  - Online Backup Engine       │
└────────────┬──────────────────┘                       └───────────────────────────────┘
             │
             ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                         Data Access Layer (SQLAlchemy 2.0 ORM)                        │
│                     Connection Pooling & Multi-Tenant Query Scoping                   │
└──────────────────────────┬─────────────────────────────────┬──────────────────────────┘
                           │                                 │
                           ▼                                 ▼
           ┌───────────────────────────────┐ ┌───────────────────────────────┐
           │   Production Database Tier    │ │    Offline Local Campus Tier  │
           │      PostgreSQL (Render)      │ │       SQLite 3 (WAL Mode)     │
           │ Connection Pooling, SSL, Pk/Fk│ │  30s Busy Timeout, Zero-Conf │
           └───────────────────────────────┘ └───────────────────────────────┘
```

---

## Technology Stack

| Layer | Component | Technology / Library | Architectural Role |
|---|---|---|---|
| **Backend** | Framework | Python 3.10+, FastAPI | High-performance asynchronous REST API framework |
| | Data Validation | Pydantic v2 | Strict schema validation and serialization |
| | ORM & DB Access | SQLAlchemy 2.0 | Unified object-relational mapping for SQLite and PostgreSQL |
| | Password Security | Passlib (`bcrypt`) | 12-round salted Bcrypt password hashing |
| | Token Management | PyJWT | Cryptographically signed JSON Web Tokens with single-use nonces |
| | Rate Limiting | SlowAPI (Limits) | Tiered IP and route-based request throttling |
| | Migrations | Alembic | Version-controlled schema migrations (`backend/alembic/versions/`) |
| **Frontend** | Architecture | Vanilla HTML5 / CSS3 / ES6+ | Zero-build, offline-cached Single Page Application / PWA |
| | Typography | Inter, Google Fonts (Local Fallbacks) | Institutional typography optimized for legibility |
| | PDF Generation | Native HTML-to-Print / CSS Paged Media | Deterministic layout rendering for reports and transcripts |
| | QR & Barcodes | HTML5-QRCode, JsBarcode | Real-time camera scanner for exeat verification and ID cards |
| **Data Tier** | Production Database | PostgreSQL 15+ | Multi-worker connection pooling, row locking, cloud resilience |
| | Local / Dev Database| SQLite 3 | WAL mode, 30-second busy timeout, zero external setup for campus LAN |
| | Backups | Custom Cryptographic Engine | Hot online backup API, SHA-256 verification, AES-256 encryption |
| **Deployment** | Cloud PaaS | Render (`render.yaml`) | Managed web service and managed PostgreSQL (`edumanage-db`) |
| | Offline LAN | Windows Batch Launcher (`Start_EduManage360.bat`) | Automated 1-click venv setup, DB migration, and LAN server launch |
| **Testing** | Test Framework | Pytest, pytest-asyncio, HTTPX | Automated test runner with `--security`, `--tenant`, `--database` suites |

---

## Security Architecture

Security controls are embedded directly into the application framework rather than treated as an afterthought:

* **Authentication & Credential Hashing**: Passwords are protected using salted Bcrypt (12 work factor rounds). A legacy migration mechanism automatically upgrades older SHA-256 hashes to Bcrypt upon successful login.
* **Cryptographic Temporary Credentials**: Default accounts provisioned during deployment or administrative reset use `secrets.token_urlsafe()` to guarantee high entropy.
* **Token Nonce Revocation**: All password reset tokens and session overrides include a unique cryptographic nonce tracked in the `revoked_tokens` database table. Replay attacks and reuse of expired/consumed tokens are strictly prevented.
* **Tenant Isolation & Anti-Spoofing**: All incoming requests are validated against the authenticated tenant. Tenant override headers (`X-School-Id`) are strictly restricted to verified `superadmin` sessions; any spoofing attempt returns `403 Forbidden`.
* **CORS Hardening**: Strict origin whitelisting configured via `CORS_ORIGINS`. Wildcards (`*`) are disallowed when credentials/cookies are active.
* **CSV Formula Injection Mitigation (CWE-1236)**: Student broadsheets, gradebooks, and financial ledgers automatically sanitize fields starting with `=`, `+`, `-`, or `@` to neutralize spreadsheet execution vulnerabilities.
* **Credential Masking**: Health checks, logging adapters, and migration tools automatically scrub database credentials and API secrets from output streams.
* **Encrypted Backups**: The database backup utility incorporates AES-256-GCM envelope encryption (`cryptography.fernet`) and generates SHA-256 checksums for tamper detection.

For full security specifications and disclosure procedures, consult [`SECURITY.md`](SECURITY.md).

---

## Database Architecture

EduManage 360 uses a dual-engine architecture:
* **Cloud Environments**: PostgreSQL provides multi-worker concurrency, connection pooling, and SSL encryption.
* **Campus LAN Environments**: SQLite 3 operates in **WAL (Write-Ahead Logging)** mode with `busy_timeout = 30000ms`, allowing concurrent reads during write operations without locking the database.

### Database Migrations
All schema updates are version-controlled using Alembic. Migration scripts reside in `backend/alembic/versions/`.

```bash
# Apply pending schema migrations
alembic upgrade head

# Generate a new migration revision
alembic revision --autogenerate -m "describe_schema_change"

# Roll back the most recent migration
alembic downgrade -1
```

For complete migration instructions and schema history, consult [`DATABASE_MIGRATIONS.md`](DATABASE_MIGRATIONS.md).

---

## API Architecture

The backend exposes a modular REST API structured across 33 domain-specific route controllers under `/api`:

| Route Prefix | Domain | Major Capabilities |
|---|---|---|
| `/api/auth` | Authentication | Login, logout, token refresh, password resets, session status |
| `/api/schools` | Institutions | School profile, branding, academic terms, grading scales |
| `/api/students` | Student Body | Student enrollment, profiling, class allocation, emergency contacts |
| `/api/grades` | Assessment | Score entry, continuous assessments, terminal calculations, rankings |
| `/api/report-cards` | Transcripts | Terminal report card generation, broadsheets, PDF formatting |
| `/api/fees` | Financials | Fee schedules, student invoices, payment recording, ledger balances |
| `/api/timetables` | Scheduling | CSP timetable generation, class periods, teacher workload balancing |
| `/api/admissions` | Admissions | Applicant registration, placement processing, admission letters |
| `/api/cssps` | CSSPS Intake | Placement spreadsheet import, automated parsing, student ingestion |
| `/api/exeat` | Boarding Security | Exeat approvals, security gate QR verification, status audits |
| `/api/audit` | Forensics | Immutable event logging, security logs, change tracking |
| `/api/backups` | Data Continuity | Online hot backup creation, encryption, integrity verification |
| `/api/system` | Maintenance | Sanitized health checks, system diagnostics, version telemetry |

The interactive OpenAPI documentation is automatically available on running instances at `/docs` (Swagger UI) and `/redoc` (ReDoc).

---

## Local Development

Follow these steps to set up and run EduManage 360 in a local development environment.

### Prerequisites
* Python 3.10 or higher
* Git
* SQLite 3 (included with Python) or PostgreSQL 15+ (optional for cloud testing)

### Step-by-Step Setup

```bash
# 1. Clone the repository
git clone https://github.com/Bismark-Duah/SMS.git
cd SMS

# 2. Create and activate a Python virtual environment
python -m venv .venv

# On Windows (Command Prompt):
.venv\Scripts\activate

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# On Linux/macOS:
source .venv/bin/activate

# 3. Install core dependencies
pip install -r backend/requirements.txt

# 4. Configure environment variables
# Copy the example environment file
cp .env.example .env

# Edit .env to set your application secrets:
# SECRET_KEY=your-secure-random-secret-key-min-32-chars
# DATABASE_URL=sqlite:///./school.db
# INITIAL_SUPERADMIN_PASSWORD=your-secure-initial-password

# 5. Run database migrations to initialize the schema
alembic upgrade head

# 6. Start the development server
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Once started, access the application in your browser:
* **Frontend Application**: `http://localhost:8000`
* **Interactive API Docs**: `http://localhost:8000/docs`

---

## Offline Campus LAN Deployment

For schools deploying on a local campus without internet connectivity:

1. **Host PC / Local Server**: Connect a central campus PC or laptop to the school's local Wi-Fi router or switch via Ethernet.
2. **One-Click Windows Launcher**: Run [`Start_EduManage360.bat`](Start_EduManage360.bat) from the project root. The script automatically:
   - Validates the Python runtime
   - Provisions the virtual environment and dependencies
   - Applies pending Alembic migrations
   - Launches the Uvicorn server bound to `0.0.0.0:8000`
   - Detects the local LAN IPv4 address (e.g., `192.168.1.100`)
3. **Staff Access**: Teachers and administrative staff can connect to the school Wi-Fi and open `http://192.168.1.100:8000` from any laptop, tablet, or smartphone.

---

## Production Deployment

EduManage 360 is configured for declarative deployment on **Render** via [`render.yaml`](render.yaml).

```
Render Cloud
┌─────────────────────────────────────────────────────────────┐
│  Web Service (edumanage360-api)                             │
│  - Runtime: Python 3.10+                                    │
│  - Build: pip install -r backend/requirements.txt           │
│  - Pre-Deploy: alembic upgrade head                         │
│  - Start: uvicorn backend.app.main:app --host 0.0.0.0       │
└──────────────────────────────┬──────────────────────────────┘
                               │ Internal Encrypted Connection
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  Managed PostgreSQL Database (edumanage-db)                 │
│  - Database: edumanage_production                           │
│  - Automated backups & SSL transport                        │
└─────────────────────────────────────────────────────────────┘
```

### Essential Production Environment Variables

| Variable | Description | Example / Requirement |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/edumanage_production` |
| `SECRET_KEY` | Cryptographic secret for JWT signing | 64-character random hexadecimal string |
| `ENVIRONMENT` | Deployment environment identifier | `production` |
| `CORS_ORIGINS` | Comma-separated list of allowed origins | `https://sms-nald.onrender.com` |
| `INITIAL_SUPERADMIN_PASSWORD` | Initial platform administrator password | High-entropy random password (used on first initialization) |
| `HUBTEL_CLIENT_ID` | Hubtel SMS API Client ID | Optional: required only for SMS dispatching |
| `HUBTEL_CLIENT_SECRET`| Hubtel SMS API Client Secret | Optional: required only for SMS dispatching |

> [!IMPORTANT]
> **Administrator Credential Provisioning**: Production administrator credentials are intentionally not published in this repository. Initial administrator setup must be completed through the secure deployment/configuration process, and temporary credentials must be rotated before normal operation.

---

## Testing & Verification

The repository includes a comprehensive automated test suite spanning security, multi-tenancy, database operations, and academic business logic.

### Unified Test Runner
Use the provided [`run_tests.py`](run_tests.py) test runner to execute targeted test suites:

```bash
# Run multi-tenant isolation tests
python run_tests.py --tenant

# Run security, authentication, and vulnerability tests
python run_tests.py --security

# Run database, migration, and connection pooling tests
python run_tests.py --database

# Run the complete test suite
python run_tests.py --all
```

For complete test architecture details and test authoring standards, consult [`TESTING.md`](TESTING.md).

---

## Backup & Disaster Recovery

EduManage 360 features a dedicated cryptographic backup and restoration engine:

* **Hot Online Snapshots**: Uses SQLite's online backup API to take live point-in-time database snapshots without locking active user sessions.
* **Integrity Hashing**: Every backup generates a companion SHA-256 hash (`.sha256`) to verify data integrity before restoration.
* **At-Rest Encryption**: Backups can be encrypted at rest using AES-256 envelope encryption.
* **Restoration Verification**: Built-in restoration routines validate table structures and schema versions before committing a restored database.

For step-by-step backup, verification, and disaster recovery procedures, consult [`docs/BACKUP_AND_RECOVERY.md`](docs/BACKUP_AND_RECOVERY.md).

---

## Performance & Scalability

Operational performance varies depending on the chosen deployment tier:

### Campus LAN Tier (SQLite WAL Mode)
* **Operational Environment**: Local PC or campus server on a standard Wi-Fi router or switch.
* **Concurrency Profile**: Designed for local campus staff devices performing simultaneous roll calls, grading, and cashier entries over a local Wi-Fi router.
* **Operational Characteristics**: SQLite WAL mode allows non-blocking concurrent reads while write transactions queue safely under a configurable 30-second busy timeout.
* **Resource Footprint**: Minimal memory footprint (< 150 MB RAM), running comfortably on standard school computer hardware.

### Cloud Tier (PostgreSQL on Render)
* **Production Deployment**: Hosted on Render with managed PostgreSQL.
* **Concurrency Profile**: Multi-worker Uvicorn processes with connection pooling handle multi-school administrative workloads across campuses.
* **Performance Profile**: Designed to scale through PostgreSQL-backed deployment and connection pooling, and can be evaluated under larger institutional workloads through dedicated load testing.

> [!NOTE]
> Capacity and throughput depend on the hosting environment, hardware specifications, and network infrastructure. Concurrency limits should be evaluated under specific institutional workloads through dedicated load testing.

---

## Repository Structure

```
SMS/
├── backend/
│   ├── alembic/              # Alembic database migration revisions
│   │   └── versions/         # Version-controlled schema migration scripts
│   ├── app/
│   │   ├── core/             # Application configuration, security, and hashing
│   │   ├── db/               # Database session management and engine initialization
│   │   ├── models/           # SQLAlchemy ORM database models
│   │   ├── routes/           # 33 domain-specific FastAPI route controllers
│   │   ├── schemas/          # Pydantic request/response validation schemas
│   │   ├── services/         # Business logic (timetables, grading, SMS, backups)
│   │   └── main.py           # FastAPI application entry point and middleware
│   └── requirements.txt      # Python backend package dependencies
├── frontend/
│   ├── assets/               # Institutional branding, crests, and static icons
│   ├── css/                  # Application stylesheets and responsive layouts
│   ├── js/                   # Frontend controller modules and API clients
│   └── *.html                # Role-specific HTML views and dashboard interfaces
├── docs/                     # Architectural, security, and operational documentation
├── scripts/                  # Administrative, migration, and maintenance utilities
├── tests/                    # 81 automated test suites (security, tenant, DB, API)
├── render.yaml               # Render Cloud deployment blueprint
├── run_tests.py              # Unified CLI test runner
├── Start_EduManage360.bat    # Windows 1-click offline campus LAN launcher
├── SECURITY.md               # Institutional security policy and reporting protocols
├── TESTING.md                # Automated testing documentation and guide
├── DATABASE_MIGRATIONS.md    # Alembic database migration reference
└── README.md                 # Primary system documentation
```

---

## Documentation Index

Comprehensive technical documentation is maintained within the repository:

* **[Security Policy](SECURITY.md)** — Vulnerability reporting protocols and security controls.
* **[Testing Architecture](TESTING.md)** — Test runner flags, suite categorization, and CI verification.
* **[Database Migrations](DATABASE_MIGRATIONS.md)** — Alembic schema evolution and rollback procedures.
* **[Backup & Recovery](docs/BACKUP_AND_RECOVERY.md)** — Cryptographic backup procedures and disaster recovery.
* **[Production Engineering Audit](docs/FINAL_PRODUCTION_ENGINEERING_AUDIT.md)** — Comprehensive architecture, security, and verification audit.
* **[Guided School Onboarding](docs/GUIDED_SCHOOL_ONBOARDING.md)** — Institutional setup and academic term configuration.
* **[Render PostgreSQL Setup](docs/RENDER_POSTGRES_SETUP.md)** — Cloud database provisioning and connection configuration.
* **[Audit & Forensic Visibility](docs/AUDIT_AND_FORENSIC_VISIBILITY.md)** — Forensic event tracking specifications.
* **[Frontend Security Audit](docs/FRONTEND_SECURITY_AUDIT.md)** — Client-side protection and sanitization review.
* **[CORS Hardening Specification](docs/CORS_HARDENING.md)** — Cross-origin resource sharing policy specification.

---

## Known Limitations

Transparency is essential for institutional software:

1. **Cloud Synchronization**: While offline campus deployments function independently and migration scripts exist (`scripts/migrate_to_postgres.py`, `scripts/pull_cloud_database.py`), an automated, background bi-directional delta synchronization daemon is currently an architectural roadmap capability.
2. **External SMS Delivery**: The SMS alert module requires an active internet connection to communicate with the Hubtel SMS gateway. When deployed strictly offline, SMS dispatches queue until internet connectivity is restored.
3. **Formal Load Testing**: While SQLite WAL mode and PostgreSQL connection pooling have been validated in operational environments, formal synthetic load benchmarks establishing absolute concurrency limits remain ongoing.

---

## Roadmap

* [ ] **Automated Delta Sync Daemon**: Continuous background synchronization between offline local campus servers and the cloud PostgreSQL database with conflict resolution.
* [ ] **Cross-Platform Desktop Packaging**: Electron / PyInstaller bundled desktop binaries for turnkey Windows and macOS installation.
* [ ] **Mobile Parent & Student Portal**: Lightweight, offline-capable Progressive Web Application (PWA) optimized for low-bandwidth mobile devices.
* [ ] **Biometric Attendance Hardware Integration**: Direct USB/network fingerprint terminal integration for staff roll call and student gate logging.

---

## License

This software is licensed under a **Proprietary Institutional License**. All rights reserved.

Unauthorized copying, modification, distribution, or commercial use of this software without explicit authorization from the project maintainers is strictly prohibited. For licensing inquiries, contact the institutional development team.
