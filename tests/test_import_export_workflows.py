import os
import sys
import io
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.database import get_db, Base, engine, SessionLocal
from backend.app.models import User, Role, School, Student, ClassSection, Fee, AcademicYear, Semester
from backend.app.services.auth import create_jwt, hash_password
from backend.app.services.import_export_service import (
    sanitize_csv_cell,
    sanitize_row_for_export,
    sanitize_filename,
    decode_csv_bytes,
    generate_safe_csv_content
)

client = TestClient(app)


def setup_module():
    Base.metadata.create_all(bind=engine)


def test_sanitize_csv_cell_formula_injection_defense():
    """Verify CWE-1236 CSV Formula Injection defense on dangerous triggers."""
    # Formulas triggering DDE or execution in Excel/Calc
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("=cmd|'/C calc'!A0") == "'=cmd|'/C calc'!A0"
    assert sanitize_csv_cell("+SUM(A1:A10)") == "'+SUM(A1:A10)"
    assert sanitize_csv_cell("-2+5") == "'-2+5"
    assert sanitize_csv_cell("@SUM(1,2)") == "'@SUM(1,2)"
    assert sanitize_csv_cell("\tmalicious_tab") == "'\tmalicious_tab"
    assert sanitize_csv_cell("\rmalicious_cr") == "'\rmalicious_cr"
    
    # Leading whitespace before formula
    assert sanitize_csv_cell("   =2+2") == "'   =2+2"
    
    # Safe values
    assert sanitize_csv_cell("John Doe") == "John Doe"
    assert sanitize_csv_cell("STU-1234") == "STU-1234"
    assert sanitize_csv_cell(1234) == 1234
    assert sanitize_csv_cell(99.5) == 99.5
    assert sanitize_csv_cell(True) is True
    assert sanitize_csv_cell(None) == ""


def test_sanitize_filename_path_traversal_defense():
    """Verify CWE-22 Path Traversal defense in filename generation."""
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\windows\\system32\\calc.exe") == "calc.exe"
    assert sanitize_filename("malicious\0name.csv") == "maliciousname.csv"
    assert sanitize_filename("students/export/test.csv") == "test.csv"
    assert sanitize_filename("valid_report_2026.csv") == "valid_report_2026.csv"
    assert sanitize_filename("???!!!###.csv") == "csv"
    assert sanitize_filename("") == "export.csv"
    assert sanitize_filename(None) == "export.csv"


def test_decode_csv_bytes_and_binary_rejection():
    """Verify encoding decoding and rejection of corrupted/binary files."""
    # UTF-8 with BOM
    bom_content = b"\xef\xbb\xbfname,email\nKwame,kwame@school.local"
    decoded_bom = decode_csv_bytes(bom_content)
    assert decoded_bom == "name,email\nKwame,kwame@school.local"

    # Standard UTF-8
    utf8_content = "name,email\nKofi,kofi@school.local".encode("utf-8")
    assert decode_csv_bytes(utf8_content) == "name,email\nKofi,kofi@school.local"

    # Latin-1
    latin_content = "name,city\nJosé,Accra".encode("latin-1")
    assert "José" in decode_csv_bytes(latin_content)

    # Empty content rejected
    with pytest.raises(HTTPException) as excinfo:
        decode_csv_bytes(b"")
    assert excinfo.value.status_code == 400

    # Binary / Null byte rejected
    binary_content = b"\x4d\x5a\x90\x00\x03\x00\x00\x00"  # PE binary header
    with pytest.raises(HTTPException) as excinfo:
        decode_csv_bytes(binary_content)
    assert excinfo.value.status_code == 400
    assert "binary" in excinfo.value.detail.lower()

    # Exceeding size limit rejected
    with pytest.raises(HTTPException) as excinfo:
        decode_csv_bytes(b"x" * 200, max_bytes=100)
    assert excinfo.value.status_code == 400
    assert "exceeds" in excinfo.value.detail.lower()


def test_generate_safe_csv_content():
    """Verify CSV string generation with formula sanitization."""
    headers = ["ID", "Formula_Header", "Name"]
    rows = [
        [1, "=SUM(A1:B1)", "Alice"],
        [2, "-calc", "+Kwame"],
        [3, "@echo", "Normal Bob"]
    ]
    csv_str = generate_safe_csv_content(headers, rows)
    assert "'=SUM(A1:B1)" in csv_str
    assert "'-calc" in csv_str
    assert "'+Kwame" in csv_str
    assert "'@echo" in csv_str
    assert "Alice" in csv_str


