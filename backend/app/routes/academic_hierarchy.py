from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List, Optional
from datetime import datetime

from ..database import get_db
from ..models import (
    User, Department, ClassSection, Subject, Semester, Student, Score,
    StudentSemesterSummary, Setting, ClassSectionReportStatus, ClassSubjectScoreStatus,
    class_section_subjects, MessageLog
)
from ..schemas import (
    TeacherDepartmentAssign, HODScoreApproval, BroadsheetRemarksUpdate,
    BroadsheetResponse, BroadsheetStudentRow, AcademicOverviewResponse
)
from ..dependencies import get_current_user, get_school_id

router = APIRouter()

def _get_current_semester(db: Session) -> Semester:
    sem = db.query(Semester).filter(Semester.is_current == True).first()
    if not sem:
        sem = db.query(Semester).order_by(Semester.id.desc()).first()
    return sem

def _get_publishing_mode(db: Session) -> str:
    setting = db.query(Setting).filter(Setting.key == "report_publishing_mode").first()
    if setting and setting.value:
        return setting.value.upper()
    return "HYBRID_BOTH"

def _is_academic_head(user: User) -> bool:
    roles = [r.name.lower() for r in user.roles]
    username_lower = user.username.lower()
    return any(r in roles for r in ["admin", "headmaster", "assistant_head_academic", "assistant head academic"]) or \
           "academic" in username_lower or "admin" in username_lower

def _is_hod(db: Session, user: User, department_id: Optional[int] = None) -> bool:
    if _is_academic_head(user):
        return True
    query = db.query(Department).filter(Department.hod_id == user.id)
    if department_id:
        query = query.filter(Department.id == department_id)
    return query.first() is not None

def _is_form_master_of_class(user: User, class_section: ClassSection) -> bool:
    if _is_academic_head(user):
        return True
    return class_section.form_master_id == user.id


