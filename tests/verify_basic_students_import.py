import os
import sys
import io
from fastapi import UploadFile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import School, ClassSection, SchoolStage, Student, User, StudentHealth
from backend.app.routes.students import import_students_csv, list_students

import asyncio

async def run_test():
    print("=" * 70)
    print("TEST SUITE: Basic School Direct CSV Enrollment Pipeline")
    print("=" * 70)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Setup Basic School, Stages, and Classes
        school = db.query(School).filter(School.code == "TBASIC").first()
        if not school:
            school = School(name="Test Basic Academy", code="TBASIC", school_mode="BASIC_ONLY", boarding_type="DAY_ONLY")
            db.add(school)
            db.commit()
            db.refresh(school)

        stage_kg = db.query(SchoolStage).filter(SchoolStage.name == "Kindergarten").first()
        if not stage_kg:
            stage_kg = SchoolStage(name="Kindergarten", school_type="Basic")
            db.add(stage_kg)
            db.commit()
            db.refresh(stage_kg)

        stage_primary = db.query(SchoolStage).filter(SchoolStage.name == "Primary").first()
        if not stage_primary:
            stage_primary = SchoolStage(name="Primary", school_type="Basic")
            db.add(stage_primary)
            db.commit()
            db.refresh(stage_primary)

        stage_jhs = db.query(SchoolStage).filter(SchoolStage.name == "JHS").first()
        if not stage_jhs:
            stage_jhs = SchoolStage(name="JHS", school_type="Basic")
            db.add(stage_jhs)
            db.commit()
            db.refresh(stage_jhs)

        cls_kg2 = db.query(ClassSection).filter(ClassSection.name == "KG 2", ClassSection.school_id == school.id).first()
        if not cls_kg2:
            cls_kg2 = ClassSection(name="KG 2", stage_id=stage_kg.id, school_id=school.id)
            db.add(cls_kg2)
            db.commit()

        cls_p4 = db.query(ClassSection).filter(ClassSection.name == "Class 4B", ClassSection.school_id == school.id).first()
        if not cls_p4:
            cls_p4 = ClassSection(name="Class 4B", stage_id=stage_primary.id, school_id=school.id)
            db.add(cls_p4)
            db.commit()

        cls_jhs1 = db.query(ClassSection).filter(ClassSection.name == "JHS 1A", ClassSection.school_id == school.id).first()
        if not cls_jhs1:
            cls_jhs1 = ClassSection(name="JHS 1A", stage_id=stage_jhs.id, school_id=school.id)
            db.add(cls_jhs1)
            db.commit()

        # Clean existing test student codes if any
        db.query(Student).filter(Student.student_code.in_(["TBAS-001", "TBAS-002", "TBAS-003"])).delete(synchronize_session=False)
        db.commit()

        # 2. Sample Basic School CSV Content
        csv_text = """full_name,student_code,class_name,gender,date_of_birth,guardian_name,phone,alternative_phone,address,blood_group,allergies
Kwame Mensah,TBAS-001,Class 4B,Male,2015-06-12,Mr. Ebenezer Mensah,0244123456,0200000000,"House 12, Kumasi",O+,"Peanut allergy"
Ama Konadu,TBAS-002,KG 2,Female,2019-10-04,Madam Grace Konadu,0501234567,,"Plot 4, Sunyani",A+,
Yaw Osei,TBAS-003,JHS 1A,Male,2012-03-21,Opanin Yaw Osei,0209876543,,"Accra Enclave",B+,"Asthma"
"""

        csv_bytes = csv_text.encode("utf-8")
        upload_file = UploadFile(filename="basic_students.csv", file=io.BytesIO(csv_bytes))

        from backend.app.models import Role
        role_admin = db.query(Role).filter(Role.name == "admin").first()
        if not role_admin:
            role_admin = Role(name="admin")
            db.add(role_admin)
            db.commit()

        admin_user = db.query(User).filter(User.username == "admin_basic_tester").first()
        if not admin_user:
            admin_user = User(username="admin_basic_tester", password_hash="test_hash", school_id=school.id)
            admin_user.roles.append(role_admin)
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
        else:
            admin_user.school_id = school.id
            if role_admin not in admin_user.roles:
                admin_user.roles.append(role_admin)
            db.commit()

        # 3. Execute Direct CSV Import
        res = await import_students_csv(file=upload_file, db=db, current_user=admin_user)
        print(f"[OK] Import Result: {res}")
        assert res["status"] == "success", f"Import failed: {res}"
        assert res["imported"] == 3, f"Expected 3 imported, got {res['imported']}"

        # 4. Verify Basic Students in Database
        s1 = db.query(Student).filter(Student.student_code == "TBAS-001").first()
        assert s1 is not None, "Student 1 not found"
        assert s1.full_name == "Kwame Mensah"
        assert s1.class_section_id == cls_p4.id
        assert s1.school_type == "Basic"
        assert s1.residential_status == "D"
        assert s1.status == "ACTIVE"
        assert s1.date_of_birth is not None and str(s1.date_of_birth).startswith("2015-06-12")
        h1 = db.query(StudentHealth).filter(StudentHealth.student_id == s1.id).first()
        assert h1 is not None, "Health profile for Student 1 not found"
        assert h1.blood_group == "O+"
        assert h1.allergies == "Peanut allergy"
        print(f"[OK] Verified Student 1 (Primary): {s1.full_name} | Class: {s1.class_section.name} | DOB: {s1.date_of_birth.date()} | Blood: {h1.blood_group} | Allergies: {h1.allergies}")

        s2 = db.query(Student).filter(Student.student_code == "TBAS-002").first()
        assert s2 is not None, "Student 2 not found"
        assert s2.full_name == "Ama Konadu"
        assert s2.class_section_id == cls_kg2.id
        assert s2.school_type == "Basic"
        assert s2.residential_status == "D"
        h2 = db.query(StudentHealth).filter(StudentHealth.student_id == s2.id).first()
        assert h2 is not None and h2.blood_group == "A+"
        print(f"[OK] Verified Student 2 (KG): {s2.full_name} | Class: {s2.class_section.name} | DOB: {s2.date_of_birth.date()} | Blood: {h2.blood_group}")

        s3 = db.query(Student).filter(Student.student_code == "TBAS-003").first()
        assert s3 is not None, "Student 3 not found"
        assert s3.full_name == "Yaw Osei"
        assert s3.class_section_id == cls_jhs1.id
        assert s3.school_type == "Basic"
        assert s3.residential_status == "D"
        h3 = db.query(StudentHealth).filter(StudentHealth.student_id == s3.id).first()
        assert h3 is not None and h3.allergies == "Asthma"
        print(f"[OK] Verified Student 3 (JHS): {s3.full_name} | Class: {s3.class_section.name} | Allergies: {h3.allergies}")

        # 5. Verify API output
        student_list = list_students(db=db, current_user=admin_user)
        s1_api = next((s for s in student_list if s["student_code"] == "TBAS-001"), None)
        assert s1_api is not None
        assert s1_api["blood_group"] == "O+"
        assert s1_api["allergies"] == "Peanut allergy"
        print(f"[OK] Verified Student API Response includes health fields: blood_group='{s1_api['blood_group']}', allergies='{s1_api['allergies']}'")

        print("\n" + "=" * 70)
        print("ALL BASIC SCHOOL DIRECT ENROLLMENT TESTS PASSED 100%!")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"[ERROR]: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = asyncio.run(run_test())
    sys.exit(0 if success else 1)
