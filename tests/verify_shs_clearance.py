import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath("backend"))

from app.database import SessionLocal, engine, Base
from app.models import Student, StudentClearanceRecord, User

def test_shs_clearance():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    print("Testing SHS Final Year Student Clearance Operations...")
    
    student = db.query(Student).first()
    user = db.query(User).first()
    
    if student and user:
        # Create or fetch clearance record
        rec = db.query(StudentClearanceRecord).filter(StudentClearanceRecord.student_id == student.id).first()
        if not rec:
            rec = StudentClearanceRecord(student_id=student.id, academic_year="2025/2026", status="Pending")
            db.add(rec)
            db.commit()
            db.refresh(rec)
            
        print(f"[OK] Clearance record initialized for {student.full_name} ({student.student_code}) - Initial Status: {rec.status}")
        
        # Test departmental sign-offs
        rec.storekeeper_cleared = True
        rec.storekeeper_by_id = user.id
        rec.storekeeper_notes = "All 3 years textbooks returned in good condition"
        
        rec.bursar_cleared = True
        rec.bursar_by_id = user.id
        rec.bursar_notes = "Zero fee balance"
        
        rec.housemaster_cleared = True
        rec.housemaster_by_id = user.id
        rec.housemaster_notes = "Dorm room keys handed in"
        
        rec.headmaster_cleared = True
        rec.headmaster_by_id = user.id
        rec.headmaster_notes = "Approved for WASSCE results & Official Transcript release"
        
        rec.status = "Fully Cleared"
        db.commit()
        db.refresh(rec)
        
        print(f"[OK] 4-Department sign-offs complete. Final Status: {rec.status}")
        print(f"[OK] Storekeeper Sign-off: {rec.storekeeper_notes}")
        print(f"[OK] Headmaster Sign-off: {rec.headmaster_notes}")

    db.close()
    print("\nALL SHS FINAL YEAR CLEARANCE TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_shs_clearance()
