from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AcademicYear, Semester
from ..schemas import AcademicYearCreate, SemesterCreate, AcademicYearUpdate, SemesterUpdate

router = APIRouter()


# ── Academic Years ─────────────────────────────────────────────────────────────

@router.get("/years")
def list_years(db: Session = Depends(get_db)):
    years = db.query(AcademicYear).order_by(AcademicYear.id.desc()).all()
    result = []
    for y in years:
        result.append({
            "id": y.id,
            "label": y.label,
            "is_current": y.is_current,
            "semesters": [
                {
                    "id": s.id,
                    "name": s.name,
                    "academic_year_id": s.academic_year_id,
                    "is_current": s.is_current,
                    "start_date": str(s.start_date)[:10] if s.start_date else None,
                    "end_date": str(s.end_date)[:10] if s.end_date else None,
                }
                for s in y.semesters
            ],
        })
    return result


@router.post("/years")
def create_year(payload: AcademicYearCreate, db: Session = Depends(get_db)):
    existing = db.query(AcademicYear).filter(AcademicYear.label == payload.label).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Academic year '{payload.label}' already exists.")
    db_year = AcademicYear(**payload.dict())
    db.add(db_year)
    db.commit()
    db.refresh(db_year)
    return db_year


@router.patch("/years/{year_id}/set-current")
def set_current_year(year_id: int, db: Session = Depends(get_db)):
    """Mark a year as current, clearing the flag from all others."""
    db.query(AcademicYear).update({"is_current": False})
    year = db.query(AcademicYear).filter(AcademicYear.id == year_id).first()
    if not year:
        raise HTTPException(status_code=404, detail="Academic year not found.")
    year.is_current = True
    db.commit()
    return {"message": f"'{year.label}' is now the current academic year."}


@router.delete("/years/{year_id}")
def delete_year(year_id: int, db: Session = Depends(get_db)):
    year = db.query(AcademicYear).filter(AcademicYear.id == year_id).first()
    if not year:
        raise HTTPException(status_code=404, detail="Academic year not found.")
    # Delete child semesters first
    db.query(Semester).filter(Semester.academic_year_id == year_id).delete()
    db.delete(year)
    db.commit()
    return {"message": f"Academic year '{year.label}' deleted."}


@router.put("/years/{year_id}")
def update_year(year_id: int, payload: AcademicYearUpdate, db: Session = Depends(get_db)):
    year = db.query(AcademicYear).filter(AcademicYear.id == year_id).first()
    if not year:
        raise HTTPException(status_code=404, detail="Academic year not found.")
    
    if year.label != payload.label:
        existing = db.query(AcademicYear).filter(AcademicYear.label == payload.label).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Academic year '{payload.label}' already exists.")
            
    year.label = payload.label
    
    if payload.is_current:
        db.query(AcademicYear).update({"is_current": False})
        year.is_current = True
    else:
        year.is_current = False
        
    db.commit()
    db.refresh(year)
    return year


# ── Semesters ──────────────────────────────────────────────────────────────────

@router.get("/semesters")
def list_semesters(db: Session = Depends(get_db)):
    semesters = db.query(Semester).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "academic_year_id": s.academic_year_id,
            "academic_year": {"id": s.academic_year.id, "label": s.academic_year.label} if s.academic_year else None,
            "is_current": s.is_current,
            "start_date": str(s.start_date)[:10] if s.start_date else None,
            "end_date": str(s.end_date)[:10] if s.end_date else None,
        }
        for s in semesters
    ]


@router.post("/semesters")
def create_semester(payload: SemesterCreate, db: Session = Depends(get_db)):
    db_semester = Semester(**payload.dict())
    db.add(db_semester)
    db.commit()
    db.refresh(db_semester)
    return {
        "id": db_semester.id,
        "name": db_semester.name,
        "academic_year_id": db_semester.academic_year_id,
        "is_current": db_semester.is_current,
        "start_date": str(db_semester.start_date)[:10] if db_semester.start_date else None,
        "end_date": str(db_semester.end_date)[:10] if db_semester.end_date else None,
    }


