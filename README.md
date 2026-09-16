# 🎓 EduManage 360 — Enterprise School Management System

<div align="center">

![EduManage 360 Institutional Crest](frontend/assets/logo_primary.png)

### 100% Offline-First Multi-School Institutional ERP & Academic Management Engine
*Engineered for Basic Schools (Creche to JHS 3), Senior High Schools (SHS / SHTS), and Technical / STEM Institutions.*

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=flat-square&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%200.110-009688.svg?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Database Architecture](https://img.shields.io/badge/Database-SQLite%20WAL%20%7C%20PostgreSQL-336791.svg?style=flat-square&logo=sqlite)](backend/app/database.py)
[![Offline-First PWA](https://img.shields.io/badge/Frontend-100%25%20Offline%20PWA-4f46e5.svg?style=flat-square)](frontend/sw.js)
[![Security Standards](https://img.shields.io/badge/Security-OWASP%20ASVS%20v4.0%20Hardened-10b981.svg?style=flat-square)](docs/SECURITY_DEFENSE_MATRIX.md)
[![Test Verification](https://img.shields.io/badge/Automated%20Tests-81%20Suites%20Passing-brightgreen.svg?style=flat-square)](verify_all.py)
[![Ghana Curriculum](https://img.shields.io/badge/Curriculum-NaCCA%20Basic%20%7C%20WAEC%20SHS-orange.svg?style=flat-square)](backend/app/services/grading.py)
[![License](https://img.shields.io/badge/License-Proprietary%20Enterprise-purple.svg?style=flat-square)]()

</div>

---

## 🌟 Executive Summary

**EduManage 360** is a production-grade, multi-tenant institutional enterprise resource planning (ERP) platform designed specifically for the African educational landscape. It natively incorporates Ghana Education Service (GES), National Council for Curriculum and Assessment (NaCCA), and West African Examinations Council (WAEC) standards.

### 🏛️ The 100% Offline-First Operational Guarantee
Schools in developing regions and remote districts frequently operate under intermittent or non-existent internet connectivity. **EduManage 360 is engineered to operate 100% offline indefinitely.**
- **Zero Mandatory External APIs:** Authentication, broadsheets, terminal report cards, PDF transcripts, fee billing, and barcode scanning execute completely locally on the school's local area network (LAN / Wi-Fi).
- **Embedded Database High-Concurrency Engine:** SQLite with Write-Ahead Logging (WAL) and 30-second busy timeout supports 30–80+ concurrent staff devices connected to a single school Wi-Fi router.
- **Seamless Cloud & Multi-Campus Migration:** Automatic zero-code database switching to enterprise **PostgreSQL** for multi-campus networks and cloud deployments.
- **Enterprise Offline PWA:** Full service-worker static asset caching (`frontend/sw.js`), ensuring browsers load all 35+ administrative views even when the local server is temporarily power-cycling.

---

## 📐 System Architecture

```
                       ┌─────────────────────────────────────────────────────────┐
                       │   Staff Devices (Laptops, Phones, Tablets on School LAN)│
                       │           100% Offline Progressive Web App (PWA)        │
                       └────────────────────────────┬────────────────────────────┘
                                                    │ HTTP / WebSocket (Port 8000)
                                                    ▼
                       ┌─────────────────────────────────────────────────────────┐
                       │          FastAPI High-Performance Async Gateway         │
                       │   • Security Headers (HSTS, CSP, X-Frame-Options)       │
                       │   • Sliding-Window Auth Rate Limiter & CORS Guard       │
                       │   • Zero-Trust Session & Multi-Device Forensic Monitor  │
                       └────────────────────────────┬────────────────────────────┘
                                                    │
                               ┌────────────────────┴────────────────────┐
                               ▼                                         ▼
            ┌──────────────────────────────────────┐  ┌──────────────────────────────────────┐
            │       Local Deployment Engine        │  │       Enterprise Cloud Engine        │
            │           SQLite (WAL Mode)          │  │              PostgreSQL              │
            │  • Simultaneous Multi-Reader Concur. │  │  • Multi-Campus Connection Pool     │
            │  • Immediate Sequential Write Lock   │  │  • Read-Replicas & SSL Encryption    │
            │  • Auto-Checkpointing & 30s Timeout  │  │  • Centralized Ministry Aggregation  │
            └──────────────────────────────────────┘  └──────────────────────────────────────┘
                               │                                         ▲
                               └─────────── [Sync Engine] ───────────────┘
                                   Bi-Directional Conflict Resolution
```

---

## 🏛️ Comprehensive Institutional Modules

```
                                    ┌───────────────────────────────────────┐
                                    │       EduManage 360 Core Engine       │
                                    └───────────────────┬───────────────────┘
               ┌────────────────────────┬───────────────┴───────────────┬────────────────────────┐
               ▼                        ▼                               ▼                        ▼
       [Academic & Exams]      [Admissions & Boarding]         [Finance & Bursary]      [Security & Identity]
       • NaCCA & GES Curriculum • CSSPS Batch CSV Intake        • Multi-category Bills   • 26 Granular RBAC Roles
       • 30/70 & 50/50 SBA      • House/Dorm Auto-Allocator     • Student Ledgers        • Zero-Trust Session Guard
       • Broadsheets & Matrices • QR Gate Pass Exeats           • Instant Receipts       • Offline Self-Service Reset
       • Batch PDF Report Cards • Parent Auto-Linking           • Paystack MoMo Gateway  • Dual-Tier Audit Ledger
```

### 1. 🎓 Academic & Examination Engine
* **Dual Curriculum Architecture:** Native support for both **Basic Schools** (Kindergarten to JHS 3 with NaCCA Grade 1–9 stanine scale) and **Senior High Schools** (SHS 1–3 with WAEC 8-aggregate and A1–F9 alpha-numeric grading).
* **Configurable SBA Weightings:** Dynamic 30% School-Based Assessment (Class Tests, Projects, Homework) + 70% Terminal Examination, or modern 50/50 Continuous Assessment weighting.
* **Automated Broadsheets & Matrix Ledgers:** Instant computation of raw scores, class averages, subject ranks, and official terminal rankings with RFC 4180 CSV export and formula injection sanitization (CWE-1236).
* **Batch Print-Ready PDF Report Cards:** Single-page terminal report cards featuring high-resolution school crests, attendance summaries, conduct remarks, signature stamps, and next term resumption notices.
* **Promotions & Semester Rollover:** Automated academic rollover engine with transactional integrity guards that preserve historical ledger integrity.

### 2. 📋 Admissions, CSSPS Intake & Boarding Management
* **Ministry CSSPS Batch Intake:** One-click CSV ingestion for Ghana Ministry of Education Computerized School Selection & Placement System (CSSPS) files with automatic alias mapping and duplicate rejection.
* **Automated House & Dormitory Allocator:** Gender-balanced, capacity-aware automated room and bed allocator for boarding institutions.
* **Parent-Guardian Auto-Linking:** Intelligently matches sibling records under a single unified guardian portal account based on validated phone number hashes.
* **Cumulative Record Books (CRB):** Continuous bio-profile tracking, co-curricular records, medical histories, and automated graduating student digital clearance certificates.

### 3. 💳 Bursary, Fees & Financial Accounting
* **Flexible Multi-Category Billing:** Dynamic fee schedules differentiated by class level, academic stream, and residential status (Boarding vs. Day).
* **Real-Time Student Ledgers:** Complete double-entry debit/credit ledger tracking, arrears reporting, and itemized outstanding balance calculations.
* **Thermal & A4 Payment Receipts:** Print-ready official receipts with cryptographic verification hashes and timestamped operator signatures.
* **Hybrid Payment Gateway:** Offline manual payment recording (Cash, Direct Bank Deposit, Cheque) plus automated Mobile Money (MTN MoMo, Telecel Cash, AT Money) via Paystack split-settlement integration.

### 4. 🛏️ Boarding & QR-Code Exeat Gate Security
* **Digital Multi-Stage Exeat Workflow:** Electronic exeat requests initiated by Form Masters, approved by Senior Housemasters, and dispatched to parent phones.
* **Live QR-Coded Gate Passes:** Campus security officers scan digitally-signed student QR badges using any mobile browser to record gate departures and returns with sub-second latency.
* **Dormitory Capacity Management:** Real-time visibility into bed capacities, house allocations, and occupancy ratios.

### 5. 📅 Automated Timetable & Period Scheduling Engine
* **Conflict-Free CSP Engine:** Constraint-satisfaction heuristic solver that schedules school-wide master timetables, eliminating room double-booking and teacher period overlaps.
* **Teacher Workload Balancing:** Enforces GES weekly period limits (maximum 24–28 periods/week) with administrative duty exemptions.
* **Printable Class & Master Grid Exports:** Generates crisp classroom and staff noticeboard PDF timetables.

### 6. ⏱️ Attendance Scanner & Truancy Detection
* **Multi-Modal Register Modes:** Supports manual morning/afternoon class registers, USB barcode scanners, and mobile camera QR badge check-in.
* **Automated Truancy Alerts:** Detects consecutive unexcused absences and triggers automated parent alerts.

### 7. 📢 Omnichannel Messaging Engine
* **Offline-Safe Hybrid SMS Gateway:** Queues messages locally and simulates delivery offline; automatically dispatches through Hubtel / SMS gateways when connectivity is detected.
* **Direct WhatsApp Integration:** Instant click-to-chat links for immediate parent notifications without API fees.
* **Automated Event Triggers:** Automated broadcasts on payment confirmation, gate exeat check-in, attendance absence, and terminal report card publishing.

### 8. 🛡️ Zero-Trust Security, RBAC & Forensic Visibility
* **26 Granular Roles:** Comprehensive role hierarchy (Super Admin, Headmaster, Assistant Head Academic/Admin/Domestic, HOD, Form Master, Housemaster, Bursar, Teacher, Parent, Student, Security Officer).
* **Enterprise Offline Self-Service Password Recovery:** Secure password recovery using multi-factor institutional verification (Phone + Staff ID/DOB/PIN) with sliding-window rate limiting, timing attack resistance, and single-use JWT nonces.
* **Multi-Device Session Guard:** Active session tracking that detects concurrent device logins and terminates orphaned tokens.
* **Dual-Tier Forensic Audit Ledger:** Real-time institutional activity feed (`frontend/audit-logs.html`) capturing user agents, client IPs, timestamps, and actions with sensitive credential masking.

---

## ⚡ Concurrency & Database Engine Comparison

| Deployment Criterion | SQLite (WAL Mode) | PostgreSQL |
| :--- | :---: | :---: |
| **Recommended Concurrency** | **1 – 80+ Active Devices** | **100 – 10,000+ Active Devices** |
| **Setup Complexity** | **Zero Setup** (Embedded single file `school.db`) | Requires local/cloud PostgreSQL service |
| **Ideal Environment** | School Laptop, Local Wi-Fi Router, Desktop PC | Dedicated Server PC, Cloud VPS (Render/AWS) |
| **Database Locks** | `NORMAL` sync, 30s busy timeout, WAL queue | Row-level locking with MVCC |
| **Operational Dependency** | **100% Offline** (Zero external network) | Local LAN server or Internet for Cloud |

---

## 🚀 Quick Start & Installation

### Method 1: Windows 1-Click Desktop Launcher (Recommended for Schools)
EduManage 360 includes pre-configured automation scripts with pre-boot database backups and Chrome/Edge app-window kiosk mode:

1. Double-click [`Start_EduManage360.bat`](Start_EduManage360.bat).
2. The server creates a timestamped database backup in `backups/`, boots the async runtime on port 8000, and opens the application.
3. To stop gracefully: Run [`Stop_EduManage360.bat`](Stop_EduManage360.bat).
4. To restart: Run [`Restart_EduManage360.bat`](Restart_EduManage360.bat).

### Method 2: Python Production Server Runner

```bash
# 1. Clone the repository
git clone https://github.com/Bismark-Duah/SMS.git
cd SMS

# 2. Set up virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux / macOS

# 3. Install production dependencies
pip install -r backend/requirements.txt

# 4. Copy environment configuration
copy .env.example .env      # Windows
# cp .env.example .env       # Linux / macOS

# 5. Launch Production Server
python run.py
```

Access the application in your browser: **`http://127.0.0.1:8000`**

### Connecting Staff Devices Over School Wi-Fi (No Internet Required)
1. Connect the host computer to the school's local Wi-Fi router.
2. Run `ipconfig` (Windows) or `ip a` (Linux) to obtain the host's IPv4 address (e.g. `192.168.1.100`).
3. Teachers and staff on the same Wi-Fi network open: **`http://192.168.1.100:8000`**.

---

## 🔑 Default Master Credentials

| Account Role | Default Username | Default Password | Access Level |
| :--- | :--- | :--- | :--- |
| **Super Administrator** | `superadmin` | `superadmin123!` | System-wide / Multi-School Platform |
| **School Administrator** | `admin` | `admin123!` | Primary Institutional Portal |

> [!IMPORTANT]
> The system enforces mandatory password change warnings upon initial deployment. Update default master credentials immediately in production under **Settings > User Management**.

---

## 📦 Disaster Recovery & Client Handoff

```bash
# Execute automated pre-handoff sanitization and timestamped backup
python scripts/prepare_client_handoff.py

# Run standalone disaster recovery and database verification
python backend/app/scripts/disaster_recovery.py
```

---

## 🧪 Comprehensive Verification Suite

EduManage 360 features an enterprise-grade automated test runner validating **81 test suites** across security, database concurrency, academic engines, UI accessibility, and offline PWA assets:

```bash
python verify_all.py
```

```text
==================================================
               VERIFICATION REPORT                
==================================================
 [PASS]   tests/verify_promotions.py     : PASS
 [PASS]   tests/verify_messaging.py      : PASS
 [PASS]   tests/verify_academic_hierarchy.py : PASS
 [PASS]   tests/verify_report_card.py    : PASS
 [PASS]   tests/verify_sba_weighting.py  : PASS
 [PASS]   tests/verify_timetable.py      : PASS
 [PASS]   tests/test_sqlite_wal_and_concurrency.py : PASS
 [PASS]   tests/test_fee_financial_audit.py : PASS
 [PASS]   tests/test_academic_engine_audit.py : PASS
 [PASS]   tests/test_security_audit_hardening.py : PASS
 [PASS]   tests/test_offline_pwa_audit.py : PASS
 [PASS]   tests/test_password_recovery.py : PASS
 [PASS]   tests/test_backup_and_recovery.py : PASS
 [PASS]   tests/test_frontend_authorization_assumptions.py : PASS
 [PASS]   tests/test_responsive_mobile_ux.py : PASS
 [PASS]   tests/test_accessibility_audit.py : PASS
 [PASS]   tests/test_guided_school_onboarding.py : PASS
 [PASS]   tests/test_import_export_workflows.py : PASS
 [PASS]   tests/test_audit_and_forensic_visibility.py : PASS
==================================================
 ALL 81 SYSTEM VERIFICATION TESTS PASSED!
==================================================
```

---

## 📁 Repository Structure

```
SMS/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI application entrypoint & middleware
│   │   ├── database.py              # Dual SQLite WAL & PostgreSQL database engine
│   │   ├── models.py                # SQLAlchemy enterprise schema models
│   │   ├── routes/                  # 30+ domain route modules (auth, students, fees, etc.)
│   │   └── services/                # Business logic engines (grading, timetable, reports)
│   ├── migrations/                  # Alembic database migration revisions
│   └── requirements.txt             # Production Python dependencies
├── frontend/
│   ├── index.html                   # Login & landing portal
│   ├── dashboard.html               # Main executive institutional dashboard
│   ├── audit-logs.html              # Forensic audit trail & activity feed
│   ├── css/styles.css               # Centralized CSS design system & WCAG tokens
│   ├── js/                          # Modular vanilla JS controllers
│   └── sw.js                        # Offline-first Service Worker cache manifest
├── scripts/                         # Operational utilities (client handoff, backups)
├── docs/                            # Comprehensive engineering and security specs
├── tests/                           # 81 automated unit, regression & integration suites
├── run.py                           # Production server runner & port allocator
└── verify_all.py                    # Master system-wide test verification runner
```

---

## 📄 License & Proprietary Notice

© 2026 **EduManage 360**. All rights reserved.  
Engineered for institutional academic management, governance, and digital transformation.
