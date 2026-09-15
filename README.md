# 🎓 EduManage360 — Enterprise School Management System

<div align="center">

![EduManage360 Banner](frontend/assets/logo_primary.png)

**100% Offline-First Multi-School Institutional ERP & Academic Management Engine**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=flat-square&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%200.110-009688.svg?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Database Dual Engine](https://img.shields.io/badge/Database-SQLite%20WAL%20%7C%20PostgreSQL-336791.svg?style=flat-square&logo=sqlite)](file:///d:/documents/my%20apps/SMS/backend/app/database.py)
[![Offline-First PWA](https://img.shields.io/badge/Architecture-100%25%20Offline%20First-4f46e5.svg?style=flat-square)](file:///d:/documents/my%20apps/SMS/frontend/sw.js)
[![Security Standard](https://img.shields.io/badge/Security-OWASP%20ASVS%20Compliant-10b981.svg?style=flat-square)](file:///d:/documents/my%20apps/SMS/backend/app/routes/auth.py)
[![License](https://img.shields.io/badge/License-Proprietary-orange.svg?style=flat-square)]()

</div>

---

## 🌟 Executive Overview

**EduManage360** is an enterprise-grade, high-performance School Management System (SMS) engineered specifically for **Basic Schools (Kindergarten to JHS 3)**, **Senior High Schools (SHS / SHTS)**, and **Technical/STEM Institutions**. 

Built around a strict **100% Offline-First Philosophy**, EduManage360 operates seamlessly without active internet connections on local school networks (LAN/Wi-Fi), while featuring built-in **hybrid cloud synchronization** and zero-code migration to **PostgreSQL** for multi-campus and cloud deployments.

---

## 🏛️ Institutional Modules by Department

```
                                    ┌───────────────────────────────────────┐
                                    │       EduManage360 Core Engine        │
                                    └───────────────────┬───────────────────┘
               ┌────────────────────────┬───────────────┴───────────────┬────────────────────────┐
               ▼                        ▼                               ▼                        ▼
       [Academic & Exams]      [Admissions & Boarding]         [Finance & Bursary]      [Security & Identity]
       • NaCCA & GES Curriculum • CSSPS Batch Import            • Multi-category Bills   • 26 Granular RBAC Roles
       • 30/70 & 50/50 SBA      • House/Dorm Auto-Allocator     • Student Ledgers        • Zero-Trust Session Guard
       • Broadsheets & Transcripts• QR Gate Pass Exeats        • Instant Receipts       • Offline Self-Service Reset
       • Batch PDF Report Cards • Parent Auto-Linking           • Paystack Split Gateway • Forensic Audit Ledger
```

### 1. 🎓 Academic & Examination Engine
* **Ghana GES & NaCCA Curriculum Alignment:** Complete pre-seeded curriculum supporting Kindergarten, Primary (Class 1–6), Junior High (JHS 1–3), and Senior High (SHS Form 1–3).
* **Configurable SBA Weightings:** Dynamic 30% Continuous Assessment (Class Tests, Project Work, Homework) + 70% Terminal Exam or 50/50 SBA weighting.
* **Automated Broadsheets & Ranking:** Instant calculation of raw scores, aggregates, class positions, subject rankings, and grade remarks (Grade 1–9 for Basic, A1–F9 for SHS/WASSCE).
* **Batch Report Card PDF Generator:** Single-page, print-ready terminal report cards with institutional crests, attendance summaries, conduct/attitude remarks, and next term re-opening dates.
* **Promotions & Academic Rollover:** Automated grade-to-grade student promotion engine and semester rollover with database locking guards.

### 2. 📋 Student Admissions & CSSPS Enrollment
* **One-Click CSSPS Batch Intake:** Instant CSV importer supporting Ghana Ministry of Education CSSPS placement exports with automated duplicate detection.
* **Automated Indexing & Identifiers:** Generates institutional student codes, tracking BECE index numbers and raw aggregates.
* **Smart House & Dormitory Allocator:** Automated gender-balanced and capacity-aware allocation of students to houses and dormitories.
* **Parent-Guardian Auto-Linking:** Automatically identifies and links siblings under a single parent account based on contact phone verification.
* **Cumulative Record Books & Clearance:** Continuous bio-profile tracking, co-curricular records, and digital graduating student clearance certificates.

### 3. 💳 Bursary, Fees & Financial Accounting
* **Multi-Tiered Fee Billing:** Class-, stage-, program-, and residential status-based (Boarding vs. Day) fee structures.
* **Real-Time Student Ledgers:** Complete debit/credit ledgers, fee payment history, arrears tracking, and automated balance notifications.
* **Instant Thermal/A4 Receipt Generation:** Print-ready payment receipts with cryptographic transaction references.
* **Optional Paystack Online Gateway:** Automated Mobile Money (MTN MoMo, Telecel Cash, AT Money) and Card payment integration with 95/5 automated split settlements.

### 4. 🛏️ Boarding & Exeat Gate Security
* **Digital Exeat Workflow:** Housemaster request submission, Senior Housemaster approval, and parent SMS/WhatsApp notification.
* **QR-Coded Gate Passes:** Security officers scan QR gate passes at school gates using any smartphone or webcam to verify departure and return timestamps.
* **Live Dormitory Occupancy:** Real-time visibility into bed capacities, house allocations, and student residential statuses.

### 5. 📅 Automated Timetable & Scheduling
* **Conflict-Free Scheduling Engine:** Automatically generates school-wide master timetables preventing teacher period clashes, room double-booking, and uneven subject distribution.
* **Teacher Workload Balancing:** Respects weekly maximum period limits and duty-exempt periods for senior administrative staff.
* **Printable Class & Master Grids:** Exportable and printable PDF timetables for classrooms and staff noticeboards.

### 6. ⏱️ Attendance Scanner & Truancy Engine
* **Multi-Modal Attendance:** Manual class register entry, barcode scanner mode, and student ID badge QR check-in.
* **Automated Truancy Alerts:** Detects consecutive unexcused absences and triggers automated notifications to parents.

### 7. 📢 Omnichannel Messaging & Communication
* **Multi-Channel Delivery:** Bulk SMS broadcasts and direct WhatsApp chat links.
* **Hybrid SMS Gateway:** Operates in local simulation mode offline and connects to Hubtel/SMS APIs when internet access is available.
* **Automated Event Triggers:** Automated SMS alerts on attendance absence, fee payments, disciplinary infractions, and report card publishing.

### 8. 🛡️ Zero-Trust Security, RBAC & Self-Service Password Reset
* **26 Granular Institutional Roles:** Super Admin, Headmaster, Academic Head, Domestic Head, Administration Head, HOD, Form Master, Housemaster, Bursar, Teacher, Parent, Student, Security, etc.
* **Enterprise Offline Self-Service Password Reset:** Enables teachers, staff, students, and parents to securely reset forgotten passwords without administrator intervention using multi-factor institutional verification (Phone + Staff ID/DOB/PIN) with sliding-window rate limiting, timing attack resistance, single-use JWT nonces, and session revocation.
* **Zero-Trust Multi-Device Session Guard:** Active session tracking that detects multi-device logins and revokes orphaned tokens.
* **Forensic Audit Ledger:** Immutable audit trail capturing client IP, user agent, timestamp, and device category for all critical institutional actions.

---

## ⚡ Architecture & Database Concurrency

EduManage360 utilizes a **Database-Aware Asynchronous Concurrency Architecture**:

```
 [30–80+ Staff Devices (Laptops, Tablets, Phones on School Wi-Fi)]
                                │
                                ▼
               [FastAPI / Uvicorn Async Server]
                                │
               ┌────────────────┴────────────────┐
               ▼                                 ▼
      [Concurrent Reads]                [Sequential Writes]
   (Unlimited Simultaneous)             (WAL Queue: 2-10ms)
               │                                 │
               ▼                                 ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                SQLite WAL (Write-Ahead Log)                 │
   │  • PRAGMA journal_mode      = WAL                           │
   │  • PRAGMA busy_timeout      = 30,000 ms                     │
   │  • PRAGMA synchronous       = NORMAL                        │
   │  • PRAGMA wal_autocheckpoint= 1000                          │
   └─────────────────────────────────────────────────────────────┘
```

| Database Engine | Recommended Concurrency | Ideal Deployment Environment | Setup Requirement |
| :--- | :---: | :--- | :--- |
| **SQLite (WAL Mode)** | **1 – 60+ Active Users** | Local School Laptop, Desktop PC, Local Wi-Fi Router | **Zero Setup** (Embedded single file `school.db`) |
| **PostgreSQL** | **100 – 1,000+ Active Users**| Dedicated School Server PC, Cloud (Render / AWS / VPS) | Local/Cloud PostgreSQL service running |

---

## 🚀 Getting Started & Deployment

### Method 1: Windows 1-Click Desktop Launcher (Recommended for Schools)

EduManage360 includes pre-built batch launchers with automatic pre-startup database backups and Edge/Chrome kiosk mode:

1. Double-click [`Start_EduManage360.bat`](file:///d:/documents/my%20apps/SMS/Start_EduManage360.bat) to start the system.
2. The server boots in the background, secures an automatic database snapshot in `backups/`, and opens the application in a dedicated app window.
3. To stop gracefully, run [`Stop_EduManage360.bat`](file:///d:/documents/my%20apps/SMS/Stop_EduManage360.bat).
4. To restart, run [`Restart_EduManage360.bat`](file:///d:/documents/my%20apps/SMS/Restart_EduManage360.bat).

### Method 2: Python Production Server Runner

```bash
# 1. Clone or navigate to the repository
cd SMS

# 2. Activate Python environment
.venv\Scripts\activate   # Windows
# source .venv/bin/activate # Linux/macOS

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Launch Production Concurrency Controller
python run.py
```

Open your browser to: **`http://127.0.0.1:8000`**

### Connecting Staff Devices Over School Wi-Fi (No Internet Required)
1. Connect the host computer to the school's local Wi-Fi router.
2. Open Command Prompt and type `ipconfig` to find the host's IPv4 address (e.g. `192.168.1.100`).
3. Any teacher or staff member on the same Wi-Fi opens: `http://192.168.1.100:8000`.

---

## 🔑 Default Master Credentials

| Account Role | Default Username | Default Password | Access Level |
| :--- | :--- | :--- | :--- |
| **Super Administrator** | `superadmin` | `superadmin123!` | System-wide / Multi-School Portal |
| **School Administrator** | `admin` | `admin123!` | Primary School Administration Portal |

> [!IMPORTANT]
> Change the default passwords immediately upon initial login under **Settings > User Management**.

---

## 📦 Client Handover & Production Reset

Before handing the system over to a client school, run the pre-built handoff preparation utility to create a timestamped backup and purge test mock data while preserving schema, roles, and administrative accounts:

```bash
python scripts/prepare_client_handoff.py
```

---

## 🧪 Comprehensive Verification Test Suite

EduManage360 includes an automated unified verification suite covering 54 test modules:

```bash
python verify_all.py
```

```text
==================================================
 SMS SYSTEM-WIDE UNIFIED VERIFICATION SUITE       
==================================================
 [PASS]   tests/verify_academic_hierarchy.py
 [PASS]   tests/verify_report_card.py
 [PASS]   tests/verify_sba_weighting.py
 [PASS]   tests/verify_exeat.py
 [PASS]   tests/verify_timetable.py
 [PASS]   tests/test_sqlite_wal_and_concurrency.py
 [PASS]   tests/test_fee_financial_audit.py
 [PASS]   tests/test_security_audit_hardening.py
 [PASS]   tests/test_offline_pwa_audit.py
 [PASS]   tests/test_password_recovery.py
 [PASS]   tests/test_performance_and_scalability.py
==================================================
 ALL SYSTEM VERIFICATION TESTS PASSED!
==================================================
```

---

## 📄 License & Proprietary Notice

© 2026 **EduManage360**. All rights reserved.  
Engineered for institutional academic management, governance, and digital transformation.
