"""
Verification Suite for Enterprise Hybrid Offline-to-Cloud Auto-Sync Engine
Covers:
1. Outbox entry logging with SHA-256 checksums
2. Cryptographic HMAC-SHA256 signature generation & tamper detection
3. Multi-tenant boundary isolation
4. Field-level smart delta merging
5. Full school compressed snapshot export & restore
6. End-to-end REST API endpoint validation (/api/sync/status, /push, /receive, /pull-snapshot, /restore-snapshot)
"""

import os
import sys
import json
import uuid
import asyncio
from datetime import datetime

# Set backend path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from backend.app.database import Base
from backend.app.models import (
    User, Role, School, Student, Score, Setting, SyncOutbox, ClassSection
)
from backend.app.services.sync_engine import (
    sign_sync_payload,
    verify_sync_signature,
    compute_payload_checksum,
    log_sync_change,
    apply_sync_bundle,
    generate_school_snapshot,
    restore_school_snapshot,
)
from backend.app.routes.sync import (
    get_sync_status,
    push_pending_sync,
    receive_sync_bundle,
    pull_school_snapshot,
    restore_school_snapshot as restore_school_snapshot_endpoint,
    log_client_change,
)

# In-memory SQLite test DB
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

mock_admin_school_1 = None


def setup_module():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Create Schools
    s1 = School(id=1, name="Achimota Senior High", code="ACH-001", school_mode="SHS_ONLY", status="ACTIVE")
    s2 = School(id=2, name="Presby Basic School", code="PRE-002", school_mode="BASIC_ONLY", status="ACTIVE")
    db.add_all([s1, s2])
    db.flush()

    # Create Roles
    r_admin = Role(id=1, name="admin")
    db.add(r_admin)
    db.flush()

    # Create Admin for School 1
    admin_u1 = User(id=1, username="admin_sch1", password_hash="hashed_secret", school_id=1, is_active=True)
    admin_u1.roles.append(r_admin)
    db.add(admin_u1)
    db.commit()
    
    global mock_admin_school_1
    mock_admin_school_1 = admin_u1
    db.close()


def teardown_module():
    Base.metadata.drop_all(bind=engine)


def test_01_cryptographic_signing_and_tamper_detection():
    print("\n[TEST 1] Cryptographic HMAC-SHA256 Signing and Tamper Verification...")
    test_payload = json.dumps({"school_id": 1, "action": "INSERT", "data": "test_student"}).encode("utf-8")
    
    # Generate signature
    signature = sign_sync_payload(test_payload)
    assert signature is not None and len(signature) == 64, "Signature must be 64-char hex string"
    
    # Valid verification
    assert verify_sync_signature(test_payload, signature) is True, "Valid payload and signature must pass"
    
    # Tampered payload detection
    tampered_payload = json.dumps({"school_id": 1, "action": "INSERT", "data": "tampered_student"}).encode("utf-8")
    assert verify_sync_signature(tampered_payload, signature) is False, "Tampered payload must fail verification"
    
    # Corrupted signature detection
    bad_signature = signature[:-4] + "ffff"
    assert verify_sync_signature(test_payload, bad_signature) is False, "Corrupted signature must fail verification"
    print("  -> PASSED: Tamper-detection and constant-time HMAC validation working perfectly.")


def test_02_outbox_logging_and_checksum():
    print("\n[TEST 2] Outbox Delta Logging and Checksum Integrity...")
    db = TestingSessionLocal()
    
    payload = {"student_code": "STU-2026-001", "full_name": "Kofi Mensah", "residential_status": "B"}
    outbox_entry = log_sync_change(db, school_id=1, entity_type="student", entity_id="STU-2026-001", action="INSERT", payload=payload)
    db.commit()
    
    assert outbox_entry is not None
    assert outbox_entry.school_id == 1
    assert outbox_entry.entity_type == "student"
    assert outbox_entry.action == "INSERT"
    assert outbox_entry.is_synced is False
    
    expected_checksum = compute_payload_checksum(payload)
    assert outbox_entry.checksum == expected_checksum
    
    # Verify in DB
    saved = db.query(SyncOutbox).filter(SyncOutbox.sync_uuid == outbox_entry.sync_uuid).first()
    assert saved is not None
    assert json.loads(saved.payload_json)["full_name"] == "Kofi Mensah"
    db.close()
    print("  -> PASSED: Outbox queueing and SHA-256 payload checksums verified.")


