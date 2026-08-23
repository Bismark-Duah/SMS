import os
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..models import AcademicYear, Semester, Setting, Student, Fee
from ..dependencies import get_current_user, get_school_id
from ..models import User

router = APIRouter()

class RolloverPayload(BaseModel):
    target_year_id: int
    target_semester_id: int
    carry_over_fees: bool
    archive_reports: bool

def _is_admin(user: User):
    roles = [r.name.lower() for r in user.roles]
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="Access Denied: Admin privileges required.")

@router.get("/status")
def get_rollover_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _is_admin(current_user)

    # Get active academic year & semester
    active_year = db.query(AcademicYear).filter(AcademicYear.is_current == True).first()
    active_sem = db.query(Semester).filter(Semester.is_current == True).first()

    current_year_label = active_year.label if active_year else "None"
    current_sem_name = active_sem.name if active_sem else "None"

    # 1. Count students with pending recommendations
    # We can check if any active student has a pending promotion or graduation recommendation
    # Or simply count all active students to see who is currently enrolled
    school_id = get_school_id(current_user)
    stud_q = db.query(Student).filter(Student.is_active == True)
    if school_id is not None:
        stud_q = stud_q.filter(Student.school_id == school_id)
    active_students_count = stud_q.count()

    # 2. Count unpaid fees for current term
    unpaid_fees_count = 0
    total_unpaid_amount = 0.0
    if active_year and active_sem:
        fee_q = db.query(Fee).filter(
            Fee.academic_year == active_year.label,
            Fee.term == active_sem.name,
            Fee.status != "Paid"
        )
        if school_id is not None:
            fee_q = fee_q.join(Fee.student).filter(Student.school_id == school_id)
        unpaid_fees = fee_q.all()
        unpaid_fees_count = len(unpaid_fees)
        total_unpaid_amount = sum((f.amount - (f.amount_paid or 0.0)) for f in unpaid_fees)

    # 3. Get list of next target semesters / years
    years = db.query(AcademicYear).all()
    semesters = db.query(Semester).all()

    return {
        "current_year_label": current_year_label,
        "current_semester_name": current_sem_name,
        "active_students_count": active_students_count,
        "unpaid_fees_count": unpaid_fees_count,
        "total_unpaid_amount": total_unpaid_amount,
        "years": [{"id": y.id, "label": y.label, "is_current": y.is_current} for y in years],
        "semesters": [
            {
                "id": s.id,
                "name": s.name,
                "academic_year_id": s.academic_year_id,
                "is_current": s.is_current
            }
            for s in semesters
        ]
    }

@router.post("/execute")
def execute_rollover(
    payload: RolloverPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _is_admin(current_user)

    active_year = db.query(AcademicYear).filter(AcademicYear.is_current == True).first()
    active_sem = db.query(Semester).filter(Semester.is_current == True).first()

    if not active_year or not active_sem:
        raise HTTPException(status_code=400, detail="No active academic year or semester set to rollover from.")

    target_year = db.query(AcademicYear).filter(AcademicYear.id == payload.target_year_id).first()
    target_sem = db.query(Semester).filter(Semester.id == payload.target_semester_id).first()

    if not target_year or not target_sem:
        raise HTTPException(status_code=404, detail="Target academic year or semester not found.")

    if target_sem.academic_year_id != target_year.id:
        raise HTTPException(status_code=400, detail="Target semester does not belong to target academic year.")

    # 1. Archive & Lock current reports/scores if requested
    if payload.archive_reports:
        locked_setting = db.query(Setting).filter(Setting.key == "locked_semester_ids").first()
        if not locked_setting:
            locked_setting = Setting(key="locked_semester_ids", value="[]")
            db.add(locked_setting)
            db.commit()
            db.refresh(locked_setting)
        
        try:
            locked_ids = json.loads(locked_setting.value)
        except Exception:
            locked_ids = []

        if active_sem.id not in locked_ids:
            locked_ids.append(active_sem.id)
            locked_setting.value = json.dumps(locked_ids)

    # 2. Carry over outstanding fees as Arrears in target term if requested
    fees_carried_over = 0
    if payload.carry_over_fees:
        unpaid_fees = db.query(Fee).filter(
            Fee.academic_year == active_year.label,
            Fee.term == active_sem.name,
            Fee.status != "Paid"
        ).all()

        for old_fee in unpaid_fees:
            balance = old_fee.amount - (old_fee.amount_paid or 0.0)
            if balance > 0:
                # Create Arrears fee in target term
                arrears_fee = Fee(
                    student_id=old_fee.student_id,
                    fee_type="Arrears",
                    description=f"Carried over arrears from {active_year.label} {active_sem.name}",
                    amount=balance,
                    amount_paid=0.0,
                    due_date=None,
                    academic_year=target_year.label,
                    term=target_sem.name,
                    status="Pending"
                )
                db.add(arrears_fee)
                
                # Mark old fee as carried over
                old_fee.status = "Carried Over"
                fees_carried_over += 1

    # 3. Advance Active Term/Semester
    # Clear current flag on all other years/semesters
    db.query(AcademicYear).update({"is_current": False})
    db.query(Semester).update({"is_current": False})

    target_year.is_current = True
    target_sem.is_current = True

    db.commit()

    return {
        "status": "success",
        "message": f"Successfully rolled over to academic term {target_year.label} - {target_sem.name}.",
        "fees_carried_over": fees_carried_over,
        "reports_archived": payload.archive_reports
    }
