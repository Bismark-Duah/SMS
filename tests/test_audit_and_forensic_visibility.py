import os
import sys
import json
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.database import Base, engine, SessionLocal
from backend.app.models import User, Role, School, AuditLog
from backend.app.services.auth import create_jwt, hash_password
from backend.app.services.audit_service import record_audit_event, mask_sensitive_data

client = TestClient(app)


def setup_module():
    Base.metadata.create_all(bind=engine)


def test_mask_sensitive_data_redaction():
    """Verify recursive redaction of credentials and secrets from audit metadata."""
    # 1. Dictionary redaction
    raw_dict = {
        "username": "teacher1",
        "password": "SuperSecretPassword123!",
        "auth_token": "jwt-token-xyz",
        "api_key": "secret-api-key-999",
        "nested": {
            "client_secret": "my-client-secret",
            "safe_field": "visible_value"
        }
    }
    masked = mask_sensitive_data(raw_dict)
    assert masked["username"] == "teacher1"
    assert masked["password"] == "[REDACTED]"
    assert masked["auth_token"] == "[REDACTED]"
    assert masked["api_key"] == "[REDACTED]"
    assert masked["nested"]["client_secret"] == "[REDACTED]"
    assert masked["nested"]["safe_field"] == "visible_value"

    # 2. JSON string redaction
    raw_json = json.dumps({"token": "secret-token-123", "action": "LOGIN"})
    masked_json = mask_sensitive_data(raw_json)
    parsed = json.loads(masked_json)
    assert parsed["token"] == "[REDACTED]"
    assert parsed["action"] == "LOGIN"

    # 3. String pattern redaction (Bearer tokens)
    raw_str = "Authorization header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz"
    masked_str = mask_sensitive_data(raw_str)
    assert "Bearer [REDACTED]" in masked_str
    assert "eyJhbGci" not in masked_str


def test_record_audit_event_applies_masking():
    """Verify that record_audit_event automatically masks sensitive data before saving."""
    db = SessionLocal()
    try:
        school = db.query(School).filter(School.code == "AUD-TEST").first()
        if not school:
            school = School(name="Audit Test High", code="AUD-TEST", slug="audit-test-high", school_mode="COMBINED")
            db.add(school)
            db.commit()
            db.refresh(school)

        entry = record_audit_event(
            db=db,
            actor_username_override="audit_tester",
            actor_role_override="admin",
            action="PASSWORD_CHANGE",
            details={"old_password": "OldPass123!", "new_password": "NewPass456!", "status": "COMPLETED"},
            school_id=school.id
        )

        assert entry is not None
        assert entry.id is not None
        
        # Details in database must have password redacted!
        assert "OldPass123!" not in entry.details
        assert "NewPass456!" not in entry.details
        assert "[REDACTED]" in entry.details
        assert "COMPLETED" in entry.details

    finally:
        db.close()


