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

def run_all():
    print("==================================================")
    print(" SMS SYSTEM-WIDE UNIFIED VERIFICATION SUITE       ")
    print("==================================================")

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
        "scripts/test_multi_school_onboarding.py"
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

