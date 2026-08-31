import sys
import os
import re

# Ensure backend is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.database import SessionLocal, engine, run_migrations
from app.models import School, User, Role
from app.routes.auth import create_user, complete_onboarding, login, admin_reset_password, impersonate_user
from fastapi import HTTPException
from unittest.mock import MagicMock

def run_staff_onboarding_suite():
    print("=" * 60)
    print(" STAFF OPTIONAL CREDENTIALS & FIRST-LOGIN ONBOARDING TEST SUITE")
    print("=" * 60)

    # Run auto-migrations to ensure all columns exist
    run_migrations()

    db = SessionLocal()
    try:
        # 1. Setup Test School
        test_sch = db.query(School).filter(School.name == "Onboarding Test School").first()
        if not test_sch:
            test_sch = School(
                name="Onboarding Test School",
                code="OTS-001",
                slug="onboarding-test-school",
                school_mode="BASIC_ONLY",
                boarding_type="DAY_ONLY"
            )
            db.add(test_sch)
            db.commit()
            db.refresh(test_sch)

        # Mock Admin User
        admin_user = db.query(User).filter(User.username == "admin_onboard_test").first()
        if not admin_user:
            admin_user = User(
                username="admin_onboard_test",
                email="admin_onboard@test.com",
                password_hash="hash",
                school_id=test_sch.id,
                is_first_login=False
            )
            admin_role = db.query(Role).filter(Role.name == "admin").first()
            if not admin_role:
                admin_role = Role(name="admin")
                db.add(admin_role)
                db.commit()
            admin_user.roles.append(admin_role)
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

        # Cleanup test teacher if exists
        old_teacher = db.query(User).filter(User.username == "teacher_mensah_test").first()
        if old_teacher:
            db.delete(old_teacher)
            db.commit()

        print("\n[1] Testing Staff Creation with ZERO Email & ZERO Phone (100% Optional)...")
        payload = {
            "username": "teacher_mensah_test",
            "password": "Staff@123",
            "roles": ["teacher"],
            "gender": "Male"
            # Notice: email and phone_number are omitted completely!
        }

        new_teacher = create_user(
            payload=payload,
            db=db,
            current_user=admin_user,
            school_id=test_sch.id
        )

        assert new_teacher.username == "teacher_mensah_test"
        assert new_teacher.email is None, f"Expected None, got {new_teacher.email}"
        assert new_teacher.phone_number is None, f"Expected None, got {new_teacher.phone_number}"
        assert new_teacher.is_first_login is True, "Expected is_first_login=True"
        print(f"   [OK] Teacher created: {new_teacher.username} (Email: {new_teacher.email}, Phone: {new_teacher.phone_number}, FirstLogin: {new_teacher.is_first_login})")

        print("\n[2] Testing Initial Login with Starter Password...")
        mock_req = MagicMock()
        mock_req.headers.get.return_value = "Mozilla/5.0"
        mock_req.client.host = "127.0.0.1"
        mock_req.state.client_ip = "127.0.0.1"

        print(f"   [DEBUG] new_teacher: id={new_teacher.id}, active={new_teacher.is_active}, hash={new_teacher.password_hash}")
        from app.routes.auth import _verify_password
        print(f"   [DEBUG] Direct verify: {_verify_password('Staff@123', new_teacher.password_hash)}")

        login_res = login(
            payload={"username": "teacher_mensah_test", "password": "Staff@123"},
            request=mock_req,
            db=db
        )
        import json
        login_body = json.loads(login_res.body.decode("utf-8"))
        print(f"   [DEBUG] Login Status: {login_res.status_code}, Body: {login_body}")
        assert login_res.status_code == 200
        assert login_body["is_first_login"] is True, "Login response must signal is_first_login=True"
        print(f"   [OK] Login successful. Response flagged is_first_login: {login_body['is_first_login']}")

        print("\n[3] Testing POST /api/auth/complete-onboarding (Teacher Self-Profile Setup)...")
        onboard_payload = {
            "phone_number": "0244123456",
            "email": "kwame.mensah.real@gmail.com",
            "new_password": "MySecretPassword@2026"
        }

        onboard_res = complete_onboarding(
            payload=onboard_payload,
            db=db,
            current_user=new_teacher
        )

        assert onboard_res["status"] == "success"
        assert onboard_res["user"]["phone_number"] == "0244123456"
        assert onboard_res["user"]["email"] == "kwame.mensah.real@gmail.com"
        assert onboard_res["user"]["is_first_login"] is False

        # Refetch from DB
        db.refresh(new_teacher)
        assert new_teacher.phone_number == "0244123456"
        assert new_teacher.email == "kwame.mensah.real@gmail.com"
        assert new_teacher.is_first_login is False
        print(f"   [OK] Onboarding successfully persisted: Phone={new_teacher.phone_number}, Email={new_teacher.email}, FirstLogin={new_teacher.is_first_login}")

        print("\n[4] Testing Login with New Private Password...")
        login_after = login(
            payload={"username": "teacher_mensah_test", "password": "MySecretPassword@2026"},
            request=mock_req,
            db=db
        )
        login_after_body = json.loads(login_after.body.decode("utf-8"))
        assert login_after.status_code == 200
        assert login_after_body["is_first_login"] is False
        assert login_after_body["phone_number"] == "0244123456"
        assert login_after_body["email"] == "kwame.mensah.real@gmail.com"
        print(f"   [OK] Private password authenticated. Profile confirmed ready for dashboard.")

        print("\n[5] Testing Admin Reset Password (Re-arms is_first_login)...")
        reset_res = admin_reset_password(
            user_id=new_teacher.id,
            payload={"new_password": "TempStaff@2026"},
            db=db,
            current_user=admin_user
        )
        assert reset_res["status"] == "success"
        db.refresh(new_teacher)
        assert new_teacher.is_first_login is True, "Admin reset must re-arm is_first_login flag!"
        print(f"   [OK] Admin reset executed. is_first_login re-armed: {new_teacher.is_first_login}")

        print("\n[6] Testing Admin 'View As' Impersonation without Password...")
        imp_res = impersonate_user(
            user_id=new_teacher.id,
            db=db,
            current_user=admin_user
        )
        assert imp_res["is_impersonating"] is True
        assert imp_res["username"] == "teacher_mensah_test"
        assert "access_token" in imp_res
        print(f"   [OK] Admin impersonated {imp_res['username']} successfully with token.")

        print("\n" + "=" * 60)
        print(" ALL STAFF ONBOARDING & OPTIONAL CREDENTIALS TESTS PASSED!")
        print("=" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    run_staff_onboarding_suite()
