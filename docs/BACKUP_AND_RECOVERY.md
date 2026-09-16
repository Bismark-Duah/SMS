# EduManage 360 — Database Backup, Disaster Recovery & Restoration Standard

## 1. Objectives & SLAs
| Metric | Local Offline Deployment | Cloud Production (PostgreSQL) |
| :--- | :--- | :--- |
| **RPO (Recovery Point Objective)** | < 24 Hours (or manual snapshot) | < 5 Minutes (Continuous WAL Archiving) |
| **RTO (Recovery Time Objective)** | < 5 Minutes | < 15 Minutes |
| **Storage Engine** | SQLite 3.40+ (WAL Mode) | PostgreSQL 15+ Cluster |

---

## 2. What Is Backed Up
1. **Relational Database Data**:
   - Multi-tenant schools, users, roles, and privileges.
   - Academic hierarchy: stages, classes, subjects, enrollments, timetables.
   - Student academic records, continuous assessment (SBA), WAEC/BECE exam scores, report cards, transcripts.
   - Financial ledgers: fee allocations, payments, receipts, audit logs.
2. **Media & Document Assets**:
   - Student passport photographs and school logos in `static/uploads/`.
   - Exported as bundled archives via `/api/backup/export-full-zip`.

---

## 3. Storage & Cryptographic Verification
- **Local Storage Path**: `backups/` relative to project root.
- **Sidecar Checksums**: Every snapshot generates a `backup_YYYY-MM-DD_HHMMSS.db.sha256` checksum sidecar.
- **Integrity Checks**:
  - `PRAGMA quick_check`: Checked automatically upon snapshot creation.
  - `PRAGMA integrity_check`: Executed prior to any restore operation.
- **Rolling Retention**: Automatically preserves the newest 14 backups (`MAX_BACKUPS_RETAINED=14`), pruning older snapshots and sidecars.

---

## 4. SQLite Restoration Procedure

### Step 1: Execute Dry-Run Verification
Before altering the active live database, perform a safe dry run:
```bash
python -m backend.app.scripts.disaster_recovery verify --filename backup_2026-09-15_120000.db
```
Or via API:
```http
POST /api/backup/restore-test/backup_2026-09-15_120000.db
```
This inspects the snapshot in isolation, validates table schemas (`schools`, `users`, `students`), and verifies query integrity without modifying the live database.

### Step 2: Live Restoration
When confirmed:
1. Creates an automated pre-restore safety snapshot of the active database (`pre_restore_safety_backup_<timestamp>.db`).
2. Truncates active WAL frames via `PRAGMA wal_checkpoint(TRUNCATE)`.
3. Atomically replaces `school.db` and cleans up stale WAL/SHM locks.

---

## 5. PostgreSQL Production Disaster Recovery Procedure

### Backup Command (`pg_dump`)
```bash
PGPASSWORD="your_database_password" pg_dump \
  -Fc \
  -v \
  -h db.host.internal \
  -p 5432 \
  -U db_user \
  -d edumanage_production \
  -f edumanage_backup_$(date +%Y%m%d_%H%M%S).dump
```
- `-Fc`: Custom compressed PostgreSQL format (enables parallel restore with `--jobs`).

### Restoration Command (`pg_restore`)
```bash
# 1. Inspect dump contents without restoring:
pg_restore --list edumanage_backup.dump

# 2. Execute clean restore:
PGPASSWORD="your_database_password" pg_restore \
  -v \
  --clean \
  --if-exists \
  -h db.host.internal \
  -p 5432 \
  -U db_user \
  -d edumanage_production \
  edumanage_backup.dump
```

---

## 6. Disaster Recovery CLI Utility
Run CLI management commands from repository root:
```bash
# Check status and backup history
python -m backend.app.scripts.disaster_recovery status

# Trigger immediate hot backup
python -m backend.app.scripts.disaster_recovery backup

# Verify backup integrity
python -m backend.app.scripts.disaster_recovery verify

# Generate PostgreSQL production commands
python -m backend.app.scripts.disaster_recovery postgres-commands
```
