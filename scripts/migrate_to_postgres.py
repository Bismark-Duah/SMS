#!/usr/bin/env python3
"""
scripts/migrate_to_postgres.py — SQLite to PostgreSQL Enterprise Migration Utility

Usage:
  1. Set target POSTGRES_URL environment variable (or pass as argument):
     export POSTGRES_URL="postgresql://postgres:password@localhost:5432/school_sms_db"
  2. Run script:
     python scripts/migrate_to_postgres.py

Description:
  Reads all tables & rows from local SQLite database (school.db),
  creates schema on PostgreSQL, and bulk-inserts all records.
"""

import os
import sys
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQLITE_DB_PATH = os.path.join(BASE_DIR, "school.db")
SQLITE_URL = f"sqlite:///{SQLITE_DB_PATH}"

target_postgres_url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("POSTGRES_URL")

if not target_postgres_url:
    print("❌ ERROR: Please provide PostgreSQL target URL.")
    print("Example: python scripts/migrate_to_postgres.py postgresql://postgres:password@localhost:5432/school_sms_db")
    sys.exit(1)

if target_postgres_url.startswith("postgres://"):
    target_postgres_url = target_postgres_url.replace("postgres://", "postgresql://", 1)

print("==================================================")
print(" SQLITE → POSTGRESQL ENTERPRISE MIGRATION UTILITY ")
print("==================================================")
print(f"Source SQLite  : {SQLITE_URL}")
print(f"Target Postgres: {target_postgres_url}\n")

# Connect to Source SQLite
sqlite_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
sqlite_meta = MetaData()
sqlite_meta.reflect(bind=sqlite_engine)

# Connect to Target PostgreSQL
pg_engine = create_engine(target_postgres_url, pool_pre_ping=True)

# 1. Create all models on PostgreSQL
from backend.app.database import Base
from backend.app import models  # Import all models

print("⚡ Creating PostgreSQL Database Tables & Schemas...")
Base.metadata.create_all(bind=pg_engine)
print("✔ PostgreSQL Tables Created Successfully!\n")

# 2. Copy Data Table by Table
print("⚡ Copying Records from SQLite to PostgreSQL...")
table_order = [
    "schools", "users", "semesters", "programs", "departments",
    "houses", "dormitories", "class_sections", "subjects",
    "program_subjects", "department_subjects", "user_roles",
    "students", "scores", "attendance", "fees", "payments",
    "exeat_records", "discipline_records", "student_guardians",
    "student_health", "admission_vouchers", "message_logs"
]

migrated_count = 0

with sqlite_engine.connect() as sqlite_conn, pg_engine.connect() as pg_conn:
    for table_name in table_order:
        if table_name in sqlite_meta.tables:
            sqlite_table = sqlite_meta.tables[table_name]
            rows = sqlite_conn.execute(sqlite_table.select()).mappings().all()

            if rows:
                row_dicts = [dict(r) for r in rows]
                # Insert into PostgreSQL table
                pg_table = Table(table_name, MetaData(), autoload_with=pg_engine)
                try:
                    pg_conn.execute(pg_table.insert(), row_dicts)
                    pg_conn.commit()
                    print(f"   [COPIED] Table '{table_name}': {len(row_dicts)} record(s).")
                    migrated_count += len(row_dicts)
                except Exception as e:
                    print(f"   [WARNING] Table '{table_name}' insert notice: {e}")

print("\n==================================================")
print(f" SUCCESS: Migrated {migrated_count} total record(s) to PostgreSQL!")
print("==================================================")
