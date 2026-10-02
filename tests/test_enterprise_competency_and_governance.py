import sys
import os
import requests

sys.path.insert(0, os.path.abspath('.'))

from backend.app.database import SessionLocal
from backend.app.models import User, Role, Subject, Semester, TeacherAssignment
from backend.app.services.auth import create_jwt
from backend.app.middleware.device_session_guard import register_device_session

def test_enterprise_competency_and_governance():
    db = SessionLocal()
    admin = db.query(User).join(User.roles).filter(Role.name == "admin").first()
    assert admin is not None, "Admin user must exist"

    token = create_jwt({"user_id": admin.id, "sub": admin.username, "roles": [r.name for r in admin.roles]})
    register_device_session(
        user_id=admin.id,
        user_role="admin",
        user_agent="EnterpriseTestRig/1.0",
        client_ip="127.0.0.1",
        token=token,
        db=db
    )
    db.commit()

    headers = {"Authorization": f"Bearer {token}"}
    base = "http://127.0.0.1:8000/api"

    print("\n--- 1. Testing HR Capability Domain: Permanent Competency Update ---")
    # Find a regular teacher to test
    teacher = db.query(User).filter(
        User.school_id == admin.school_id,
        User.id != admin.id
    ).first()
    assert teacher is not None, "School teacher must exist"
    
    physics_subj = db.query(Subject).filter(
        (Subject.name.ilike("%Physics%")) | (Subject.code.ilike("%PHY%"))
    ).first()
    assert physics_subj is not None, "Physics subject must exist"

    payload_comp = {
        "staff_id": "GES-ENT-7788",
        "primary_subject_id": physics_subj.id,
        "max_weekly_periods": 22,
        "responsibility_role": "FORM_MASTER",
        "is_teaching_exempt": False
    }
    r = requests.put(f"{base}/auth/users/{teacher.id}/competencies", headers=headers, json=payload_comp)
    assert r.status_code == 200, f"competencies update failed: {r.text}"
    comp_data = r.json()
    print("Competency update response:", comp_data)
    assert comp_data.get("primary_subject_id") == physics_subj.id
    assert comp_data.get("primary_subject_name") == physics_subj.name

    # Check GET /auth/users returns serialized competency
    r = requests.get(f"{base}/auth/users", headers=headers)
    assert r.status_code == 200
    users_list = r.json()
    t_in_list = next((u for u in users_list if u["id"] == teacher.id), None)
    assert t_in_list is not None
    assert t_in_list.get("primary_subject_name") == physics_subj.name
    print(f"Verified HR Profile for {teacher.username}: Staff ID={t_in_list.get('staff_id')}, Primary Subject={t_in_list.get('primary_subject_name')}")

    print("\n--- 2. Testing Autonomous Solver Intelligence ---")
    cur_sem = db.query(Semester).filter(Semester.is_current == True).first()
    sem_id = cur_sem.id if cur_sem else 1

    r = requests.post(f"{base}/timetable/auto-generate", headers=headers, json={
        "semester_id": sem_id,
        "periods_per_day": 8,
        "friday_periods": 6
    })
    assert r.status_code == 200, f"auto-generate failed: {r.text}"
    gen_data = r.json()
    print("Solver Status:", gen_data.get("status"))
    print("Total Slots Placed:", gen_data.get("total_slots"))
    print("Quality Score:", gen_data.get("quality_report", {}).get("score"))

    # Verify TeacherAssignments were auto-matched
    ta_count = db.query(TeacherAssignment).filter(TeacherAssignment.semester_id == sem_id).count()
    print(f"Active TeacherAssignment records for Semester {sem_id}: {ta_count}")
    assert ta_count > 0, "Autonomous solver should match and persist teacher assignments"

    print("\n--- 3. Testing GES Workload Governance & Compliance Audit ---")
    r = requests.get(f"{base}/timetable/teacher-workloads", headers=headers)
    assert r.status_code == 200, f"teacher-workloads failed: {r.text}"
    workloads = r.json()
    print(f"Loaded {len(workloads)} staff workload records.")
    sample = workloads[0] if workloads else {}
    print("Sample Workload Record:", {
        "teacher": sample.get("teacher_name"),
        "role": sample.get("role_title"),
        "department": sample.get("department_name"),
        "primary_subject": sample.get("primary_subject_name"),
        "assigned": sample.get("assigned_periods"),
        "cap": sample.get("max_cap"),
        "compliance": sample.get("compliance_status")
    })
    # Check compliance categories exist
    statuses = set(w.get("compliance_status") for w in workloads)
    print("Detected GES Compliance Statuses across staff:", statuses)
    assert any(s in ["OPTIMAL", "EXEMPT", "UNDERLOADED", "OVERLOADED"] for s in statuses)

    print("\n--- 4. Testing 1-Click Term Rollover ---")
    # Ensure a second semester exists for rollover
    sem2 = db.query(Semester).filter(Semester.id != sem_id).first()
    if not sem2:
        sem2 = Semester(name="Semester 2 (Test)", academic_year_id=1, is_current=False)
        db.add(sem2)
        db.commit()

    # Clear target semester assignments first
    db.query(TeacherAssignment).filter(TeacherAssignment.semester_id == sem2.id).delete()
    db.commit()

    r = requests.post(f"{base}/timetable/rollover-assignments", headers=headers, json={
        "source_semester_id": sem_id,
        "target_semester_id": sem2.id
    })
    assert r.status_code == 200, f"rollover failed: {r.text}"
    roll_data = r.json()
    print("Rollover Response:", roll_data)
    assert roll_data.get("status") == "SUCCESS"
    assert roll_data.get("copied_count") > 0, "Must copy assignments to the new semester"

    copied_in_db = db.query(TeacherAssignment).filter(TeacherAssignment.semester_id == sem2.id).count()
    print(f"Verified {copied_in_db} allocations carried over into Semester {sem2.id} with 0 keystrokes!")

    print("\n[OK] ALL TWO-TIER ENTERPRISE ERP CAPABILITY & GOVERNANCE TESTS PASSED 100%!")
    db.close()

if __name__ == "__main__":
    test_enterprise_competency_and_governance()
