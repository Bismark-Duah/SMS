import os
import sys
import uuid
from datetime import datetime

# Ensure backend path is available
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import (
    School, Program, ClassSection, Student, StudentHealth, StudentGuardian,
    Setting, AdmissionVoucher
)
from backend.app.routes.cssps_enrollment import check_candidate_placement

def run_test():
    print("=" * 70)
    print("TEST SUITE: Step 1 CSSPS Placement Verification Gatekeeper")
    print("=" * 70)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Setup School & Candidate
        school = db.query(School).filter(School.school_mode.in_(["SHS_ONLY", "COMBINED", "TECHNICAL"])).first()
        if not school:
            school = School(
                name="J.A. Kufuor STEM Technical Senior High School",
                code="JAK-STEM",
                school_mode="SHS_ONLY",
                status="ACTIVE"
            )
            db.add(school)
            db.commit()
            db.refresh(school)

        program = db.query(Program).filter(Program.name.ilike("%Science%")).first()
        if not program:
            program = Program(name="General Science", code="GSCI", school_id=school.id)
            db.add(program)
            db.commit()
            db.refresh(program)

        import random
        rand_digits = f"{random.randint(1000, 9999)}"
        test_idx_12 = f"101000{rand_digits}26"
        test_idx_10 = test_idx_12[:10]

        student = Student(
            student_code=f"SHS-{test_idx_12}",
            full_name="Kwame Mensah Test",
            first_name="Kwame",
            last_name="Mensah",
            bece_index_number=test_idx_12,
            bece_aggregate=8,
            residential_status="B",
            enrollment_status="PLACED",
            program_id=program.id,
            school_id=school.id
        )
        db.add(student)
        db.commit()
        db.refresh(student)
        print(f"[Setup] Created placed test candidate: {student.full_name} with Index: {test_idx_12}")

        # ── Test 1: Query with 10-digit index + 2026 Year Dropdown ───────────
        print("\n[Test 1] Verifying 10-digit Index with separate Year '2026'...")
        res1 = check_candidate_placement(
            index_number=test_idx_10,
            year="2026",
            school_id=school.id,
            db=db
        )
        assert res1["is_placed"] is True, f"Expected is_placed=True, got {res1}"
        assert res1["full_name"] == "Kwame Mensah Test"
        assert res1["bece_index_number"] == test_idx_12
        assert res1["residential_status"] == "Boarding"
        print(f"[PASS] Success: Verified placement matching canonical 12-digit index from 10-digit input + year!")

        # ── Test 2: Query with full 12-digit index ───────────────────────────
        print("\n[Test 2] Verifying full 12-digit Index directly...")
        res2 = check_candidate_placement(
            index_number=test_idx_12,
            year="2026",
            school_id=school.id,
            db=db
        )
        assert res2["is_placed"] is True
        assert res2["bece_index_number"] == test_idx_12
        print(f"[PASS] Success: Verified full 12-digit index with redundant year parameter!")

        # ── Test 3: Query with Unplaced / Non-Existent Index ──────────────────
        print("\n[Test 3] Verifying unplaced candidate index...")
        fake_idx = "9999999999"
        res3 = check_candidate_placement(
            index_number=fake_idx,
            year="2026",
            school_id=school.id,
            db=db
        )
        assert res3["is_placed"] is False
        assert "batch_advisory" in res3
        print(f"[PASS] Success: Unplaced candidate gracefully returns is_placed=False with batch release advisory:")
        print(f"   Advisory: {res3['batch_advisory'][:90]}...")

        # ── Test 4: Verify School Branding Response ──────────────────────────
        print("\n[Test 4] Verifying School Branding attachment...")
        assert res1["school_name"] == school.name
        print(f"[PASS] Success: School branding correctly returned as '{res1['school_name']}'")

        print("\n" + "=" * 70)
        print("ALL STEP 1 PLACEMENT VERIFICATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)

    finally:
        db.close()

if __name__ == "__main__":
    run_test()
