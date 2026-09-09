"""
Test Suite: Super Admin Centralized Fintech & SMS Gateway Governance and RBAC Security Masking
Verifies:
1. School Admins cannot view raw secret keys (Paystack SK, Hubtel Secret, mNotify API key) in GET /api/settings/.
2. School Admins cannot mutate or overwrite Gateway parameters via PUT /api/settings/.
3. Super Admins have exclusive authority over POST /api/super-admin/gateways/paystack and /gateways/sms.
4. Non-Super Admins receive 403 Forbidden when attempting to access Super Admin gateway endpoints.
"""
import sys
import os
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database import SessionLocal
from backend.app.models import User, Role, School, Setting
from backend.app.routes.settings import get_settings, update_settings
from backend.app.routes.super_admin import (
    get_master_gateways,
    update_master_paystack_gateway,
    update_master_sms_gateway,
    MasterPaystackSchema,
    MasterSmsSchema
)

def test_gateway_centralization_and_security_masking():
    db = SessionLocal()
    try:
        print("\n==================================================================")
        print("TEST SUITE: Centralized Gateway Security & RBAC Masking Audit")
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
        school = db.query(School).filter(School.code == "GATEWAY-SEC-TEST").first()
        if not school:
            school = School(
                name="Gateway Security Academy",
                code="GATEWAY-SEC-TEST",
                school_mode="COMBINED",
                status="ACTIVE"
            )
            db.add(school)
            db.flush()

        # 3. Setup School Admin User
        school_admin = db.query(User).filter(User.username == "school_admin_gateway_test").first()
        if not school_admin:
            school_admin = User(
                username="school_admin_gateway_test",
                email="sch_admin@test.edu",
                password_hash="test_hash",
                school_id=school.id,
                is_active=True
            )
            school_admin.roles.append(admin_role)
            db.add(school_admin)
            db.flush()

        # 4. Setup Super Admin User
        super_admin = db.query(User).filter(User.username == "super_admin_gateway_test").first()
        if not super_admin:
            super_admin = User(
                username="super_admin_gateway_test",
                email="master_super@test.edu",
                password_hash="test_hash",
                is_active=True
            )
            super_admin.roles.append(super_admin_role)
            db.add(super_admin)
            db.flush()

        db.commit()

        # 5. Super Admin configures Master Gateways
        print("\n[Step 1] Super Admin saves Master Paystack & SMS Gateway Keys...")
        paystack_payload = MasterPaystackSchema(
            paystack_enabled="true",
            paystack_public_key="pk_live_super_master_12345",
            paystack_secret_key="sk_live_super_master_secret_67890"
        )
        res_ps = update_master_paystack_gateway(
            payload=paystack_payload,
            db=db,
            current_user=super_admin
        )
        assert res_ps["status"] == "success"

        sms_payload = MasterSmsSchema(
            sms_gateway_provider="MNOTIFY",
            mnotify_api_key="mnotify_master_secret_key_abc123",
            hubtel_client_id="hubtel_master_id_xyz",
            hubtel_client_secret="hubtel_master_secret_pass_999"
        )
        res_sms = update_master_sms_gateway(
            payload=sms_payload,
            db=db,
            current_user=super_admin
        )
        assert res_sms["status"] == "success"
        print("  [OK] Master Paystack & SMS keys securely committed by Super Admin.")

        # 6. Verify Super Admin reading master gateways
        print("\n[Step 2] Super Admin reads Master Gateways endpoint...")
        master_data = get_master_gateways(db=db, current_user=super_admin)
        assert master_data["paystack"]["paystack_public_key"] == "pk_live_super_master_12345"
        assert master_data["paystack"]["paystack_secret_key"] == "sk_live_super_master_secret_67890"
        assert master_data["sms"]["mnotify_api_key"] == "mnotify_master_secret_key_abc123"
        print("  [OK] Super Admin retrieves exact unmasked master credentials.")

        # 7. Non-Super Admin blocked from Master Gateways endpoint
        print("\n[Step 3] Verifying RBAC blocks School Admin from Super Admin endpoints...")
        from backend.app.routes.super_admin import require_super_admin
        try:
            require_super_admin(current_user=school_admin)
            assert False, "School admin should be blocked by require_super_admin"
        except HTTPException as exc:
            assert exc.status_code == 403
            print(f"  [OK] Non-super admin blocked by require_super_admin: {exc.detail}")

        # Super admin passes require_super_admin
        val_user = require_super_admin(current_user=super_admin)
        assert val_user.id == super_admin.id
        print("  [OK] Super admin successfully validated by require_super_admin.")

        # 8. School Admin GET /api/settings/ must return masked secrets
        print("\n[Step 4] School Admin fetches settings via GET /api/settings/...")
        sch_settings = get_settings(
            db=db,
            current_user=school_admin,
            school_id=school.id
        )
        assert sch_settings.get("paystack_secret_key") == "••••••••••••••••", "Paystack secret key must be masked for school admin"
        assert sch_settings.get("mnotify_api_key") == "••••••••••••••••", "mNotify API key must be masked for school admin"
        assert sch_settings.get("hubtel_client_secret") == "••••••••••••••••", "Hubtel client secret must be masked for school admin"
        print("  [OK] Paystack SK, Hubtel Secret, and mNotify API key are masked.")

        # 9. School Admin attempting PUT /api/settings/ cannot overwrite gateway keys
        print("\n[Step 5] School Admin attempts to maliciously overwrite Paystack & SMS keys via PUT /api/settings/...")
        hack_payload = {
            "school_name": "Tampered Name",
            "paystack_secret_key": "sk_live_hacked_secret_key",
            "paystack_public_key": "pk_live_hacked_public_key",
            "mnotify_api_key": "mnotify_hacked_key",
            "system_theme": "emerald"
        }
        update_settings(
            payload=hack_payload,
            db=db,
            current_user=school_admin,
            school_id=school.id
        )

        # Verify in DB that master settings remained UNCHANGED
        master_ps_sk = db.query(Setting).filter(Setting.key == "paystack_secret_key", Setting.school_id == None).first()
        master_ps_pk = db.query(Setting).filter(Setting.key == "paystack_public_key", Setting.school_id == None).first()
        master_sms_key = db.query(Setting).filter(Setting.key == "mnotify_api_key", Setting.school_id == None).first()

        assert master_ps_sk.value == "sk_live_super_master_secret_67890", "Master Paystack SK must NOT be tampered by school admin"
        assert master_ps_pk.value == "pk_live_super_master_12345", "Master Paystack PK must NOT be tampered by school admin"
        assert master_sms_key.value == "mnotify_master_secret_key_abc123", "Master SMS key must NOT be tampered by school admin"
        print("  [OK] Locked gateway parameters were stripped; Master keys remained 100% untampered!")

        print("\n==================================================================")
        print("ALL TESTS PASSED: Centralized Gateway Security & RBAC Masking Verified!")
        print("==================================================================\n")

    finally:
        db.close()

if __name__ == "__main__":
    test_gateway_centralization_and_security_masking()