@router.patch("/semesters/{semester_id}/set-current")
def set_current_semester(semester_id: int, db: Session = Depends(get_db)):
    """Mark a semester as current, clearing the flag from all others."""
    db.query(Semester).update({"is_current": False})
    semester = db.query(Semester).filter(Semester.id == semester_id).first()
    if not semester:
        raise HTTPException(status_code=404, detail="Semester not found.")
    semester.is_current = True
    db.commit()
    return {"message": f"'{semester.name}' is now the current semester."}


@router.delete("/semesters/{semester_id}")
def delete_semester(semester_id: int, db: Session = Depends(get_db)):
    semester = db.query(Semester).filter(Semester.id == semester_id).first()
    if not semester:
        raise HTTPException(status_code=404, detail="Semester not found.")
    db.delete(semester)
    db.commit()
    return {"message": f"Semester '{semester.name}' deleted."}


@router.put("/semesters/{semester_id}")
def update_semester(semester_id: int, payload: SemesterUpdate, db: Session = Depends(get_db)):
    semester = db.query(Semester).filter(Semester.id == semester_id).first()
    if not semester:
        raise HTTPException(status_code=404, detail="Semester not found.")
        
    semester.name = payload.name
    semester.start_date = payload.start_date
    semester.end_date = payload.end_date
    
    if payload.is_current:
        db.query(Semester).update({"is_current": False})
        semester.is_current = True
    else:
        semester.is_current = False
        
    db.commit()
    db.refresh(semester)
    return {
        "id": semester.id,
        "name": semester.name,
        "academic_year_id": semester.academic_year_id,
        "is_current": semester.is_current,
        "start_date": str(semester.start_date)[:10] if semester.start_date else None,
        "end_date": str(semester.end_date)[:10] if semester.end_date else None,
    }


# ── Promote ────────────────────────────────────────────────────────────────────

@router.post("/promote")
def promote_students(stage_id: int = None, db: Session = Depends(get_db)):
    from ..services.lifecycle import LifecycleService
    return LifecycleService.promote_students(db, stage_id)


# ── Executive Analytics Widgets ──────────────────────────────────────────

