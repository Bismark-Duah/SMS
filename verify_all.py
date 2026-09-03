"""
Unified End-to-End Verification Test Suite for School Management System
"""
import subprocess
import sys
import time
import urllib.request
import urllib.error

def is_server_running(url="http://127.0.0.1:8000/health"):
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False

def ensure_server():
    if is_server_running():
        return None
    print("\n[INFO] Starting temporary Uvicorn server for API integration tests...")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app.main:app", "--port", "8000"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        time.sleep(0.5)
        if is_server_running():
            print("[INFO] Uvicorn server is up and responding!")
            return proc
    print("[WARNING] Uvicorn server failed to start within timeout.")
    return proc

import os

def run_script(name):
    print(f"\nRunning: {name}...")
    try:
        env = os.environ.copy()
        root_dir = os.path.abspath(".")
        backend_dir = os.path.abspath("backend")
        env["PYTHONPATH"] = root_dir + os.pathsep + backend_dir + os.pathsep + env.get("PYTHONPATH", "")
        res = subprocess.run([sys.executable, name], capture_output=True, text=True, check=True, env=env)
        print(f"   [PASS] {name}")
        return True, res.stdout
    except subprocess.CalledProcessError as e:
        print(f"   [FAIL] {name}")
        print("--- Error Output ---")
        print(e.stderr or e.stdout)
        print("--------------------")
        return False, e.stderr or e.stdout

def _bootstrap_test_environment():
    try:
        from backend.app.database import SessionLocal, Base, engine
        from backend.app.models import User, Role, School, SchoolStage, user_roles
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        
        # Clean up any orphan user_roles
        valid_uids = [u.id for u in db.query(User.id).all()]
        db.execute(user_roles.delete().where(~user_roles.c.user_id.in_(valid_uids)))
        db.commit()

        # Ensure default roles exist
        from backend.app.routes.auth import DEFAULT_ROLES
        for r_name in DEFAULT_ROLES:
            if not db.query(Role).filter(Role.name == r_name).first():
                db.add(Role(name=r_name))
        db.commit()

        # Ensure a default test school exists for unit tests
        school = db.query(School).filter(School.id == 1).first()
        if not school:
            school = School(id=1, name="Test Academy", code="TEST-ACADEMY", school_mode="COMBINED", boarding_type="BOARDING_AND_DAY", status="ACTIVE")
            db.add(school)
            db.commit()

        # Ensure default test admin exists
        admin = db.query(User).filter(User.username == "admin").first()
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin:
            from backend.app.routes.auth import _hash_password
            admin = User(
                username="admin",
                email="admin@test.com",
                password_hash=_hash_password("admin123"),
                school_id=school.id,
                is_active=True
            )
            if admin_role:
                admin.roles.append(admin_role)
            db.add(admin)
            db.commit()
        elif admin_role and admin_role not in admin.roles:
            admin.roles.append(admin_role)
            db.commit()

        db.close()
    except Exception as e:
        print(f"[NOTE] Test environment bootstrap: {e}")

def run_all():
    print("==================================================")
    print(" SMS SYSTEM-WIDE UNIFIED VERIFICATION SUITE       ")
    print("==================================================")

    _bootstrap_test_environment()

    test_scripts = [
        "tests/verify_promotions.py",
        "tests/verify_messaging.py",
        "tests/verify_parent_portal.py",
        "tests/verify_academic_hierarchy.py",
        "tests/verify_report_card.py",
        "tests/verify_boarding_config.py",
        "tests/verify_sba_weighting.py",
        "tests/verify_backup.py",
        "tests/verify_rollover.py",
        "tests/verify_attendance_sms.py",
        "tests/verify_fee_sms.py",
        "tests/verify_discipline_sms.py",
        "tests/verify_report_publish_sms.py",
        "tests/verify_exeat.py",
        "tests/verify_guardian_autolink.py",
        "tests/verify_assignments.py",
        "tests/verify_program_subjects.py",
        "tests/verify_privileges.py",
        "tests/verify_departments.py",
        "tests/verify_timetable.py",
        "tests/verify_notifications.py",
        "tests/verify_association.py",
        "tests/verify_phase3.py",
        "tests/verify_phase5.py",
        "tests/test_analytics_endpoints.py",
        "tests/verify_ncca_curriculum.py",
        "tests/verify_house_auto_allocation.py",
        "tests/verify_school_modes.py",
        "tests/test_subject_level_filtering.py",
        "scripts/test_multi_school_onboarding.py",
        "backend/tests/test_saas_multi_tenant_financials.py",
        "backend/tests/test_admission_package_pdf.py",
        "backend/tests/test_fees_online_payments.py",
        "backend/tests/test_broadsheet_and_batch_reports.py",
        "backend/tests/test_attendance_scanner_and_truancy.py",
        "backend/tests/test_transcripts_and_promotions.py",
        "backend/tests/test_timetable_engine_and_pdf.py",
        "backend/tests/test_state_bus_and_live_reactivity.py",
        "backend/tests/test_multi_tenant_scoping_and_view.py",
        "tests/verify_enterprise_sync_engine.py",
        "tests/verify_super_admin_sync_monitor.py",
        "tests/test_sync_engine_hardening.py",
        "tests/test_sqlite_wal_and_concurrency.py",
        "tests/test_fee_financial_audit.py",
        "tests/test_academic_engine_audit.py",
        "tests/test_security_audit_hardening.py",
        "tests/test_offline_pwa_audit.py",
        "tests/test_adversary_and_edge_rigor.py",
        "tests/test_performance_and_scalability.py",
        "tests/test_devops_and_infrastructure.py"
    ]

    server_proc = ensure_server()

    results = {}
    all_passed = True

    try:
        for script in test_scripts:
            passed, out = run_script(script)
            results[script] = "PASS" if passed else "FAIL"
            if not passed:
                all_passed = False
    finally:
        if server_proc:
            print("\n[INFO] Terminating temporary Uvicorn server...")
            server_proc.terminate()

    print("\n==================================================")
    print("               VERIFICATION REPORT                ")
    print("==================================================")
    for script, status in results.items():
        color_code = "[PASS]" if status == "PASS" else "[FAIL]"
        print(f" {color_code:<8} {script:<30} : {status}")
    print("==================================================")

    if all_passed:
        print(f" ALL {len(test_scripts)} SYSTEM VERIFICATION TESTS PASSED!")
        sys.exit(0)
    else:
        print(" SOME SYSTEM VERIFICATION SCRIPTS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    run_all()

