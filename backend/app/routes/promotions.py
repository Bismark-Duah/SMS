from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from ..database import get_db
from ..models import Student, User, StudentSemesterSummary, ClassSection
from ..dependencies import get_current_user, get_school_id

router = APIRouter()

class PromoteRequest(BaseModel):
    student_ids: List[int]
    target_class_section_id: int
    increment_form: bool

class GraduateRequest(BaseModel):
    student_ids: List[int]

def check_promotion_permission(current_user: User):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    role_names = [r.name.lower() for r in current_user.roles]
    username_lower = (current_user.username or "").lower()
    
    allowed = (
        "admin" in role_names or
        "super_admin" in role_names or
        "headmaster" in role_names or
        "assistant_head_academic" in role_names or
        "form_master" in role_names or
        "teacher" in role_names or
        "academic" in username_lower or
        "admin" in username_lower
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Only administrators, academic heads, and form masters can manage promotions")


@router.get("/candidates/{class_section_id}")
def get_promotion_candidates(
    class_section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_promotion_permission(current_user)
    
    school_id = get_school_id(current_user)
    stud_q = db.query(Student).filter(
        Student.class_section_id == class_section_id,
        Student.is_active == True
    )
    if school_id is not None:
        stud_q = stud_q.filter(Student.school_id == school_id)
    students = stud_q.order_by(Student.full_name.asc()).all()

    candidates = []
    for s in students:
        summary = db.query(StudentSemesterSummary).filter(
            StudentSemesterSummary.student_id == s.id
        ).order_by(StudentSemesterSummary.id.desc()).first()

        rec = "Pending"
        remarks = ""
        if summary:
            remarks = summary.form_teacher_remarks or ""
            prom_val = (summary.promoted_to or "").lower()
            if "repeat" in prom_val:
                rec = "Repeated"
            elif "graduate" in prom_val or "completed" in prom_val:
                rec = "Graduated"
            elif "form" in prom_val or "promoted" in prom_val:
                rec = "Promoted"

        candidates.append({
            "id": s.id,
            "student_code": s.student_code,
            "full_name": s.full_name,
            "form": s.form or 1,
            "recommendation": rec,
            "remarks": remarks
        })

    return candidates


@router.post("/promote")
def promote_students(
    payload: PromoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_promotion_permission(current_user)
    
    if not payload.student_ids:
        raise HTTPException(status_code=400, detail="Student IDs list cannot be empty")
        
    school_id = get_school_id(current_user)
    target_q = db.query(ClassSection).filter(ClassSection.id == payload.target_class_section_id)
    if school_id is not None and hasattr(ClassSection, "school_id"):
        target_q = target_q.filter(ClassSection.school_id == school_id)
    target_class = target_q.first()
    if not target_class:
        raise HTTPException(status_code=404, detail="Target class section not found")

    stud_q = db.query(Student).filter(Student.id.in_(payload.student_ids))
    if school_id is not None:
        stud_q = stud_q.filter(Student.school_id == school_id)
    students = stud_q.all()
    if not students:
        raise HTTPException(status_code=404, detail="No students found matching the provided IDs")
        
    for student in students:
        student.class_section_id = payload.target_class_section_id
        if payload.increment_form and student.form is not None:
            student.form += 1
        student.is_active = True
        student.status = "ACTIVE"
        
    db.commit()
    return {"message": f"Successfully promoted {len(students)} students to {target_class.name}"}


@router.post("/graduate")
def graduate_students(
    payload: GraduateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_promotion_permission(current_user)
    
    if not payload.student_ids:
        raise HTTPException(status_code=400, detail="Student IDs list cannot be empty")
        
    students = db.query(Student).filter(Student.id.in_(payload.student_ids)).all()
    if not students:
        raise HTTPException(status_code=404, detail="No students found matching the provided IDs")
        
    for student in students:
        student.class_section_id = None
        student.is_active = False
        student.status = "GRADUATED"
        
    db.commit()
    return {"message": f"Successfully graduated {len(students)} students"}
