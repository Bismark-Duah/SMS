# reports routes — Phase 6
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from fastapi.responses import Response
from sqlalchemy.orm import Session
import csv
import io
from datetime import datetime
from ..database import get_db
from ..services.reports import ReportService
from ..models import Student, User, Score, Attendance, ClassSection, Fee, StudentSemesterSummary
from ..services.auth import decode_jwt
from ..dependencies import get_current_user, get_school_id

router = APIRouter()


@router.get("/report-data/{student_id}")
def get_report_data(
    student_id: int,
    semester_id: int = Query(...),
    token: str = Query(None),
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    """Returns structured JSON report data for in-browser HTML rendering."""
    auth_token = None
    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization.split(" ")[1]
    elif token:
        auth_token = token

    if not auth_token:
        raise HTTPException(status_code=401, detail="Authentication token required")

    try:
        payload = decode_jwt(auth_token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")

    school_id = payload.get("school_id")
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student or (school_id is not None and student.school_id != school_id):
        raise HTTPException(status_code=404, detail="Student not found.")

    data = ReportService.get_report_data(db, student_id, semester_id)
    if not data:
        raise HTTPException(status_code=404, detail="Student or semester not found.")
    return data


@router.get("/terminal-report/{student_id}")
def get_terminal_report(
    student_id: int, 
    semester_id: int = Query(...), 
    token: str = Query(None),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    auth_token = None
    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization.split(" ")[1]
    elif token:
        auth_token = token
        
    if not auth_token:
        raise HTTPException(status_code=401, detail="Authentication token required")
        
    try:
        payload = decode_jwt(auth_token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")
        
    school_id = payload.get("school_id")
    user_id = payload.get("user_id")
    roles = payload.get("roles", [])

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student or (school_id is not None and student.school_id != school_id):
        raise HTTPException(status_code=404, detail="Student not found")

    if "admin" not in roles and "super_admin" not in roles:
            
        if "student" in roles:
            current_user = db.query(User).filter(User.id == user_id).first()
            if not current_user or current_user.username != student.student_code:
                raise HTTPException(status_code=403, detail="You can only access your own report card")
                
        elif "parent" in roles:
            if student.parent_id != user_id:
                raise HTTPException(status_code=403, detail="You can only access your child's report card")
                
        elif "teacher" in roles:
            from ..models import TeacherAssignment
            assignment = db.query(TeacherAssignment).filter(
                TeacherAssignment.teacher_id == user_id,
                TeacherAssignment.class_section_id == student.class_section_id
            ).first()
            if not assignment:
                raise HTTPException(status_code=403, detail="You are not authorized to view reports for this class")
        else:
            raise HTTPException(status_code=403, detail="Role not authorized to view report cards")

    pdf_content = ReportService.generate_terminal_report(db, student_id, semester_id)
    if not pdf_content:
        raise HTTPException(status_code=404, detail="Report not found or error generating PDF")
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report_{student_id}.pdf"}
    )

@router.post("/term-summary")
def update_term_summary(
    payload: dict,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication token required")
    token = authorization.split(" ")[1]
    try:
        user_payload = decode_jwt(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")

    user_id = user_payload.get("user_id")
    roles = user_payload.get("roles", [])

    student_id = payload.get("student_id")
    semester_id = payload.get("semester_id")

    if not student_id or not semester_id:
        raise HTTPException(status_code=400, detail="student_id and semester_id are required")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    is_authorized = "admin" in roles
    if not is_authorized and "teacher" in roles:
        if student.class_section and student.class_section.form_master_id == user_id:
            is_authorized = True

    if not is_authorized:
        raise HTTPException(status_code=403, detail="You are not authorized to update term evaluations for this student")

    summary = db.query(StudentSemesterSummary).filter(
        StudentSemesterSummary.student_id == student_id,
        StudentSemesterSummary.semester_id == semester_id
    ).first()

    if not summary:
        summary = StudentSemesterSummary(
            student_id=student_id,
            semester_id=semester_id
        )
        db.add(summary)

    summary.attitude = payload.get("attitude")
    summary.conduct = payload.get("conduct")
    summary.interest = payload.get("interest")
    summary.form_teacher_remarks = payload.get("form_teacher_remarks")
    summary.headteacher_remarks = payload.get("headteacher_remarks")
    summary.promoted_to = payload.get("promoted_to")

    db.commit()
    return {"status": "success", "message": "Term summary updated"}

@router.get("/export-students")
def export_students(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(Student)
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)
    students = query.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Student Code", "Name", "Class Section", "Program"])
    
    for s in students:
        writer.writerow([
            s.id, 
            s.student_code, 
            s.full_name, 
            s.class_section.name if s.class_section else "N/A",
            s.program.name if s.program else "N/A"
        ])
    
    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=students_export.csv"}
    )

@router.get("/class-summary/{class_id}")
def get_class_summary(
    class_id: int,
    semester_id: int = Query(...),
    grade_tier: str = Query(None),
    attendance_rate: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(Student).filter(Student.class_section_id == class_id, Student.is_active == True)
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)
    students = query.all()
    results = []
    
    for student in students:
        # Calculate attendance percentage
        total_att = db.query(Attendance).filter(Attendance.student_id == student.id).count()
        present_att = db.query(Attendance).filter(Attendance.student_id == student.id, Attendance.status == "Present").count()
        att_rate = round((present_att / total_att) * 100.0, 2) if total_att > 0 else 100.0
        
        # Calculate academic scores
        scores = db.query(Score).filter(Score.student_id == student.id, Score.semester_id == semester_id).all()
        if scores:
            avg_score = round(sum(s.total_score for s in scores) / len(scores), 2)
            fails = sum(1 for s in scores if s.total_score < 40.0)
        else:
            avg_score = 0.0
            fails = 0
            
        # Determine grade average tier
        if avg_score >= 80.0:
            tier = "A"
        elif avg_score >= 70.0:
            tier = "B"
        elif avg_score >= 50.0:
            tier = "C"
        elif avg_score >= 40.0:
            tier = "Pass"
        else:
            tier = "Fail"
            
        # Filter by grade tier
        if grade_tier and tier != grade_tier:
            continue
            
        # Filter by attendance rate
        if attendance_rate:
            if attendance_rate == "Low" and att_rate >= 75.0:
                continue
            if attendance_rate == "Normal" and att_rate < 75.0:
                continue
                
        results.append({
            "student_id": student.id,
            "student_code": student.student_code,
            "full_name": student.full_name,
            "average_score": avg_score,
            "fails_count": fails,
            "attendance_rate": att_rate,
            "grade_tier": tier
        })
        
    return results

@router.get("/class-summary/{class_id}/export")
def export_class_summary(
    class_id: int,
    semester_id: int = Query(...),
    grade_tier: str = Query(None),
    attendance_rate: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = get_class_summary(class_id=class_id, semester_id=semester_id, grade_tier=grade_tier, attendance_rate=attendance_rate, db=db, current_user=current_user)
    class_section = db.query(ClassSection).filter(ClassSection.id == class_id).first()
    class_name = class_section.name if class_section else f"Class_{class_id}"
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student Code", "Name", "Average Score (%)", "Fails Count", "Attendance Rate (%)", "Grade Average Tier"])
    
    for row in data:
        writer.writerow([
            row["student_code"],
            row["full_name"],
            row["average_score"],
            row["fails_count"],
            row["attendance_rate"],
            row["grade_tier"]
        ])
        
    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=class_summary_{class_name.replace(' ', '_')}.csv"}
    )

@router.get("/financial-summary")
def get_financial_summary(
    class_id: int = Query(None),
    overdue_only: bool = Query(False),
    min_balance: float = Query(0.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(Student).filter(Student.is_active == True)
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)
    if class_id:
        query = query.filter(Student.class_section_id == class_id)
        
    students = query.all()
    now = datetime.now()
    results = []
    
    for student in students:
        fees = db.query(Fee).filter(Fee.student_id == student.id).all()
        total_billed = sum(f.amount for f in fees)
        total_paid = sum(f.amount_paid for f in fees)
        balance = round(total_billed - total_paid, 2)
        
        overdue_count = 0
        for f in fees:
            is_overdue = f.status != "Paid" and f.due_date and f.due_date < now
            if is_overdue:
                overdue_count += 1
                
        # Filter overdue only
        if overdue_only and (balance <= 0 or overdue_count == 0):
            continue
            
        # Filter minimum balance
        if balance < min_balance:
            continue
            
        results.append({
            "student_id": student.id,
            "student_code": student.student_code,
            "full_name": student.full_name,
            "class_name": student.class_section.name if student.class_section else "N/A",
            "total_billed": round(total_billed, 2),
            "total_paid": round(total_paid, 2),
            "outstanding_balance": balance,
            "overdue_count": overdue_count
        })
        
    return results

@router.get("/financial-summary/export")
def export_financial_summary(
    class_id: int = Query(None),
    overdue_only: bool = Query(False),
    min_balance: float = Query(0.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = get_financial_summary(class_id=class_id, overdue_only=overdue_only, min_balance=min_balance, db=db, current_user=current_user)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student Code", "Name", "Class", "Total Billed", "Total Paid", "Outstanding Balance", "Overdue Invoices"])
    
    for row in data:
        writer.writerow([
            row["student_code"],
            row["full_name"],
            row["class_name"],
            row["total_billed"],
            row["total_paid"],
            row["outstanding_balance"],
            row["overdue_count"]
        ])
        
    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=financial_summary.csv"}
    )

@router.get("/official-transcript/{student_id}")
def get_official_transcript(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates 100% complete SHS Academic Transcript data across Form 1-3.
    Organizes subjects into External WASSCE and Internal Assessment Subjects.
    """
    school_id = get_school_id(current_user)
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student or (school_id is not None and student.school_id != school_id):
        raise HTTPException(status_code=404, detail="Student transcript records not found.")

    transcript = ReportService.get_full_transcript_data(db, student_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Student transcript records not found.")
    return transcript


@router.get("/official-transcript-pdf/{student_id}")
def get_official_transcript_pdf(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates and streams the official 3-Year SHS Academic Transcript PDF.
    """
    school_id = get_school_id(current_user)
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student or (school_id is not None and student.school_id != school_id):
        raise HTTPException(status_code=404, detail="Student transcript records not found.")

    try:
        pdf_bytes = ReportService.generate_official_transcript_pdf(db, student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compile transcript PDF: {str(e)}")

    code_clean = (student.student_code or str(student.id)).replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Official_Transcript_{code_clean}.pdf"'
        }
    )



@router.get("/waec-transcript-by-index/{index_number}")
def get_waec_transcript_by_index(
    index_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lookup endpoint for WAEC Transcript / Statement of Results verification by 10-digit Index Number, BECE Index, or Student Code.
    """
    clean_idx = index_number.strip().upper()
    
    student = None
    if clean_idx.isdigit():
        student = db.query(Student).filter(Student.id == int(clean_idx)).first()
    if not student:
        student = db.query(Student).filter(
            (Student.bece_index_number == clean_idx) |
            (Student.student_code == clean_idx) |
            (Student.enrolment_code == clean_idx)
        ).first()

    if not student:
        raise HTTPException(status_code=404, detail=f"No candidate results found matching index number '{clean_idx}'.")

    transcript = ReportService.get_full_transcript_data(db, student.id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Student transcript records not found.")
    return transcript


# ── Parent Ward Summary ───────────────────────────────────────────────────

@router.get("/parent/ward-summary/{student_id}")
def get_parent_ward_summary(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student or (school_id is not None and student.school_id != school_id):
        raise HTTPException(status_code=404, detail="Student record not found.")

    from ..models import Semester, ExeatRecord, DisciplineRecord, Payment
    from ..services.grading import GradingService

    # 1. Current Semester & Academic Data
    current_sem = db.query(Semester).filter(Semester.is_current == True).first()
    sem_id = current_sem.id if current_sem else 1

    report_data = ReportService.get_report_data(db, student_id, sem_id)

    # 2. Attendance Stats
    attendance_records = db.query(Attendance).filter(Attendance.student_id == student_id).all()
    total_days = len(attendance_records)
    present_days = sum(1 for a in attendance_records if a.status and a.status.lower() in ["present", "p", "late", "l"])
    absent_days = total_days - present_days
    attendance_pct = round((present_days / total_days * 100.0), 1) if total_days > 0 else 100.0

    # 3. Financial Fees & Payments
    fees = db.query(Fee).filter(Fee.student_id == student_id).all()
    total_billed = sum(f.amount_due for f in fees) if fees else 0.0
    total_paid = sum(f.amount_paid for f in fees) if fees else 0.0
    balance = max(0.0, total_billed - total_paid)

    fee_ids = [f.id for f in fees]
    payments = db.query(Payment).filter(Payment.fee_id.in_(fee_ids)).order_by(Payment.id.desc()).limit(10).all() if fee_ids else []
    payment_list = [
        {
            "id": p.id,
            "amount_paid": p.amount_paid,
            "payment_date": str(p.payment_date)[:10] if p.payment_date else "",
            "payment_method": p.payment_method or "Cash",
            "reference_no": p.reference_no or "—",
            "notes": p.notes or ""
        }
        for p in payments
    ]

    # 4. Exeat Pass Records
    active_exeat = db.query(ExeatRecord).filter(
        ExeatRecord.student_id == student_id,
        ExeatRecord.status.in_(["Approved", "Departed", "Overdue"])
    ).order_by(ExeatRecord.id.desc()).first()

    exeat_history = db.query(ExeatRecord).filter(ExeatRecord.student_id == student_id).order_by(ExeatRecord.id.desc()).limit(5).all()

    # 5. Discipline Records
    discipline_records = db.query(DisciplineRecord).filter(DisciplineRecord.student_id == student_id).order_by(DisciplineRecord.id.desc()).all()

    return {
        "student_info": {
            "id": student.id,
            "full_name": student.full_name,
            "student_code": student.student_code,
            "class_name": student.class_section.name if student.class_section else "N/A",
            "house_name": student.house.name if student.house else "N/A",
            "dormitory_name": student.dormitory.name if student.dormitory else "N/A",
            "residential_status": student.residential_status or "Day",
            "gender": student.gender or "N/A"
        },
        "academic": {
            "semester_id": sem_id,
            "semester_name": current_sem.name if current_sem else "Current Semester",
            "report_data": report_data
        },
        "attendance": {
            "total_days": total_days,
            "present_days": present_days,
            "absent_days": absent_days,
            "percentage": attendance_pct
        },
        "financial": {
            "total_billed": round(total_billed, 2),
            "total_paid": round(total_paid, 2),
            "outstanding_balance": round(balance, 2),
            "payments": payment_list
        },
        "exeat": {
            "has_active_exeat": active_exeat is not None,
            "active_exeat": {
                "id": active_exeat.id,
                "exeat_type": active_exeat.exeat_type,
                "destination": active_exeat.destination,
                "expected_departure": str(active_exeat.expected_departure)[:16] if active_exeat and active_exeat.expected_departure else "",
                "expected_return": str(active_exeat.expected_return)[:16] if active_exeat and active_exeat.expected_return else "",
                "status": active_exeat.status
            } if active_exeat else None,
            "history": [
                {
                    "id": ex.id,
                    "exeat_type": ex.exeat_type,
                    "destination": ex.destination,
                    "expected_departure": str(ex.expected_departure)[:10] if ex.expected_departure else "",
                    "expected_return": str(ex.expected_return)[:10] if ex.expected_return else "",
                    "status": ex.status
                }
                for ex in exeat_history
            ]
        },
        "discipline": [
            {
                "id": d.id,
                "incident_type": d.incident_type,
                "description": d.description,
                "action_taken": d.action_taken or "Pending Action",
                "incident_date": str(d.incident_date)[:10] if d.incident_date else ""
            }
            for d in discipline_records
        ]
    }


@router.get("/class-broadsheet/{class_id}")
def get_class_broadsheet(
    class_id: int,
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates complete Class Broadsheet matrix with automatic 1st to Nth student ranking,
    total raw scores, average GPA, and subject breakdown matrix.
    """
    school_id = get_school_id(current_user)
    class_obj = db.query(ClassSection).filter(ClassSection.id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class section not found.")
    if school_id is not None and hasattr(class_obj, 'program') and class_obj.program and hasattr(class_obj.program, 'school_id') and class_obj.program.school_id is not None and class_obj.program.school_id != school_id:
        raise HTTPException(status_code=404, detail="Class section not found.")

    students = db.query(Student).filter(Student.class_section_id == class_id, Student.is_active == True).order_by(Student.full_name).all()
    if not students:
        return {"class_name": class_obj.name, "students": [], "subjects": []}

    # Fetch all scores for this class section & semester
    student_ids = [s.id for s in students]
    scores = db.query(Score).filter(Score.student_id.in_(student_ids), Score.semester_id == semester_id).all()

    # Unique subjects in scores
    subject_ids = sorted(list(set(sc.subject_id for sc in scores)))
    from ..models import Subject
    subjects_objs = db.query(Subject).filter(Subject.id.in_(subject_ids)).all() if subject_ids else []

    student_rows = []
    for s in students:
        s_scores = [sc for sc in scores if sc.student_id == s.id]
        total_raw = sum(sc.total_score for sc in s_scores if sc.total_score)
        subj_count = len(s_scores)
        avg = round(total_raw / max(1, subj_count), 2) if subj_count > 0 else 0.0

        scores_by_sub = {}
        for sc in s_scores:
            scores_by_sub[str(sc.subject_id)] = {
                "class_score": sc.class_score,
                "exam_score": sc.exam_score,
                "total": sc.total_score,
                "grade": sc.grade
            }

        student_rows.append({
            "student_id": s.id,
            "student_code": s.student_code or str(s.id),
            "full_name": s.full_name,
            "total_raw": total_raw,
            "average": avg,
            "subject_count": subj_count,
            "scores": scores_by_sub
        })

    # Sort students by total_raw descending for ranking
    student_rows.sort(key=lambda x: x["total_raw"], reverse=True)

    # Assign ranks (1st to Nth)
    for idx, r in enumerate(student_rows):
        r["rank"] = idx + 1
        rank_num = idx + 1
        suffix = "th"
        if rank_num % 10 == 1 and rank_num != 11:
            suffix = "st"
        elif rank_num % 10 == 2 and rank_num != 12:
            suffix = "nd"
        elif rank_num % 10 == 3 and rank_num != 13:
            suffix = "rd"
        r["rank_str"] = f"{rank_num}{suffix}"

    return {
        "class_id": class_id,
        "class_name": class_obj.name,
        "semester_id": semester_id,
        "total_students": len(student_rows),
        "subjects": [{"id": sub.id, "name": sub.name, "code": sub.code or sub.name} for sub in subjects_objs],
        "rows": student_rows
    }


@router.get("/batch-terminal-reports/{class_section_id}")
def get_batch_terminal_reports(
    class_section_id: int,
    semester_id: int = Query(...),
    token: str = Query(None),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Compiles all student terminal report cards in a class into a single multi-page PDF document.
    """
    auth_token = None
    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization.split(" ")[1]
    elif token:
        auth_token = token

    if not auth_token:
        raise HTTPException(status_code=401, detail="Authentication token required")

    try:
        payload = decode_jwt(auth_token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")

    school_id = payload.get("school_id")
    user_id = payload.get("user_id")
    roles = [r.lower() for r in payload.get("roles", [])]

    cs = db.query(ClassSection).filter(ClassSection.id == class_section_id).first()
    if not cs or (school_id is not None and hasattr(cs, "school_id") and cs.school_id and cs.school_id != school_id):
        raise HTTPException(status_code=404, detail="Class section not found.")

    admin_or_academic_head = {"admin", "super_admin", "headmaster", "headmistress", "assistant_head_academic", "assistant_headmaster_academic"}
    if not any(r in admin_or_academic_head for r in roles):
        if "teacher" in roles:
            is_form_master = cs.form_master_id == user_id
            if not is_form_master:
                raise HTTPException(status_code=403, detail="Only assigned Form Masters or Academic Heads can generate batch report cards.")
        else:
            raise HTTPException(status_code=403, detail="Not authorized to generate batch report cards.")

    pdf_bytes = ReportService.generate_batch_terminal_reports_pdf(db, class_section_id, semester_id)
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="No student report records found to compile for this class.")

    clean_cls_name = (cs.name or f"Class_{class_section_id}").replace(" ", "_").replace("/", "-")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Batch_Report_Cards_{clean_cls_name}_Sem_{semester_id}.pdf"'
        }
    )


@router.get("/broadsheet-pdf/{class_section_id}")
def get_broadsheet_pdf(
    class_section_id: int,
    semester_id: int = Query(...),
    token: str = Query(None),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Generates and returns an official GES/WAEC continuous assessment Broadsheet Ledger matrix PDF in Landscape.
    """
    auth_token = None
    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization.split(" ")[1]
    elif token:
        auth_token = token

    if not auth_token:
        raise HTTPException(status_code=401, detail="Authentication token required")

    try:
        payload = decode_jwt(auth_token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")

    school_id = payload.get("school_id")
    user_id = payload.get("user_id")
    roles = [r.lower() for r in payload.get("roles", [])]

    cs = db.query(ClassSection).filter(ClassSection.id == class_section_id).first()
    if not cs or (school_id is not None and hasattr(cs, "school_id") and cs.school_id and cs.school_id != school_id):
        raise HTTPException(status_code=404, detail="Class section not found.")

    admin_or_academic_head = {"admin", "super_admin", "headmaster", "headmistress", "assistant_head_academic", "assistant_headmaster_academic"}
    if not any(r in admin_or_academic_head for r in roles):
        if "teacher" in roles:
            is_form_master = cs.form_master_id == user_id
            if not is_form_master:
                raise HTTPException(status_code=403, detail="Only assigned Form Masters or Academic Heads can generate broadsheet ledgers.")
        else:
            raise HTTPException(status_code=403, detail="Not authorized to generate broadsheet ledgers.")

    pdf_bytes = ReportService.generate_broadsheet_pdf(db, class_section_id, semester_id)
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="No broadsheet records found to compile for this class.")

    clean_cls_name = (cs.name or f"Class_{class_section_id}").replace(" ", "_").replace("/", "-")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Broadsheet_Ledger_{clean_cls_name}_Sem_{semester_id}.pdf"'
        }
    )


@router.get("/broadsheet-csv/{class_section_id}")
def get_broadsheet_csv(
    class_section_id: int,
    semester_id: int = Query(...),
    token: str = Query(None),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Generates and returns an RFC 4180 CSV export of the class broadsheet matrix and statistical summary.
    """
    auth_token = None
    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization.split(" ")[1]
    elif token:
        auth_token = token

    if not auth_token:
        raise HTTPException(status_code=401, detail="Authentication token required")

    try:
        payload = decode_jwt(auth_token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")

    school_id = payload.get("school_id")
    user_id = payload.get("user_id")
    roles = [r.lower() for r in payload.get("roles", [])]

    cs = db.query(ClassSection).filter(ClassSection.id == class_section_id).first()
    if not cs or (school_id is not None and hasattr(cs, "school_id") and cs.school_id and cs.school_id != school_id):
        raise HTTPException(status_code=404, detail="Class section not found.")

    admin_or_academic_head = {"admin", "super_admin", "headmaster", "headmistress", "assistant_head_academic", "assistant_headmaster_academic"}
    if not any(r in admin_or_academic_head for r in roles):
        if "teacher" in roles:
            is_form_master = cs.form_master_id == user_id
            if not is_form_master:
                raise HTTPException(status_code=403, detail="Only assigned Form Masters or Academic Heads can export class broadsheets.")
        else:
            raise HTTPException(status_code=403, detail="Not authorized to export class broadsheets.")

    csv_content = ReportService.generate_broadsheet_csv(db, class_section_id, semester_id)
    if not csv_content:
        raise HTTPException(status_code=404, detail="No broadsheet data found for this class section.")

    clean_cls_name = (cs.name or f"Class_{class_section_id}").replace(" ", "_").replace("/", "-")
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="Broadsheet_{clean_cls_name}_Sem_{semester_id}.csv"'
        }
    )



