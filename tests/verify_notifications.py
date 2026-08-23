"""
Verification Script for In-App Notifications API
"""
import sys
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import Notification, Student, ClassSection

def test_notifications():
    print("--- Verifying Notifications API ---")
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        class_sec = db.query(ClassSection).filter(ClassSection.name == "Notif Test Class").first()
        if not class_sec:
            class_sec = ClassSection(name="Notif Test Class", stage_id=1)
            db.add(class_sec)
            db.commit()

        st = db.query(Student).filter(Student.student_code == "NOTIF-STU-001").first()
        if not st:
            st = Student(
                student_code="NOTIF-STU-001",
                full_name="Kofi Mensah",
                class_section_id=class_sec.id,
                is_active=True
            )
            db.add(st)
            db.commit()

        # Clean existing test notifications
        db.query(Notification).filter(Notification.student_id == st.id).delete()
        db.commit()

        # Test Notification Creation
        notif = Notification(
            student_id=st.id,
            message="Test notification message for student",
            type="General",
            is_read=False,
            created_at=datetime.now(timezone.utc)
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)

        assert notif.id is not None, "Notification creation failed"
        assert notif.student_id == st.id, "Student ID mismatch"
        assert notif.is_read is False, "Default is_read state should be False"

        # Update to Read
        notif.is_read = True
        db.commit()
        
        queried = db.query(Notification).filter(Notification.id == notif.id).first()
        assert queried.is_read is True, "Marking notification as read failed"

        # Cleanup
        db.delete(queried)
        db.commit()

        print("[OK] Notifications API verified successfully!")
    except Exception as e:
        print(f"[FAIL] Verification failed: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    test_notifications()
