from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AcademicYear, Semester, User
from ..schemas import AcademicYearCreate, SemesterCreate, AcademicYearUpdate, SemesterUpdate
from ..dependencies import get_current_user

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from ..models import (
        Student, ClassSection, Subject, Department, User, ExeatRecord, 
        DisciplineRecord, House, Score, ClassSubjectScoreStatus, 
        ClassSectionReportStatus, Setting, School, TeacherAssignment
    )
    from ..dependencies import get_school_id
    from datetime import datetime
    from sqlalchemy import func

    school_id = get_school_id(current_user)

    # School Mode check
    setting = db.query(Setting).filter(Setting.key == "school_mode").first()
    school_mode = setting.value if setting and setting.value else "COMBINED"

    # Base queries scoped to school tenant
    user_query = db.query(User)
    student_query = db.query(Student).filter(Student.is_active == True)
    class_query = db.query(ClassSection)
    dept_query = db.query(Department)
    house_query = db.query(House)

    if school_id is not None:
        user_query = user_query.filter(User.school_id == school_id)
        student_query = student_query.filter(Student.school_id == school_id)
        class_query = class_query.filter(ClassSection.school_id == school_id) if hasattr(ClassSection, 'school_id') else class_query
        dept_query = dept_query.filter(Department.school_id == school_id)
        house_query = house_query.filter(House.school_id == school_id)

    teachers_count = user_query.join(User.roles).filter(User.roles.any(name="teacher")).count()
    depts_count = dept_query.count() if school_mode != "BASIC_ONLY" else 0
    classes_count = class_query.count()
    active_students_count = student_query.count()

    # Scores metrics
    scores_query = db.query(Score)
    if school_id is not None:
        scores_query = scores_query.join(Student, Student.id == Score.student_id).filter(Student.school_id == school_id)
    
    all_scores = scores_query.all()
    total_scores_recorded = len(all_scores)

    # Total subject assignments across classes
    assignments_query = db.query(TeacherAssignment)
    if school_id is not None:
        assignments_query = assignments_query.join(User, User.id == TeacherAssignment.teacher_id).filter(User.school_id == school_id)
    all_assignments = assignments_query.all()

    # Calculate Assessment Submission Progress
    expected_scores_count = max(1, active_students_count * max(1, len(all_assignments)))
    sba_completion_pct = round(min(100.0, (total_scores_recorded / expected_scores_count) * 100.0), 1) if all_scores else 0.0

    # Grade Distribution Curve & School Pass Rate
    grade_dist = {"A1": 0, "B2_B3": 0, "C4_C6": 0, "D7_E8": 0, "F9": 0}
    passing_scores_count = 0
    student_failing_counts = {} # student_id -> count of failing subjects

    for sc in all_scores:
        total = (sc.class_score or 0.0) + (sc.exam_score or 0.0)
        if total >= 50.0:
            passing_scores_count += 1
        else:
            student_failing_counts[sc.student_id] = student_failing_counts.get(sc.student_id, 0) + 1

        if total >= 75.0:
            grade_dist["A1"] += 1
        elif total >= 65.0:
            grade_dist["B2_B3"] += 1
        elif total >= 50.0:
            grade_dist["C4_C6"] += 1
        elif total >= 40.0:
            grade_dist["D7_E8"] += 1
        else:
            grade_dist["F9"] += 1

    school_pass_rate_pct = round((passing_scores_count / max(1, total_scores_recorded)) * 100.0, 1) if total_scores_recorded > 0 else 0.0
    at_risk_students_count = sum(1 for cnt in student_failing_counts.values() if cnt >= 2)

    # Core Subjects Performance Matrix
    core_subjects = ["English Language", "Core Mathematics", "Integrated Science", "Social Studies", "Mathematics", "Science"]
    core_matrix = []
    for c_name in ["English Language", "Core Mathematics", "Integrated Science", "Social Studies"]:
        sub_scores = [sc for sc in all_scores if sc.subject and c_name.lower() in sc.subject.name.lower()]
        if sub_scores:
            totals = [(sc.class_score or 0.0) + (sc.exam_score or 0.0) for sc in sub_scores]
            avg = round(sum(totals) / max(1, len(totals)), 1)
            pass_cnt = sum(1 for t in totals if t >= 50.0)
            pass_p = round((pass_cnt / max(1, len(totals))) * 100.0, 1)
            core_matrix.append({"subject": c_name, "average": avg, "pass_rate": pass_p, "count": len(totals)})
        else:
            core_matrix.append({"subject": c_name, "average": 0.0, "pass_rate": 0.0, "count": 0})

    # Department Compliance Matrix
    departments_matrix = []
    if school_mode != "BASIC_ONLY":
        depts = dept_query.all()
        for d in depts:
            hod_user = d.hod
            dept_subjects = d.subjects or []
            dept_subject_ids = [s.id for s in dept_subjects]
            
            dept_teachers_count = db.query(TeacherAssignment.teacher_id).filter(TeacherAssignment.subject_id.in_(dept_subject_ids)).distinct().count() if dept_subject_ids else 0
            dept_scores_count = len([sc for sc in all_scores if sc.subject_id in dept_subject_ids]) if dept_subject_ids else 0
            dept_expected = max(1, active_students_count * len(dept_subject_ids)) if dept_subject_ids else 1
            pct = round(min(100.0, (dept_scores_count / dept_expected) * 100.0), 1) if dept_subject_ids else 0.0
            
            status_str = "COMPLETE" if pct >= 100 else ("IN_PROGRESS" if pct > 0 else "PENDING")
            hod_display = (getattr(hod_user, 'full_name', None) or hod_user.username) if hod_user else "Unassigned"

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

    # Pending Teacher Submissions Roster (Top 6 Unsubmitted allocations)
    pending_submissions = []
    for asgn in all_assignments[:12]:
        sub_id = asgn.subject_id
        cls_id = asgn.class_section_id
        asgn_scores = [sc for sc in all_scores if sc.subject_id == sub_id and sc.student and sc.student.class_section_id == cls_id]
        if not asgn_scores:
            t_user = asgn.teacher
            t_name = (getattr(t_user, 'full_name', None) or t_user.username) if t_user else "Unassigned Teacher"
            c_name = asgn.class_section.name if asgn.class_section else "General"
            s_name = asgn.subject.name if asgn.subject else "Subject"
            pending_submissions.append({
                "teacher_name": t_name,
                "class_name": c_name,
                "subject_name": s_name,
                "status": "NOT_STARTED"
            })

    pending_hod_approvals = db.query(ClassSubjectScoreStatus).filter(ClassSubjectScoreStatus.status != "Approved").count()
    published_classes_count = db.query(ClassSectionReportStatus).filter(ClassSectionReportStatus.is_published == True).count()

    # 2. Domestic Executive Metrics
    is_boarder_filter = (Student.residential_status.in_(["B", "b", "Boarding", "BOARDING", "boarding"])) | (Student.house_id.isnot(None))
    total_boarders = student_query.filter(is_boarder_filter).count() if school_mode != "BASIC_ONLY" else 0
    total_day_students = max(0, active_students_count - total_boarders)

    now = datetime.now()

    # Exeats Movement & Safe Custody
    away_exeats_query = db.query(ExeatRecord).join(Student, Student.id == ExeatRecord.student_id).filter(
        Student.is_active == True,
        ExeatRecord.status.in_(["Departed", "Away", "Approved"])
    )
    if school_id is not None:
        away_exeats_query = away_exeats_query.filter(Student.school_id == school_id)

    away_exeats = away_exeats_query.all()
    currently_away_exeat = len(away_exeats) if school_mode != "BASIC_ONLY" else 0

    overdue_exeats = [ex for ex in away_exeats if ex.status == "Departed" and ex.expected_return and ex.expected_return < now]
    overdue_exeat_count = len(overdue_exeats) if school_mode != "BASIC_ONLY" else 0

    overdue_roster = []
    if school_mode != "BASIC_ONLY":
        for ex in overdue_exeats[:8]:
            st = ex.student
            st_name = st.full_name if st else "Unknown Student"
            h_name = st.house.name if st and st.house else "General"
            parent_phone = ex.parent_contact or (st.phone if st else None) or "Not Recorded"
            exp_str = ex.expected_return.strftime("%d %b, %H:%M") if ex.expected_return else "Overdue"
            overdue_roster.append({
                "id": ex.id,
                "student_name": st_name,
                "house_name": h_name,
                "expected_return": exp_str,
                "parent_phone": parent_phone,
                "reason": ex.reason or "Exeat",
                "exeat_type": ex.exeat_type or "General"
            })

    # Active Exeats Breakdown
    exeat_breakdown = {"Weekend": 0, "Medical": 0, "Special": 0, "Official": 0, "Day": 0}
    for ex in away_exeats:
        t = (ex.exeat_type or "Special").capitalize()
        if t in exeat_breakdown:
            exeat_breakdown[t] += 1
        else:
            exeat_breakdown["Special"] += 1

    # Student Health & Medical Registry Roster
    from ..models import StudentHealth
    health_query = db.query(StudentHealth).join(Student, Student.id == StudentHealth.student_id).filter(
        Student.is_active == True,
        (
            ((StudentHealth.allergies.isnot(None)) & (StudentHealth.allergies != "")) |
            ((StudentHealth.chronic_conditions.isnot(None)) & (StudentHealth.chronic_conditions != ""))
        )
    )
    if school_id is not None:
        health_query = health_query.filter(Student.school_id == school_id)

    health_records = health_query.all()
    medical_flags_count = len(health_records)

    medical_roster = []
    for hr in health_records[:8]:
        st = hr.student
        st_name = st.full_name if st else "Student"
        h_name = st.house.name if st and st.house else "Day/Unassigned"
        conds = []
        if hr.allergies:
            conds.append(f"Allergies: {hr.allergies}")
        if hr.chronic_conditions:
            conds.append(f"Chronic: {hr.chronic_conditions}")
        cond_str = " | ".join(conds) if conds else "Health Flag"
        emergency_phone = hr.emergency_contact or (st.phone if st else None) or "Not Recorded"
        medical_roster.append({
            "student_name": st_name,
            "house_name": h_name,
            "condition": cond_str,
            "emergency_phone": emergency_phone,
            "blood_group": hr.blood_group or "—"
        })

    # Discipline Queue
    disc_query = db.query(DisciplineRecord).join(Student, Student.id == DisciplineRecord.student_id).filter(
        DisciplineRecord.action_taken.is_(None)
    )
    if school_id is not None:
        disc_query = disc_query.filter(Student.school_id == school_id)

    disc_records = disc_query.order_by(DisciplineRecord.id.desc()).all()
    active_discipline_incidents = len(disc_records)

    pending_discipline_cases = []
    for dr in disc_records[:6]:
        st = dr.student
        st_name = st.full_name if st else "Student"
        h_name = st.house.name if st and st.house else "General"
        dt_str = dr.incident_date.strftime("%d %b %Y") if dr.incident_date else "Recent"
        pending_discipline_cases.append({
            "id": dr.id,
            "student_name": st_name,
            "house_name": h_name,
            "incident_type": dr.incident_type,
            "incident_date": dt_str,
            "description": dr.description
        })

    total_houses = house_query.count() if school_mode != "BASIC_ONLY" else 0

    # House & Dormitory Occupancy Matrix
    houses_matrix = []
    if school_mode != "BASIC_ONLY":
        all_houses = house_query.all()
        for h in all_houses:
            hm_user = db.query(User).filter(User.id == h.house_master_id).first() if h.house_master_id else None
            dorms = getattr(h, 'dormitories', [])
            dorms_count = len(dorms) if dorms else 0
            boarders_count = db.query(Student).filter(Student.house_id == h.id, Student.is_active == True).count()
            capacity = sum([d.capacity for d in dorms if hasattr(d, 'capacity') and d.capacity]) if dorms else 50
            capacity = max(1, capacity)
            occ_pct = round(min(100.0, (boarders_count / capacity) * 100.0), 1)
            
            hm_display = (getattr(hm_user, 'full_name', None) or hm_user.username) if hm_user else "Unassigned"

            status_str = "OPTIMAL"
            if occ_pct >= 95:
                status_str = "FULL"
            elif occ_pct >= 75:
                status_str = "HIGH"

            houses_matrix.append({
                "id": h.id,
                "name": h.name,
                "gender_type": getattr(h, 'gender', None) or "MIXED",
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
            "school_pass_rate_pct": school_pass_rate_pct,
            "at_risk_students_count": at_risk_students_count,
            "grade_distribution": grade_dist,
            "core_subjects_performance": core_matrix,
            "pending_submissions": pending_submissions[:6],
            "total_teachers": teachers_count,
            "total_departments": depts_count,
            "total_classes": classes_count,
            "pending_hod_approvals": pending_hod_approvals,
            "published_classes_count": published_classes_count,
            "departments_matrix": departments_matrix
        },
        "domestic": {
            "total_boarders": total_boarders,
            "total_day_students": total_day_students,
            "currently_away_exeat": currently_away_exeat,
            "overdue_exeat_count": overdue_exeat_count,
            "active_discipline_incidents": active_discipline_incidents,
            "medical_flags_count": medical_flags_count,
            "total_houses": total_houses,
            "houses_matrix": houses_matrix,
            "overdue_exeats_roster": overdue_roster,
            "active_exeats_breakdown": exeat_breakdown,
            "critical_medical_roster": medical_roster,
            "pending_discipline_cases": pending_discipline_cases
        }
    }

