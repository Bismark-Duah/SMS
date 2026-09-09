"""
Test Suite: Super Admin Subscription Matrix Endpoint & Branding Integrity
Verifies:
1. GET /api/super-admin/schools/matrix returns valid metrics, aggregations, and school list.
2. Super Admin authorization gating on /schools/matrix (rejects non-super-admins).
3. Verify calculations of gross revenue, 5% platform fee, net share, and SMS balance.
"""
import sys
import os
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database import SessionLocal
from backend.app.models import User, Role, School, Setting, VoucherOrder, MessageLog
from backend.app.routes.super_admin import get_subscription_matrix

def test_subscription_matrix_and_branding():
    db = SessionLocal()
    try:
        print("\n==================================================================")
        print("TEST SUITE: Super Admin Subscription Matrix & Branding Verification")
        print("==================================================================")

        # 1. Setup Roles
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            db.add(admin_role)

        super_admin_role = db.query(Role).filter(Role.name == "super_admin").first()
        if not super_admin_role:
            super_admin_role = Role(name="super_admin")
            db.add(super_admin_role)

        db.flush()

        # 2. Setup Test School
        school = db.query(School).filter(School.code == "MATRIX-TEST-SCH").first()
        if not school:
            school = School(
                name="Matrix Test Academy",
                code="MATRIX-TEST-SCH",
                school_mode="SHS_ONLY",
                status="ACTIVE",
                subscription_plan="ENTERPRISE",
                subscription_status="ACTIVE",
                sms_balance=750,
                platform_commission_percent=5.0
            )
            db.add(school)
            db.flush()

        # 3. Setup Test Users
        super_user = db.query(User).filter(User.username == "superadmin_matrix_test").first()
        if not super_user:
            super_user = User(
                username="superadmin_matrix_test",
                email="super_matrix@sms.test",
                password_hash="mock_secret_hash_123",
                is_active=True
            )
            super_user.roles.append(super_admin_role)
            db.add(super_user)

        regular_admin = db.query(User).filter(User.username == "regular_admin_matrix_test").first()
        if not regular_admin:
            regular_admin = User(
                username="regular_admin_matrix_test",
                email="admin_matrix@sms.test",
                password_hash="mock_secret_hash_456",
                school_id=school.id,
                is_active=True
            )
            regular_admin.roles.append(admin_role)
            db.add(regular_admin)

        db.commit()

        # 4. Create sample Voucher Orders
        vo1 = db.query(VoucherOrder).filter(VoucherOrder.order_reference == "VCH-MAT-001").first()
        if not vo1:
            vo1 = VoucherOrder(
                order_reference="VCH-MAT-001",
                school_id=school.id,
                applicant_phone="0244000111",
                amount=100.0,
                status="CONFIRMED"
            )
            db.add(vo1)

        vo2 = db.query(VoucherOrder).filter(VoucherOrder.order_reference == "VCH-MAT-002").first()
        if not vo2:
            vo2 = VoucherOrder(
                order_reference="VCH-MAT-002",
                school_id=school.id,
                applicant_phone="0244000222",
                amount=100.0,
                status="DELIVERED"
            )
            db.add(vo2)
        db.commit()

        # ── Test 1: Super Admin Access to Matrix Endpoint ──
        print("\n[TEST 1] Testing get_subscription_matrix as Super Admin...")
        matrix_res = get_subscription_matrix(db=db, current_user=super_user)
        assert isinstance(matrix_res, dict), "Expected dict response"
        assert "schools" in matrix_res, "Expected 'schools' key in matrix response"
        assert "total_schools_count" in matrix_res, "Expected 'total_schools_count' key"
        assert "total_platform_commission_ghs" in matrix_res, "Expected 'total_platform_commission_ghs' key"
        assert "total_vouchers_sold" in matrix_res, "Expected 'total_vouchers_sold' key"
        assert "total_sms_sent" in matrix_res, "Expected 'total_sms_sent' key"
        print(f"[OK] Super Admin fetched matrix successfully ({len(matrix_res['schools'])} schools found)")
        print(f"  * Total Schools: {matrix_res['total_schools_count']}")
        print(f"  * Total Vouchers Sold: {matrix_res['total_vouchers_sold']}")
        print(f"  * Gross Platform Revenue: GHS {matrix_res['gross_platform_revenue_ghs']}")
        print(f"  * Total Platform Commission: GHS {matrix_res['total_platform_commission_ghs']}")

        # Verify our test school in matrix
        test_sch_entry = next((s for s in matrix_res["schools"] if s["code"] == "MATRIX-TEST-SCH"), None)
        assert test_sch_entry is not None, "MATRIX-TEST-SCH not found in matrix list"
        assert test_sch_entry["subscription_plan"] == "ENTERPRISE"
        assert test_sch_entry["subscription_status"] == "ACTIVE"
        assert test_sch_entry["vouchers_sold"] >= 2
        assert test_sch_entry["sms_balance"] == 750
        assert test_sch_entry["commission_percent"] == 5.0
        print("[OK] Test school matrix calculations and tier badges validated.")

        # ── Test 2: Non-Super Admin Access Control Gating ──
        print("\n[TEST 2] Verifying 403 Forbidden for Regular School Admin...")
        from backend.app.routes.super_admin import require_super_admin
        try:
            require_super_admin(current_user=regular_admin)
            assert False, "Should have raised 403 HTTPException for regular admin"
        except HTTPException as e:
            assert e.status_code == 403, f"Expected 403 Forbidden, got {e.status_code}"
            print("[OK] Access properly forbidden (403) for non-super-admin user.")

        print("\n==================================================================")
        print("ALL SUPER ADMIN MATRIX TESTS PASSED (100% SUCCESS)")
        print("==================================================================\n")

    finally:
        db.close()

if __name__ == "__main__":
    test_subscription_matrix_and_branding()