def test_student_import_csv_workflow_and_validation():
    """Verify student import CSV validation, invalid format rejection, and duplicate handling."""
    db = SessionLocal()
    try:
        # Create test school and admin
        school = db.query(School).filter(School.name == "Import Test Academy").first()
        if not school:
            school = School(name="Import Test Academy", code="ITA", slug="import-test-academy", school_mode="COMBINED")
            db.add(school)
            db.commit()
            db.refresh(school)

        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            db.add(admin_role)
            db.commit()

        admin_user = db.query(User).filter(User.username == "import_admin_test").first()
        if not admin_user:
            admin_user = User(
                username="import_admin_test",
                email="import_admin@test.local",
                password_hash=hash_password("Pass123!"),
                school_id=school.id,
                is_active=True
            )
            admin_user.roles.append(admin_role)
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

        token = create_jwt({
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "school_id": school.id,
            "roles": ["admin"]
        })
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Reject non-CSV file
        resp = client.post(
            "/api/students/import-csv",
            headers=headers,
            files={"file": ("test.txt", io.BytesIO(b"Hello world"), "text/plain")}
        )
        assert resp.status_code == 400
        assert "only standard .csv files" in resp.json()["detail"].lower()

        # 2. Reject empty CSV
        resp = client.post(
            "/api/students/import-csv",
            headers=headers,
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
        )
        assert resp.status_code == 400

        # 3. Reject binary masqueraded as CSV
        resp = client.post(
            "/api/students/import-csv",
            headers=headers,
            files={"file": ("binary.csv", io.BytesIO(b"\x00\x01\x02\x03"), "text/csv")}
        )
        assert resp.status_code == 400
        assert "binary" in resp.json()["detail"].lower()

        # Clean up any existing students from previous test runs
        db.query(Student).filter(Student.student_code.like("IMP-TEST-%")).delete(synchronize_session=False)
        db.commit()

        # 4. Valid CSV import with 1 valid row and 1 invalid row (missing name)
        csv_payload = (
            "student_code,full_name,gender,residential_status\n"
            "IMP-TEST-001,Kojo Mensah,Male,Day\n"
            "IMP-TEST-002,,Female,Day\n"
        ).encode("utf-8")

        resp = client.post(
            "/api/students/import-csv",
            headers=headers,
            files={"file": ("students.csv", io.BytesIO(csv_payload), "text/csv")}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 1
        assert data["skipped"] == 1
        assert data["status"] == "partial_success"
        assert any("name is required" in e.lower() for e in data["errors"])

        # 5. Duplicate student_code detection on re-upload
        resp_dup = client.post(
            "/api/students/import-csv",
            headers=headers,
            files={"file": ("students_dup.csv", io.BytesIO(csv_payload), "text/csv")}
        )
        assert resp_dup.status_code == 200
        dup_data = resp_dup.json()
        assert dup_data["imported"] == 0
        assert any("already exists" in e.lower() for e in dup_data["errors"])

    finally:
        db.query(Student).filter(Student.student_code.like("IMP-TEST-%")).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_export_students_neutralizes_formula_injection():
    """Verify /api/reports/export-students neutralizes formulas in CSV output."""
    db = SessionLocal()
    try:
        school = db.query(School).filter(School.name == "Formula Academy").first()
        if not school:
            school = School(name="Formula Academy", code="FA", slug="formula-academy", school_mode="COMBINED")
            db.add(school)
            db.commit()
            db.refresh(school)

        # Create student with potential CSV injection in name
        student = db.query(Student).filter(Student.student_code == "FORMULA-01").first()
        if not student:
            student = Student(
                student_code="FORMULA-01",
                full_name="=cmd|' /C calc'!A0",
                first_name="Exploit",
                last_name="Test",
                school_id=school.id,
                is_active=True
            )
            db.add(student)
            db.commit()

        admin_role = db.query(Role).filter(Role.name == "admin").first()
        admin_user = db.query(User).filter(User.username == "formula_admin").first()
        if not admin_user:
            admin_user = User(
                username="formula_admin",
                email="formula_admin@test.local",
                password_hash=hash_password("Pass123!"),
                school_id=school.id,
                is_active=True
            )
            admin_user.roles.append(admin_role)
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

        token = create_jwt({
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "school_id": school.id,
            "roles": ["admin"]
        })
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/reports/export-students", headers=headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "Content-Disposition" in resp.headers

        csv_text = resp.text
        # The exported cell must be prefixed with single quote to prevent spreadsheet execution!
        assert "'=cmd|' /C calc'!A0" in csv_text

    finally:
        db.query(Student).filter(Student.student_code == "FORMULA-01").delete(synchronize_session=False)
        db.commit()
        db.close()


if __name__ == "__main__":
    test_sanitize_csv_cell_formula_injection_defense()
    test_sanitize_filename_path_traversal_defense()
    test_decode_csv_bytes_and_binary_rejection()
    test_generate_safe_csv_content()
    test_student_import_csv_workflow_and_validation()
    test_export_students_neutralizes_formula_injection()
    print("ALL IMPORT/EXPORT WORKFLOW TESTS PASSED!")