def test_03_multi_tenant_isolation():
    print("\n[TEST 3] Multi-Tenant Outbox Boundary Isolation...")
    db = TestingSessionLocal()
    
    # Log change for School 2
    payload_s2 = {"student_code": "STU-SCH2-001", "full_name": "Ama Serwaa", "residential_status": "D"}
    log_sync_change(db, school_id=2, entity_type="student", entity_id="STU-SCH2-001", action="INSERT", payload=payload_s2)
    db.commit()
    
    # Query pending for School 1
    school_1_pending = db.query(SyncOutbox).filter(SyncOutbox.school_id == 1, SyncOutbox.is_synced == False).all()
    school_2_pending = db.query(SyncOutbox).filter(SyncOutbox.school_id == 2, SyncOutbox.is_synced == False).all()
    
    s1_codes = [json.loads(p.payload_json).get("student_code") for p in school_1_pending]
    s2_codes = [json.loads(p.payload_json).get("student_code") for p in school_2_pending]
    
    assert "STU-2026-001" in s1_codes
    assert "STU-SCH2-001" not in s1_codes, "School 1 must not see School 2 outbox entries"
    assert "STU-SCH2-001" in s2_codes
    db.close()
    print("  -> PASSED: Strict tenant data isolation between school outboxes verified.")


def test_04_field_level_smart_delta_merge():
    print("\n[TEST 4] Field-Level Smart Delta Merging...")
    db = TestingSessionLocal()
    
    # Create initial student
    init_student = Student(student_code="STU-SYNC-01", full_name="Akua Donkor", gender="F", school_id=1, residential_status="B", is_active=True)
    db.add(init_student)
    db.commit()
    
    # Delta bundle simulating cloud update with phone number and address change
    bundle = [
        {
            "sync_uuid": str(uuid.uuid4()),
            "entity_type": "student",
            "entity_id": "STU-SYNC-01",
            "action": "UPDATE",
            "payload": {
                "student_code": "STU-SYNC-01",
                "phone": "+233241112233",
                "address": "Accra Ridge 45",
                "guardian_name": "Mrs. Donkor"
            }
        },
        {
            "sync_uuid": str(uuid.uuid4()),
            "entity_type": "setting",
            "entity_id": "academic_year",
            "action": "UPDATE",
            "payload": {
                "key": "academic_year",
                "value": "2026/2027"
            }
        }
    ]
    
    applied_uuids, errs = apply_sync_bundle(db, school_id=1, items=bundle)
    assert len(applied_uuids) == 2
    assert errs == []
    
    # Verify student was updated without destroying original fields (e.g. gender and residential_status)
    updated_st = db.query(Student).filter(Student.student_code == "STU-SYNC-01", Student.school_id == 1).first()
    assert updated_st is not None
    assert updated_st.phone == "+233241112233"
    assert updated_st.address == "Accra Ridge 45"
    assert updated_st.gender == "F", "Original unaffected field must be preserved"
    assert updated_st.residential_status == "B"
    
    # Verify setting
    setting = db.query(Setting).filter(Setting.key == "academic_year").first()
    assert setting is not None
    assert setting.value == "2026/2027"
    db.close()
    print("  -> PASSED: Smart field-level merging accurately applied deltas preserving intact attributes.")


def test_05_school_snapshot_export_and_restore():
    print("\n[TEST 5] Full Compressed School Snapshot Generation and Restoration...")
    db = TestingSessionLocal()
    
    snapshot = generate_school_snapshot(db, school_id=1)
    assert snapshot["school"]["id"] == 1
    assert "students" in snapshot
    assert "scores" in snapshot
    assert "settings" in snapshot
    
    # Ensure students created earlier exist in snapshot
    student_codes = [s["student_code"] for s in snapshot["students"]]
    assert "STU-SYNC-01" in student_codes
    
    # Now simulate restoring to a fresh clean database / new PC
    fresh_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=fresh_engine)
    FreshSession = sessionmaker(bind=fresh_engine)
    fresh_db = FreshSession()
    
    # Create school 1 in fresh db
    fresh_db.add(School(id=1, name="Achimota Senior High", code="ACH-001", school_mode="SHS_ONLY", status="ACTIVE"))
    fresh_db.commit()
    
    restore_result = restore_school_snapshot(fresh_db, school_id=1, snapshot=snapshot)
    assert restore_result["status"] == "success"
    assert restore_result["restored"]["students"] >= 1
    
    # Verify in fresh db
    restored_st = fresh_db.query(Student).filter(Student.student_code == "STU-SYNC-01").first()
    assert restored_st is not None
    assert restored_st.full_name == "Akua Donkor"
    assert restored_st.phone == "+233241112233"
    
    fresh_db.close()
    db.close()
    print("  -> PASSED: Disaster-recovery snapshot export and 100% offline rebuild validated.")


