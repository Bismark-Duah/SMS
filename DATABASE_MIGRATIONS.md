# Database Migrations & Schema Evolution Guide — EduManage 360

This document outlines the database schema migration architecture, lifecycle management, and disaster recovery procedures for **EduManage 360**.

---

## 1. Dual-Engine Architecture

EduManage 360 supports a dual-engine database strategy designed for offline resilience and cloud scalability:

| Environment | Database Engine | Operational Characteristics | Connection String |
|---|---|---|---|
| **Local / Offline** | **SQLite 3** | Default mode. WAL (Write-Ahead Logging) enabled. Zero network latency, portable single-file database (`school.db`). | `sqlite:///./school.db` |
| **Cloud / Production** | **PostgreSQL** | High concurrency, multi-node replication, connection pooling. Deployed via managed PostgreSQL on Render (`edumanage-db`). | `postgresql://user:pass@host:5432/db` |

Both engines share a unified SQLAlchemy ORM schema definition ([`backend/app/models.py`](file:///backend/app/models.py)) and are synchronized using **Alembic**.

---

## 2. Alembic Configuration & Directory Structure

- **Configuration File**: [`alembic.ini`](file:///alembic.ini) (at project root and mirrored in `backend/alembic.ini`).
- **Environment Script**: [`backend/alembic/env.py`](file:///backend/alembic/env.py) dynamically inspects `DATABASE_URL` from the environment:
  - If unset or SQLite, configures non-transactional DDL with `render_as_batch=True` to support SQLite column modifications.
  - If PostgreSQL, configures schema-aware transactions and constraints.
- **Migration Revisions**: Stored in [`backend/alembic/versions/`](file:///backend/alembic/versions/):
  - `0001_initial_schema_baseline.py`: Initial schema creation for all system tables.
  - `0002_database_constraints_and_integrity.py`: Composite unique constraints, foreign keys, and indexes.

---

## 3. Migration Commands & Workflows

### Running Migrations

```bash
# Apply all pending migrations to bring database to latest version
alembic upgrade head

# Inspect current applied revision
alembic current

# View migration history
alembic history --verbose
```

### Creating New Revisions

When modifying models in [`backend/app/models.py`](file:///backend/app/models.py):

```bash
# Generate a new migration script by diffing ORM models against the database
alembic revision --autogenerate -m "add_column_name_to_table"
```

> [!IMPORTANT]
> Always review the generated script in `backend/alembic/versions/` before committing. Ensure new columns on existing populated tables are either nullable (`nullable=True`) or have a server default (`server_default=...`) to prevent migration failures on production datasets.

### Rolling Back Migrations

```bash
# Revert the most recently applied migration
alembic downgrade -1

# Revert to a specific revision ID
alembic downgrade 0001_baseline
```

---

## 4. Programmatic & Cloud Deployment Automation

### Programmatic Execution
On application startup, [`backend/app/database.py`](file:///backend/app/database.py) executes `run_migrations()`, which runs Alembic migrations programmatically:

```python
from backend.app.database import run_migrations

# Automatically checks and applies head revision
run_migrations()
```

### Production Deployment Automation
In [`render.yaml`](file:///render.yaml), schema migrations are automatically executed as part of the build step before the web server boots:

```yaml
buildCommand: pip install -r backend/requirements.txt && alembic upgrade head
```

This guarantees zero schema drift between code releases and the production database.

---

## 5. Dialect Parity Rules (SQLite & PostgreSQL)

1. **Batch Mode for SQLite**:
   - SQLite does not natively support `ALTER TABLE DROP COLUMN` or changing constraints. Always ensure `with op.batch_alter_table("table_name") as batch_op:` is used in revision scripts.
2. **Boolean and Integer Types**:
   - SQLite stores booleans as `0` or `1`. PostgreSQL uses native `BOOLEAN`. SQLAlchemy and Alembic automatically handle this abstraction.
3. **Foreign Key Enforcement**:
   - In SQLite, foreign keys require `PRAGMA foreign_keys=ON;`, which is activated automatically on connection in `backend/app/database.py`.
4. **Deterministic Timestamps**:
   - Store timestamps in UTC timezone using `DateTime` columns.
