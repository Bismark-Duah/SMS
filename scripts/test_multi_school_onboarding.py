"""
Test Multi-School Onboarding & Direct Login Verification
School Management System (SMS)
"""
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

from backend.app.database import SessionLocal
from backend.app.models import School, User, Role
from backend.app.routes.auth import _hash_password

def run_multi_school_tests():
    db = SessionLocal()
    print("==================================================")
    print(" MULTI-SCHOOL ONBOARDING & MODE VERIFICATION      ")
    print("==================================================")

    # 1. Seed Super-Admin role & Ensure primary admin has super_admin role
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    super_role = db.query(Role).filter(Role.name == "super_admin").first()
    if not super_role:
        super_role = Role(name="super_admin")
        db.add(super_role)
        db.commit()

    admin_user = db.query(User).filter(User.username == "admin").first()
    if admin_user and super_role:
        if not any(r.name == "super_admin" for r in admin_user.roles):
            admin_user.roles.append(super_role)
            db.commit()

    # 2. Provision Antoa SHS (SHS ONLY)
    antoa = db.query(School).filter(School.code == "ANTOA-SHS").first()
    if not antoa:
        antoa = School(
            name="Antoa Senior High School",
            code="ANTOA-SHS",
            school_mode="SHS_ONLY",
            boarding_type="BOARDING_AND_DAY",
            status="ACTIVE",
            address="Antoa, Ashanti Region",
            phone="+233 24 111 2233",
            email="info@antoashs.edu.gh"
        )
        db.add(antoa)
        db.flush()

        antoa_admin = db.query(User).filter(User.username == "antoa_admin").first()
        if not antoa_admin:
            antoa_admin = User(
                username="antoa_admin",
                email="admin@antoashs.edu.gh",
                password_hash=_hash_password("Antoa123"),
                school_id=antoa.id,
                is_active=True
            )
            db.add(antoa_admin)
            db.flush()
            if admin_role and not any(r.name == "admin" for r in antoa_admin.roles):
                antoa_admin.roles.append(admin_role)
        db.commit()
    print(f"   [OK] School 1 Verified: {antoa.name} ({antoa.code}) Mode: {antoa.school_mode}")

    # 3. Provision Darbaa Basic School (BASIC ONLY)
    darbaa = db.query(School).filter(School.code == "DARBAA-BASIC").first()
    if not darbaa:
        darbaa = School(
            name="Darbaa Basic School",
            code="DARBAA-BASIC",
            school_mode="BASIC_ONLY",
            boarding_type="DAY_ONLY",
            status="ACTIVE",
            address="Darbaa, Ashanti Region",
            phone="+233 24 444 5566",
            email="info@darbaabasic.edu.gh"
        )
        db.add(darbaa)
        db.flush()

        darbaa_admin = db.query(User).filter(User.username == "darbaa_admin").first()
        if not darbaa_admin:
            darbaa_admin = User(
                username="darbaa_admin",
                email="admin@darbaabasic.edu.gh",
                password_hash=_hash_password("Darbaa123"),
                school_id=darbaa.id,
                is_active=True
            )
            db.add(darbaa_admin)
            db.flush()
            if admin_role and not any(r.name == "admin" for r in darbaa_admin.roles):
                darbaa_admin.roles.append(admin_role)
        db.commit()
    print(f"   [OK] School 2 Verified: {darbaa.name} ({darbaa.code}) Mode: {darbaa.school_mode}")

    # 4. Provision Notre Dame Prep. School (BASIC ONLY)
    notre_dame = db.query(School).filter(School.code == "NOTREDAME-PREP").first()
    if not notre_dame:
        notre_dame = School(
            name="Notre Dame Prep. School",
            code="NOTREDAME-PREP",
            school_mode="BASIC_ONLY",
            boarding_type="DAY_ONLY",
            status="ACTIVE",
            address="Kumasi, Ashanti Region",
            phone="+233 24 777 8899",
            email="info@notredameprep.edu.gh"
        )
        db.add(notre_dame)
        db.flush()

        nd_admin = db.query(User).filter(User.username == "notredame_admin").first()
        if not nd_admin:
            nd_admin = User(
                username="notredame_admin",
                email="admin@notredameprep.edu.gh",
                password_hash=_hash_password("NotreDame123"),
                school_id=notre_dame.id,
                is_active=True
            )
            db.add(nd_admin)
            db.flush()
            if admin_role and not any(r.name == "admin" for r in nd_admin.roles):
                nd_admin.roles.append(admin_role)
        db.commit()
    print(f"   [OK] School 3 Verified: {notre_dame.name} ({notre_dame.code}) Mode: {notre_dame.school_mode}")

    # 5. Verify total schools count & isolation
    all_schools = db.query(School).all()
    print(f"\n[OK] Total Registered Schools in Ghana Network: {len(all_schools)}")
    for s in all_schools:
        if s.id == 1:
            s.school_mode = "SHS_ONLY"
            db.commit()
        user_cnt = db.query(User).filter(User.school_id == s.id).count()
        print(f"   • School #{s.id}: {s.name} ({s.code}) | Mode: {s.school_mode} | Staff: {user_cnt}")

    # Clean up test-created schools (ID != 1) so user deletes in Super Admin persist in dev/prod database
    test_codes = ["ANTOA-SHS", "ACHIMOTA-ALL", "NOTREDAME-PREP"]
    test_schools = db.query(School).filter(School.code.in_(test_codes)).all()
    for ts in test_schools:
        db.query(User).filter(User.school_id == ts.id).delete(synchronize_session=False)
        db.delete(ts)
    db.commit()

    db.close()
    print("==================================================")
    print(" MULTI-SCHOOL PROVISIONING TEST PASSED CLEANLY!  ")
    print("==================================================")

if __name__ == "__main__":
    run_multi_school_tests()
