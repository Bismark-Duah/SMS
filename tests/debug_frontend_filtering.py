import os
import sys
import json
sys.path.insert(0, os.path.abspath("backend"))

from app.database import SessionLocal
from app.models import User
from app.routes.auth import list_users
from app.routes.assignments import list_assignments, list_privileges

def debug_sim():
    db = SessionLocal()
    admin = db.query(User).filter(User.username == "admin").first()
    
    # 1. Fetch Users
    raw_users = list_users(db=db)
    # Serialize to JSON as frontend receives
    users_json = json.loads(json.dumps([
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "roles": [{"id": r.id, "name": r.name} for r in u.roles]
        } for u in raw_users
    ]))

    # Filter allTeachers as assignments.js line 46 does:
    allTeachers = [u for u in users_json if u.get("roles") and any(r["name"].lower() not in ["student", "parent"] for r in u["roles"])]
    print(f"allTeachers count: {len(allTeachers)}")

    # 2. Fetch Assignments
    asgns = list_assignments(db=db, current_user=admin)
    allAssignmentsData = asgns

    # 3. Fetch Privileges
    privs = list_privileges(db=db, current_user=admin)
    allPrivilegesData = json.loads(json.dumps([
        {
            "id": p.id,
            "teacher_id": p.teacher_id,
            "teacher_name": p.teacher_name,
            "privilege_type": p.privilege_type,
            "target_id": p.target_id,
            "target_name": p.target_name
        } for p in privs
    ]))
    print(f"allPrivilegesData count: {len(allPrivilegesData)}")

    # 4. Construct Teacher Profiles Map (exact assignments.js lines 305-345)
    teacherMap = {}
    for t in allTeachers:
        teacherId = t["id"]
        teacherName = t.get("full_name") or t.get("username")

        tAsgns = [a for a in allAssignmentsData if str(a.get("teacher_id")) == str(teacherId)]
        tPrivs = [p for p in allPrivilegesData if str(p.get("teacher_id")) == str(teacherId)]

        # Role-based fallback check (exact assignments.js logic)
        roleNames = [r["name"].lower() for r in t.get("roles", [])]
        if "hod" in roleNames and not any("hod" in (p.get("privilege_type") or "").lower() for p in tPrivs):
            tPrivs.append({
                "id": f"fallback-hod-{teacherId}",
                "teacher_id": teacherId,
                "teacher_name": teacherName,
                "privilege_type": "Head of Department (HOD)",
                "target_name": "Department Leadership"
            })

        teacherMap[teacherId] = {
            "id": teacherId,
            "name": teacherName,
            "email": t.get("email") or "Staff Member",
            "assignmentsCount": len(tAsgns),
            "privilegesCount": len(tPrivs),
            "privileges": tPrivs,
            "rawUser": t
        }

    teacherProfiles = list(teacherMap.values())
    print(f"Total teacherProfiles: {len(teacherProfiles)}")

    # 5. Filter by currentRoleFilter = 'hod'
    hod_profiles = [
        tp for tp in teacherProfiles if any(
            "hod" in (p.get("privilege_type") or "").lower() or
            "head of department" in (p.get("privilege_type") or "").lower() or
            "department" in (p.get("privilege_type") or "").lower()
            for p in tp["privileges"]
        )
    ]
    print(f"\nHOD Profiles count found: {len(hod_profiles)}")
    for hp in hod_profiles:
        print(f"  - Teacher ID {hp['id']}: {hp['name']} | Privileges: {[p['privilege_type'] + ' (' + str(p['target_name']) + ')' for p in hp['privileges']]}")

    db.close()

if __name__ == "__main__":
    debug_sim()
