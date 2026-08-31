from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AcademicYear, Semester, User
from ..schemas import AcademicYearCreate, SemesterCreate, AcademicYearUpdate, SemesterUpdate
from ..dependencies import get_current_user, get_school_id

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
    current_user: User = Depends(get_current_user),
    school_id: Optional[int] = Depends(get_school_id)
):
    from ..models import (
        Student, ClassSection, Subject, Department, User, ExeatRecord, 
        DisciplineRecord, House, Score, ClassSubjectScoreStatus, 
        ClassSectionReportStatus, Setting, School, TeacherAssignment
    )
    from datetime import datetime
    from sqlalchemy import func

    valid_user = current_user if (isinstance(current_user, User) or (hasattr(current_user, 'id') and not str(type(current_user)).endswith("Depends'>"))) else None
    target_sch_id = int(school_id) if isinstance(school_id, (int, float)) else None
    if target_sch_id is None and valid_user and getattr(valid_user, 'school_id', None):
        target_sch_id = valid_user.school_id

    # School Mode check
    if target_sch_id:
        sch_obj = db.query(School).filter(School.id == target_sch_id).first()
        school_mode = sch_obj.school_mode if sch_obj and sch_obj.school_mode else "COMBINED"
    else:
        setting = db.query(Setting).filter(Setting.key == "school_mode").first()
        school_mode = setting.value if setting and setting.value else "COMBINED"

    # Base queries scoped to school tenant
    user_query = db.query(User)
    student_query = db.query(Student).filter(Student.is_active == True)
    class_query = db.query(ClassSection)
    dept_query = db.query(Department)
    house_query = db.query(House)

    if target_sch_id is not None:
        user_query = user_query.filter(User.school_id == target_sch_id)
        student_query = student_query.filter(Student.school_id == target_sch_id)
        class_query = class_query.filter(ClassSection.school_id == target_sch_id) if hasattr(ClassSection, 'school_id') else class_query
        dept_query = dept_query.filter(Department.school_id == target_sch_id)
        house_query = house_query.filter(House.school_id == target_sch_id)

    teachers_count = user_query.join(User.roles).filter(User.roles.any(name="teacher")).count()
    depts_count = dept_query.count() if school_mode != "BASIC_ONLY" else 0
    classes_count = class_query.count()
    active_students_count = student_query.count()

    # Scores metrics
    scores_query = db.query(Score)
    if target_sch_id is not None:
        scores_query = scores_query.join(Student, Student.id == Score.student_id).filter(Student.school_id == target_sch_id)
    
    all_scores = scores_query.all()
    total_scores_recorded = len(all_scores)

    # Total subject assignments across classes
    assignments_query = db.query(TeacherAssignment)
    if target_sch_id is not None:
        assignments_query = assignments_query.join(User, User.id == TeacherAssignment.teacher_id).filter(User.school_id == target_sch_id)
    all_assignments = assignments_query.all()

    # Calculate Assessment Submission Progress
    expected_scores_count = max(1, active_students_count * max(1, len(all_assignments)))
    sba_completion_pct = round(min(100.0, (total_scores_recorded / expected_scores_count) * 100.0), 1) if all_scores else 0.0

    # Grade Distribution Curve & School Pass Rate
    grade_dist = {"A1": 0, "B2_B3": 0, "C4_C6": 0, "D7_E8": 0, "F9": 0}
    basic_grade_dist = {
        "Grade_1": 0, "Grade_2": 0, "Grade_3": 0, "Grade_4": 0, 
        "Grade_5": 0, "Grade_6": 0, "Grade_7": 0, "Grade_8": 0, "Grade_9": 0
    }
    proficiency_dist = {
        "Advanced": 0, "Proficient": 0, "Approaching": 0, "Developing": 0, "Beginning": 0
    }
    passing_scores_count = 0
    student_failing_counts = {} # student_id -> count of failing subjects

    for sc in all_scores:
        total = (sc.class_score or 0.0) + (sc.exam_score or 0.0)
        if total >= 50.0:
            passing_scores_count += 1
        else:
            student_failing_counts[sc.student_id] = student_failing_counts.get(sc.student_id, 0) + 1

        # SHS WASSCE Scale
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

        # Basic NCCA / BECE 9-Point Scale & Proficiency Bands
        if total >= 90.0:
            basic_grade_dist["Grade_1"] += 1
            proficiency_dist["Advanced"] += 1
        elif total >= 80.0:
            basic_grade_dist["Grade_2"] += 1
            proficiency_dist["Advanced"] += 1
        elif total >= 70.0:
            basic_grade_dist["Grade_3"] += 1
            proficiency_dist["Proficient"] += 1
        elif total >= 60.0:
            basic_grade_dist["Grade_4"] += 1
            proficiency_dist["Proficient"] += 1
        elif total >= 55.0:
            basic_grade_dist["Grade_5"] += 1
            proficiency_dist["Approaching"] += 1
        elif total >= 50.0:
            basic_grade_dist["Grade_6"] += 1
            proficiency_dist["Approaching"] += 1
        elif total >= 45.0:
            basic_grade_dist["Grade_7"] += 1
            proficiency_dist["Developing"] += 1
        elif total >= 40.0:
            basic_grade_dist["Grade_8"] += 1
            proficiency_dist["Developing"] += 1
        else:
            basic_grade_dist["Grade_9"] += 1
            proficiency_dist["Beginning"] += 1

    school_pass_rate_pct = round((passing_scores_count / max(1, total_scores_recorded)) * 100.0, 1) if total_scores_recorded > 0 else 0.0
    at_risk_students_count = sum(1 for cnt in student_failing_counts.values() if cnt >= 2)

    # Core Subjects Performance Matrix
    if school_mode == "BASIC_ONLY":
        basic_core_names = [
            "English Language", "Mathematics", "Science", "Social Studies", 
            "Computing", "Ghanaian Language", "Religious and Moral Education", 
            "Creative Arts", "Career Technology", "French"
        ]
        core_matrix = []
        for c_name in basic_core_names:
            sub_scores = [
                sc for sc in all_scores 
                if sc.subject and any(
                    k.lower() in sc.subject.name.lower() 
                    for k in [c_name, c_name.replace(" Language", ""), c_name.replace("Religious and Moral Education", "RME"), c_name.replace("Science", "Natural Science"), c_name.replace("Social Studies", "Our World Our People")]
                )
            ]
            if sub_scores:
                totals = [(sc.class_score or 0.0) + (sc.exam_score or 0.0) for sc in sub_scores]
                avg = round(sum(totals) / max(1, len(totals)), 1)
                pass_cnt = sum(1 for t in totals if t >= 50.0)
                pass_p = round((pass_cnt / max(1, len(totals))) * 100.0, 1)
                core_matrix.append({"subject": c_name, "average": avg, "pass_rate": pass_p, "count": len(totals)})
            else:
                core_matrix.append({"subject": c_name, "average": 0.0, "pass_rate": 0.0, "count": 0})
    else:
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

    # Department Compliance Matrix (SHS) & Classes Compliance Matrix (Basic)
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

    # Class-by-Class SBA Matrix (for Basic School mode & Master Overview)
    classes_matrix = []
    all_class_sections = class_query.all()
    for cls_item in all_class_sections:
        fm_user = cls_item.form_master
        fm_name = (getattr(fm_user, 'full_name', None) or fm_user.username) if fm_user else "Unassigned Class Teacher"
        c_students = [s for s in student_query.all() if s.class_section_id == cls_item.id]
        c_student_ids = {s.id for s in c_students}
        c_scores = [sc for sc in all_scores if sc.student_id in c_student_ids]
        
        cls_assignments = [asgn for asgn in all_assignments if asgn.class_section_id == cls_item.id]
        exp_c_scores = max(1, len(c_students) * max(1, len(cls_assignments))) if cls_assignments else max(1, len(c_students))
        c_sba_pct = round(min(100.0, (len(c_scores) / exp_c_scores) * 100.0), 1) if c_scores else 0.0
        
        c_pass_cnt = sum(1 for sc in c_scores if (sc.class_score or 0.0) + (sc.exam_score or 0.0) >= 50.0)
        c_pass_rate = round((c_pass_cnt / max(1, len(c_scores))) * 100.0, 1) if c_scores else 0.0
        
        status_str = "COMPLETE" if c_sba_pct >= 100 else ("IN_PROGRESS" if c_sba_pct > 0 else "PENDING")
        stage_title = cls_item.stage.name if cls_item.stage else "Basic"
        
        classes_matrix.append({
            "id": cls_item.id,
            "name": cls_item.name,
            "stage_name": stage_title,
            "class_teacher": fm_name,
            "student_count": len(c_students),
            "subjects_count": len(cls_assignments),
            "sba_completion_pct": c_sba_pct,
            "pass_rate_pct": c_pass_rate,
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
    if target_sch_id is not None:
        away_exeats_query = away_exeats_query.filter(Student.school_id == target_sch_id)

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
    if target_sch_id is not None:
        health_query = health_query.filter(Student.school_id == target_sch_id)

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
    if target_sch_id is not None:
        disc_query = disc_query.filter(Student.school_id == target_sch_id)

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

    # 3. Administration Executive Metrics
    all_users = user_query.all()
    total_staff = len(all_users)
    active_users_count = sum(1 for u in all_users if getattr(u, 'is_active', True))
    inactive_users_count = total_staff - active_users_count

    # Faculty teaching vs support staff
    assigned_teacher_ids = {ta.teacher_id for ta in db.query(TeacherAssignment).all() if ta.teacher_id}
    teaching_staff_count = 0
    unassigned_teachers_count = 0
    for u in all_users:
        user_role_names = [r.name.lower() for r in getattr(u, 'roles', [])]
        is_teacher = any(r in ['teacher', 'form_master', 'form_mistress', 'hod', 'assistant_headmaster_academic', 'assistant_head_academic'] for r in user_role_names) or (u.id in assigned_teacher_ids)
        if is_teacher:
            teaching_staff_count += 1
            if u.id not in assigned_teacher_ids:
                unassigned_teachers_count += 1

    non_teaching_staff_count = max(0, total_staff - teaching_staff_count)

    # Departmental staffing & HR allocation
    departments_staffing = []
    all_depts = dept_query.all() if school_mode != "BASIC_ONLY" else []
    for d in all_depts:
        hod_u = getattr(d, 'hod', None)
        hod_name = (getattr(hod_u, 'full_name', None) or hod_u.username) if hod_u else "Unassigned"
        dept_teachers = [u for u in all_users if getattr(u, 'department_id', None) == d.id]
        departments_staffing.append({
            "id": d.id,
            "name": d.name,
            "code": getattr(d, 'code', d.name[:4].upper()),
            "hod_name": hod_name,
            "staff_count": len(dept_teachers),
            "subjects_count": len(getattr(d, 'subjects', []))
        })

    # Admissions Funnel & CRF Tracking
    all_active_students = student_query.filter(Student.is_active == True).all()
    total_students_enrolled = len(all_active_students)
    
    placed_count = sum(1 for s in all_active_students if str(getattr(s, 'enrollment_status', '')).upper() == 'PLACED')
    form_completed_count = sum(1 for s in all_active_students if str(getattr(s, 'enrollment_status', '')).upper() in ['FORM_COMPLETED', 'FORM COMPLETED'])
    fully_registered_count = sum(1 for s in all_active_students if str(getattr(s, 'enrollment_status', '')).upper() in ['FULLY REGISTERED', 'FULLY_REGISTERED', 'REGISTERED'])
    if (placed_count + form_completed_count + fully_registered_count) == 0 and total_students_enrolled > 0:
        fully_registered_count = total_students_enrolled

    # GES Cumulative Record Folder (CRF) Tracking for Basic Education
    crf_completed_count = 0
    for s in all_active_students:
        has_crf = any([
            getattr(s, 'family_background_notes', None),
            getattr(s, 'personality_traits', None),
            getattr(s, 'teacher_observations', None),
            getattr(s, 'co_curricular_activities', None),
            getattr(s, 'hobbies_talents', None),
            getattr(s, 'leadership_notes', None)
        ])
        if has_crf:
            crf_completed_count += 1
    crf_completion_pct = round((crf_completed_count / max(1, len(all_active_students))) * 100.0, 1) if all_active_students else 0.0

    # Demographics (Stage-based for Basic School, Form-based for SHS)
    if school_mode == "BASIC_ONLY":
        kg_boys, kg_girls = 0, 0
        pri_boys, pri_girls = 0, 0
        jhs_boys, jhs_girls = 0, 0
        for s in all_active_students:
            c_name = (s.class_section.name if s.class_section else (s.class_name or "")).lower()
            is_male = (getattr(s, 'gender', 'M') or '').upper().startswith('M') or (getattr(s, 'gender', 'M') or '').upper() == 'BOY'
            if any(k in c_name for k in ['kg', 'nursery', 'creche', 'kindergarten', 'early']):
                if is_male: kg_boys += 1
                else: kg_girls += 1
            elif any(k in c_name for k in ['jhs', 'basic 7', 'basic 8', 'basic 9']) or (getattr(s, 'form', 0) in [1, 2, 3] and 'class' not in c_name and 'primary' not in c_name and 'basic 1' not in c_name and 'basic 2' not in c_name and 'basic 3' not in c_name and 'basic 4' not in c_name and 'basic 5' not in c_name and 'basic 6' not in c_name):
                if is_male: jhs_boys += 1
                else: jhs_girls += 1
            else:
                if is_male: pri_boys += 1
                else: pri_girls += 1
        
        stage_demographics = [
            {"stage": "Early Childhood (Nursery & KG)", "form": "Early Childhood", "boys": kg_boys, "girls": kg_girls, "total": kg_boys + kg_girls},
            {"stage": "Primary School (Class 1–6)", "form": "Primary School", "boys": pri_boys, "girls": pri_girls, "total": pri_boys + pri_girls},
            {"stage": "Junior High School (JHS 1–3)", "form": "Junior High School", "boys": jhs_boys, "girls": jhs_girls, "total": jhs_boys + jhs_girls},
        ]
        form_demographics = stage_demographics
    else:
        form1_boys = sum(1 for s in all_active_students if getattr(s, 'form', 1) == 1 and (getattr(s, 'gender', 'M') or '').upper().startswith('M'))
        form1_girls = sum(1 for s in all_active_students if getattr(s, 'form', 1) == 1 and (getattr(s, 'gender', 'F') or '').upper().startswith('F'))
        
        form2_boys = sum(1 for s in all_active_students if getattr(s, 'form', 1) == 2 and (getattr(s, 'gender', 'M') or '').upper().startswith('M'))
        form2_girls = sum(1 for s in all_active_students if getattr(s, 'form', 1) == 2 and (getattr(s, 'gender', 'F') or '').upper().startswith('F'))

        form3_boys = sum(1 for s in all_active_students if getattr(s, 'form', 1) == 3 and (getattr(s, 'gender', 'M') or '').upper().startswith('M'))
        form3_girls = sum(1 for s in all_active_students if getattr(s, 'form', 1) == 3 and (getattr(s, 'gender', 'F') or '').upper().startswith('F'))

        form_demographics = [
            {"stage": "Form 1", "form": "Form 1", "boys": form1_boys, "girls": form1_girls, "total": form1_boys + form1_girls},
            {"stage": "Form 2", "form": "Form 2", "boys": form2_boys, "girls": form2_girls, "total": form2_boys + form2_girls},
            {"stage": "Form 3", "form": "Form 3", "boys": form3_boys, "girls": form3_girls, "total": form3_boys + form3_girls},
        ]
        stage_demographics = form_demographics

    # Institutional Broadcast SMS Stats
    total_broadcast_messages = 0
    from ..models import MessageLog
    try:
        total_broadcast_messages = db.query(MessageLog).count()
    except Exception:
        pass

    # Recent Audit Log Activity
    recent_audit_logs = []
    from ..models import ActivityAuditLog
    try:
        audit_query = db.query(ActivityAuditLog)
        if target_sch_id is not None:
            audit_query = audit_query.filter(ActivityAuditLog.school_id == target_sch_id)
        audit_records = audit_query.order_by(ActivityAuditLog.timestamp.desc()).limit(6).all()
        for al in audit_records:
            ts_str = al.timestamp.strftime("%d %b, %H:%M") if al.timestamp else "Recent"
            recent_audit_logs.append({
                "id": al.id,
                "user_name": al.user_name or "System",
                "action": al.action,
                "entity_type": al.entity_type,
                "details": al.details or "",
                "timestamp": ts_str
            })
    except Exception:
        pass

    # 4. HOD Departmental Analytics
    dept = None
    if valid_user:
        dept = db.query(Department).filter(
            (Department.hod_id == valid_user.id) | (Department.id == getattr(valid_user, 'department_id', None))
        ).first()
    if not dept and school_mode != "BASIC_ONLY":
        dept = dept_query.first()

    departmental_data = {}
    if dept:
        dept_subjects = dept.subjects or []
        dept_sub_ids = [s.id for s in dept_subjects]
        dept_teachers = [u for u in all_users if getattr(u, 'department_id', None) == dept.id]
        
        # Dept scores
        dept_scores = [sc for sc in all_scores if sc.subject_id in dept_sub_ids]
        dept_pass_cnt = sum(1 for sc in dept_scores if (sc.class_score or 0.0) + (sc.exam_score or 0.0) >= 50.0)
        dept_pass_rate = round((dept_pass_cnt / max(1, len(dept_scores))) * 100.0, 1) if dept_scores else 0.0
        
        dept_exp_scores = max(1, active_students_count * max(1, len(dept_subjects))) if dept_subjects else 1
        dept_sba_pct = round(min(100.0, (len(dept_scores) / dept_exp_scores) * 100.0), 1) if dept_subjects else 0.0

        dept_grade_dist = {"A1": 0, "B2_B3": 0, "C4_C6": 0, "D7_E8": 0, "F9": 0}
        for sc in dept_scores:
            tot = (sc.class_score or 0.0) + (sc.exam_score or 0.0)
            if tot >= 75.0:
                dept_grade_dist["A1"] += 1
            elif tot >= 65.0:
                dept_grade_dist["B2_B3"] += 1
            elif tot >= 50.0:
                dept_grade_dist["C4_C6"] += 1
            elif tot >= 40.0:
                dept_grade_dist["D7_E8"] += 1
            else:
                dept_grade_dist["F9"] += 1

        # Teacher allocations & submission status in this department
        dept_submissions = []
        for asgn in db.query(TeacherAssignment).filter(TeacherAssignment.subject_id.in_(dept_sub_ids)).all():
            t_user = asgn.teacher
            t_name = (getattr(t_user, 'full_name', None) or t_user.username) if t_user else "Unassigned Teacher"
            c_name = asgn.class_section.name if asgn.class_section else "General"
            s_name = asgn.subject.name if asgn.subject else "Subject"
            c_id = asgn.class_section_id
            
            c_scores = [sc for sc in all_scores if sc.subject_id == asgn.subject_id and sc.student and sc.student.class_section_id == c_id]
            c_size = db.query(Student).filter(Student.class_section_id == c_id, Student.is_active == True).count() if c_id else 0
            c_pct = round(min(100.0, (len(c_scores) / max(1, c_size)) * 100.0), 1) if c_size > 0 else 0.0
            
            status_label = "COMPLETE" if c_pct >= 100 else ("IN_PROGRESS" if c_pct > 0 else "PENDING")
            dept_submissions.append({
                "teacher_name": t_name,
                "class_name": c_name,
                "subject_name": s_name,
                "recorded_count": len(c_scores),
                "total_students": c_size,
                "completion_pct": c_pct,
                "status": status_label
            })

        hod_u = getattr(dept, 'hod', None)
        hod_display = (getattr(hod_u, 'full_name', None) or hod_u.username) if hod_u else "Unassigned"

        departmental_data = {
            "id": dept.id,
            "name": dept.name,
            "code": getattr(dept, 'code', dept.name[:4].upper()),
            "hod_name": hod_display,
            "teacher_count": len(dept_teachers),
            "subject_count": len(dept_subjects),
            "sba_completion_pct": dept_sba_pct,
            "pass_rate_pct": dept_pass_rate,
            "grade_distribution": dept_grade_dist,
            "submissions": dept_submissions[:10],
            "total_scores_recorded": len(dept_scores)
        }

    # 5. Form Master Class Analytics
    cls = None
    if valid_user:
        cls = db.query(ClassSection).filter(ClassSection.form_master_id == valid_user.id).first()
    if not cls:
        cls = class_query.first()

    class_master_data = {}
    if cls:
        c_students = db.query(Student).filter(Student.class_section_id == cls.id, Student.is_active == True).all()
        c_boys = sum(1 for s in c_students if (s.gender or '').upper().startswith('M') or (s.gender or '').upper() == 'BOY')
        c_girls = len(c_students) - c_boys
        
        # Today's attendance for this class
        c_st_ids = {s.id for s in c_students}
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        from ..models import Attendance
        att_records = db.query(Attendance).filter(
            Attendance.student_id.in_(c_st_ids),
            Attendance.date >= today_start,
            Attendance.date <= today_end
        ).all() if c_st_ids else []
        att_present = sum(1 for a in att_records if (a.status or '').capitalize() in ['Present', 'Late'])
        att_pct = round((att_present / max(1, len(c_students))) * 100.0, 1) if c_students and att_records else 0.0

        # Class scores & performance
        cls_scores = [sc for sc in all_scores if sc.student_id in c_st_ids]
        cls_pass_cnt = sum(1 for sc in cls_scores if (sc.class_score or 0.0) + (sc.exam_score or 0.0) >= 50.0)
        cls_pass_rate = round((cls_pass_cnt / max(1, len(cls_scores))) * 100.0, 1) if cls_scores else 0.0

        # At-risk students in this class
        c_failing_counts = {}
        st_avg_scores = {}
        for sc in cls_scores:
            tot = (sc.class_score or 0.0) + (sc.exam_score or 0.0)
            if sc.student_id not in st_avg_scores:
                st_avg_scores[sc.student_id] = []
            st_avg_scores[sc.student_id].append(tot)
            if tot < 50.0:
                c_failing_counts[sc.student_id] = c_failing_counts.get(sc.student_id, 0) + 1

        at_risk_list = []
        for s in c_students:
            f_cnt = c_failing_counts.get(s.id, 0)
            if f_cnt >= 2:
                scores_arr = st_avg_scores.get(s.id, [0])
                avg_m = round(sum(scores_arr) / max(1, len(scores_arr)), 1)
                at_risk_list.append({
                    "id": s.id,
                    "name": s.full_name,
                    "index_number": s.index_number or s.admission_number or "—",
                    "failing_subjects_count": f_cnt,
                    "average_score": avg_m,
                    "guardian_phone": s.phone or "Not Recorded"
                })

        # Subject continuous assessment completion matrix for this class
        class_subjects_matrix = []
        for asgn in db.query(TeacherAssignment).filter(TeacherAssignment.class_section_id == cls.id).all():
            s_name = asgn.subject.name if asgn.subject else "Subject"
            t_user = asgn.teacher
            t_name = (getattr(t_user, 'full_name', None) or t_user.username) if t_user else "Unassigned"
            sub_sc = [sc for sc in cls_scores if sc.subject_id == asgn.subject_id]
            pct = round(min(100.0, (len(sub_sc) / max(1, len(c_students))) * 100.0), 1) if c_students else 0.0
            class_subjects_matrix.append({
                "subject_name": s_name,
                "teacher_name": t_name,
                "scores_recorded": len(sub_sc),
                "total_students": len(c_students),
                "completion_pct": pct,
                "status": "COMPLETE" if pct >= 100 else ("IN_PROGRESS" if pct > 0 else "PENDING")
            })

        class_master_data = {
            "class_id": cls.id,
            "class_name": cls.name,
            "stage_name": cls.stage.name if cls.stage else "",
            "total_students": len(c_students),
            "boys_count": c_boys,
            "girls_count": c_girls,
            "attendance_today_pct": att_pct,
            "attendance_taken": len(att_records) > 0,
            "pass_rate_pct": cls_pass_rate,
            "at_risk_count": len(at_risk_list),
            "at_risk_students": at_risk_list[:6],
            "subjects_matrix": class_subjects_matrix[:8]
        }

    # 6. Subject Teacher Personal Analytics
    teacher_allocations = []
    teacher_at_risk_list = []
    today_periods = []
    t_sba_overall_pct = 0.0
    
    t_user_id = valid_user.id if valid_user else None
    t_assignments = db.query(TeacherAssignment).filter(TeacherAssignment.teacher_id == t_user_id).all() if t_user_id else []
    if not t_assignments and all_assignments:
        first_t_id = all_assignments[0].teacher_id
        t_assignments = db.query(TeacherAssignment).filter(TeacherAssignment.teacher_id == first_t_id).all()
        t_user_id = first_t_id

    if t_assignments:
        total_rec = 0
        total_exp = 0
        for asgn in t_assignments:
            c_id = asgn.class_section_id
            s_id = asgn.subject_id
            c_name = asgn.class_section.name if asgn.class_section else "Class"
            s_name = asgn.subject.name if asgn.subject else "Subject"
            c_size = db.query(Student).filter(Student.class_section_id == c_id, Student.is_active == True).count() if c_id else 0
            sc_list = [sc for sc in all_scores if sc.subject_id == s_id and sc.student and sc.student.class_section_id == c_id]
            rec_cnt = len(sc_list)
            pct = round(min(100.0, (rec_cnt / max(1, c_size)) * 100.0), 1) if c_size > 0 else 0.0
            
            total_rec += rec_cnt
            total_exp += c_size
            
            for sc in sc_list:
                tot = (sc.class_score or 0.0) + (sc.exam_score or 0.0)
                if tot < 50.0 and sc.student:
                    teacher_at_risk_list.append({
                        "id": sc.student.id,
                        "name": sc.student.full_name,
                        "class_name": c_name,
                        "subject_name": s_name,
                        "score": tot,
                        "phone": sc.student.phone or "Not Recorded"
                    })

            teacher_allocations.append({
                "assignment_id": asgn.id,
                "class_id": c_id,
                "class_name": c_name,
                "subject_id": s_id,
                "subject_name": s_name,
                "class_size": c_size,
                "scores_recorded": rec_cnt,
                "completion_pct": pct,
                "status": "COMPLETE" if pct >= 100 else ("IN_PROGRESS" if pct > 0 else "NOT_STARTED")
            })

        t_sba_overall_pct = round(min(100.0, (total_rec / max(1, total_exp)) * 100.0), 1) if total_exp > 0 else 0.0

        dow = datetime.now().isoweekday()
        from ..models import Timetable
        tt_records = db.query(Timetable).filter(
            Timetable.teacher_id == t_user_id,
            Timetable.day_of_week == dow
        ).order_by(Timetable.period_number.asc()).all()
        for tt in tt_records:
            today_periods.append({
                "period_number": tt.period_number,
                "start_time": tt.start_time or "—",
                "end_time": tt.end_time or "—",
                "subject_name": tt.subject.name if tt.subject else "Subject",
                "class_name": tt.class_section.name if tt.class_section else "Class",
                "room": tt.room or "Standard Classroom"
            })

    teacher_data = {
        "total_classes": len({a.class_section_id for a in t_assignments if a.class_section_id}),
        "total_subjects": len({a.subject_id for a in t_assignments if a.subject_id}),
        "total_allocations": len(t_assignments),
        "sba_completion_pct": t_sba_overall_pct,
        "allocations": teacher_allocations,
        "today_timetable": today_periods,
        "at_risk_students": teacher_at_risk_list[:8]
    }

    # 7. Housemaster / Housemistress Personal House Analytics
    target_house = None
    if valid_user:
        target_house = db.query(House).filter(
            (House.house_master_id == valid_user.id) |
            (House.assistant_house_master_id == valid_user.id) |
            (House.senior_in_charge_id == valid_user.id) |
            (House.house_master_girls_id == valid_user.id) |
            (House.assistant_house_master_girls_id == valid_user.id)
        ).first()
    if not target_house and school_mode != "BASIC_ONLY":
        target_house = house_query.first()

    house_master_data = {}
    if target_house:
        h_boarders = db.query(Student).filter(Student.house_id == target_house.id, Student.is_active == True).all()
        h_dorms = getattr(target_house, 'dormitories', [])
        h_cap = sum([d.capacity for d in h_dorms if hasattr(d, 'capacity') and d.capacity]) if h_dorms else 50
        h_cap = max(1, h_cap)
        h_occ_pct = round(min(100.0, (len(h_boarders) / h_cap) * 100.0), 1)

        h_st_ids = {s.id for s in h_boarders}
        h_away_exeats = [ex for ex in away_exeats if ex.student_id in h_st_ids]
        h_overdue = [ex for ex in h_away_exeats if ex.status == "Departed" and ex.expected_return and ex.expected_return < now]

        h_medical = [hr for hr in medical_roster if any(s.full_name == hr["student_name"] for s in h_boarders)]
        h_discipline = [dc for dc in pending_discipline_cases if any(s.full_name == dc["student_name"] for s in h_boarders)]

        dorm_list = []
        for d in h_dorms:
            d_students_cnt = db.query(Student).filter(Student.dormitory_id == d.id, Student.is_active == True).count()
            d_cap = d.capacity if hasattr(d, 'capacity') and d.capacity else 20
            d_pct = round(min(100.0, (d_students_cnt / max(1, d_cap)) * 100.0), 1)
            dorm_list.append({
                "id": d.id,
                "name": d.name,
                "occupants": d_students_cnt,
                "capacity": d_cap,
                "occupancy_pct": d_pct
            })

        house_master_data = {
            "house_id": target_house.id,
            "house_name": target_house.name,
            "gender_type": getattr(target_house, 'gender', 'MIXED'),
            "total_boarders": len(h_boarders),
            "total_capacity": h_cap,
            "occupancy_pct": h_occ_pct,
            "dormitories": dorm_list,
            "active_exeats_count": len(h_away_exeats),
            "active_exeats": [{
                "id": ex.id,
                "student_name": ex.student.full_name if ex.student else "Student",
                "exeat_type": ex.exeat_type or "Special",
                "expected_return": ex.expected_return.strftime("%d %b, %H:%M") if ex.expected_return else "—",
                "is_overdue": ex in h_overdue,
                "parent_phone": ex.parent_contact or (ex.student.phone if ex.student else None) or "Not Recorded"
            } for ex in h_away_exeats[:8]],
            "medical_alerts": h_medical[:6],
            "discipline_cases": h_discipline[:6]
        }

    # 8. Bursar & Financial Analytics
    from ..models import Fee, Payment, Asset, TextbookAllocation, UniformItem, UniformDisbursement, GatePassLog, StudentClearanceRecord
    all_fees = db.query(Fee).all()
    all_payments = db.query(Payment).all()

    total_billed = sum(f.amount for f in all_fees) if all_fees else 0.0
    total_collected = sum(f.amount_paid for f in all_fees) if all_fees else 0.0
    total_arrears = max(0.0, total_billed - total_collected)
    collection_rate = round((total_collected / max(1.0, total_billed)) * 100.0, 1) if total_billed > 0 else 0.0

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    payments_today = [p for p in all_payments if p.payment_date and p.payment_date >= today_start and p.payment_date <= today_end]
    collected_today = sum(p.amount_paid for p in payments_today)

    fee_types_map = {}
    for f in all_fees:
        ft = f.fee_type or "Tuition"
        if ft not in fee_types_map:
            fee_types_map[ft] = {"billed": 0.0, "collected": 0.0}
        fee_types_map[ft]["billed"] += f.amount or 0.0
        fee_types_map[ft]["collected"] += f.amount_paid or 0.0

    fee_categories = []
    for ft, vals in fee_types_map.items():
        b = vals["billed"]
        c = vals["collected"]
        pct = round((c / max(1.0, b)) * 100.0, 1) if b > 0 else 0.0
        fee_categories.append({
            "category": ft,
            "billed": round(b, 2),
            "collected": round(c, 2),
            "arrears": round(max(0.0, b - c), 2),
            "collection_pct": pct
        })

    recent_payments_list = []
    sorted_payments = sorted(all_payments, key=lambda x: x.payment_date or datetime.min, reverse=True)
    for p in sorted_payments[:8]:
        st = p.fee.student if p.fee and p.fee.student else None
        st_ident = (st.student_code or st.bece_index_number or st.enrolment_code) if st else "—"
        recent_payments_list.append({
            "id": p.id,
            "receipt_no": p.reference_no or f"REC-{p.id:04d}",
            "student_name": st.full_name if st else "Student",
            "index_number": st_ident,
            "amount": round(p.amount_paid, 2),
            "method": p.payment_method or "Cash",
            "date": p.payment_date.strftime("%d %b, %H:%M") if p.payment_date else "—"
        })

    debtors_list = []
    for f in all_fees:
        owed = (f.amount or 0.0) - (f.amount_paid or 0.0)
        if owed > 0 and f.student and f.student.is_active:
            debtors_list.append({
                "student_id": f.student.id,
                "student_name": f.student.full_name,
                "class_name": f.student.class_section.name if f.student.class_section else "—",
                "fee_type": f.fee_type or "Fees",
                "amount_owed": round(owed, 2),
                "guardian_phone": f.student.phone or "Not Recorded"
            })
    debtors_list = sorted(debtors_list, key=lambda x: x["amount_owed"], reverse=True)[:8]

    bursar_data = {
        "total_billed_ghc": round(total_billed, 2),
        "total_collected_ghc": round(total_collected, 2),
        "total_arrears_ghc": round(total_arrears, 2),
        "collection_rate_pct": collection_rate,
        "collected_today_ghc": round(collected_today, 2),
        "payments_today_count": len(payments_today),
        "fee_categories": fee_categories,
        "recent_payments": recent_payments_list,
        "top_debtors": debtors_list
    }

    # 9. Storekeeper & Inventory Analytics
    all_assets = db.query(Asset).all()
    all_uniforms = db.query(UniformItem).all()
    all_textbooks = db.query(TextbookAllocation).all()
    
    total_uniform_stock = sum(u.quantity_in_stock for u in all_uniforms) if all_uniforms else 0
    low_stock_uniforms = [u for u in all_uniforms if (u.quantity_in_stock or 0) < 10]
    damaged_assets = [a for a in all_assets if (a.status or '').lower() in ['damaged', 'repair', 'broken']]

    storekeeper_data = {
        "total_assets_count": len(all_assets),
        "total_textbooks_issued": len([t for t in all_textbooks if t.status == 'Issued']),
        "total_uniforms_in_stock": total_uniform_stock,
        "low_stock_alerts_count": len(low_stock_uniforms) + len(damaged_assets),
        "low_stock_items": [{
            "item_name": u.item_name,
            "type": "Uniform / Kit",
            "quantity_remaining": u.quantity_in_stock,
            "unit_price": u.unit_price or 0.0
        } for u in low_stock_uniforms[:6]],
        "damaged_assets": [{
            "name": a.name,
            "category": a.category,
            "location": a.location or "General Store",
            "status": a.status
        } for a in damaged_assets[:6]]
    }

    # 10. Security & Gatehouse Analytics
    all_gate_logs = db.query(GatePassLog).all()
    today_gate = [g for g in all_gate_logs if g.timestamp and g.timestamp >= today_start and g.timestamp <= today_end]
    
    security_data = {
        "active_gate_exeats_count": len([ex for ex in away_exeats if ex.status == "Departed"]),
        "overdue_exeats_count": len(overdue_roster),
        "today_gate_movements_count": len(today_gate),
        "overdue_watchlist": [{
            "id": ex.id,
            "student_name": ex.student.full_name if ex.student else "Student",
            "class_name": ex.student.class_section.name if ex.student and ex.student.class_section else "—",
            "destination": ex.destination,
            "expected_return": ex.expected_return.strftime("%d %b, %H:%M") if ex.expected_return else "—",
            "parent_phone": ex.parent_contact or (ex.student.phone if ex.student else None) or "Not Recorded"
        } for ex in overdue_roster[:8]],
        "recent_gate_logs": [{
            "action": g.action,
            "student_name": g.student.full_name if g.student else "Student",
            "time": g.timestamp.strftime("%H:%M") if g.timestamp else "—",
            "officer": g.officer_name or "Security Officer"
        } for g in sorted(today_gate, key=lambda x: x.timestamp or datetime.min, reverse=True)[:8]]
    }

    # 11. Student & Parent Stakeholder Portals
    st_record = None
    if valid_user:
        st_record = db.query(Student).filter(Student.parent_id == valid_user.id).first()
        if not st_record and getattr(valid_user, 'username', None):
            st_record = db.query(Student).filter(Student.student_code == valid_user.username).first()
    if not st_record:
        st_record = db.query(Student).filter(Student.is_active == True).first()

    student_portal_data = {}
    if st_record:
        st_scores = [sc for sc in all_scores if sc.student_id == st_record.id]
        st_avg = round(sum((sc.class_score or 0.0) + (sc.exam_score or 0.0) for sc in st_scores) / max(1, len(st_scores)), 1) if st_scores else 0.0
        
        st_fees = db.query(Fee).filter(Fee.student_id == st_record.id).all()
        st_billed = sum(f.amount for f in st_fees) if st_fees else 0.0
        st_paid = sum(f.amount_paid for f in st_fees) if st_fees else 0.0

        st_att = db.query(Attendance).filter(Attendance.student_id == st_record.id).all()
        st_pres = sum(1 for a in st_att if (a.status or '').capitalize() in ['Present', 'Late'])
        st_att_pct = round((st_pres / max(1, len(st_att))) * 100.0, 1) if st_att else 100.0

        st_active_ex = db.query(ExeatRecord).filter(
            ExeatRecord.student_id == st_record.id,
            ExeatRecord.status.in_(["Approved", "Departed", "Pending"])
        ).first()

        st_code = st_record.student_code or st_record.bece_index_number or st_record.enrolment_code or "—"
        student_portal_data = {
            "student_id": st_record.id,
            "name": st_record.full_name,
            "index_number": st_code,
            "class_name": st_record.class_section.name if st_record.class_section else "Unassigned",
            "stage_name": st_record.class_section.stage.name if st_record.class_section and st_record.class_section.stage else "",
            "program_name": st_record.program.name if st_record.program else "General",
            "house_name": st_record.house.name if st_record.house else "Day Student",
            "dormitory_name": st_record.dormitory.name if st_record.dormitory else "None",
            "term_average": st_avg,
            "attendance_rate_pct": st_att_pct,
            "fee_summary": {
                "billed": round(st_billed, 2),
                "paid": round(st_paid, 2),
                "balance": round(max(0.0, st_billed - st_paid), 2)
            },
            "subjects_count": len(st_scores),
            "active_exeat_status": st_active_ex.status if st_active_ex else "On Campus"
        }

    parent_portal_data = {
        "wards": [student_portal_data] if student_portal_data else []
    }

    return {
        "school_mode": school_mode,
        "academic": {
            "sba_completion_pct": sba_completion_pct,
            "crf_completion_pct": crf_completion_pct,
            "school_pass_rate_pct": school_pass_rate_pct,
            "at_risk_students_count": at_risk_students_count,
            "grade_distribution": grade_dist,
            "basic_grade_distribution": basic_grade_dist,
            "proficiency_distribution": proficiency_dist,
            "core_subjects_performance": core_matrix,
            "pending_submissions": pending_submissions[:6],
            "total_teachers": teachers_count,
            "total_departments": depts_count,
            "total_classes": classes_count,
            "pending_hod_approvals": pending_hod_approvals,
            "published_classes_count": published_classes_count,
            "departments_matrix": departments_matrix,
            "classes_matrix": classes_matrix
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
        },
        "administration": {
            "total_staff": total_staff,
            "teaching_staff_count": teaching_staff_count,
            "non_teaching_staff_count": non_teaching_staff_count,
            "unassigned_teachers_count": unassigned_teachers_count,
            "active_users_count": active_users_count,
            "inactive_users_count": inactive_users_count,
            "total_students_enrolled": total_students_enrolled,
            "crf_completion_pct": crf_completion_pct,
            "admissions_funnel": {
                "placed": placed_count,
                "form_completed": form_completed_count,
                "fully_registered": fully_registered_count,
                "total": total_students_enrolled
            },
            "form_demographics": form_demographics,
            "stage_demographics": stage_demographics,
            "departments_staffing": departments_staffing,
            "total_broadcast_messages": total_broadcast_messages,
            "recent_audit_logs": recent_audit_logs,
            "total_classes": classes_count,
            "total_departments": depts_count
        },
        "departmental": departmental_data,
        "class_master": class_master_data,
        "teacher": teacher_data,
        "house_master": house_master_data,
        "bursar": bursar_data,
        "storekeeper": storekeeper_data,
        "security": security_data,
        "student_portal": student_portal_data,
        "parent_portal": parent_portal_data
    }

