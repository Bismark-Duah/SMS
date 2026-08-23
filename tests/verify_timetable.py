"""
Verification Script for Timetable Management System
"""
import sys
from sqlalchemy.orm import Session

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User, Role, ClassSection, Subject, Timetable, Semester, AcademicYear

def test_timetable():
    print("--- Verifying Timetable Management ---")
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        # Create test Class, Subject, User, Semester
        class_sec = db.query(ClassSection).filter(ClassSection.name == "Timetable Test Class").first()
        if not class_sec:
            class_sec = ClassSection(name="Timetable Test Class", stage_id=1)
            db.add(class_sec)
            db.commit()

        subj = db.query(Subject).filter(Subject.code == "TT_SUBJ_01").first()
        if not subj:
            subj = Subject(name="Timetable Science", code="TT_SUBJ_01", is_core=True)
            db.add(subj)
            db.commit()

        teacher = db.query(User).filter(User.username == "tt_teacher").first()
        if not teacher:
            teacher = User(username="tt_teacher", email="tt_teacher@school.edu", password_hash="pass", is_active=True)
            db.add(teacher)
            db.commit()

        # Clean existing test slot
        db.query(Timetable).filter(Timetable.class_section_id == class_sec.id).delete()
        db.commit()

        # Test Slot Creation
        slot = Timetable(
            class_section_id=class_sec.id,
            subject_id=subj.id,
            teacher_id=teacher.id,
            day_of_week=0, # Monday
            period_number=1,
            start_time="08:00",
            end_time="09:00",
            room="Lab 1"
        )
        db.add(slot)
        db.commit()
        db.refresh(slot)

        assert slot.id is not None, "Timetable slot creation failed"
        assert slot.class_section_id == class_sec.id, "Class section assignment failed"
        assert slot.day_of_week == 0, "Day of week mismatch"
        assert slot.period_number == 1, "Period number mismatch"
        assert slot.room == "Lab 1", "Room assignment mismatch"

        # Cleanup
        db.delete(slot)
        db.commit()

        print("[OK] Timetable Management verified successfully!")
    except Exception as e:
        print(f"[FAIL] Verification failed: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    test_timetable()
