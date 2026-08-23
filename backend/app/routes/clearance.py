from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..database import get_db
from ..models import StudentClearanceRecord, Student, ClassSection, SchoolStage, TextbookAllocation, Fee, DisciplineRecord, User
from ..dependencies import get_current_user, get_school_id

router = APIRouter()

def _get_live_clearance_metrics(db: Session, student_id: int):
    """Calculates live departmental clearance checks for a student."""
    # 1. Storekeeper Check: Unreturned Textbooks
    unreturned_books = db.query(TextbookAllocation).filter(
        TextbookAllocation.student_id == student_id,
        TextbookAllocation.status == "Issued"
    ).all()
    unreturned_list = [{"id": b.id, "title": b.book_title, "barcode": b.barcode_id} for b in unreturned_books]
    storekeeper_ok = len(unreturned_books) == 0

    # 2. Bursar Check: Fee Arrears
    fees = db.query(Fee).filter(Fee.student_id == student_id).all()
    total_due = sum(f.amount_due for f in fees) if fees else 0.0
    total_paid = sum(f.amount_paid for f in fees) if fees else 0.0
    outstanding_balance = max(0.0, total_due - total_paid)
    bursar_ok = outstanding_balance <= 0.0

    # 3. House Master Check: Unresolved Discipline Issues
    discipline_issues = db.query(DisciplineRecord).filter(
        DisciplineRecord.student_id == student_id,
        DisciplineRecord.action_taken.is_(None)
    ).count()
    housemaster_ok = discipline_issues == 0

    return {
        "storekeeper_ok": storekeeper_ok,
        "unreturned_books": unreturned_list,
        "bursar_ok": bursar_ok,
        "outstanding_balance": round(outstanding_balance, 2),
        "housemaster_ok": housemaster_ok,
        "open_discipline_issues": discipline_issues
    }

# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/final-year-students")
def list_final_year_clearance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns list of graduating SHS 3 students with their clearance status matrix.
    Filters students whose class stage is SHS 3 / Final Year.
    """
    school_id = get_school_id(current_user)
    
    # Query students in SHS 3 / Form 3 stage or with '3' in stage name
    query = db.query(Student).join(ClassSection, Student.class_section_id == ClassSection.id)\
                             .join(SchoolStage, ClassSection.stage_id == SchoolStage.id)
                             
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)
        
    students = query.all()
    
    # Filter final year (SHS 3 / Form 3 / Grade 12)
    final_year_students = []
    for s in students:
        stage_name = s.class_section.stage.name.upper() if (s.class_section and s.class_section.stage) else ""
        class_name = s.class_section.name.upper() if s.class_section else ""
        if "3" in stage_name or "3" in class_name or "SHS 3" in stage_name or "FINAL" in stage_name:
            final_year_students.append(s)
            
    # If no specific '3' filter matched, return all active students for demonstration flexibility
    if not final_year_students:
        final_year_students = students[:50]

    results = []
    for s in final_year_students:
        rec = db.query(StudentClearanceRecord).filter(StudentClearanceRecord.student_id == s.id).first()
        metrics = _get_live_clearance_metrics(db, s.id)
        
        results.append({
            "student_id": s.id,
            "student_code": s.student_code,
            "full_name": s.full_name,
            "class_name": s.class_section.name if s.class_section else "N/A",
            "house_name": s.house.name if s.house else "N/A",
            "clearance_id": rec.id if rec else None,
            "storekeeper_cleared": rec.storekeeper_cleared if rec else metrics["storekeeper_ok"],
            "bursar_cleared": rec.bursar_cleared if rec else metrics["bursar_ok"],
            "housemaster_cleared": rec.housemaster_cleared if rec else metrics["housemaster_ok"],
            "headmaster_cleared": rec.headmaster_cleared if rec else False,
            "status": rec.status if rec else ("Fully Cleared" if (metrics["storekeeper_ok"] and metrics["bursar_ok"] and metrics["housemaster_ok"]) else "Pending"),
            "live_metrics": metrics
        })
        
    return results


@router.get("/status/{student_id}")
def get_student_clearance_status(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    rec = db.query(StudentClearanceRecord).filter(StudentClearanceRecord.student_id == student_id).first()
    metrics = _get_live_clearance_metrics(db, student_id)
    
    return {
        "student_id": student.id,
        "student_code": student.student_code,
        "full_name": student.full_name,
        "class_name": student.class_section.name if student.class_section else "N/A",
        "house_name": student.house.name if student.house else "N/A",
        "record": {
            "id": rec.id if rec else None,
            "storekeeper_cleared": rec.storekeeper_cleared if rec else False,
            "storekeeper_by": rec.storekeeper_by.full_name if rec and rec.storekeeper_by else None,
            "storekeeper_notes": rec.storekeeper_notes if rec else None,
            "bursar_cleared": rec.bursar_cleared if rec else False,
            "bursar_by": rec.bursar_by.full_name if rec and rec.bursar_by else None,
            "bursar_notes": rec.bursar_notes if rec else None,
            "housemaster_cleared": rec.housemaster_cleared if rec else False,
            "housemaster_by": rec.housemaster_by.full_name if rec and rec.housemaster_by else None,
            "housemaster_notes": rec.housemaster_notes if rec else None,
            "headmaster_cleared": rec.headmaster_cleared if rec else False,
            "headmaster_by": rec.headmaster_by.full_name if rec and rec.headmaster_by else None,
            "headmaster_notes": rec.headmaster_notes if rec else None,
            "status": rec.status if rec else "Pending",
            "completed_date": rec.completed_date
        },
        "live_metrics": metrics
    }


@router.post("/sign-off")
def sign_off_department(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    student_id = payload.get("student_id")
    department = payload.get("department") # storekeeper | bursar | housemaster | headmaster
    notes = payload.get("notes", "")

    if not student_id or not department:
        raise HTTPException(status_code=400, detail="student_id and department are required")

    rec = db.query(StudentClearanceRecord).filter(StudentClearanceRecord.student_id == student_id).first()
    if not rec:
        rec = StudentClearanceRecord(student_id=student_id, status="Pending")
        db.add(rec)

    dept_lower = department.lower()
    if dept_lower == "storekeeper":
        rec.storekeeper_cleared = True
        rec.storekeeper_by_id = current_user.id
        rec.storekeeper_notes = notes
    elif dept_lower == "bursar":
        rec.bursar_cleared = True
        rec.bursar_by_id = current_user.id
        rec.bursar_notes = notes
    elif dept_lower == "housemaster":
        rec.housemaster_cleared = True
        rec.housemaster_by_id = current_user.id
        rec.housemaster_notes = notes
    elif dept_lower == "headmaster":
        rec.headmaster_cleared = True
        rec.headmaster_by_id = current_user.id
        rec.headmaster_notes = notes
    else:
        raise HTTPException(status_code=400, detail=f"Invalid department '{department}'")

    # Check if all 4 departments are cleared
    if rec.storekeeper_cleared and rec.bursar_cleared and rec.housemaster_cleared and rec.headmaster_cleared:
        rec.status = "Fully Cleared"
        rec.completed_date = datetime.now()

    db.commit()
    db.refresh(rec)
    return {"status": "success", "message": f"{department.capitalize()} clearance sign-off recorded.", "clearance_status": rec.status}
