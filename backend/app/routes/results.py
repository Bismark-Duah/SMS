from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from ..database import get_db
from ..models import Score, TeacherAssignment, User, Student, Subject, Setting, SchoolStage, ClassSection, School
from ..schemas import ScoreCreate
from ..services.grading import GradingService
from ..dependencies import get_current_user, get_school_id
from ..services.sync_engine import log_sync_change

router = APIRouter()

def _get_school_mode(db: Session, school_id: Optional[int] = None) -> str:
    if school_id:
        sch = db.query(School).filter(School.id == school_id).first()
        if sch and sch.school_mode:
            return sch.school_mode
    setting = db.query(Setting).filter(Setting.key == "school_mode").first()
    return setting.value if setting and setting.value else "COMBINED"


def _check_score_lock(db: Session, semester_id: int, user: User):
    locked_semesters_setting = db.query(Setting).filter(Setting.key == "locked_semester_ids").first()
    if locked_semesters_setting and locked_semesters_setting.value:
        import json
        try:
            locked_ids = json.loads(locked_semesters_setting.value)
            if semester_id in locked_ids:
                role_names = [r.name.lower() for r in user.roles]
                if not any(r in role_names for r in ["admin", "super_admin", "headmaster", "headmistress", "assistant_headmaster_academic", "assistant_head_academic", "assistant_headmaster_admin", "assistant_head_admin"]):
                    raise HTTPException(
                        status_code=403,
                        detail="Access Denied: This academic term is locked. Only the Assistant Headmaster (Academic) or Headmaster can override scores."
                    )
        except HTTPException:
            raise
        except Exception:
            pass

# ── Existing Endpoints ─────────────────────────────────────────────────────────

