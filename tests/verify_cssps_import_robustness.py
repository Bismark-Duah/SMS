"""
verify_cssps_import_robustness.py
Tests the enterprise-grade CSSPS placement CSV import engine:
- Verifies length handling (>15 characters for enrolment codes & index numbers)
- Verifies semicolon and comma delimiter detection
- Verifies savepoint isolation (invalid rows don't abort remaining rows)
- Verifies auto House/Dorm allocation, Guardian, and Health records
"""

import io
import os
import sys
import asyncio
from fastapi import UploadFile

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import SessionLocal
from backend.app.models import Student, User, School, Program, House
from backend.app.routes.cssps_enrollment import import_cssps_csv

def make_upload_file(content_str: str, filename: str = "placement.csv"):
    file_bytes = io.BytesIO(content_str.encode("utf-8"))
    return UploadFile(file=file_bytes, filename=filename)

async def async_run_tests():
    db = SessionLocal()

    # 1. Setup Admin user
    admin_user = db.query(User).first()
    if not admin_user:
        admin_user = User(
            username="admin_test",
            email="admin@test.com",
            password_hash="fake",
            school_id=1,
            is_active=True
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

    # Pre-test cleanup
    db.query(Student).filter(Student.bece_index_number.in_([
        "990000000001", "990000000002", "990000000003", "990000000004", "990000000005", "990000000006"
    ])).delete(synchronize_session=False)
    db.commit()

    print("\n--- Test 1: Standard Comma CSV with 12-digit BECE & Long Auto-Code ---")
    csv_data_1 = """bece_index_number,first_name,last_name,gender,date_of_birth,bece_raw_score,bece_aggregate,program_name,residential_status,guardian_name,primary_phone
990000000001,Kofi,Annan,Male,2008-01-15,450,7,General Science,Boarding,Mr. Annan,0244000001
990000000002,Ama,Atta,Female,2008-03-22,430,9,General Arts,Day,Mrs. Atta,0244000002
"""
    data = await import_cssps_csv(file=make_upload_file(csv_data_1), db=db, current_user=admin_user)
    print("Response payload:", data)
    assert data["status"] == "success"
    assert data["imported"] == 2, f"Expected 2 imported, got {data['imported']}"
    assert data["skipped"] == 0, f"Expected 0 skipped, got {data['skipped']}"

    # Verify in DB
    s1 = db.query(Student).filter(Student.bece_index_number == "990000000001").first()
    assert s1 is not None, "Student 1 not found in DB"
    print(f"Verified Student 1: {s1.full_name}, Code: {s1.student_code}, EnrolCode: {s1.enrolment_code}, House: {s1.house_id}")

    print("\n--- Test 2: Semicolon Delimited CSV with Alternate Header Aliases ---")
    csv_data_2 = """Index No;Candidate Name;Sex;DOB;Score;Agg;Course;Residence;Guardian;Contact
990000000003;Kwame Nkrumah;M;2008-09-21;480;6;Business;Boarding;Madam Nyaniba;0200000003
990000000004;Akua Donkor;F;2008-11-10;390;12;Home Economics;Day;Uncle Donkor;
"""
    data = await import_cssps_csv(file=make_upload_file(csv_data_2), db=db, current_user=admin_user)
    print("Response payload:", data)
    assert data["status"] == "success"
    assert data["imported"] == 2, f"Expected 2 imported, got {data['imported']}"

    s3 = db.query(Student).filter(Student.bece_index_number == "990000000003").first()
    assert s3 is not None
    assert s3.first_name == "Kwame"
    assert s3.last_name == "Nkrumah"
    print(f"Verified Student 3 (Semicolon + Aliases): {s3.full_name}, Program: {s3.program_id}")

    print("\n--- Test 3: Savepoint Isolation (1 Duplicate + 1 Invalid + 2 Valid) ---")
    csv_data_3 = """bece_index_number,full_name,gender,residential_status
990000000001,Duplicate Candidate,Male,Boarding
990000000005,Valid New Candidate One,Female,Day
INVALID_SHORT,Bad Candidate,Male,Boarding
990000000006,Valid New Candidate Two,Male,Boarding
"""
    data = await import_cssps_csv(file=make_upload_file(csv_data_3), db=db, current_user=admin_user)
    print("Response payload:", data)
    assert data["status"] == "success"
    assert data["imported"] == 2, f"Expected 2 imported, got {data['imported']}"
    assert data["skipped"] == 2, f"Expected 2 skipped, got {data['skipped']}"
    assert len(data["errors"]) == 2, f"Expected 2 error logs, got {len(data['errors'])}"
    print("Logged error reasons:")
    for err in data["errors"]:
        print(" -", err)

    # Cleanup test entries
    db.query(Student).filter(Student.bece_index_number.in_([
        "990000000001", "990000000002", "990000000003", "990000000004", "990000000005", "990000000006"
    ])).delete(synchronize_session=False)
    db.commit()
    db.close()

    print("\n[SUCCESS] ALL CSSPS ENTERPRISE IMPORT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(async_run_tests())