def test_audit_logs_tenant_isolation_and_super_admin_exclusion():
    """Verify strict multi-tenant boundaries and hiding of Super Admin actions."""
    db = SessionLocal()
    try:
        # Create School A and School B
        school_a = db.query(School).filter(School.code == "SCH-AUD-A").first()
        if not school_a:
            school_a = School(name="Audit School A", code="SCH-AUD-A", slug="audit-school-a", school_mode="COMBINED")
            db.add(school_a)
            db.commit()
            db.refresh(school_a)

        school_b = db.query(School).filter(School.code == "SCH-AUD-B").first()
        if not school_b:
            school_b = School(name="Audit School B", code="SCH-AUD-B", slug="audit-school-b", school_mode="COMBINED")
            db.add(school_b)
            db.commit()
            db.refresh(school_b)

        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            db.add(admin_role)
            db.commit()

        # Create Admin for School A
        admin_a = db.query(User).filter(User.username == "admin_school_a").first()
        if not admin_a:
            admin_a = User(
                username="admin_school_a",
                email="admin_a@test.local",
                password_hash=hash_password("Pass123!"),
                school_id=school_a.id,
                is_active=True
            )
            admin_a.roles.append(admin_role)
            db.add(admin_a)
            db.commit()
            db.refresh(admin_a)

        # Create audit records
        # 1. School A normal event
        record_audit_event(
            db=db,
            actor_username_override="admin_school_a",
            actor_role_override="admin",
            action="STUDENT_ENROLLMENT_A",
            details="Enrolled student Kwesi in School A",
            school_id=school_a.id
        )

        # 2. School B normal event
        record_audit_event(
            db=db,
            actor_username_override="admin_school_b",
            actor_role_override="admin",
            action="STUDENT_ENROLLMENT_B",
            details="Enrolled student Akua in School B",
            school_id=school_b.id
        )

        # 3. Super Admin action on School A
        record_audit_event(
            db=db,
            actor_username_override="superadmin",
            actor_role_override="super_admin",
            action="SUPER_ADMIN_CONFIG_RESET",
            details="Platform config changed by master superadmin",
            school_id=school_a.id,
            is_super_admin_action=True
        )

        token_a = create_jwt({
            "sub": admin_a.username,
            "user_id": admin_a.id,
            "school_id": school_a.id,
            "roles": ["admin"]
        })
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Query School A feed
        resp = client.get("/api/audit/logs", headers=headers_a)
        assert resp.status_code == 200
        data = resp.json()
        actions = [log["action"] for log in data["logs"]]

        # Admin A can see School A event
        assert "STUDENT_ENROLLMENT_A" in actions

        # Admin A CANNOT see School B event
        assert "STUDENT_ENROLLMENT_B" not in actions

        # Admin A CANNOT see Super Admin platform action
        assert "SUPER_ADMIN_CONFIG_RESET" not in actions

        # Cross-tenant query attempt by Admin A for School B must be rejected
        resp_forbidden = client.get(f"/api/audit/logs?school_id={school_b.id}", headers=headers_a)
        assert resp_forbidden.status_code == 403
        assert "access denied" in resp_forbidden.json()["detail"].lower()

    finally:
        db.close()


def test_audit_logs_filtering_and_forensic_search():
    """Verify filtering by action, entity_type, actor_username, and free text search."""
    db = SessionLocal()
    try:
        school = db.query(School).filter(School.code == "AUD-FILT").first()
        if not school:
            school = School(name="Audit Filter School", code="AUD-FILT", slug="audit-filter-school", school_mode="COMBINED")
            db.add(school)
            db.commit()
            db.refresh(school)

        admin_role = db.query(Role).filter(Role.name == "admin").first()
        admin_user = db.query(User).filter(User.username == "filter_admin").first()
        if not admin_user:
            admin_user = User(
                username="filter_admin",
                email="filter_admin@test.local",
                password_hash=hash_password("Pass123!"),
                school_id=school.id,
                is_active=True
            )
            admin_user.roles.append(admin_role)
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

        # Seed distinct records
        record_audit_event(
            db=db,
            actor_username_override="bursar_kwame",
            actor_role_override="bursar",
            action="FEE_COLLECTION",
            entity_type="Fee",
            entity_id="101",
            details="Collected term 1 boarding fees",
            school_id=school.id
        )

        record_audit_event(
            db=db,
            actor_username_override="teacher_ama",
            actor_role_override="teacher",
            action="SCORE_UPLOAD",
            entity_type="Score",
            entity_id="202",
            details="Uploaded mathematics mid-term marks",
            school_id=school.id
        )

        token = create_jwt({
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "school_id": school.id,
            "roles": ["admin"]
        })
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Filter by action
        res_action = client.get("/api/audit/logs?action=FEE_COLLECTION", headers=headers).json()
        assert all(l["action"] == "FEE_COLLECTION" for l in res_action["logs"])
        assert len(res_action["logs"]) >= 1

        # 2. Filter by entity_type
        res_entity = client.get("/api/audit/logs?entity_type=Score", headers=headers).json()
        assert all(l["entity_type"] == "Score" for l in res_entity["logs"])
        assert len(res_entity["logs"]) >= 1

        # 3. Filter by username
        res_user = client.get("/api/audit/logs?actor_username=teacher_ama", headers=headers).json()
        assert all(l["actor_username"] == "teacher_ama" for l in res_user["logs"])
        assert len(res_user["logs"]) >= 1

        # 4. Free text search
        res_search = client.get("/api/audit/logs?search=mathematics", headers=headers).json()
        assert any("mathematics" in l["details"].lower() for l in res_search["logs"])

    finally:
        db.close()


