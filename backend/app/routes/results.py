from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..models import Score, TeacherAssignment, User, Student, Subject, Setting, SchoolStage, ClassSection, School
from ..schemas import ScoreCreate
from ..services.grading import GradingService
from ..dependencies import get_current_user, get_school_id

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
        db.commit()
        db.refresh(existing)
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
    db.commit()
    db.refresh(db_score)
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

    result = []
    for student in students:
        score = db.query(Score).filter(
            Score.student_id == student.id,
            Score.subject_id == subject_id,
            Score.semester_id == semester_id,
        ).first()
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
    scores = db.query(Score).join(Student).filter(
        Student.class_section_id == class_id,
        Score.subject_id == subject_id,
        Score.semester_id == semester_id
    ).all()

    if not scores:
        raise HTTPException(status_code=404, detail="No scores found for this class, subject, and semester.")

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

    scores = db.query(Score).join(Student).filter(
        Student.class_section_id == class_id,
        Score.subject_id == subject_id,
        Score.semester_id == semester_id
    ).all()

    if not scores:
        raise HTTPException(status_code=404, detail="No scores found for approval.")

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

    scores = db.query(Score).join(Student).filter(
        Student.class_section_id == class_id,
        Score.semester_id == semester_id
    ).all()

    if not scores:
        raise HTTPException(status_code=404, detail="No scores found for publishing.")

    for s in scores:
        s.approval_status = "PUBLISHED"

    db.commit()
    return {"message": f"Academic Head successfully published terminal scores for {len(scores)} record(s) across class section.", "status": "PUBLISHED"}
