from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models import Student, StudentGuardian, StudentHealth, Score, Attendance, User
from ..schemas import CumulativeRecordUpdate
from ..dependencies import get_current_user, get_school_id

router = APIRouter(prefix="/api/cumulative-records", tags=["Basic School Cumulative Records"])

@router.get("/{student_id}")
def get_cumulative_record(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student or (school_id is not None and student.school_id != school_id):
        raise HTTPException(status_code=404, detail="Student not found.")

    guardians = db.query(StudentGuardian).filter(StudentGuardian.student_id == student_id).all()
    health = db.query(StudentHealth).filter(StudentHealth.student_id == student_id).first()
    scores = db.query(Score).filter(Score.student_id == student_id).all()
    attendance_records = db.query(Attendance).filter(Attendance.student_id == student_id).all()

    total_days = len(attendance_records)
    days_present = sum(1 for a in attendance_records if a.status.upper() == "PRESENT")
    days_absent = total_days - days_present

    # Calculate average score across terms
    score_list = [s.total_score for s in scores if s.total_score is not None]
    avg_score = round(sum(score_list) / len(score_list), 1) if score_list else 0.0

    return {
        "student_id": student.id,
        "student_code": student.student_code,
        "full_name": student.full_name,
        "school_type": student.school_type,
        "form": student.form,
        "gender": student.gender,
        "date_of_birth": student.date_of_birth.strftime("%Y-%m-%d") if student.date_of_birth else None,
        "address": student.address,
        
        # 1. Personal & Family Background
        "family_background": {
            "guardian_name": student.guardian_name,
            "phone": student.phone,
            "family_background_notes": student.family_background_notes,
            "socio_economic_notes": student.socio_economic_notes,
            "guardians": [
                {
                    "name": g.guardian_name,
                    "relation": g.relationship_type,
                    "phone": g.primary_phone,
                    "occupation": g.occupation,
                    "address": g.residential_address
                } for g in guardians
            ]
        },

        # 2. Scholastic & SBA Data
        "scholastic_summary": {
            "total_assessments": len(scores),
            "overall_average": avg_score,
            "scores_breakdown": [
                {
                    "subject_id": s.subject_id,
                    "subject_name": s.subject.name if s.subject else "Subject",
                    "total_score": s.total_score,
                    "grade": s.grade,
                    "remark": s.remark
                } for s in scores
            ]
        },

        # 3. Attendance & Conduct Ledger
        "attendance_conduct": {
            "total_days_tracked": total_days,
            "days_present": days_present,
            "days_absent": days_absent,
            "attendance_rate": f"{round((days_present/total_days)*100, 1)}%" if total_days > 0 else "N/A"
        },

        # 4. Physical & Health Data
        "health_physical": {
            "height_cm": health.height_cm if health else None,
            "weight_kg": health.weight_kg if health else None,
            "blood_group": health.blood_group if health else None,
            "allergies": health.allergies if health else None,
            "chronic_conditions": health.chronic_conditions if health else None,
            "pe_limitations": health.pe_limitations if health else None,
            "doctor_clearance_status": health.doctor_clearance_status if health else False
        },

        # 5. Personality & Social Traits
        "personality_social": {
            "personality_traits": student.personality_traits,
            "leadership_notes": student.leadership_notes,
            "teacher_observations": student.teacher_observations
        },

        # 6. Co-Curricular & Talent Profile
        "cocurricular_talents": {
            "co_curricular_activities": student.co_curricular_activities,
            "hobbies_talents": student.hobbies_talents,
            "awards": student.awards
        }
    }

@router.put("/{student_id}")
def update_cumulative_record(student_id: int, data: CumulativeRecordUpdate, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    if data.family_background_notes is not None:
        student.family_background_notes = data.family_background_notes
    if data.socio_economic_notes is not None:
        student.socio_economic_notes = data.socio_economic_notes
    if data.personality_traits is not None:
        student.personality_traits = data.personality_traits
    if data.leadership_notes is not None:
        student.leadership_notes = data.leadership_notes
    if data.teacher_observations is not None:
        student.teacher_observations = data.teacher_observations
    if data.co_curricular_activities is not None:
        student.co_curricular_activities = data.co_curricular_activities
    if data.hobbies_talents is not None:
        student.hobbies_talents = data.hobbies_talents
    if data.awards is not None:
        student.awards = data.awards

    # Update Health profile
    health = db.query(StudentHealth).filter(StudentHealth.student_id == student_id).first()
    if not health:
        health = StudentHealth(student_id=student_id)
        db.add(health)

    if data.height_cm is not None:
        health.height_cm = data.height_cm
    if data.weight_kg is not None:
        health.weight_kg = data.weight_kg
    if data.medical_conditions is not None:
        health.chronic_conditions = data.medical_conditions
    if data.pe_limitations is not None:
        health.pe_limitations = data.pe_limitations

    db.commit()
    return {"message": "Student Cumulative Record updated successfully!"}


@router.get("/pdf/{student_id}")
def get_cumulative_record_pdf(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates and streams the official GES/NaCCA Basic School Cumulative Record Folder PDF.
    """
    from fastapi.responses import Response
    from ..services.reports import ReportService

    school_id = get_school_id(current_user)
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student or (school_id is not None and student.school_id != school_id):
        raise HTTPException(status_code=404, detail="Student not found.")

    try:
        pdf_bytes = ReportService.generate_basic_cumulative_folder_pdf(db, student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate cumulative record folder PDF: {str(e)}")

    code_clean = (student.student_code or str(student.id)).replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Cumulative_Record_Folder_{code_clean}.pdf"'
        }
    )

