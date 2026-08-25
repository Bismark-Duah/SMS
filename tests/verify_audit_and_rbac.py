import os
import sys
import json
from fastapi import HTTPException

# Ensure backend path is available
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import School, User, Role, ActivityAuditLog, Score, Subject, Student, Semester
from backend.app.services.audit import AuditService
from backend.app.routes.audit import get_audit_logs
from backend.app.dependencies import get_user_assigned_scope

def run_tests():
    print("================================================================")
    print("TEST SUITE: Phase 3 Audit Trail, PWA Offline Store & RBAC")
    print("================================================================")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Setup Roles & Users
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            db.add(admin_role)
            db.commit()

        teacher_role = db.query(Role).filter(Role.name == "teacher").first()
        if not teacher_role:
            teacher_role = Role(name="teacher")
            db.add(teacher_role)
            db.commit()

        admin_user = db.query(User).filter(User.username == "test_admin_phase3").first()
        if not admin_user:
            admin_user = User(username="test_admin_phase3", email="admin_phase3@school.com", password_hash="dummy", school_id=1)
            admin_user.roles.append(admin_role)
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

        teacher_user = db.query(User).filter(User.username == "test_teacher_phase3").first()
        if not teacher_user:
            teacher_user = User(username="test_teacher_phase3", email="teacher_phase3@school.com", password_hash="dummy", school_id=1)
            teacher_user.roles.append(teacher_role)
            db.add(teacher_user)
            db.commit()
            db.refresh(teacher_user)

        # 2. Test AuditService.log() Directly
        log_entry = AuditService.log(
            db=db,
            action="SCORE_UPDATE",
            entity_type="Score",
            entity_id=999,
            details={"old_grade": "B2", "new_grade": "A1", "reason": "Remarking"},
            user=admin_user,
            school_id=1,
            ip_address="192.168.1.50"
        )
        assert log_entry is not None, "Audit log entry should be created"
        assert log_entry.action == "SCORE_UPDATE"
        assert log_entry.user_name == "test_admin_phase3"
        print(f"[OK] AuditService.log successfully recorded: Action={log_entry.action}, User={log_entry.user_name}")

        # 3. Test get_audit_logs endpoint function as Admin (Allowed)
        admin_res = get_audit_logs(
            action=None, entity_type=None, search=None, limit=50, offset=0,
            current_user=admin_user, db=db
        )
        assert "logs" in admin_res
        assert admin_res["total"] >= 1
        print(f"[OK] Admin GET /api/audit/logs verified: {admin_res['total']} total audit logs returned")

        # 4. Test get_audit_logs endpoint function as Teacher (Forbidden - RBAC check)
        teacher_forbidden = False
        try:
            get_audit_logs(
                action=None, entity_type=None, search=None, limit=50, offset=0,
                current_user=teacher_user, db=db
            )
        except HTTPException as exc:
            if exc.status_code == 403:
                teacher_forbidden = True
        assert teacher_forbidden, "Teacher must be blocked from accessing institutional audit logs"
        print(f"[OK] RBAC Scope Guard verified: Teacher blocked from accessing institutional audit logs (HTTP 403)")

        # 5. Test Scope Evaluation
        admin_scope = get_user_assigned_scope(admin_user, db)
        assert admin_scope["is_admin"] is True, "Admin should have is_admin=True in assigned scope"

        teacher_scope = get_user_assigned_scope(teacher_user, db)
        assert teacher_scope["is_admin"] is False, "Teacher should have is_admin=False in assigned scope"
        print(f"[OK] Role Scope Evaluation verified: Admin is_admin={admin_scope['is_admin']}, Teacher is_admin={teacher_scope['is_admin']}")

        # 6. Verify Offline Store & Service Worker Files
        frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
        offline_store_path = os.path.join(frontend_dir, "js", "offline-store.js")
        sw_path = os.path.join(frontend_dir, "sw.js")

        assert os.path.exists(offline_store_path), "offline-store.js must exist"
        assert os.path.exists(sw_path), "sw.js must exist"

        with open(offline_store_path, "r", encoding="utf-8") as f:
            offline_code = f.read()
            assert "indexedDB.open" in offline_code
            assert "pending_scores" in offline_code
            assert "cached_rosters" in offline_code
            assert "syncPendingData" in offline_code
        print("[OK] PWA Offline Store JavaScript verified: IndexedDB schema & sync methods present")

        with open(sw_path, "r", encoding="utf-8") as f:
            sw_code = f.read()
            assert "STATIC_ASSETS" in sw_code
            assert "offline-store.js" in sw_code
        print("[OK] Service Worker cache manifest verified: PWA offline assets listed")

        print("\n================================================================")
        print("SUCCESS: ALL PHASE 3 AUDIT, PWA & RBAC TESTS PASSED 100%!")
        print("================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
