import os
import sys
import io
from fastapi import UploadFile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import School, Program, ClassSection, SchoolStage, Student, User, House, Dormitory
from backend.app.routes.students import import_students_csv, list_students

import asyncio

async def run_test():
    print("=" * 70)
    print("TEST SUITE: Continuing Students Direct CSV Enrollment with House & Dormitory")
    print("=" * 70)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Prepare School, Houses, and Dormitories
        school = db.query(School).filter(School.school_mode.in_(["SHS_ONLY", "COMBINED"])).first()
        if not school:
            school = School(name="Test SHS", code="TSHS", school_mode="SHS_ONLY", boarding_type="BOARDING_AND_DAY")
            db.add(school)
            db.commit()
            db.refresh(school)

        # Setup House and Dormitory
        house_nkrumah = db.query(House).filter(House.name == "Kwame Nkrumah House", House.school_id == school.id).first()
        if not house_nkrumah:
            house_nkrumah = House(name="Kwame Nkrumah House", gender="Male", house_type="BOARDING", school_id=school.id)
            db.add(house_nkrumah)
            db.commit()
            db.refresh(house_nkrumah)

        dorm_block_a = db.query(Dormitory).filter(Dormitory.name == "Block A Room 1", Dormitory.house_id == house_nkrumah.id).first()
        if not dorm_block_a:
            dorm_block_a = Dormitory(name="Block A Room 1", house_id=house_nkrumah.id, capacity=20)
            db.add(dorm_block_a)
            db.commit()
            db.refresh(dorm_block_a)

        house_aggrey = db.query(House).filter(House.name == "Aggrey House", House.school_id == school.id).first()
        if not house_aggrey:
            house_aggrey = House(name="Aggrey House", gender="Male", house_type="BOARDING", school_id=school.id)
            db.add(house_aggrey)
            db.commit()
            db.refresh(house_aggrey)

        dorm_room_4 = db.query(Dormitory).filter(Dormitory.name == "Room 4", Dormitory.house_id == house_aggrey.id).first()
        if not dorm_room_4:
            dorm_room_4 = Dormitory(name="Room 4", house_id=house_aggrey.id, capacity=15)
            db.add(dorm_room_4)
            db.commit()
            db.refresh(dorm_room_4)

        stage_shs2 = db.query(SchoolStage).filter(SchoolStage.name == "SHS Form 2").first()
        if not stage_shs2:
            stage_shs2 = SchoolStage(name="SHS Form 2", school_type="SHS")
            db.add(stage_shs2)
            db.commit()

        stage_shs3 = db.query(SchoolStage).filter(SchoolStage.name == "SHS Form 3").first()
        if not stage_shs3:
            stage_shs3 = SchoolStage(name="SHS Form 3", school_type="SHS")
            db.add(stage_shs3)
            db.commit()

        prog_sci = db.query(Program).filter(Program.name == "General Science").first()
        if not prog_sci:
            prog_sci = Program(name="General Science", code="SCI", school_id=school.id)
            db.add(prog_sci)
            db.commit()

        prog_arts = db.query(Program).filter(Program.name == "General Arts").first()
        if not prog_arts:
            prog_arts = Program(name="General Arts", code="ARTS", school_id=school.id)
            db.add(prog_arts)
            db.commit()

        cls_shs2 = db.query(ClassSection).filter(ClassSection.name == "SHS 2 Science 1").first()
        if not cls_shs2:
            cls_shs2 = ClassSection(name="SHS 2 Science 1", stage_id=stage_shs2.id, program_id=prog_sci.id, school_id=school.id)
            db.add(cls_shs2)
            db.commit()

        cls_shs3 = db.query(ClassSection).filter(ClassSection.name == "SHS 3 Arts 1").first()
        if not cls_shs3:
            cls_shs3 = ClassSection(name="SHS 3 Arts 1", stage_id=stage_shs3.id, program_id=prog_arts.id, school_id=school.id)
            db.add(cls_shs3)
            db.commit()

        # Clean existing test student codes if any
        db.query(Student).filter(Student.student_code.in_(["TSHS-CONT-001", "TSHS-CONT-002", "TSHS-CONT-003"])).delete(synchronize_session=False)
        db.commit()

        # 2. Prepare Sample Continuing Students CSV Content with House & Dormitory columns
        csv_text = """full_name,student_code,form,class_name,program_name,gender,residential_status,house_name,dormitory_name,guardian_name,phone,address
Emmanuel Osei,TSHS-CONT-001,2,SHS 2 Science 1,General Science,Male,Boarding,Kwame Nkrumah House,Block A Room 1,Mr. Osei Mensah,0244111222,"House 1, Kumasi"
Patricia Antwi,TSHS-CONT-002,3,SHS 3 Arts 1,General Arts,Female,Day,,,Madam Mary Antwi,0209333444,"Plot 12, Sunyani"
Kofi Boateng,TSHS-CONT-003,2,SHS 2 Science 1,General Science,Male,Boarding,Aggrey House,Room 4,Opanin Yaw Boateng,0209876543,"Accra Enclave"
"""

        csv_bytes = csv_text.encode("utf-8")
        upload_file = UploadFile(filename="continuing_students.csv", file=io.BytesIO(csv_bytes))

        # Admin User Mock
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(username="admin_test", role="admin", is_super_admin=True, school_id=school.id)
            db.add(admin_user)
            db.commit()

        # 3. Execute Direct CSV Import
        res = await import_students_csv(file=upload_file, db=db, current_user=admin_user)
        print(f"[OK] Import Result: {res}")
        assert res["status"] == "success", f"Import failed: {res}"
        assert res["imported"] == 3, f"Expected 3 imported, got {res['imported']}"

        # 4. Verify Continuing Students in Database
        s1 = db.query(Student).filter(Student.student_code == "TSHS-CONT-001").first()
        assert s1 is not None, "Student 1 not found"
        assert s1.full_name == "Emmanuel Osei"
        assert s1.form == 2
        assert s1.class_section_id == cls_shs2.id
        assert s1.status == "ACTIVE"
        assert s1.enrollment_status == "Fully Registered"
        assert s1.residential_status == "B"
        assert s1.house_id == house_nkrumah.id
        assert s1.dormitory_id == dorm_block_a.id
        print(f"[OK] Verified Student 1: {s1.full_name} | Form {s1.form} | House: {s1.house.name} | Room: {s1.dormitory.name} | Status: {s1.status}")

        s2 = db.query(Student).filter(Student.student_code == "TSHS-CONT-002").first()
        assert s2 is not None, "Student 2 not found"
        assert s2.full_name == "Patricia Antwi"
        assert s2.form == 3
        assert s2.class_section_id == cls_shs3.id
        assert s2.status == "ACTIVE"
        assert s2.enrollment_status == "Fully Registered"
        assert s2.residential_status == "D"
        assert s2.house_id is None
        assert s2.dormitory_id is None
        print(f"[OK] Verified Student 2: {s2.full_name} | Form {s2.form} | Residential: {s2.residential_status} | Status: {s2.status}")

        s3 = db.query(Student).filter(Student.student_code == "TSHS-CONT-003").first()
        assert s3 is not None, "Student 3 not found"
        assert s3.full_name == "Kofi Boateng"
        assert s3.form == 2
        assert s3.residential_status == "B"
        assert s3.house_id == house_aggrey.id
        assert s3.dormitory_id == dorm_room_4.id
        print(f"[OK] Verified Student 3: {s3.full_name} | House: {s3.house.name} | Room: {s3.dormitory.name} | Status: {s3.status}")

        # 5. Verify list_students API returns house and dorm info
        student_list = list_students(db=db, current_user=admin_user)
        s1_api = next((s for s in student_list if s["student_code"] == "TSHS-CONT-001"), None)
        assert s1_api is not None, "Student 1 not in API output"
        assert s1_api["house_name"] == "Kwame Nkrumah House"
        assert s1_api["dormitory_name"] == "Block A Room 1"
        assert s1_api["residential_status"] == "B"
        print(f"[OK] Verified Student API Response includes house_name='{s1_api['house_name']}' and dormitory_name='{s1_api['dormitory_name']}'")

        print("\n" + "=" * 70)
        print("ALL CONTINUING STUDENTS DIRECT ENROLLMENT TESTS PASSED 100%!")
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