@router.get("/executive-analytics")
def get_executive_analytics(
    db: Session = Depends(get_db)
):
    from ..models import Student, ClassSection, Subject, Department, User, ExeatRecord, DisciplineRecord, House, Score, ClassSubjectScoreStatus, ClassSectionReportStatus, Setting, School, TeacherAssignment
    from datetime import datetime

    # School Mode check
    setting = db.query(Setting).filter(Setting.key == "school_mode").first()
    school_mode = setting.value if setting and setting.value else "COMBINED"

    # 1. Academic Executive Metrics
    teachers_count = db.query(User).join(User.roles).filter(User.roles.any(name="teacher")).count()
    depts_count = db.query(Department).count() if school_mode != "BASIC_ONLY" else 0
    classes_count = db.query(ClassSection).count()

    total_scores_recorded = db.query(Score).count()
    active_students_count = db.query(Student).filter(Student.is_active == True).count()
    active_subjects_count = db.query(Subject).count()
    expected_total_scores = max(1, active_students_count * active_subjects_count)
    sba_completion_pct = round(min(100.0, (total_scores_recorded / expected_total_scores) * 100.0), 1)

    pending_hod_approvals = db.query(ClassSubjectScoreStatus).filter(ClassSubjectScoreStatus.status != "Approved").count()
    published_classes_count = db.query(ClassSectionReportStatus).filter(ClassSectionReportStatus.is_published == True).count()

    # Department compliance matrix (SHS / Combined mode only)
    departments_matrix = []
    if school_mode != "BASIC_ONLY":
        depts = db.query(Department).all()
        for d in depts:
            hod_user = db.query(User).filter(User.id == d.hod_user_id).first() if d.hod_user_id else None
            dept_subjects = db.query(Subject).filter(Subject.department_id == d.id).all()
            dept_subject_ids = [s.id for s in dept_subjects]
            
            dept_teachers_count = db.query(TeacherAssignment.teacher_id).filter(TeacherAssignment.subject_id.in_(dept_subject_ids)).distinct().count() if dept_subject_ids else 0
            dept_scores_count = db.query(Score).filter(Score.subject_id.in_(dept_subject_ids)).count() if dept_subject_ids else 0
            dept_expected = max(1, active_students_count * len(dept_subject_ids)) if dept_subject_ids else 1
            pct = round(min(100.0, (dept_scores_count / dept_expected) * 100.0), 1) if dept_subject_ids else 0.0
            
            status_str = "COMPLETE" if pct >= 100 else ("IN_PROGRESS" if pct > 0 else "PENDING")
            
            hod_display = "Unassigned"
            if hod_user:
                hod_display = getattr(hod_user, 'full_name', None) or hod_user.username

            departments_matrix.append({
                "id": d.id,
                "name": d.name,
                "code": d.code,
                "hod_name": hod_display,
                "teacher_count": dept_teachers_count,
                "subject_count": len(dept_subjects),
                "sba_completion_pct": pct,
                "status": status_str
            })

    # 2. Domestic Executive Metrics
    total_boarders = db.query(Student).filter(Student.is_active == True, Student.residential_status.ilike("%boarding%")).count() if school_mode != "BASIC_ONLY" else 0
    currently_away_exeat = db.query(ExeatRecord).filter(ExeatRecord.status.in_(["Departed", "Away"])).count() if school_mode != "BASIC_ONLY" else 0
    
    now = datetime.now()
    overdue_exeat_count = db.query(ExeatRecord).filter(
        ExeatRecord.status == "Departed",
        ExeatRecord.expected_return < now
    ).count() if school_mode != "BASIC_ONLY" else 0

    active_discipline_incidents = db.query(DisciplineRecord).filter(DisciplineRecord.action_taken.is_(None)).count()
    total_houses = db.query(House).count() if school_mode != "BASIC_ONLY" else 0

    # House & Dormitory Occupancy Matrix (SHS & Combined modes only)
    houses_matrix = []
    medical_flags_count = 0
    if school_mode != "BASIC_ONLY":
        all_houses = db.query(House).all()
        from ..models import StudentHealth
        medical_flags_count = db.query(StudentHealth).filter(
            ((StudentHealth.allergies.isnot(None)) & (StudentHealth.allergies != "")) |
            ((StudentHealth.chronic_conditions.isnot(None)) & (StudentHealth.chronic_conditions != ""))
        ).count()

        for h in all_houses:
            hm_user = db.query(User).filter(User.id == h.house_master_id).first() if h.house_master_id else None
            dorms = getattr(h, 'dormitories', [])
            dorms_count = len(dorms) if dorms else 0
            boarders_count = db.query(Student).filter(Student.house_id == h.id, Student.is_active == True).count()
            capacity = sum([d.capacity for d in dorms if hasattr(d, 'capacity') and d.capacity]) if dorms else 50
            capacity = max(1, capacity)
            occ_pct = round(min(100.0, (boarders_count / capacity) * 100.0), 1)
            
            hm_display = "Unassigned"
            if hm_user:
                hm_display = getattr(hm_user, 'full_name', None) or hm_user.username

            status_str = "OPTIMAL"
            if occ_pct >= 95:
                status_str = "FULL"
            elif occ_pct >= 75:
                status_str = "HIGH"

            houses_matrix.append({
                "id": h.id,
                "name": h.name,
                "gender_type": getattr(h, 'gender_type', None) or "MIXED",
                "house_master_name": hm_display,
                "dorm_count": dorms_count,
                "boarder_count": boarders_count,
                "capacity": capacity,
                "occupancy_pct": occ_pct,
                "status": status_str
            })

    return {
        "school_mode": school_mode,
        "academic": {
            "sba_completion_pct": sba_completion_pct,
            "total_teachers": teachers_count,
            "total_departments": depts_count,
            "total_classes": classes_count,
            "pending_hod_approvals": pending_hod_approvals,
            "published_classes_count": published_classes_count,
            "departments_matrix": departments_matrix
        },
        "domestic": {
            "total_boarders": total_boarders,
            "currently_away_exeat": currently_away_exeat,
            "overdue_exeat_count": overdue_exeat_count,
            "active_discipline_incidents": active_discipline_incidents,
            "medical_flags_count": medical_flags_count,
            "total_houses": total_houses,
            "houses_matrix": houses_matrix
        }
    }