@router.get("/")
def list_scores(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    school_id = get_school_id(current_user)
    query = db.query(Score)
    if school_id is not None:
        query = query.join(Score.student).filter(Student.school_id == school_id)
    mode = _get_school_mode(db, school_id)

    if mode == "BASIC_ONLY":
        query = query.join(Score.student).join(Student.class_section).join(ClassSection.stage).filter(SchoolStage.school_type == "Basic")
    elif mode == "SHS_ONLY":
        query = query.join(Score.student).join(Student.class_section).join(ClassSection.stage).filter(SchoolStage.school_type == "SHS")

    if current_user:
        role_names = [r.name.lower() for r in current_user.roles]
        admin_exec_roles = {"admin", "super_admin", "headmaster", "headmistress", "assistant_headmaster_academic", "assistant_head_academic", "hod"}
        if not any(r in admin_exec_roles for r in role_names):
            assignments = (
                db.query(TeacherAssignment)
                .filter(TeacherAssignment.teacher_id == current_user.id)
                .all()
            )
            if not assignments:
                return []
            from sqlalchemy import and_, or_
            query = query.join(Student).filter(
                or_(
                    *[
                        and_(
                            Score.subject_id == a.subject_id,
                            Student.class_section_id == a.class_section_id,
                        )
                        for a in assignments
                    ]
                )
            )

    return query.all()


@router.post("/")
def create_score(
    score: ScoreCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_score_lock(db, score.semester_id, current_user)

    school_id = get_school_id(current_user)
    student = db.query(Student).filter(Student.id == score.student_id).first()
    if not student or (school_id is not None and student.school_id != school_id):
        raise HTTPException(status_code=404, detail="Student not found in your school.")

    if current_user:
        role_names = [r.name.lower() for r in current_user.roles]
        admin_exec_roles = {"admin", "super_admin", "headmaster", "headmistress", "assistant_headmaster_academic", "assistant_head_academic", "hod"}
        if not any(r in admin_exec_roles for r in role_names):
            assignment = db.query(TeacherAssignment).filter(
                TeacherAssignment.teacher_id == current_user.id,
                TeacherAssignment.subject_id == score.subject_id,
                TeacherAssignment.class_section_id == student.class_section_id,
            ).first()
            if not assignment:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to record scores for this student/subject.",
                )


    # Upsert: if a score already exists for student+subject+semester, update it
    existing = db.query(Score).filter(
        Score.student_id == score.student_id,
        Score.subject_id == score.subject_id,
        Score.semester_id == score.semester_id,
    ).first()

    total = GradingService.calculate_total(score.class_score, score.exam_score)
    grading = GradingService.get_grade(total)

    if existing:
        existing.class_score = score.class_score
        existing.exam_score = score.exam_score
        existing.total_score = total
        existing.grade = grading["grade"]
        existing.remark = grading["remark"]
        
        log_sync_change(db, school_id or 1, "score", existing.id, "UPDATE", {
            "student_id": score.student_id,
            "subject_id": score.subject_id,
            "semester_id": score.semester_id,
            "class_score": score.class_score,
            "exam_score": score.exam_score,
            "total_score": total,
            "grade": grading["grade"],
            "remark": grading["remark"]
        })
        
        db.commit()
        db.refresh(existing)

        from ..services.audit import AuditService
        AuditService.log(
            db=db,
            action="SCORE_UPDATE",
            entity_type="Score",
            entity_id=existing.id,
            details={
                "student_id": score.student_id,
                "subject_id": score.subject_id,
                "semester_id": score.semester_id,
                "class_score": score.class_score,
                "exam_score": score.exam_score,
                "total_score": total,
                "grade": grading["grade"]
            },
            user=current_user,
            school_id=school_id
        )
        return existing

    db_score = Score(
        student_id=score.student_id,
        subject_id=score.subject_id,
        semester_id=score.semester_id,
        class_score=score.class_score,
        exam_score=score.exam_score,
        total_score=total,
        grade=grading["grade"],
        remark=grading["remark"],
    )
    db.add(db_score)
    db.flush()

    log_sync_change(db, school_id or 1, "score", db_score.id, "INSERT", {
        "student_id": score.student_id,
        "subject_id": score.subject_id,
        "semester_id": score.semester_id,
        "class_score": score.class_score,
        "exam_score": score.exam_score,
        "total_score": total,
        "grade": grading["grade"],
        "remark": grading["remark"]
    })

    db.commit()
    db.refresh(db_score)

    from ..services.audit import AuditService
    AuditService.log(
        db=db,
        action="SCORE_CREATE",
        entity_type="Score",
        entity_id=db_score.id,
        details={
            "student_id": score.student_id,
            "subject_id": score.subject_id,
            "semester_id": score.semester_id,
            "class_score": score.class_score,
            "exam_score": score.exam_score,
            "total_score": total,
            "grade": grading["grade"]
        },
        user=current_user,
        school_id=school_id
    )
    return db_score


# ── New Endpoints ──────────────────────────────────────────────────────────────

@router.get("/class/{class_id}")
def get_class_scores(
    class_id: int,
    semester_id: int = Query(...),
    subject_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all scores for a class section in a semester, enriched with student
    and subject names. Optionally filtered by subject_id.
    """
    school_id = get_school_id(current_user)
    query = (
        db.query(Score)
        .options(joinedload(Score.student), joinedload(Score.subject))
        .join(Student, Score.student_id == Student.id)
        .filter(Student.class_section_id == class_id, Score.semester_id == semester_id)
    )
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)
    if subject_id:
        query = query.filter(Score.subject_id == subject_id)

    scores = query.order_by(Student.full_name).all()

    return [
        {
            "id": s.id,
            "student_id": s.student_id,
            "student_name": s.student.full_name if s.student else f"Student {s.student_id}",
            "student_code": s.student.student_code if s.student else "",
            "subject_id": s.subject_id,
            "subject_name": s.subject.name if s.subject else f"Subject {s.subject_id}",
            "semester_id": s.semester_id,
            "class_score": s.class_score,
            "exam_score": s.exam_score,
            "total_score": s.total_score,
            "grade": s.grade,
            "remark": s.remark,
        }
        for s in scores
    ]


@router.get("/class/{class_id}/students")
def get_class_students_for_scoring(
    class_id: int,
    semester_id: int = Query(...),
    subject_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all active students in a class with any existing score for the
    given semester+subject pre-loaded (for the bulk entry form).
    """
    school_id = get_school_id(current_user)
    stud_query = db.query(Student).filter(Student.class_section_id == class_id, Student.is_active == True)
    if school_id is not None:
        stud_query = stud_query.filter(Student.school_id == school_id)
    students = stud_query.order_by(Student.full_name).all()

    if not students:
        return []

    # Batch query all existing scores in a single SQL operation to eliminate N+1 queries
    student_ids = [s.id for s in students]
    existing_scores = db.query(Score).filter(
        Score.student_id.in_(student_ids),
        Score.subject_id == subject_id,
        Score.semester_id == semester_id,
    ).all()
    score_map = {sc.student_id: sc for sc in existing_scores}

    result = []
    for student in students:
        score = score_map.get(student.id)
        result.append(
            {
                "student_id": student.id,
                "student_code": student.student_code,
                "student_name": student.full_name,
                "class_score": score.class_score if score else 0.0,
                "exam_score": score.exam_score if score else 0.0,
                "total_score": score.total_score if score else 0.0,
                "grade": score.grade if score else "",
                "remark": score.remark if score else "",
                "score_id": score.id if score else None,
            }
        )
    return result


@router.put("/{score_id}")
def update_score(
    score_id: int,
    score: ScoreCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(Score).filter(Score.id == score_id)
    if school_id is not None:
        query = query.join(Score.student).filter(Student.school_id == school_id)
    existing = query.first()
    if not existing:
        raise HTTPException(status_code=404, detail="Score record not found.")

    _check_score_lock(db, existing.semester_id, current_user)

    total = GradingService.calculate_total(score.class_score, score.exam_score)
    grading = GradingService.get_grade(total)

    existing.class_score = score.class_score
    existing.exam_score = score.exam_score
    existing.total_score = total
    existing.grade = grading["grade"]
    existing.remark = grading["remark"]

    log_sync_change(db, school_id or 1, "score", existing.id, "UPDATE", {
        "student_id": existing.student_id,
        "subject_id": existing.subject_id,
        "semester_id": existing.semester_id,
        "class_score": score.class_score,
        "exam_score": score.exam_score,
        "total_score": total,
        "grade": grading["grade"],
        "remark": grading["remark"]
    })

    db.commit()
    db.refresh(existing)
    return existing


# ── Analytics ──────────────────────────────────────────────────────────────────

@router.get("/analytics/class-averages/{class_id}")
def get_class_averages(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculates average scores per subject for a specific class section."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from sqlalchemy import func

    school_id = get_school_id(current_user)
    query = (
        db.query(Subject.name.label("subject_name"), func.avg(Score.total_score).label("average_score"))
        .join(Score.subject)
        .join(Score.student)
        .filter(Student.class_section_id == class_id)
    )
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)

    averages = query.group_by(Subject.id).all()

    return [{"subject": a.subject_name, "average": round(float(a.average_score), 2)} for a in averages]


# ── 3-Tier Marks Approval Workflow ─────────────────────────────────────────────

@router.post("/submit-to-hod")
def submit_to_hod(
    class_id: int = Query(...),
    subject_id: int = Query(...),
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tier 1: Subject Teacher submits class score sheet to HOD."""
    school_id = get_school_id(current_user)
    scores_q = db.query(Score).join(Student).filter(
        Student.class_section_id == class_id,
        Score.subject_id == subject_id,
        Score.semester_id == semester_id
    )
    if school_id is not None:
        scores_q = scores_q.filter(Student.school_id == school_id)
    scores = scores_q.all()

    if not scores:
        raise HTTPException(status_code=404, detail="No scores found for this class, subject, and semester in your school.")

    for s in scores:
        s.approval_status = "SUBMITTED_TO_HOD"

    db.commit()
    return {"message": f"Successfully submitted {len(scores)} score record(s) to HOD for review.", "status": "SUBMITTED_TO_HOD"}


@router.post("/approve-by-hod")
def approve_by_hod(
    class_id: int = Query(...),
    subject_id: int = Query(...),
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tier 2: HOD verifies and approves department score sheet."""
    role_names = [r.name.lower() for r in current_user.roles] if hasattr(current_user, 'roles') and current_user.roles else []
    allowed = {"admin", "super_admin", "headmaster", "headmistress", "assistant_headmaster_academic", "assistant_head_academic", "hod"}
    if not any(r in allowed for r in role_names):
        raise HTTPException(status_code=403, detail="Only HODs or Academic Executives can approve score sheets.")

    school_id = get_school_id(current_user)
    scores_q = db.query(Score).join(Student).filter(
        Student.class_section_id == class_id,
        Score.subject_id == subject_id,
        Score.semester_id == semester_id
    )
    if school_id is not None:
        scores_q = scores_q.filter(Student.school_id == school_id)
    scores = scores_q.all()

    if not scores:
        raise HTTPException(status_code=404, detail="No scores found for approval in your school.")

    for s in scores:
        s.approval_status = "APPROVED_BY_HOD"

    db.commit()
    return {"message": f"HOD successfully approved {len(scores)} score record(s).", "status": "APPROVED_BY_HOD"}


@router.post("/publish-by-academic-head")
def publish_by_academic_head(
    class_id: int = Query(...),
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tier 3: Academic Head gives final clearance to publish class report cards."""
    role_names = [r.name.lower() for r in current_user.roles] if hasattr(current_user, 'roles') and current_user.roles else []
    allowed = {"admin", "super_admin", "headmaster", "headmistress", "assistant_headmaster_academic", "assistant_head_academic"}
    if not any(r in allowed for r in role_names):
        raise HTTPException(status_code=403, detail="Only the Assistant Headmaster (Academic) or Headmaster can publish terminal class reports.")

    school_id = get_school_id(current_user)
    scores_q = db.query(Score).join(Student).filter(
        Student.class_section_id == class_id,
        Score.semester_id == semester_id
    )
    if school_id is not None:
        scores_q = scores_q.filter(Student.school_id == school_id)
    scores = scores_q.all()

    if not scores:
        raise HTTPException(status_code=404, detail="No scores found for publishing in your school.")

    for s in scores:
        s.approval_status = "PUBLISHED"

    db.commit()
    return {"message": f"Academic Head successfully published terminal scores for {len(scores)} record(s) across class section.", "status": "PUBLISHED"}


# ── Comparative Analytics & Ranking Intelligence Suite ─────────────────────────

@router.get("/comparative-rankings")
def get_comparative_rankings(
    semester_id: Optional[int] = None,
    stage_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Role-Scoped Comparative Intelligence & Ranking Engine:
    Computes inter-class league standings, departmental credit benchmarks,
    cross-class subject mastery, term deltas, and scholar podiums.
    """
    from ..models import (
        Semester, Department, House, Fee, Payment, DisciplineRecord, 
        TeacherAssignment, Role
    )
    from sqlalchemy import func, desc

    school_id = get_school_id(current_user)

    # 1. Resolve Target Semester & Previous Semester for Deltas
    if semester_id:
        sem = db.query(Semester).filter(Semester.id == semester_id).first()
    else:
        sem = db.query(Semester).filter(Semester.is_current == True).first()
        if not sem:
            sem = db.query(Semester).order_by(Semester.id.desc()).first()

    sem_id = sem.id if sem else 0
    sem_name = sem.name if sem else "Current Term"

    # Previous semester for delta calculations
    prev_sem = None
    if sem:
        prev_sem = db.query(Semester).filter(Semester.id < sem.id).order_by(Semester.id.desc()).first()
    prev_sem_id = prev_sem.id if prev_sem else None

    # 2. Extract User Roles & Scope
    role_names = [r.name.lower() for r in current_user.roles] if hasattr(current_user, 'roles') and current_user.roles else []
    is_super_admin = "super_admin" in role_names
    is_admin = any(r in role_names for r in ["admin", "super_admin", "headmaster", "headmistress", "assistant_headmaster_academic", "assistant_head_academic", "assistant_headmaster_admin", "assistant_head_admin"])
    is_hod = "hod" in role_names
    is_form_master = any(r in role_names for r in ["form_master", "form_mistress"])
    is_teacher = "teacher" in role_names
    is_housemaster = "housemaster" in role_names
    is_bursar = any(r in role_names for r in ["bursar", "accountant"])

    # 3. Compute Inter-Class League Table
    class_q = db.query(ClassSection)
    if school_id is not None:
        class_q = class_q.filter(ClassSection.school_id == school_id) if hasattr(ClassSection, 'school_id') else class_q
    if stage_filter and stage_filter != "ALL":
        class_q = class_q.join(ClassSection.stage).filter(SchoolStage.name.ilike(f"%{stage_filter}%"))
    
    classes = class_q.all()

    class_league = []
    class_prev_scores = {}

    # Pre-fetch previous semester averages for delta comparison
    if prev_sem_id:
        for c in classes:
            prev_scores = db.query(Score.total_score).join(Student).filter(
                Student.class_section_id == c.id,
                Score.semester_id == prev_sem_id
            ).all()
            if prev_scores:
                avg = sum(s[0] for s in prev_scores if s[0] is not None) / len(prev_scores)
                class_prev_scores[c.id] = round(avg, 2)

    for c in classes:
        active_students = db.query(Student).filter(
            Student.class_section_id == c.id,
            Student.is_active == True
        ).all()
        student_ids = [st.id for st in active_students]

        scores = db.query(Score).filter(
            Score.student_id.in_(student_ids),
            Score.semester_id == sem_id
        ).all() if student_ids else []

        scores_recorded = len(scores)
        valid_scores = [s.total_score for s in scores if s.total_score is not None]
        avg_score = round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else 0.0

        quality_passes = sum(1 for v in valid_scores if v >= 50.0)
        distinctions = sum(1 for v in valid_scores if v >= 75.0)
        pass_rate_pct = round((quality_passes / len(valid_scores) * 100), 1) if valid_scores else 0.0
        distinction_rate_pct = round((distinctions / len(valid_scores) * 100), 1) if valid_scores else 0.0

        form_master_user = db.query(User).filter(User.id == c.form_master_id).first() if c.form_master_id else None
        form_master_name = form_master_user.username if form_master_user else "Unassigned"

        # Find top student in this class
        top_student = None
        if active_students:
            st_averages = []
            for st in active_students:
                st_sc = [s.total_score for s in scores if s.student_id == st.id and s.total_score is not None]
                if st_sc:
                    st_averages.append({
                        "name": st.full_name,
                        "code": st.student_code or f"STU-{st.id}",
                        "average": round(sum(st_sc) / len(st_sc), 2)
                    })
            if st_averages:
                top_student = max(st_averages, key=lambda x: x["average"])

        class_league.append({
            "class_id": c.id,
            "class_name": c.name,
            "stage_name": c.stage.name if c.stage else "General",
            "form_master_name": form_master_name,
            "is_my_class": (c.form_master_id == current_user.id),
            "student_count": len(active_students),
            "scores_recorded": scores_recorded,
            "average_score": avg_score,
            "pass_rate_pct": pass_rate_pct,
            "distinction_rate_pct": distinction_rate_pct,
            "distinctions_count": distinctions,
            "previous_average": class_prev_scores.get(c.id, None),
            "top_student": top_student
        })

    # Sort class league by average_score descending, then pass_rate_pct
    class_league.sort(key=lambda x: (x["average_score"], x["pass_rate_pct"]), reverse=True)

    # Assign ranks and calculate rank deltas
    prev_ranks = {}
    if class_prev_scores:
        sorted_prev = sorted(class_prev_scores.items(), key=lambda x: x[1], reverse=True)
        for idx, (cid, _) in enumerate(sorted_prev):
            prev_ranks[cid] = idx + 1

    for idx, item in enumerate(class_league):
        item["rank"] = idx + 1
        cid = item["class_id"]
        if cid in prev_ranks:
            item["rank_delta"] = prev_ranks[cid] - (idx + 1)
        else:
            item["rank_delta"] = 0

    # 4. Compute Departmental Quality Benchmarks
    dept_q = db.query(Department)
    if school_id is not None:
        dept_q = dept_q.filter(Department.school_id == school_id)
    departments = dept_q.all()

    department_benchmarks = []
    for d in departments:
        hod_user = db.query(User).filter(User.id == d.hod_id).first() if d.hod_id else None
        faculty_count = db.query(User).filter(User.department_id == d.id).count()

        # Department subjects
        subjs = d.subjects
        subj_ids = [s.id for s in subjs]

        dept_sc_q = db.query(Score.total_score).join(Score.student).filter(
            Score.subject_id.in_(subj_ids),
            Score.semester_id == sem_id
        )
        if school_id is not None:
            dept_sc_q = dept_sc_q.filter(Student.school_id == school_id)
        dept_scores = dept_sc_q.all() if subj_ids else []

        valid_dept_sc = [s[0] for s in dept_scores if s[0] is not None]
        avg_dept = round(sum(valid_dept_sc) / len(valid_dept_sc), 2) if valid_dept_sc else 0.0
        pass_dept = sum(1 for v in valid_dept_sc if v >= 50.0)
        dist_dept = sum(1 for v in valid_dept_sc if v >= 75.0)

        pass_dept_pct = round((pass_dept / len(valid_dept_sc) * 100), 1) if valid_dept_sc else 0.0
        dist_dept_pct = round((dist_dept / len(valid_dept_sc) * 100), 1) if valid_dept_sc else 0.0

        department_benchmarks.append({
            "department_id": d.id,
            "department_name": d.name,
            "department_code": d.code or d.name[:4].upper(),
            "hod_name": hod_user.username if hod_user else "Unassigned",
            "is_my_department": (d.hod_id == current_user.id or current_user.department_id == d.id),
            "subjects_count": len(subjs),
            "faculty_count": faculty_count,
            "scores_recorded": len(valid_dept_sc),
            "average_score": avg_dept,
            "quality_pass_rate_pct": pass_dept_pct,
            "distinction_rate_pct": dist_dept_pct
        })

    department_benchmarks.sort(key=lambda x: (x["quality_pass_rate_pct"], x["average_score"]), reverse=True)
    for idx, d in enumerate(department_benchmarks):
        d["rank"] = idx + 1

    # 5. Cross-Class Subject Mastery Benchmark
    subj_q = db.query(Subject)
    if school_id is not None:
        subj_q = subj_q.filter(Subject.school_id == school_id) if hasattr(Subject, 'school_id') else subj_q
    subjects = subj_q.all()

    subject_mastery = []
    for sub in subjects:
        # All scores for this subject in current semester
        all_sub_q = db.query(Score.total_score, Student.class_section_id).join(Student).filter(
            Score.subject_id == sub.id,
            Score.semester_id == sem_id
        )
        if school_id is not None:
            all_sub_q = all_sub_q.filter(Student.school_id == school_id)
        all_sub_scores = all_sub_q.all()

        if not all_sub_scores:
            continue

        valid_all = [s[0] for s in all_sub_scores if s[0] is not None]
        overall_sub_avg = round(sum(valid_all) / len(valid_all), 2) if valid_all else 0.0

        # Group by class
        class_breakdown = {}
        for score_val, cs_id in all_sub_scores:
            if score_val is None:
                continue
            if cs_id not in class_breakdown:
                class_breakdown[cs_id] = []
            class_breakdown[cs_id].append(score_val)

        classes_ranked = []
        for cs_id, sc_list in class_breakdown.items():
            cs_obj = db.query(ClassSection).filter(ClassSection.id == cs_id).first()
            if not cs_obj:
                continue
            cs_avg = round(sum(sc_list) / len(sc_list), 2)
            cs_pass = sum(1 for v in sc_list if v >= 50.0)
            cs_pass_pct = round((cs_pass / len(sc_list) * 100), 1)
            classes_ranked.append({
                "class_id": cs_obj.id,
                "class_name": cs_obj.name,
                "average_score": cs_avg,
                "pass_rate_pct": cs_pass_pct,
                "students_tested": len(sc_list)
            })

        classes_ranked.sort(key=lambda x: x["average_score"], reverse=True)

        subject_mastery.append({
            "subject_id": sub.id,
            "subject_name": sub.name,
            "subject_code": sub.code or sub.name[:4].upper(),
            "overall_average": overall_sub_avg,
            "total_students_tested": len(valid_all),
            "class_rankings": classes_ranked
        })

    subject_mastery.sort(key=lambda x: x["total_students_tested"], reverse=True)

    # 6. Top 10 Scholars & Most Improved Leaderboards
    student_q = db.query(Student).filter(Student.is_active == True)
    if school_id is not None:
        student_q = student_q.filter(Student.school_id == school_id)
    all_students = student_q.all()

    student_roster = []
    for st in all_students:
        curr_sc = db.query(Score.total_score).filter(
            Score.student_id == st.id,
            Score.semester_id == sem_id
        ).all()
        curr_vals = [s[0] for s in curr_sc if s[0] is not None]
        if not curr_vals:
            continue

        curr_avg = round(sum(curr_vals) / len(curr_vals), 2)

        prev_avg = None
        if prev_sem_id:
            prev_sc = db.query(Score.total_score).filter(
                Score.student_id == st.id,
                Score.semester_id == prev_sem_id
            ).all()
            prev_vals = [s[0] for s in prev_sc if s[0] is not None]
            if prev_vals:
                prev_avg = round(sum(prev_vals) / len(prev_vals), 2)

        improvement_delta = round(curr_avg - prev_avg, 2) if prev_avg is not None else 0.0

        student_roster.append({
            "student_id": st.id,
            "student_name": st.full_name,
            "student_code": st.student_code or f"STU-{st.id}",
            "class_name": st.class_section.name if st.class_section else "Unassigned",
            "gender": st.gender or "N/A",
            "subjects_taken": len(curr_vals),
            "average_score": curr_avg,
            "previous_average": prev_avg,
            "improvement_delta": improvement_delta
        })

    # Top 10 Scholars
    top_scholars = sorted(student_roster, key=lambda x: (x["average_score"], x["subjects_taken"]), reverse=True)[:10]
    for idx, sc in enumerate(top_scholars):
        sc["rank"] = idx + 1

    # Top 10 Most Improved
    improved_candidates = [s for s in student_roster if s["previous_average"] is not None and s["improvement_delta"] > 0]
    most_improved = sorted(improved_candidates, key=lambda x: x["improvement_delta"], reverse=True)[:10]
    for idx, sc in enumerate(most_improved):
        sc["rank"] = idx + 1

    # 7. Role-Scoped Specialized Widgets
    # Teacher Allocated Classes Comparison
    teacher_classes_benchmark = []
    if is_teacher and not is_admin:
        assignments = db.query(TeacherAssignment).filter(TeacherAssignment.teacher_id == current_user.id).all()
        for asgn in assignments:
            cs = asgn.class_section
            sub = asgn.subject
            if not cs or not sub:
                continue

            asgn_scores = db.query(Score.total_score).join(Student).filter(
                Student.class_section_id == cs.id,
                Score.subject_id == sub.id,
                Score.semester_id == sem_id
            ).all()
            vals = [s[0] for s in asgn_scores if s[0] is not None]
            c_avg = round(sum(vals) / len(vals), 2) if vals else 0.0
            c_pass = round((sum(1 for v in vals if v >= 50.0) / len(vals) * 100), 1) if vals else 0.0

            teacher_classes_benchmark.append({
                "assignment_id": asgn.id,
                "class_name": cs.name,
                "subject_name": sub.name,
                "average_score": c_avg,
                "pass_rate_pct": c_pass,
                "students_count": len(vals)
            })

    # Inter-House League
    house_league = []
    houses = db.query(House).filter(House.school_id == school_id).all() if school_id is not None else db.query(House).all()
    for h in houses:
        boarders = db.query(Student).filter(
            Student.house_id == h.id,
            Student.is_active == True
        ).all()
        b_ids = [b.id for b in boarders]
        h_scores = db.query(Score.total_score).filter(
            Score.student_id.in_(b_ids),
            Score.semester_id == sem_id
        ).all() if b_ids else []

        h_vals = [s[0] for s in h_scores if s[0] is not None]
        h_avg = round(sum(h_vals) / len(h_vals), 2) if h_vals else 0.0

        hm_user = db.query(User).filter(User.id == h.house_master_id).first() if h.house_master_id else None

        house_league.append({
            "house_id": h.id,
            "house_name": h.name,
            "gender": h.gender or "Co-ed",
            "housemaster_name": hm_user.username if hm_user else "Unassigned",
            "boarders_count": len(boarders),
            "average_score": h_avg,
            "is_my_house": (h.house_master_id == current_user.id)
        })

    house_league.sort(key=lambda x: x["average_score"], reverse=True)
    for idx, hl in enumerate(house_league):
        hl["rank"] = idx + 1

    # Inter-Class Fee Recovery League
    fee_recovery_league = []
    if is_admin or is_bursar:
        for c in classes:
            st_in_class = db.query(Student.id).filter(Student.class_section_id == c.id, Student.is_active == True).all()
            s_ids = [s[0] for s in st_in_class]
            
            billed_sum = db.query(func.sum(Fee.amount)).filter(
                Fee.student_id.in_(s_ids)
            ).scalar() or 0.0

            paid_sum = db.query(func.sum(Fee.amount_paid)).filter(
                Fee.student_id.in_(s_ids)
            ).scalar() or 0.0

            recovery_pct = round((paid_sum / billed_sum * 100), 1) if billed_sum > 0 else 100.0
            arrears = max(0.0, billed_sum - paid_sum)

            fee_recovery_league.append({
                "class_id": c.id,
                "class_name": c.name,
                "students_count": len(s_ids),
                "billed_amount": round(billed_sum, 2),
                "collected_amount": round(paid_sum, 2),
                "arrears_amount": round(arrears, 2),
                "recovery_rate_pct": recovery_pct
            })

        fee_recovery_league.sort(key=lambda x: x["recovery_rate_pct"], reverse=True)
        for idx, fl in enumerate(fee_recovery_league):
            fl["rank"] = idx + 1

    return {
        "semester": {
            "id": sem_id,
            "name": sem_name,
            "previous_semester_name": prev_sem.name if prev_sem else None
        },
        "class_league": class_league,
        "department_benchmarks": department_benchmarks,
        "subject_mastery": subject_mastery,
        "top_scholars": top_scholars,
        "most_improved": most_improved,
        "teacher_classes_benchmark": teacher_classes_benchmark,
        "house_league": house_league,
        "fee_recovery_league": fee_recovery_league,
        "user_context": {
            "user_id": current_user.id,
            "username": current_user.username,
            "role": role_names[0] if role_names else "user",
            "is_admin_exec": is_admin,
            "is_hod": is_hod,
            "is_form_master": is_form_master,
            "is_teacher": is_teacher,
            "is_housemaster": is_housemaster,
            "is_bursar": is_bursar
        }
    }


from pydantic import BaseModel
from typing import List

class ClassMatrixScoreItem(BaseModel):
    student_id: int
    subject_id: int
    class_score: Optional[float] = 0.0
    exam_score: Optional[float] = 0.0
    remarks: Optional[str] = None

class BatchClassMatrixRequest(BaseModel):
    class_section_id: int
    semester_id: int
    records: List[ClassMatrixScoreItem]


@router.post("/batch-class-matrix")
def save_batch_class_matrix(
    payload: BatchClassMatrixRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    All-in-One Class Score Matrix Batch Persistence:
    Updates or inserts scores for an entire class roster across multiple subjects
    in a single atomic database transaction.
    """
    _check_score_lock(db, payload.semester_id, current_user)
    school_id = getattr(current_user, 'school_id', None)
    is_super = any(r.name in ["super_admin", "admin"] for r in current_user.roles) if hasattr(current_user, 'roles') else False

    cls_sec = db.query(ClassSection).filter(ClassSection.id == payload.class_section_id).first()
    if not cls_sec or (not is_super and school_id is not None and hasattr(ClassSection, "school_id") and cls_sec.school_id is not None and cls_sec.school_id != school_id):
        raise HTTPException(status_code=404, detail="Class section not found")

    saved_count = 0
    for item in payload.records:
        total = round((item.class_score or 0.0) + (item.exam_score or 0.0), 2)
        grading = GradingService.get_grade(total, db)

        existing = db.query(Score).filter(
            Score.student_id == item.student_id,
            Score.subject_id == item.subject_id,
            Score.semester_id == payload.semester_id
        ).first()

        if existing:
            existing.class_score = item.class_score
            existing.exam_score = item.exam_score
            existing.total_score = total
            existing.grade = grading["grade"]
            existing.remark = item.remarks or grading["remark"]
            saved_count += 1
            log_sync_change(db, school_id or 1, "score", existing.id, "UPDATE", {
                "student_id": item.student_id,
                "subject_id": item.subject_id,
                "semester_id": payload.semester_id,
                "class_score": item.class_score,
                "exam_score": item.exam_score,
                "total_score": total,
                "grade": grading["grade"],
                "remark": item.remarks or grading["remark"]
            })
        else:
            new_sc = Score(
                student_id=item.student_id,
                subject_id=item.subject_id,
                semester_id=payload.semester_id,
                class_score=item.class_score,
                exam_score=item.exam_score,
                total_score=total,
                grade=grading["grade"],
                remark=item.remarks or grading["remark"]
            )
            db.add(new_sc)
            db.flush()
            saved_count += 1
            log_sync_change(db, school_id or 1, "score", new_sc.id, "INSERT", {
                "student_id": item.student_id,
                "subject_id": item.subject_id,
                "semester_id": payload.semester_id,
                "class_score": item.class_score,
                "exam_score": item.exam_score,
                "total_score": total,
                "grade": grading["grade"],
                "remark": item.remarks or grading["remark"]
            })

    db.commit()
    return {
        "status": "success",
        "saved_count": saved_count,
        "class_id": payload.class_section_id,
        "class_name": cls_sec.name,
        "message": f"Successfully persisted {saved_count} marks record(s) for {cls_sec.name}."
    }