@router.put("/teacher-department")
def assign_teacher_department(
    payload: TeacherDepartmentAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _is_academic_head(current_user):
        raise HTTPException(status_code=403, detail="Only Administrators or Assistant Head Academic can assign teachers to departments")

    teacher = db.query(User).filter(User.id == payload.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    if payload.department_id:
        dept = db.query(Department).filter(Department.id == payload.department_id).first()
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found")
        teacher.department_id = dept.id
    else:
        teacher.department_id = None

    db.commit()
    return {"message": "Teacher department affiliation updated successfully"}


@router.get("/hod/vetting")
def get_hod_vetting_status(
    department_id: Optional[int] = None,
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sem = db.query(Semester).filter(Semester.id == semester_id).first() if semester_id else _get_current_semester(db)
    if not sem:
        raise HTTPException(status_code=404, detail="No active academic semester found")

    school_id = get_school_id(current_user)

    # Determine departments to show
    if _is_academic_head(current_user):
        dept_query = db.query(Department)
        if school_id is not None:
            dept_query = dept_query.filter(Department.school_id == school_id)
        depts = dept_query.all()
    else:
        dept_query = db.query(Department).filter(Department.hod_id == current_user.id)
        if school_id is not None:
            dept_query = dept_query.filter(Department.school_id == school_id)
        depts = dept_query.all()
        if not depts:
            raise HTTPException(status_code=403, detail="Access Denied: You are not registered as an HOD")

    if department_id:
        depts = [d for d in depts if d.id == department_id]

    results = []
    for d in depts:
        hod_name = d.hod.username if d.hod else "Unassigned"
        subject_list = []
        
        for subj in d.subjects:
            # Find classes that have this subject assigned
            classes_with_subj = db.query(ClassSection).join(
                class_section_subjects, ClassSection.id == class_section_subjects.c.class_section_id
            ).filter(class_section_subjects.c.subject_id == subj.id).all()

            for cs in classes_with_subj:
                # Get score count vs total student count
                total_students = db.query(Student).filter(Student.class_section_id == cs.id, Student.is_active == True).count()
                scores_count = db.query(Score).filter(
                    Score.subject_id == subj.id,
                    Score.semester_id == sem.id,
                    Score.student_id.in_(
                        db.query(Student.id).filter(Student.class_section_id == cs.id)
                    )
                ).count()

                status_rec = db.query(ClassSubjectScoreStatus).filter(
                    ClassSubjectScoreStatus.class_section_id == cs.id,
                    ClassSubjectScoreStatus.subject_id == subj.id,
                    ClassSubjectScoreStatus.semester_id == sem.id
                ).first()

                curr_status = status_rec.status if status_rec else ("Approved_HOD" if scores_count >= total_students and total_students > 0 else ("Submitted_HOD" if scores_count > 0 else "Draft"))

                completion_pct = round((scores_count / total_students * 100), 1) if total_students > 0 else 0.0

                subject_list.append({
                    "class_section_id": cs.id,
                    "class_name": cs.name,
                    "subject_id": subj.id,
                    "subject_name": subj.name,
                    "total_students": total_students,
                    "scores_entered": scores_count,
                    "completion_percentage": completion_pct,
                    "status": curr_status,
                    "approved_by_hod": status_rec.approved_by_hod.username if (status_rec and status_rec.approved_by_hod) else None
                })

        results.append({
            "department_id": d.id,
            "department_name": d.name,
            "hod_name": hod_name,
            "items": subject_list
        })

    return results


@router.put("/hod/approve-scores")
def approve_score_submission(
    payload: HODScoreApproval,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    subj = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Check HOD authority over department owning subject
    dept = db.query(Department).join(Department.subjects).filter(Subject.id == subj.id).first()
    if dept and dept.hod_id != current_user.id and not _is_academic_head(current_user):
        raise HTTPException(status_code=403, detail=f"Access Denied: You are not the HOD for {dept.name}")

    status_rec = db.query(ClassSubjectScoreStatus).filter(
        ClassSubjectScoreStatus.class_section_id == payload.class_section_id,
        ClassSubjectScoreStatus.subject_id == payload.subject_id,
        ClassSubjectScoreStatus.semester_id == payload.semester_id
    ).first()

    new_status = "Approved_HOD" if payload.action == "approve" else ("Draft" if payload.action == "reject" else "Submitted_HOD")

    if not status_rec:
        status_rec = ClassSubjectScoreStatus(
            class_section_id=payload.class_section_id,
            subject_id=payload.subject_id,
            semester_id=payload.semester_id,
            status=new_status,
            approved_by_hod_id=current_user.id if new_status == "Approved_HOD" else None,
            approved_at=datetime.now() if new_status == "Approved_HOD" else None
        )
        db.add(status_rec)
    else:
        status_rec.status = new_status
        if new_status == "Approved_HOD":
            status_rec.approved_by_hod_id = current_user.id
            status_rec.approved_at = datetime.now()

    db.commit()
    return {"message": f"Subject score status updated to '{new_status}' successfully"}


@router.get("/broadsheet/{class_section_id}", response_model=BroadsheetResponse)
def get_class_broadsheet(
    class_section_id: int,
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    school_id = get_school_id(current_user)
    cs_query = db.query(ClassSection).filter(ClassSection.id == class_section_id)
    if school_id is not None:
        cs_query = cs_query.filter(ClassSection.school_id == school_id)
    cs = cs_query.first()
    if not cs:
        raise HTTPException(status_code=404, detail="Class section not found")

    sem = db.query(Semester).filter(Semester.id == semester_id).first() if semester_id else _get_current_semester(db)
    if not sem:
        raise HTTPException(status_code=404, detail="No active semester found")

    mode = _get_publishing_mode(db)
    form_master_name = cs.form_master.username if cs.form_master else "Unassigned"

    # Fetch subjects for this class section
    subjects = cs.subjects
    subject_dicts = []
    for s in subjects:
        st_rec = db.query(ClassSubjectScoreStatus).filter(
            ClassSubjectScoreStatus.class_section_id == cs.id,
            ClassSubjectScoreStatus.subject_id == s.id,
            ClassSubjectScoreStatus.semester_id == sem.id
        ).first()
        status_val = st_rec.status if st_rec else "Draft"
        subject_dicts.append({
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "is_core": s.is_core,
            "status": status_val
        })

    # Fetch students in class
    students = db.query(Student).filter(Student.class_section_id == cs.id, Student.is_active == True).order_by(Student.full_name).all()

    # Calculate scores & broadsheet matrix
    raw_student_data = []

    for st in students:
        scores = db.query(Score).filter(
            Score.student_id == st.id,
            Score.semester_id == sem.id
        ).all()

        subj_score_map = {}
        total_marks = 0.0
        subj_count = 0

        for s in scores:
            subj_score_map[s.subject.name] = s.total_score or 0.0
            total_marks += (s.total_score or 0.0)
            subj_count += 1

        avg_mark = round(total_marks / subj_count, 2) if subj_count > 0 else 0.0

        # Form teacher remarks & summaries
        summary = db.query(StudentSemesterSummary).filter(
            StudentSemesterSummary.student_id == st.id,
            StudentSemesterSummary.semester_id == sem.id
        ).first()

        raw_student_data.append({
            "student_id": st.id,
            "student_name": st.full_name,
            "student_code": st.student_code,
            "subject_scores": subj_score_map,
            "total_marks": round(total_marks, 2),
            "average_mark": avg_mark,
            "attitude": summary.attitude if summary else None,
            "conduct": summary.conduct if summary else None,
            "interest": summary.interest if summary else None,
            "form_teacher_remarks": summary.form_teacher_remarks if summary else None
        })

    # Rank students by total_marks descending
    sorted_data = sorted(raw_student_data, key=lambda x: x["total_marks"], reverse=True)
    for idx, item in enumerate(sorted_data):
        item["class_rank"] = idx + 1

    # Check published status
    pub_status = db.query(ClassSectionReportStatus).filter(
        ClassSectionReportStatus.class_section_id == cs.id,
        ClassSectionReportStatus.semester_id == sem.id
    ).first()
    is_published = pub_status.is_published if pub_status else False

    student_rows = [BroadsheetStudentRow(**item) for item in raw_student_data]

    return BroadsheetResponse(
        class_section_id=cs.id,
        class_name=cs.name,
        semester_id=sem.id,
        semester_name=sem.name,
        form_master_name=form_master_name,
        publishing_mode=mode,
        is_published=is_published,
        subjects=subject_dicts,
        students=student_rows
    )


@router.post("/broadsheet/remarks")
def save_broadsheet_remarks(
    payload: BroadsheetRemarksUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cs = db.query(ClassSection).filter(ClassSection.id == payload.class_section_id).first()
    if not cs:
        raise HTTPException(status_code=404, detail="Class section not found")

    if not _is_form_master_of_class(current_user, cs):
        raise HTTPException(status_code=403, detail="Only the assigned Form Master or Assistant Head Academic can save class remarks")

    for item in payload.remarks:
        summary = db.query(StudentSemesterSummary).filter(
            StudentSemesterSummary.student_id == item.student_id,
            StudentSemesterSummary.semester_id == payload.semester_id
        ).first()

        if not summary:
            summary = StudentSemesterSummary(
                student_id=item.student_id,
                semester_id=payload.semester_id,
                attitude=item.attitude,
                conduct=item.conduct,
                interest=item.interest,
                form_teacher_remarks=item.form_teacher_remarks
            )
            db.add(summary)
        else:
            if item.attitude is not None: summary.attitude = item.attitude
            if item.conduct is not None: summary.conduct = item.conduct
            if item.interest is not None: summary.interest = item.interest
            if item.form_teacher_remarks is not None: summary.form_teacher_remarks = item.form_teacher_remarks

    db.commit()
    return {"message": "Form teacher remarks saved successfully"}


@router.post("/broadsheet/publish")
def publish_class_reports(
    class_section_id: int,
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cs = db.query(ClassSection).filter(ClassSection.id == class_section_id).first()
    if not cs:
        raise HTTPException(status_code=404, detail="Class section not found")

    sem = db.query(Semester).filter(Semester.id == semester_id).first() if semester_id else _get_current_semester(db)
    if not sem:
        raise HTTPException(status_code=404, detail="No active semester found")

    mode = _get_publishing_mode(db)
    is_head = _is_academic_head(current_user)
    is_form_master = (cs.form_master_id == current_user.id)

    # Validate Mode Permissions
    if mode == "ACADEMIC_HEAD_ONLY" and not is_head:
        raise HTTPException(
            status_code=403,
            detail="Under your school's current policy setting (Centralized Executive Approval), terminal report cards can ONLY be published by the Assistant Head Academic or Headmaster."
        )

    if mode == "FORM_MASTER_DIRECT" and not (is_form_master or is_head):
        raise HTTPException(
            status_code=403,
            detail="Access Denied: Only the Form Master for this class or Administrator can publish these report cards."
        )

    if mode == "HYBRID_BOTH" and not (is_form_master or is_head):
        raise HTTPException(
            status_code=403,
            detail="Access Denied: Only the Form Master for this class or Assistant Head Academic can publish these report cards."
        )

    pub_rec = db.query(ClassSectionReportStatus).filter(
        ClassSectionReportStatus.class_section_id == cs.id,
        ClassSectionReportStatus.semester_id == sem.id
    ).first()

    if not pub_rec:
        pub_rec = ClassSectionReportStatus(
            class_section_id=cs.id,
            semester_id=sem.id,
            is_published=True,
            published_by_id=current_user.id,
            published_at=datetime.now()
        )
        db.add(pub_rec)
    else:
        pub_rec.is_published = True
        pub_rec.published_by_id = current_user.id
        pub_rec.published_at = datetime.now()

    # Draft SMS report notification for active students with guardian phone
    students = db.query(Student).filter(
        Student.class_section_id == cs.id,
        Student.is_active == True
    ).all()

    for s in students:
        if s.phone and len(s.phone.strip()) >= 7:
            guardian_name = s.guardian_name or (s.parent.username if s.parent else "Parent/Guardian")
            msg_body = (
                f"Dear {guardian_name}, the Terminal Report Card for {s.full_name} ({cs.name}) "
                f"for {sem.name} has been published and is now available for viewing."
            )

            msg_pattern = f"%Terminal Report Card for {s.full_name}%{sem.name}%"
            existing_log = db.query(MessageLog).filter(
                MessageLog.student_id == s.id,
                MessageLog.message_type == "TERMINAL_REPORT",
                MessageLog.message_body.like(msg_pattern)
            ).first()

            if not existing_log:
                db.add(MessageLog(
                    sender_id=current_user.id,
                    student_id=s.id,
                    recipient_name=guardian_name,
                    recipient_phone=s.phone,
                    channel="SMS",
                    message_type="TERMINAL_REPORT",
                    message_body=msg_body,
                    overall_grade="PUBLISHED",
                    status="PENDING"
                ))

    db.commit()
    return {"message": f"Terminal report cards for {cs.name} have been published and are now visible to guardians!"}


@router.get("/overview", response_model=AcademicOverviewResponse)
def get_academic_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    school_id = get_school_id(current_user)
    sem = _get_current_semester(db)
    sem_id = sem.id if sem else 0

    teachers_q = db.query(User).join(User.roles).filter(Role.name.in_(["teacher", "form_master", "form_mistress"]))
    depts_q = db.query(Department)
    classes_q = db.query(ClassSection)

    if school_id is not None:
        teachers_q = teachers_q.filter(User.school_id == school_id)
        depts_q = depts_q.filter(Department.school_id == school_id)
        classes_q = classes_q.filter(ClassSection.school_id == school_id)

    total_teachers = teachers_q.count()
    total_departments = depts_q.count()
    total_classes = classes_q.count()

    pub_q = db.query(ClassSectionReportStatus).filter(
        ClassSectionReportStatus.semester_id == sem_id,
        ClassSectionReportStatus.is_published == True
    )
    if school_id is not None:
        pub_q = pub_q.join(ClassSectionReportStatus.class_section).filter(ClassSection.school_id == school_id)
    published_classes = pub_q.count()

    # Calculate overall score completion %
    total_expected_scores = 0
    total_actual_scores = 0

    for cs in db.query(ClassSection).all():
        student_count = db.query(Student).filter(Student.class_section_id == cs.id, Student.is_active == True).count()
        subj_count = len(cs.subjects)
        total_expected_scores += (student_count * subj_count)

        actual = db.query(Score).filter(
            Score.semester_id == sem_id,
            Score.student_id.in_(db.query(Student.id).filter(Student.class_section_id == cs.id))
        ).count()
        total_actual_scores += actual

    overall_pct = round((total_actual_scores / total_expected_scores * 100), 1) if total_expected_scores > 0 else 100.0

    pending_hod = db.query(ClassSubjectScoreStatus).filter(
        ClassSubjectScoreStatus.semester_id == sem_id,
        ClassSubjectScoreStatus.status.in_(["Draft", "Submitted_HOD"])
    ).count()

    mode = _get_publishing_mode(db)

    return AcademicOverviewResponse(
        total_teachers=total_teachers,
        total_departments=total_departments,
        overall_completion_percentage=overall_pct,
        report_publishing_mode=mode,
        pending_hod_approvals=pending_hod,
        published_classes_count=published_classes,
        total_classes_count=total_classes
    )
