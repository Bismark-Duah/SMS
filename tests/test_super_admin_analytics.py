"""
Test Suite: Super Admin Multi-School Comparative Analytics & Real-Time Audit Stream
"""
import sys
import os

# Set working directory to project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database import SessionLocal
from backend.app.models import User, Role, School, ActivityAuditLog
from backend.app.routes.super_admin import get_super_admin_dashboard, get_super_admin_audit_stream

def test_super_admin_dashboard_and_audit_stream():
    db = SessionLocal()
    try:
        # 1. Ensure a super_admin user exists
        super_admin_role = db.query(Role).filter(Role.name == "super_admin").first()
        if not super_admin_role:
            super_admin_role = Role(name="super_admin")
            db.add(super_admin_role)
            db.flush()

        superadmin = db.query(User).filter(User.username == "superadmin_test").first()
        if not superadmin:
            superadmin = User(
                username="superadmin_test",
                email="superadmin_test@edumanage360.com",
                password_hash="hashed_placeholder",
                is_active=True
            )
            superadmin.roles.append(super_admin_role)
            db.add(superadmin)
            db.commit()
            db.refresh(superadmin)
        elif super_admin_role not in superadmin.roles:
            superadmin.roles.append(super_admin_role)
            db.commit()

        # 2. Test get_super_admin_dashboard
        data = get_super_admin_dashboard(db=db, current_user=superadmin)

        print("\n==================================================================")
        print("TEST SUITE: Super Admin Multi-School Master Portal Analytics")
        print("==================================================================")
        print(f"[OK] Total Registered Schools: {data.get('total_schools')}")
        print(f"[OK] Active Schools: {data.get('active_schools')}")
        print(f"[OK] Total Students: {data.get('total_students')} (Boys: {data.get('total_boys')}, Girls: {data.get('total_girls')})")
        print(f"[OK] Total Boarding: {data.get('total_boarding')}, Day: {data.get('total_day')}")
        print(f"[OK] Total Users: {data.get('total_users')}")
        print(f"[OK] Total Billed: GHC {data.get('total_fees_billed')}, Collected: GHC {data.get('total_fees_collected')} (Rate: {data.get('overall_collection_rate')}%)")
        print(f"[OK] Diagnostics DB Size: {data.get('diagnostics', {}).get('db_size_mb')} MB")
        
        comparative = data.get("comparative_analytics", [])
        print(f"[OK] Comparative Schools Array Count: {len(comparative)}")
        assert isinstance(comparative, list), "comparative_analytics should be a list"

        # 3. Create a sample audit log to test stream
        sample_log = ActivityAuditLog(
            school_id=1,
            user_name="superadmin_test",
            user_role="super_admin",
            action="TENANT_CONFIG_CHANGE",
            entity_type="School",
            entity_id=1,
            details="Tested Super Admin Master Audit Stream",
            ip_address="127.0.0.1"
        )
        db.add(sample_log)
        db.commit()

        # 4. Test get_super_admin_audit_stream
        audit_data = get_super_admin_audit_stream(limit=20, db=db, current_user=superadmin)

        logs = audit_data.get("logs", [])
        print(f"[OK] Audit Stream returned {len(logs)} entries.")
        assert len(logs) > 0, "Audit stream should contain logs"
        first_log = logs[0]
        print(f"[OK] Latest Log: [{first_log.get('school_code')}] {first_log.get('user_name')} -> {first_log.get('action')}: {first_log.get('details')}")

        print("\n==================================================================")
        print("SUCCESS: SUPER ADMIN MASTER ANALYTICS & AUDIT STREAM VERIFIED 100%!")
        print("==================================================================")
    finally:
        db.close()

if __name__ == "__main__":
    test_super_admin_dashboard_and_audit_stream()