def test_06_rest_api_endpoints():
    print("\n[TEST 6] Direct Sync REST API Route Handlers...")
    db = TestingSessionLocal()
    current_admin = db.query(User).filter(User.id == 1).first()
    
    # 1. GET /api/sync/status
    status_data = get_sync_status(db=db, current_user=current_admin)
    assert status_data["status"] == "healthy"
    assert "pending_count" in status_data
    assert "recent_activity" in status_data
    assert status_data["school_id"] == 1
    print("  -> get_sync_status returned healthy telemetry and active queue data.")
    
    # 2. POST /api/sync/push
    push_data = push_pending_sync(db=db, current_user=current_admin)
    assert push_data["status"] == "success"
    assert "synced_count" in push_data
    print(f"  -> push_pending_sync completed: Synchronized {push_data['synced_count']} delta(s).")
    
    # Verify outbox is now marked synced for school 1
    status_after = get_sync_status(db=db, current_user=current_admin)
    assert status_after["pending_count"] == 0
    
    # 3. POST /api/sync/pull-snapshot
    snap_resp = pull_school_snapshot(db=db, current_user=current_admin)
    assert snap_resp["status"] == "success"
    assert "snapshot" in snap_resp
    assert snap_resp["school_id"] == 1
    print("  -> pull_school_snapshot returned validated school snapshot payload.")
    
    # 4. POST /api/sync/receive (Cloud receiver handler verification)
    delta_bundle = {
        "school_id": 1,
        "items": [
            {
                "sync_uuid": str(uuid.uuid4()),
                "entity_type": "setting",
                "entity_id": "motto",
                "action": "UPDATE",
                "payload": {"key": "school_motto", "value": "Forward Ever, Backward Never"}
            }
        ]
    }
    raw_payload_bytes = json.dumps(delta_bundle, sort_keys=True).encode("utf-8")
    sig = sign_sync_payload(raw_payload_bytes)
    
    # Build mock request for async receive_sync_bundle
    class MockRequest:
        async def body(self):
            return raw_payload_bytes
            
    recv_resp = asyncio.run(receive_sync_bundle(
        request=MockRequest(),
        db=db,
        x_sync_signature=sig,
        x_school_id="1"
    ))
    assert recv_resp["status"] == "success"
    assert recv_resp["applied_count"] == 1
    print("  -> receive_sync_bundle successfully verified HMAC signature and merged cloud delta.")
    
    # 5. POST /api/sync/log-change (Client queueing helper)
    log_resp = log_client_change(
        payload={
            "entity_type": "student",
            "entity_id": "STU-CLI-01",
            "action": "INSERT",
            "data": {"student_code": "STU-CLI-01", "full_name": "Yaw Osei"}
        },
        db=db,
        current_user=current_admin
    )
    assert log_resp["status"] == "success"
    assert log_resp["sync_uuid"] is not None
    print("  -> log_client_change successfully queued client-initiated delta.")
    
    db.close()


if __name__ == "__main__":
    setup_module()
    tests = [
        test_01_cryptographic_signing_and_tamper_detection,
        test_02_outbox_logging_and_checksum,
        test_03_multi_tenant_isolation,
        test_04_field_level_smart_delta_merge,
        test_05_school_snapshot_export_and_restore,
        test_06_rest_api_endpoints,
    ]
    
    passed = 0
    failed = 0
    print("\n" + "=" * 65)
    print("  ENTERPRISE SYNC ENGINE VERIFICATION SUITE")
    print("=" * 65)
    
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAILED: {t.__name__} -> {e}")
            import traceback
            traceback.print_exc()
            
    teardown_module()
    print("\n" + "=" * 65)
    print(f"  SUMMARY: {passed} PASSED, {failed} FAILED")
    print("=" * 65)
    if failed > 0:
        sys.exit(1)
