# EduManage 360 — Developer Onboarding & Environment Setup Guide

## 1. System Prerequisites
Before beginning development or local testing, ensure your host machine meets the following baseline requirements:
- **Operating System:** Windows 10/11, Ubuntu 20.04+, Debian 11+, or macOS 12+
- **Python Runtime:** Python 3.10, 3.11, 3.12, or 3.14 (64-bit recommended)
- **Database Engine:**
  - **Development & Offline Schools:** SQLite 3.35+ (bundled natively with Python runtime; no separate installation needed)
  - **Enterprise Multi-Campus:** PostgreSQL 14, 15, or 16 (optional)
- **Version Control:** Git 2.30+
- **Web Browser:** Google Chrome, Microsoft Edge, Mozilla Firefox, or Safari (supporting Service Workers and modern ES6+)

---

## 2. Fast-Track Local Setup

### Step 1: Clone Repository & Enter Directory
```bash
git clone https://github.com/Bismark-Duah/SMS.git
cd SMS
```

### Step 2: Initialize Python Virtual Environment
It is strictly recommended to use an isolated virtual environment to prevent package collisions:

**Windows (Command Prompt / PowerShell):**
```powershell
python -m venv .venv

# Command Prompt:
.venv\Scripts\activate

# PowerShell:
.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Production & Testing Dependencies
```bash
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### Step 4: Configure Environment Variables
Copy the template file `.env.example` to `.env`:

**Windows:**
```powershell
copy .env.example .env
```

**Linux / macOS:**
```bash
cp .env.example .env
```

Review the `.env` settings. The default configuration connects to the local embedded SQLite database (`sqlite:///./school.db`) in high-concurrency WAL mode with zero configuration.

### Step 5: Execute Database Migrations
Initialize or update the database schema using Alembic:
```bash
alembic upgrade head
```

---

## 3. Launching the Application

### Option A: Standard Production Concurrency Runner (Recommended)
```bash
python run.py
```
This utility automatically detects port availability, optimizes SQLite WAL PRAGMAs, ensures default roles and accounts are seeded, and launches the Uvicorn server on `http://127.0.0.1:8000`.

### Option B: FastAPI Development Server with Hot-Reload
```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

### Option C: Windows 1-Click Desktop Launcher
For school office staff and test demonstration environments:
- Double-click [`Start_EduManage360.bat`](file:///d:/documents/my%20apps/SMS/Start_EduManage360.bat).
- The script automatically executes a pre-boot database snapshot to `backups/` and launches the application in kiosk app mode.

---

## 4. Administrator Credential Provisioning

Production administrator credentials are intentionally not published in this repository. Initial administrator setup must be completed through the secure deployment/configuration process (e.g., via `INITIAL_SUPERADMIN_PASSWORD` in your environment or the initial onboarding wizard), and temporary credentials must be rotated before normal operation.

---

## 5. Running Verification & Automated Test Suites

The codebase is protected by **82 automated verification suites** covering security boundaries, database concurrency, academic engines, and offline asset caching:

### Run All 82 Verification Suites
```bash
python verify_all.py
```

### Run an Individual Test Suite
```bash
# Example: Run the Audit & Forensic Visibility Suite
python tests/test_audit_and_forensic_visibility.py

# Example: Run the Import & Export Security Suite
python tests/test_import_export_workflows.py

# Example: Run the Offline PWA Asset Coverage Suite
python tests/test_offline_pwa_audit.py
```

---

## 6. Switching to Enterprise PostgreSQL

To run the application against a PostgreSQL database:

1. Create a PostgreSQL database and user:
   ```sql
   CREATE USER edumanage_user WITH PASSWORD 'strong_password_here';
   CREATE DATABASE edumanage_db OWNER edumanage_user;
   GRANT ALL PRIVILEGES ON DATABASE edumanage_db TO edumanage_user;
   ```
2. Update `DATABASE_URL` in `.env`:
   ```dotenv
   DATABASE_URL=postgresql://edumanage_user:strong_password_here@localhost:5432/edumanage_db
   ```
3. Run migrations to generate the schema:
   ```bash
   alembic upgrade head
   ```
4. Start the application:
   ```bash
   python run.py
   ```

---

## 7. Disaster Recovery & Client Handoff Scripts

Before deploying to a new institutional client, clean development test data while preserving core curricula, roles, and schema:
```bash
python scripts/prepare_client_handoff.py
```
This utility automatically:
1. Generates an immutable timestamped backup in `backups/`.
2. Purges transient mock student attendance, marks, and test receipts.
3. Leaves administrative users, academic stages, and subject offerings pristine.
