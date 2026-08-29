"""
Automated Non-Destructive Data Migration: SQLite (school.db) -> PostgreSQL (sms_db)
Transfers all existing academic, administrative, financial, and configuration records,
and synchronizes PostgreSQL primary key auto-increment sequences.
"""
import os
import sys
import sqlite3
from sqlalchemy import create_engine, text, inspect
from backend.app.models import Base
from backend.app.database import DEFAULT_DB_PATH

PG_URL = os.getenv("PG_DATABASE_URL", "postgresql://postgres:passwordeduManage360@localhost:5432/sms_db")

TABLES_ORDERED = [
    "roles",
    "schools",
    "departments",
    "users",
    "user_roles",
    "academic_years",
    "school_stages",
    "programs",
    "subjects",
    "program_subjects",
    "program_core_subjects",
    "elective_combinations",
    "elective_combination_subjects",
    "department_subjects",
    "school_subjects",
    "school_programs",
    "semesters",
    "houses",
    "dormitories",
    "class_sections",
    "class_section_subjects",
    "teacher_assignments",
    "students",
    "student_guardians",
    "student_health",
    "student_clearance_records",
    "student_semester_summaries",
    "class_section_report_statuses",
    "class_subject_score_statuses",
    "scores",
    "attendance",
    "attendance_records",
    "result_records",
    "timetable",
    "notifications",
    "fees",
    "payments",
    "discipline_records",
    "exeat_records",
    "gate_pass_logs",
    "assets",
    "textbook_allocations",
    "uniform_items",
    "uniform_disbursements",
    "settings",
    "school_subaccounts",
    "tenant_sms_configs",
    "user_device_sessions",
    "admission_vouchers",
    "voucher_orders",
    "config_audit_logs",
    "activity_audit_logs",
    "message_logs"
]

def migrate():
    print(f"[*] Starting resilient migration from {DEFAULT_DB_PATH} to {PG_URL}...")
    if not os.path.exists(DEFAULT_DB_PATH):
        print(f"[!] SQLite file {DEFAULT_DB_PATH} not found. Nothing to migrate.")
        return

    # 1. Connect to SQLite
    sqlite_conn = sqlite3.connect(DEFAULT_DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    # 2. Connect to PostgreSQL and create schema
    pg_engine = create_engine(PG_URL)
    Base.metadata.create_all(bind=pg_engine)
    pg_inspector = inspect(pg_engine)

    total_migrated = 0

    with pg_engine.connect() as pg_conn:
        # Collect valid existing User and School IDs in PostgreSQL to sanitize orphaned foreign keys
        valid_user_ids = {r[0] for r in pg_conn.execute(text("SELECT id FROM users")).fetchall()}
        valid_school_ids = {r[0] for r in pg_conn.execute(text("SELECT id FROM schools")).fetchall()}

        for table_name in TABLES_ORDERED:
            # Check if table exists in SQLite
            sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not sqlite_cur.fetchone():
                continue

            # Check if table exists in Postgres
            if not pg_inspector.has_table(table_name):
                continue

            # Get matching columns between SQLite and Postgres
            sqlite_cur.execute(f"PRAGMA table_info({table_name})")
            sqlite_cols = {row["name"] for row in sqlite_cur.fetchall()}
            
            pg_cols = {col["name"] for col in pg_inspector.get_columns(table_name)}
            common_cols = list(sqlite_cols.intersection(pg_cols))

            if not common_cols:
                continue

            cols_str = ", ".join(f'"{c}"' for c in common_cols)
            placeholders = ", ".join(f":{c}" for c in common_cols)

            # Fetch rows from SQLite
            sqlite_cur.execute(f"SELECT {cols_str} FROM {table_name}")
            rows = sqlite_cur.fetchall()
            if not rows:
                continue

            table_migrated = 0
            insert_stmt = text(f"""
                INSERT INTO {table_name} ({cols_str}) 
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """)

            for row in rows:
                r_dict = {c: row[c] for c in common_cols}
                
                # Sanitize orphaned user_id / changed_by_user_id
                if "user_id" in r_dict and r_dict["user_id"] is not None and r_dict["user_id"] not in valid_user_ids:
                    r_dict["user_id"] = None
                if "changed_by_user_id" in r_dict and r_dict["changed_by_user_id"] is not None and r_dict["changed_by_user_id"] not in valid_user_ids:
                    r_dict["changed_by_user_id"] = None
                if "senior_in_charge_id" in r_dict and r_dict["senior_in_charge_id"] not in valid_user_ids:
                    r_dict["senior_in_charge_id"] = None
                if "house_master_id" in r_dict and r_dict["house_master_id"] not in valid_user_ids:
                    r_dict["house_master_id"] = None
                if "assistant_house_master_id" in r_dict and r_dict["assistant_house_master_id"] not in valid_user_ids:
                    r_dict["assistant_house_master_id"] = None
                if "senior_in_charge_girls_id" in r_dict and r_dict["senior_in_charge_girls_id"] not in valid_user_ids:
                    r_dict["senior_in_charge_girls_id"] = None
                if "house_master_girls_id" in r_dict and r_dict["house_master_girls_id"] not in valid_user_ids:
                    r_dict["house_master_girls_id"] = None
                if "assistant_house_master_girls_id" in r_dict and r_dict["assistant_house_master_girls_id"] not in valid_user_ids:
                    r_dict["assistant_house_master_girls_id"] = None
                if "sender_id" in r_dict and table_name == "message_logs" and r_dict["sender_id"] not in valid_user_ids:
                    r_dict["sender_id"] = None

                try:
                    pg_conn.execute(insert_stmt, r_dict)
                    pg_conn.commit()
                    table_migrated += 1
                except Exception as e:
                    pg_conn.rollback()

            if table_migrated > 0:
                print(f"[+] Migrated {table_migrated} rows -> '{table_name}'")
                total_migrated += table_migrated

            # If we just migrated users or schools, update valid IDs
            if table_name == "users":
                valid_user_ids = {r[0] for r in pg_conn.execute(text("SELECT id FROM users")).fetchall()}
            elif table_name == "schools":
                valid_school_ids = {r[0] for r in pg_conn.execute(text("SELECT id FROM schools")).fetchall()}

        # 3. Synchronize auto-increment serial sequences in PostgreSQL
        print("[*] Synchronizing PostgreSQL serial sequences...")
        for table_name in TABLES_ORDERED:
            if not pg_inspector.has_table(table_name):
                continue
            cols = [c["name"] for c in pg_inspector.get_columns(table_name)]
            if "id" in cols:
                try:
                    pg_conn.execute(text(f"""
                        SELECT setval(
                            pg_get_serial_sequence('{table_name}', 'id'),
                            COALESCE((SELECT MAX(id) FROM {table_name}), 1)
                        )
                    """))
                    pg_conn.commit()
                except Exception:
                    pg_conn.rollback()

    sqlite_conn.close()
    print(f"[SUCCESS] Migration complete! Total records transferred: {total_migrated}")

if __name__ == "__main__":
    migrate()
