"""
Database Maintenance & Test Data Purge Script
School Management System (SMS)
"""
import os
import sqlite3

def purge_test_data(db_path="school.db"):
    if not os.path.exists(db_path):
        print(f"Database file '{db_path}' not found.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print("Starting database maintenance and test data purge...")

    # 1. Delete test programs
    cur.execute("DELETE FROM program_subjects WHERE program_id IN (SELECT id FROM programs WHERE name LIKE 'Test Science Program%')")
    cur.execute("DELETE FROM programs WHERE name LIKE 'Test Science Program%'")
    print(f"-> Removed test programs.")

    # 2. Delete test classes
    test_patterns = [
        '%Test Class%', '%Priv Class%', '%Timetable Test%', '%MSG Test%',
        '%Attendance Test%', '%Fee Test%', '%Discipline Test%', '%Report Pub Test%',
        '%Asgn Test%', '%Notif Test%'
    ]
    where_clause = " OR ".join(["name LIKE ?"] * len(test_patterns))
    cur.execute(f"SELECT id FROM class_sections WHERE {where_clause}", test_patterns)
    test_ids = [r[0] for r in cur.fetchall()]

    if test_ids:
        ids_str = ",".join(map(str, test_ids))
        cur.execute(f"DELETE FROM class_section_subjects WHERE class_section_id IN ({ids_str})")
        cur.execute(f"DELETE FROM teacher_assignments WHERE class_section_id IN ({ids_str})")
        cur.execute(f"DELETE FROM timetable WHERE class_section_id IN ({ids_str})")
        cur.execute(f"DELETE FROM class_sections WHERE id IN ({ids_str})")
        print(f"-> Removed {len(test_ids)} test classes.")

    conn.commit()
    conn.close()
    print("Database maintenance completed successfully.")

if __name__ == "__main__":
    purge_test_data()
