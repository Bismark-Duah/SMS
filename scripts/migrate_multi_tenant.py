"""
Multi-Tenant SQLite Migration Script
School Management System (SMS)
"""
import sqlite3
import os

def migrate_db(db_path="school.db"):
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print("Running Multi-Tenant DB Schema Migration...")

    # 1. Create schools table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS schools (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        school_mode TEXT DEFAULT 'COMBINED',
        boarding_type TEXT DEFAULT 'BOARDING_AND_DAY',
        status TEXT DEFAULT 'ACTIVE',
        address TEXT,
        phone TEXT,
        email TEXT,
        logo_url TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. Seed Default School 1 if missing
    cur.execute("SELECT id FROM schools WHERE id = 1")
    if not cur.fetchone():
        cur.execute("""
        INSERT INTO schools (id, name, code, school_mode, boarding_type, status, address, phone, email)
        VALUES (1, 'J.A.KUFFOUR STEM TECHNICAL', 'JAK-STEM', 'SHS_ONLY', 'BOARDING_AND_DAY', 'ACTIVE', '456 Academy Rd, Accra', '+233 24 123 4567', 'info@testacademy.edu')
        """)
        print("[OK] Seeded Default School 1 (J.A.KUFFOUR STEM TECHNICAL).")
    
    # 3. Add school_id column to target tables if missing
    target_tables = [
        "users", "students", "class_sections", "subjects", "programs", "departments",
        "settings", "fees", "attendance", "scores", "exeat_records", "discipline_records",
        "message_logs", "notifications", "dormitories", "houses", "academic_years"
    ]

    for table in target_tables:
        # Check table columns
        cur.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cur.fetchall()]
        if "school_id" not in cols:
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN school_id INTEGER DEFAULT 1 REFERENCES schools(id) ON DELETE CASCADE")
                print(f"   [MIGRATED] Added school_id column to '{table}'")
            except Exception as e:
                print(f"   [NOTICE] Table '{table}' column addition error: {e}")
        else:
            # Backfill any nulls
            cur.execute(f"UPDATE {table} SET school_id = 1 WHERE school_id IS NULL")

    conn.commit()
    conn.close()
    print("[OK] Multi-Tenant Database Migration Complete!")

if __name__ == "__main__":
    migrate_db()
