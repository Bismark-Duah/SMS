"""
Test Suite: Staff ID Integration, Contact Labeling, Admissions Branding & Public School Role Gating
"""
import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database import SessionLocal, run_migrations
from backend.app.models import User, Role, School
from backend.app.routes.auth import (
    _hash_password, login, get_current_user_profile,
    create_user, list_users, list_roles
)
from backend.app import schemas

class MockRequest:
    def __init__(self):
        self.headers = {"user-agent": "TestRunner/1.0"}
        self.state = None
        self.client = None

def test_staff_id_and_role_gating():
    run_migrations()
    db = SessionLocal()
    try:
        print("\n==================================================================")
        print("TEST SUITE: Staff ID, Contact Label, Branding & Public Role Gating")
        print("==================================================================")

        # 1. Setup Roles
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            db.add(admin_role)
            db.flush()

        proprietor_role = db.query(Role).filter(Role.name == "proprietor").first()
        if not proprietor_role:
            proprietor_role = Role(name="proprietor")
            db.add(proprietor_role)
            db.flush()

        teacher_role = db.query(Role).filter(Role.name == "teacher").first()
        if not teacher_role:
            teacher_role = Role(name="teacher")
            db.add(teacher_role)
            db.flush()

        # 2. Setup Public School and Private School
        pub_school = db.query(School).filter(School.code == "PUB-TEST-SCH").first()
        if not pub_school:
            pub_school = School(
                name="Achimota Public Basic School",
                code="PUB-TEST-SCH",
                school_mode="BASIC_ONLY",
                ownership_type="PUBLIC",
                status="ACTIVE"
            )
            db.add(pub_school)
            db.flush()
        else:
            pub_school.ownership_type = "PUBLIC"
            db.flush()

        priv_school = db.query(School).filter(School.code == "PRIV-TEST-SCH").first()
        if not priv_school:
            priv_school = School(
                name="Galaxy International Private Academy",
                code="PRIV-TEST-SCH",
                school_mode="COMBINED",
                ownership_type="PRIVATE",
                status="ACTIVE"
            )
            db.add(priv_school)
            db.flush()
        else:
            priv_school.ownership_type = "PRIVATE"
            db.flush()

        # Create Admins
        pub_admin = db.query(User).filter(User.username == "pub_admin_tester").first()
        if not pub_admin:
            pub_admin = User(
                username="pub_admin_tester",
                email="pubadmin@public.edu.gh",
                phone_number="0240000001",
                staff_id="GES-PUB-9901",
                password_hash=_hash_password("Staff@123"),
                school_id=pub_school.id,
                is_active=True
            )
            pub_admin.roles.append(admin_role)
            db.add(pub_admin)
            db.flush()
        else:
            pub_admin.staff_id = "GES-PUB-9901"
            pub_admin.password_hash = _hash_password("Staff@123")
            db.flush()

        priv_admin = db.query(User).filter(User.username == "priv_admin_tester").first()
        if not priv_admin:
            priv_admin = User(
                username="priv_admin_tester",
                email="privadmin@galaxy.edu.gh",
                phone_number="0240000002",
                staff_id="STF-PRIV-1002",
                password_hash=_hash_password("Staff@123"),
                school_id=priv_school.id,
                is_active=True
            )
            priv_admin.roles.append(admin_role)
            db.add(priv_admin)
            db.flush()

        db.commit()

        # 3. Test Login Response: includes staff_id and ownership_type
        print("\n[Step 1] Verifying Login Response for Public School Admin...")
        login_resp = login(
            payload={"username": "pub_admin_tester", "password": "Staff@123"},
            request=MockRequest(),
            db=db
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.body}"
        login_data = json.loads(login_resp.body.decode())
        assert login_data.get("staff_id") == "GES-PUB-9901", f"Expected staff_id GES-PUB-9901, got {login_data.get('staff_id')}"
        assert login_data.get("ownership_type") == "PUBLIC", f"Expected ownership_type PUBLIC, got {login_data.get('ownership_type')}"
        print("[PASS] Login returns staff_id and ownership_type successfully.")

        # 4. Test GET /me endpoint
        print("\n[Step 2] Verifying GET /api/auth/me Profile...")
        me_data = get_current_user_profile(current_user=pub_admin, db=db)
        assert me_data.get("staff_id") == "GES-PUB-9901", f"Expected staff_id GES-PUB-9901, got {me_data.get('staff_id')}"
        print("[PASS] Profile endpoint /me returns staff_id successfully.")

        # 5. Test User Creation with Staff ID
        print("\n[Step 3] Creating new Teacher with Staff ID via create_user...")
        # Clean existing test teacher if present
        existing_teacher = db.query(User).filter(User.username == "test_teacher_staffid").first()
        if existing_teacher:
            db.delete(existing_teacher)
            db.commit()

        created_user = create_user(
            payload={
                "username": "test_teacher_staffid",
                "phone_number": "0551234567",
                "staff_id": "STF-774411",
                "email": "teacher_staffid@school.edu.gh",
                "password": "Staff@123",
                "gender": "Female",
                "roles": ["teacher"]
            },
            db=db,
            current_user=pub_admin,
            school_id=pub_school.id,
            x_school_id=str(pub_school.id)
        )
        assert created_user.staff_id == "STF-774411", f"Created user missing staff_id: {created_user.staff_id}"
        print("[PASS] User created with staff_id successfully.")

        # 6. Test list_users contains staff_id
        print("\n[Step 4] Verifying staff_id in list_users output...")
        users_list = list_users(
            db=db,
            current_user=pub_admin,
            school_id=pub_school.id,
            x_school_id=str(pub_school.id)
        )
        found_user = next((u for u in users_list if u.username == "test_teacher_staffid"), None)
        assert found_user is not None
        assert getattr(found_user, "staff_id", None) == "STF-774411"
        print("[PASS] User list includes staff_id field.")

        # 7. Test Role Gating for Public vs Private School
        print("\n[Step 5] Verifying Role Gating on list_roles (Public School)...")
        pub_roles_objs = list_roles(
            db=db,
            school_id=pub_school.id,
            x_school_id=str(pub_school.id)
        )
        pub_roles = [r.name.lower() for r in pub_roles_objs]
        assert "proprietor" not in pub_roles, f"Proprietor role should be excluded for PUBLIC school: {pub_roles}"
        print("[PASS] Proprietor role is excluded for Public schools.")

        print("\n[Step 6] Verifying Role Gating on list_roles (Private School)...")
        priv_roles_objs = list_roles(
            db=db,
            school_id=priv_school.id,
            x_school_id=str(priv_school.id)
        )
        priv_roles = [r.name.lower() for r in priv_roles_objs]
        assert "proprietor" in priv_roles, f"Proprietor role should be present for PRIVATE school: {priv_roles}"
        print("[PASS] Proprietor role is present for Private schools.")

        # 8. Test Frontend HTML & JS Assertions
        print("\n[Step 7] Checking Frontend files for Contact label, Staff ID, Orion Tech purge, and emoji cleanup...")
        
        # users.html checks
        with open("frontend/users.html", "r", encoding="utf-8") as f:
            users_html = f.read()
        assert "Contact <span" in users_html, "users.html missing 'Contact' label"
        assert "Ghana Phone Number" not in users_html, "users.html still has 'Ghana Phone Number'"
        assert 'id="staffId"' in users_html, "users.html missing #staffId input"
        assert 'placeholder="Staff ID"' in users_html, "users.html missing Staff ID placeholder"
        assert "GES No" not in users_html, "users.html should not contain 'GES No'"
        assert "👨‍👩‍👧" not in users_html, "users.html should not contain parent emoji"
        assert "✏️ Edit User Roles" not in users_html, "users.html should not contain edit emoji"
        assert "🔑 Reset Password" not in users_html, "users.html should not contain key emoji"
        print("[PASS] frontend/users.html assertions passed.")

        # enrollment.html checks
        with open("frontend/enrollment.html", "r", encoding="utf-8") as f:
            enrollment_html = f.read()
        assert "ORION TECH" not in enrollment_html, "enrollment.html still contains 'ORION TECH'"
        assert "Enter 6-digit verification code received via SMS / MoMo:" in enrollment_html, "enrollment.html missing updated prompt"
        print("[PASS] frontend/enrollment.html assertions passed.")

        # users.js checks
        with open("frontend/js/users.js", "r", encoding="utf-8") as f:
            users_js = f.read()
        assert "staff_id" in users_js, "users.js missing staff_id handling"
        assert "r.privateOnly && isPublicSchool" in users_js, "users.js missing public school proprietor gating"
        assert "🏛️" not in users_js, "users.js should not contain decorative emojis in roles"
        assert "👨‍🏫" not in users_js, "users.js should not contain decorative emojis in roles"
        print("[PASS] frontend/js/users.js assertions passed.")

        print("\n==================================================================")
        print("ALL 7 VERIFICATION STEPS PASSED SUCCESSFULLY!")
        print("==================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    test_staff_id_and_role_gating()
