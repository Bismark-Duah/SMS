import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.database import SessionLocal, engine, run_migrations
from app.models import School, User, Role, Setting, Student, ClassSection, Subject, Semester, AcademicYear, Score
from app.routes.auth import list_roles
from app.routes.fees import get_fee_summary, require_admin
from app.routes.settings import get_settings
from app.routes.academic import get_executive_analytics
from fastapi import HTTPException

def run_universal_hierarchy_and_rbac_test_suite():
    print("=" * 60)
    print(" UNIVERSAL GHANAIAN SCHOOL HIERARCHY & RBAC TEST SUITE")
    print("=" * 60)

    run_migrations()
    db = SessionLocal()
    try:
        # 1. Setup Public Basic School
        pub_basic = db.query(School).filter(School.code == "PUB-BAS-001").first()
        if not pub_basic:
            pub_basic = School(
                name="Accra Presby Public Basic School",
                code="PUB-BAS-001",
                slug="accra-presby-basic",
                school_mode="BASIC_ONLY",
                ownership_type="PUBLIC",
                boarding_type="DAY_ONLY"
            )
            db.add(pub_basic)
            db.commit()
            db.refresh(pub_basic)
        else:
            pub_basic.ownership_type = "PUBLIC"
            db.commit()

        # 2. Setup Private Basic School
        pvt_basic = db.query(School).filter(School.code == "PVT-BAS-001").first()
        if not pvt_basic:
            pvt_basic = School(
                name="Crown Preparatory Private Basic School",
                code="PVT-BAS-001",
                slug="crown-preparatory",
                school_mode="BASIC_ONLY",
                ownership_type="PRIVATE",
                boarding_type="BOARDING_AND_DAY"
            )
            db.add(pvt_basic)
            db.commit()
            db.refresh(pvt_basic)
        else:
            pvt_basic.ownership_type = "PRIVATE"
            db.commit()

        # 3. Setup Public SHS
        pub_shs = db.query(School).filter(School.code == "PUB-SHS-001").first()
        if not pub_shs:
            pub_shs = School(
                name="Accra Academy Public SHS",
                code="PUB-SHS-001",
                slug="accra-academy",
                school_mode="SHS_ONLY",
                ownership_type="PUBLIC",
                boarding_type="BOARDING_AND_DAY"
            )
            db.add(pub_shs)
            db.commit()
            db.refresh(pub_shs)
        else:
            pub_shs.ownership_type = "PUBLIC"
            db.commit()

        # 4. Setup Private SHS
        pvt_shs = db.query(School).filter(School.code == "PVT-SHS-001").first()
        if not pvt_shs:
            pvt_shs = School(
                name="Ideal College Private Senior High",
                code="PVT-SHS-001",
                slug="ideal-college",
                school_mode="SHS_ONLY",
                ownership_type="PRIVATE",
                boarding_type="BOARDING_AND_DAY"
            )
            db.add(pvt_shs)
            db.commit()
            db.refresh(pvt_shs)
        else:
            pvt_shs.ownership_type = "PRIVATE"
            db.commit()

        print("\n[1] Testing Dynamic Role Filtering by School Ownership (Public vs Private)...")
        # Public Basic School: Proprietor must NOT be listed
        roles_pub_bas = list_roles(db=db, school_id=pub_basic.id)
        role_names_pub_bas = [r.name.lower() for r in roles_pub_bas]
        assert "proprietor" not in role_names_pub_bas, "Proprietor role MUST be suppressed in Public Basic School"
        assert "headmaster" in role_names_pub_bas
        assert "school_administrator" in role_names_pub_bas
        assert "ict_coordinator" in role_names_pub_bas
        assert "secretary" in role_names_pub_bas
        print(f"   [OK] Public Basic School ({pub_basic.name}): 'proprietor' suppressed, operational roles active.")

        # Private Basic School: Proprietor MUST be listed
        roles_pvt_bas = list_roles(db=db, school_id=pvt_basic.id)
        role_names_pvt_bas = [r.name.lower() for r in roles_pvt_bas]
        assert "proprietor" in role_names_pvt_bas, "Proprietor role MUST be active in Private Basic School"
        print(f"   [OK] Private Basic School ({pvt_basic.name}): 'proprietor' role available.")

        # Public SHS: Proprietor must NOT be listed
        roles_pub_shs = list_roles(db=db, school_id=pub_shs.id)
        role_names_pub_shs = [r.name.lower() for r in roles_pub_shs]
        assert "proprietor" not in role_names_pub_shs, "Proprietor role MUST be suppressed in Public SHS"
        assert "school_administrator" in role_names_pub_shs
        assert "ict_coordinator" in role_names_pub_shs
        print(f"   [OK] Public SHS ({pub_shs.name}): 'proprietor' suppressed, 'headmaster' active.")

        # Private SHS: Proprietor MUST be listed
        roles_pvt_shs = list_roles(db=db, school_id=pvt_shs.id)
        role_names_pvt_shs = [r.name.lower() for r in roles_pvt_shs]
        assert "proprietor" in role_names_pvt_shs, "Proprietor role MUST be active in Private SHS"
        assert "school_administrator" in role_names_pvt_shs
        assert "ict_coordinator" in role_names_pvt_shs
        assert "secretary" in role_names_pvt_shs
        print(f"   [OK] Private SHS ({pvt_shs.name}): All operational and executive roles verified.")

        print("\n[2] Testing Separation of Duties (SoD) & Zero-Trust Route Access...")
        # Roles
        bursar_role = db.query(Role).filter(Role.name == "bursar").first()
        teacher_role = db.query(Role).filter(Role.name == "teacher").first()
        sec_role = db.query(Role).filter(Role.name == "secretary").first()
        prop_role = db.query(Role).filter(Role.name == "proprietor").first()
        admin_officer_role = db.query(Role).filter(Role.name == "school_administrator").first()
        if not admin_officer_role:
            admin_officer_role = Role(name="school_administrator")
            db.add(admin_officer_role)
            db.commit()

        ict_role = db.query(Role).filter(Role.name == "ict_coordinator").first()
        if not ict_role:
            ict_role = Role(name="ict_coordinator")
            db.add(ict_role)
            db.commit()

        # Users
        bursar_user = db.query(User).filter(User.username == "test_bursar_rbac").first()
        if not bursar_user:
            bursar_user = User(username="test_bursar_rbac", password_hash="hash", school_id=pvt_basic.id, is_first_login=False)
            bursar_user.roles.append(bursar_role)
            db.add(bursar_user)
            db.commit()
            db.refresh(bursar_user)

        teacher_user = db.query(User).filter(User.username == "test_teacher_rbac").first()
        if not teacher_user:
            teacher_user = User(username="test_teacher_rbac", password_hash="hash", school_id=pvt_basic.id, is_first_login=False)
            teacher_user.roles.append(teacher_role)
            db.add(teacher_user)
            db.commit()
            db.refresh(teacher_user)

        sec_user = db.query(User).filter(User.username == "test_secretary_rbac").first()
        if not sec_user:
            sec_user = User(username="test_secretary_rbac", password_hash="hash", school_id=pvt_basic.id, is_first_login=False)
            sec_user.roles.append(sec_role)
            db.add(sec_user)
            db.commit()
            db.refresh(sec_user)

        prop_user = db.query(User).filter(User.username == "test_proprietor_rbac").first()
        if not prop_user:
            prop_user = User(username="test_proprietor_rbac", password_hash="hash", school_id=pvt_basic.id, is_first_login=False)
            prop_user.roles.append(prop_role)
            db.add(prop_user)
            db.commit()
            db.refresh(prop_user)

        school_admin_user = db.query(User).filter(User.username == "test_school_admin_officer").first()
        if not school_admin_user:
            school_admin_user = User(username="test_school_admin_officer", password_hash="hash", school_id=pvt_basic.id, is_first_login=False)
            school_admin_user.roles.append(admin_officer_role)
            db.add(school_admin_user)
            db.commit()
            db.refresh(school_admin_user)

        ict_user = db.query(User).filter(User.username == "test_ict_coord_rbac").first()
        if not ict_user:
            ict_user = User(username="test_ict_coord_rbac", password_hash="hash", school_id=pvt_basic.id, is_first_login=False)
            ict_user.roles.append(ict_role)
            db.add(ict_user)
            db.commit()
            db.refresh(ict_user)

        # 1. Test require_admin(bursar_user) -> passes (Bursar has finance access)
        require_admin(bursar_user)
        fee_sum = get_fee_summary(db=db, current_user=bursar_user)
        assert "total_billed" in fee_sum
        print("   [OK] Bursar access to financial summary: PERMITTED (200 OK)")

        # 2. Test require_admin(teacher_user) -> raises 403 (Teacher cannot access financial ledgers)
        try:
            get_fee_summary(db=db, current_user=teacher_user)
            assert False, "Teacher MUST be forbidden from accessing financial summary"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"   [OK] Teacher access to fees blocked: 403 Forbidden ({e.detail})")

        # 3. Test require_admin(sec_user) -> raises 403 (Secretary cannot access bank/fee summary)
        try:
            get_fee_summary(db=db, current_user=sec_user)
            assert False, "Secretary MUST be forbidden from accessing financial summary"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"   [OK] Secretary access to fees blocked: 403 Forbidden ({e.detail})")

        # 4. Test require_admin(school_admin_user) -> raises 403 (School Admin Officer cannot access financial collections)
        try:
            get_fee_summary(db=db, current_user=school_admin_user)
            assert False, "School Administrator MUST be forbidden from accessing financial collection desk"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"   [OK] School Administrator access to fees blocked: 403 Forbidden ({e.detail})")

        # 5. Test require_admin(ict_user) -> raises 403 (ICT Coordinator cannot access financial collections)
        try:
            get_fee_summary(db=db, current_user=ict_user)
            assert False, "ICT Coordinator MUST be forbidden from accessing financial collection desk"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"   [OK] ICT Coordinator access to fees blocked: 403 Forbidden ({e.detail})")

        # 6. Test require_admin(prop_user) -> passes (Proprietor has full executive financial access)
        prop_sum = get_fee_summary(db=db, current_user=prop_user)
        assert "total_billed" in prop_sum
        print("   [OK] Proprietor access to financial summary: PERMITTED (200 OK)")

        print("\n[3] Testing GET /api/settings/ returns ownership_type...")
        settings_res = get_settings(db=db, current_user=prop_user, school_id=pvt_basic.id)
        assert "ownership_type" in settings_res
        assert settings_res["ownership_type"] == "PRIVATE"
        print(f"   [OK] Private School Settings verified: ownership_type='{settings_res['ownership_type']}'")

        pub_settings_res = get_settings(db=db, current_user=None, school_id=pub_basic.id)
        assert pub_settings_res.get("ownership_type") == "PUBLIC"
        print(f"   [OK] Public School Settings verified: ownership_type='{pub_settings_res['ownership_type']}'")

        print("\n" + "=" * 60)
        print(" ALL UNIVERSAL HIERARCHY & RBAC TESTS PASSED SUCCESSFULLY!")
        print("=" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    run_universal_hierarchy_and_rbac_test_suite()