def test_audit_logs_csv_export_and_formula_defense():
    """Verify forensic CSV export sanitizes formulas and enforces Content-Disposition."""
    db = SessionLocal()
    try:
        school = db.query(School).filter(School.code == "AUD-EXP").first()
        if not school:
            school = School(name="Audit Export School", code="AUD-EXP", slug="audit-export-school", school_mode="COMBINED")
            db.add(school)
            db.commit()
            db.refresh(school)

        admin_role = db.query(Role).filter(Role.name == "admin").first()
        admin_user = db.query(User).filter(User.username == "export_admin").first()
        if not admin_user:
            admin_user = User(
                username="export_admin",
                email="export_admin@test.local",
                password_hash=hash_password("Pass123!"),
                school_id=school.id,
                is_active=True
            )
            admin_user.roles.append(admin_role)
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

        # Create record with formula injection payload in details
        record_audit_event(
            db=db,
            actor_username_override="=cmd|'/C calc'!A0",
            actor_role_override="admin",
            action="=2+2",
            details="@SUM(1,2)",
            school_id=school.id
        )

        token = create_jwt({
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "school_id": school.id,
            "roles": ["admin"]
        })
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/audit/export", headers=headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "Content-Disposition" in resp.headers
        assert "attachment; filename=\"audit_logs_" in resp.headers["Content-Disposition"]

        csv_text = resp.text
        # Check formula prefixes neutralized with single quote "'"
        assert "'=cmd|'/C calc'!A0" in csv_text
        assert "'=2+2" in csv_text
        assert "'@SUM(1,2)" in csv_text

    finally:
        db.query(AuditLog).filter(AuditLog.school_id == school.id).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_audit_logs_unauthorized_access_rejected():
    """Verify that unauthenticated callers and non-admin staff are rejected."""
    # 1. No token -> 401
    resp_no_token = client.get("/api/audit/logs")
    assert resp_no_token.status_code == 401

    # 2. Student role without admin privileges -> 403
    db = SessionLocal()
    try:
        student_role = db.query(Role).filter(Role.name == "student").first()
        if not student_role:
            student_role = Role(name="student")
            db.add(student_role)
            db.commit()

        student_user = db.query(User).filter(User.username == "student_kofi").first()
        if not student_user:
            student_user = User(
                username="student_kofi",
                email="student_kofi@test.local",
                password_hash=hash_password("Pass123!"),
                school_id=1,
                is_active=True
            )
            student_user.roles.append(student_role)
            db.add(student_user)
            db.commit()
            db.refresh(student_user)

        student_token = create_jwt({
            "sub": student_user.username,
            "user_id": student_user.id,
            "school_id": student_user.school_id,
            "roles": ["student"]
        })
        resp_forbidden = client.get("/api/audit/logs", headers={"Authorization": f"Bearer {student_token}"})
        assert resp_forbidden.status_code == 403
    finally:
        db.close()


if __name__ == "__main__":
    test_mask_sensitive_data_redaction()
    test_record_audit_event_applies_masking()
    test_audit_logs_tenant_isolation_and_super_admin_exclusion()
    test_audit_logs_filtering_and_forensic_search()
    test_audit_logs_csv_export_and_formula_defense()
    test_audit_logs_unauthorized_access_rejected()
    print("ALL AUDIT AND FORENSIC VISIBILITY TESTS PASSED!")
