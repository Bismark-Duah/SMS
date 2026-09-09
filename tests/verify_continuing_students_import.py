import os
import sys
import io
from fastapi import UploadFile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import School, Program, ClassSection, SchoolStage, Student, User
from backend.app.routes.students import import_students_csv

import asyncio

async def run_test():
    print("=" * 70)
    print("TEST SUITE: Continuing Students Direct CSV Enrollment (Bypassing Admission Portal)")
    print("=" * 70)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Prepare School and SHS 2/3 Classes
        school = db.query(School).filter(School.school_mode.in_(["SHS_ONLY", "COMBINED"])).first()
        if not school:
            school = School(name="Test SHS", code="TSHS", school_mode="SHS_ONLY")
            db.add(school)
            db.commit()
            db.refresh(school)

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

        cls_shs2 = db.query(ClassSection).filter(ClassSection.name == "SHS 2 Science 1").first()
        if not cls_shs2:
            cls_shs2 = ClassSection(name="SHS 2 Science 1", stage_id=stage_shs2.id, program_id=prog_sci.id, school_id=school.id)
            db.add(cls_shs2)
            db.commit()

        cls_shs3 = db.query(ClassSection).filter(ClassSection.name == "SHS 3 Science 1").first()
        if not cls_shs3:
            cls_shs3 = ClassSection(name="SHS 3 Science 1", stage_id=stage_shs3.id, program_id=prog_sci.id, school_id=school.id)
            db.add(cls_shs3)
            db.commit()

        # 2. Prepare Sample Continuing Students CSV Content
        csv_text = """full_name,student_code,form,class_name,program_name,gender,residential_status,guardian_name,phone,address
Emmanuel Osei,TSHS-2024-099,2,SHS 2 Science 1,General Science,Male,Boarding,Mr. Osei Mensah,0244111222,"House 1, Kumasi"
Patricia Antwi,TSHS-2023-144,3,SHS 3 Science 1,General Science,Female,Day,Madam Mary Antwi,0209333444,"Plot 12, Sunyani"
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
        assert res["imported"] >= 2, f"Expected 2 imported, got {res['imported']}"

        # 4. Verify Continuing Students in Database
        s1 = db.query(Student).filter(Student.student_code == "TSHS-2024-099").first()
        assert s1 is not None, "Student 1 not found"
        assert s1.full_name == "Emmanuel Osei"
        assert s1.form == 2
        assert s1.class_section_id == cls_shs2.id
        assert s1.status == "ACTIVE"
        assert s1.enrollment_status == "Fully Registered"
        print(f"[OK] Verified Student 1: {s1.full_name} | Form {s1.form} | Class: {s1.class_section.name} | Status: {s1.status} | Enrollment: {s1.enrollment_status}")

        s2 = db.query(Student).filter(Student.student_code == "TSHS-2023-144").first()
        assert s2 is not None, "Student 2 not found"
        assert s2.full_name == "Patricia Antwi"
        assert s2.form == 3
        assert s2.class_section_id == cls_shs3.id
        assert s2.status == "ACTIVE"
        assert s2.enrollment_status == "Fully Registered"
        print(f"[OK] Verified Student 2: {s2.full_name} | Form {s2.form} | Class: {s2.class_section.name} | Status: {s2.status} | Enrollment: {s2.enrollment_status}")

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
