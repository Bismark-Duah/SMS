"""
Automated Verification Script for Program-Subject Associations
"""
import sys
import time
from sqlalchemy.orm import Session

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import Program, Subject, ClassSection, SchoolStage
from backend.app.schemas import ProgramCreate, SubjectCreate, ClassSectionCreate
from backend.app.routes.programs import create_program, get_program_subjects, set_program_subjects
from backend.app.routes.subjects import create_subject
from backend.app.routes.classes import create_section, get_class_subjects, set_class_subjects

def run_tests():
    print("==================================================")
    print(" PROGRAM-SUBJECT ASSOCIATION VERIFICATION SUITE   ")
    print("==================================================")

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        ts = int(time.time())

        # 1. Create Test Program
        print("\n[1] Creating Test Program...")
        prog_data = ProgramCreate(name=f"Test Science Program {ts}")
        prog = create_program(prog_data, db=db)
        program_id = prog.id
        print(f"   [OK] Created program ID {program_id}: {prog.name}.")

        # 2. Create Test Subjects
        print("\n[2] Creating Test Subjects...")
        sub1_data = SubjectCreate(name=f"Test Physics {ts}", code=f"TPHY_{ts}", is_core=True)
        sub2_data = SubjectCreate(name=f"Test Chemistry {ts}", code=f"TCHE_{ts}", is_core=False)
        sub1 = create_subject(sub1_data, db=db)
        sub2 = create_subject(sub2_data, db=db)
        print(f"   [OK] Created subjects: {sub1.name} (#{sub1.id}), {sub2.name} (#{sub2.id}).")

        # 3. Associate Subject 1 with Program
        print(f"\n[3] Associating Subject #{sub1.id} with Program #{program_id}...")
        set_program_subjects(program_id=program_id, payload=[sub1.id], db=db)

        prog_subs = get_program_subjects(program_id=program_id, db=db)
        assert len(prog_subs) == 1, "Expected 1 associated subject!"
        assert prog_subs[0]["id"] == sub1.id, "Subject ID mismatch!"
        print("   [OK] Program subject association verified.")

        # 4. Create Class Section linked to Program
        print("\n[4] Creating Class Section linked to Program...")
        stage = db.query(SchoolStage).first()
        if not stage:
            stage = SchoolStage(name="Prog Test Stage", school_type="Basic")
            db.add(stage)
            db.commit()

        class_data = ClassSectionCreate(name=f"Test Class {ts}", stage_id=stage.id, program_id=program_id)
        csec = create_section(class_data, db=db)
        class_id = csec["id"] if isinstance(csec, dict) else csec.id
        class_name = csec["name"] if isinstance(csec, dict) else csec.name
        print(f"   [OK] Created Class #{class_id}: {class_name} linked to Program #{program_id}.")

        # 5. Retrieve Inherited Class Subjects (Fallback from Program)
        print("\n[5] Verifying Class Subject inheritance from Program...")
        class_subs = get_class_subjects(section_id=class_id, raw=False, db=db)
        assert len(class_subs) == 1, "Class should inherit 1 subject from program!"
        assert class_subs[0]["id"] == sub1.id, "Inherited subject ID mismatch!"
        print("   [OK] Class subject inheritance verified.")

        # 6. Apply Direct Class Override
        print(f"\n[6] Applying manual override: associating Subject #{sub2.id} directly to Class #{class_id}...")
        set_class_subjects(section_id=class_id, payload=[sub2.id], db=db)

        class_subs_overridden = get_class_subjects(section_id=class_id, raw=False, db=db)
        assert len(class_subs_overridden) == 1, "Overridden class should have 1 subject!"
        assert class_subs_overridden[0]["id"] == sub2.id, "Overridden subject ID mismatch!"
        print("   [OK] Class manual subject override verified.")

        print("\n==================================================")
        print(" ALL PROGRAM-SUBJECT TESTS PASSED SUCCESSFULLY!  ")
        print("==================================================")

    except Exception as e:
        print(f"\n[FAIL] VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
