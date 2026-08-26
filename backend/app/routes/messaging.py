from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..database import get_db
from ..models import (
    Student, ClassSection, House, Program, User, Setting,
    Score, Semester, AcademicYear, TeacherAssignment,
    Fee, StudentSemesterSummary, MessageLog, ExeatRecord, DisciplineRecord, School
)
from ..dependencies import get_current_user, get_school_id
from ..services.grading import GradingService
from ..services.reports import ReportService
from ..services.communication_service import CommunicationService

router = APIRouter()

def _get_user_roles(user: User) -> List[str]:
    if not user or not hasattr(user, 'roles'):
        return []
    return [r.name.lower() for r in user.roles]

def _check_messaging_permission(current_user: User) -> bool:
    if not current_user:
        return False
    roles = _get_user_roles(current_user)
    uname = (current_user.username or "").lower()
    return (
        "admin" in roles or
        "headmaster" in roles or
        "assistant_head_academic" in roles or
        "form_master" in roles or
        "house_master" in roles or
        "teacher" in roles or
        "academic" in uname or
        "admin" in uname
    )

def _get_school_mode(db: Session, school_id: Optional[int] = None) -> str:
    if school_id:
        sch = db.query(School).filter(School.id == school_id).first()
        if sch and sch.school_mode:
            return sch.school_mode
    setting = db.query(Setting).filter(Setting.key == "school_mode").first()
    return setting.value if setting and setting.value else "COMBINED"

def _get_grading_standard(db: Session, school_id: Optional[int] = None) -> str:
    setting = db.query(Setting).filter(Setting.key == "grading_standard").first()
    if setting and setting.value:
        return setting.value
    mode = _get_school_mode(db, school_id)
    return "BECE" if mode == "BASIC_ONLY" else "WAEC"

def _compute_overall_grade(average_score: float, standard: str) -> str:
    if standard == "BECE":
        if average_score >= 80: return "Grade 1 (Distinction)"
        elif average_score >= 70: return "Grade 2 (Higher)"
        elif average_score >= 60: return "Grade 3 (High)"
        elif average_score >= 55: return "Grade 4 (Standard)"
        elif average_score >= 50: return "Grade 5 (Pass)"
        else: return "Grade 9 (Fail)"
    else: # WAEC
        if average_score >= 80: return "A1 (Excellent)"
        elif average_score >= 75: return "B2 (Very Good)"
        elif average_score >= 70: return "B3 (Good)"
        elif average_score >= 65: return "C4 (Credit)"
        elif average_score >= 60: return "C5 (Credit)"
        elif average_score >= 50: return "C6 (Credit)"
        elif average_score >= 45: return "D7 (Pass)"
        elif average_score >= 40: return "E8 (Pass)"
        else: return "F9 (Fail)"

# ── GET /recipients ────────────────────────────────────────────────────────────

@router.get("/recipients")
def get_messaging_recipients(
    class_id: Optional[int] = Query(None),
    house_id: Optional[int] = Query(None),
    program_id: Optional[int] = Query(None),
    group_by_parent: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _check_messaging_permission(current_user):
        raise HTTPException(status_code=403, detail="Not authorized to access messaging")

    roles = _get_user_roles(current_user)
    is_admin_or_head = ("admin" in roles or "headmaster" in roles or "assistant_head_academic" in roles)

    school_id = get_school_id(current_user)
    query = db.query(Student).filter(Student.is_active == True)
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)

    # Scoping for regular teachers / form masters if specific dropdown filters are not provided
    if not is_admin_or_head:
        assigned_section_ids = [
            a[0] for a in db.query(TeacherAssignment.class_section_id)
            .filter(TeacherAssignment.teacher_id == current_user.id).all()
        ]
        assigned_houses = db.query(House).filter(
            (House.senior_in_charge_id == current_user.id) |
            (House.house_master_id == current_user.id) |
            (House.assistant_house_master_id == current_user.id) |
            (House.senior_in_charge_girls_id == current_user.id) |
            (House.house_master_girls_id == current_user.id) |
            (House.assistant_house_master_girls_id == current_user.id)
        ).all()
        house_ids = [h.id for h in assigned_houses]

        filters = []
        if assigned_section_ids:
            filters.append(Student.class_section_id.in_(assigned_section_ids))
        if house_ids:
            filters.append(Student.house_id.in_(house_ids))

        if filters and not (class_id or house_id or program_id):
            from sqlalchemy import or_
            query = query.filter(or_(*filters))

    # Specific dropdown filters
    if class_id:
        query = query.filter(Student.class_section_id == class_id)
    if house_id:
        query = query.filter(Student.house_id == house_id)
    if program_id:
        query = query.filter(Student.program_id == program_id)

    students = query.order_by(Student.full_name).all()

    results = []
    seen_parents = set()

    for s in students:
        phone = s.phone
        guardian_name = s.guardian_name or (s.parent.username if s.parent else "Parent/Guardian")
        
        if group_by_parent and phone:
            if phone in seen_parents:
                continue
            seen_parents.add(phone)

        results.append({
            "id": s.id,
            "student_code": s.student_code,
            "full_name": s.full_name,
            "class_name": s.class_section.name if s.class_section else "Unassigned",
            "house_name": s.house.name if s.house else "Day Student",
            "guardian_name": guardian_name,
            "phone": phone or "",
            "has_phone": bool(phone and len(phone.strip()) >= 7),
            "parent_id": s.parent_id,
        })

    return results


# ── POST /report-payload ──────────────────────────────────────────────────────

@router.post("/report-payload")
def generate_report_payload(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student_id = payload.get("student_id")
    msg_type = payload.get("msg_type", "TERMINAL_REPORT")
    if not student_id:
        raise HTTPException(status_code=400, detail="student_id is required")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    guardian_name = student.guardian_name or (student.parent.username if student.parent else "Parent/Guardian")
    phone = student.phone or ""
    class_name = student.class_section.name if student.class_section else "N/A"

    # Handle EXEAT_NOTICE message type
    if msg_type == "EXEAT_NOTICE":
        exeat = db.query(ExeatRecord).filter(
            ExeatRecord.student_id == student_id
        ).order_by(ExeatRecord.id.desc()).first()

        exeat_type = exeat.exeat_type if exeat else "General Exeat"
        dest = exeat.destination if exeat else "Home"
        reason = exeat.reason if exeat else "Leave of absence"
        status = exeat.status if exeat else "Approved"

        wa_payload = (
            f"🏡 *EXEAT & LEAVE PASS NOTICE*\n"
            f"👤 *Student:* {student.full_name} ({student.student_code})\n"
            f"📚 *Class:* {class_name}\n"
            f"📋 *Type:* {exeat_type}\n"
            f"📍 *Destination:* {dest}\n"
            f"📝 *Reason:* {reason}\n"
            f"🟢 *Status:* {status}\n\n"
            f"📌 _Official notice from School Management System_"
        )
        sms_payload = (
            f"EXEAT NOTICE: {student.full_name} ({class_name})\n"
            f"Type: {exeat_type} | Status: {status}\n"
            f"Dest: {dest}\n"
            f"Reason: {reason}"
        )
        return {
            "student_id": student.id,
            "student_code": student.student_code,
            "full_name": student.full_name,
            "class_name": class_name,
            "guardian_name": guardian_name,
            "phone": phone,
            "avg_score": 0.0,
            "overall_grade": status,
            "position": "N/A",
            "whatsapp_payload": wa_payload,
            "sms_payload": sms_payload,
            "subject_count": 0
        }

    # Handle ABSENCE_ALERT message type
    if msg_type == "ABSENCE_ALERT":
        pending_msg = db.query(MessageLog).filter(
            MessageLog.student_id == student_id,
            MessageLog.message_type == "ABSENCE_ALERT",
            MessageLog.status == "PENDING"
        ).order_by(MessageLog.id.desc()).first()

        if pending_msg:
            sms_payload = pending_msg.message_body
            wa_payload = f"🔔 *ABSENCE ALERT*\n\n{pending_msg.message_body}"
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")
            sms_payload = f"Dear {guardian_name}, please be informed that your child {student.full_name} was marked ABSENT from school on {date_str}."
            wa_payload = f"🔔 *ABSENCE ALERT*\n\n{sms_payload}"

        return {
            "student_id": student.id,
            "student_code": student.student_code,
            "full_name": student.full_name,
            "class_name": class_name,
            "guardian_name": guardian_name,
            "phone": phone,
            "avg_score": 0.0,
            "overall_grade": "ABSENT",
            "position": "N/A",
            "whatsapp_payload": wa_payload,
            "sms_payload": sms_payload,
            "subject_count": 0
        }

    # Handle DISCIPLINE_NOTICE message type
    if msg_type == "DISCIPLINE_NOTICE":
        pending_msg = db.query(MessageLog).filter(
            MessageLog.student_id == student_id,
            MessageLog.message_type == "DISCIPLINE_NOTICE",
            MessageLog.status == "PENDING"
        ).order_by(MessageLog.id.desc()).first()

        if pending_msg:
            sms_payload = pending_msg.message_body
            wa_payload = f"⚠️ *DISCIPLINE NOTICE*\n\n{pending_msg.message_body}"
        else:
            disc_rec = db.query(DisciplineRecord).filter(
                DisciplineRecord.student_id == student_id
            ).order_by(DisciplineRecord.id.desc()).first()

            inc_type = disc_rec.incident_type if disc_rec else "General Notice"
            desc_str = disc_rec.description if disc_rec else "No details specified"
            action_str = f" Action taken: {disc_rec.action_taken}." if disc_rec and disc_rec.action_taken else ""

            sms_payload = f"Dear {guardian_name}, a discipline notice ({inc_type}) has been logged for your child {student.full_name}: {desc_str}.{action_str}"
            wa_payload = f"⚠️ *DISCIPLINE NOTICE*\n\n{sms_payload}"

        return {
            "student_id": student.id,
            "student_code": student.student_code,
            "full_name": student.full_name,
            "class_name": class_name,
            "guardian_name": guardian_name,
            "phone": phone,
            "avg_score": 0.0,
            "overall_grade": "DISCIPLINE",
            "position": "N/A",
            "whatsapp_payload": wa_payload,
            "sms_payload": sms_payload,
            "subject_count": 0
        }

    # Default TERMINAL_REPORT / FEE_NOTICE calculation using central ReportService
    semester_id = payload.get("semester_id")
    if semester_id:
        semester = db.query(Semester).filter(Semester.id == semester_id).first()
    else:
        semester = db.query(Semester).filter(Semester.is_current == True).first()

    if not semester:
        semester = db.query(Semester).first()

    sem_id = semester.id if semester else 1
    report_data = ReportService.get_report_data(db, student_id, sem_id)

    if not report_data:
        sem_name = semester.name if semester else "Term 1"
        year_label = semester.academic_year.label if semester and semester.academic_year else "2025/2026"
        report_data = {
            "school": {"name": "J.A. KUFFOUR STEM TECHNICAL", "motto": "Knowledge is Power", "title": "TERMINAL REPORT CARD"},
            "student": {"id": student.id, "code": student.student_code, "name": student.full_name, "class_name": class_name, "house_dorm": "Day Student", "guardian_name": guardian_name, "phone": phone, "gender": "N/A"},
            "academic": {"year": year_label, "term": sem_name, "vacation_date": "-", "reopening_date": "-"},
            "scores": [],
            "summary": {"total_marks": 0, "average_mark": 0.0, "overall_grade": "N/A", "class_position": "N/A", "attendance_present": 0, "attendance_total": 0},
            "evaluations": {"attitude": "-", "conduct": "Good", "interest": "-", "form_teacher_remarks": "Hardworking student.", "headmaster_remarks": "-", "promoted_to": "-"},
            "finances": {"fee_balance": 0.0}
        }

    sch_info = report_data.get("school", {})
    st_info = report_data.get("student", {})
    acad_info = report_data.get("academic", {})
    sum_info = report_data.get("summary", {})
    eval_info = report_data.get("evaluations", {})
    fin_info = report_data.get("finances", {})
    scores_list = report_data.get("scores", [])

    sch_name = sch_info.get("name", "J.A. KUFFOUR STEM TECHNICAL")
    year_lbl = acad_info.get("year", "2025/2026")
    term_lbl = acad_info.get("term", "Term 1")
    avg_score = sum_info.get("average_mark", 0.0)
    overall_grade = sum_info.get("overall_grade", "N/A")
    position_str = sum_info.get("class_position", "N/A")
    conduct = eval_info.get("conduct", "Good")
    remarks = eval_info.get("form_teacher_remarks", "Hardworking student.")
    fee_balance = fin_info.get("fee_balance", 0.0)

    subject_items = []
    for sc in scores_list:
        subject_items.append({
            "name": sc.get("subject", "Subject"),
            "class_score": sc.get("class_score", 0.0),
            "exam_score": sc.get("exam_score", 0.0),
            "score": sc.get("total_score", 0.0),
            "grade": sc.get("grade", "N/A"),
            "remark": sc.get("remark", ""),
            "position": sc.get("position", "N/A")
        })

    # Construct WhatsApp Payload
    wa_lines = [
        f"🏫 *{sch_name}*",
        f"📄 *OFFICIAL TERMINAL REPORT CARD*",
        f"📅 *Academic Year: {year_lbl} | {term_lbl}*",
        f"─────────────────────────────",
        f"👤 *Student:* {student.full_name} ({student.student_code})",
        f"📚 *Class:* {class_name}",
        f"🏠 *House/Dorm:* {st_info.get('house_dorm', 'Day Student')}",
        f"👤 *Guardian:* {guardian_name}",
        f"",
        f"📊 *ACADEMIC SUBJECT SCORES:*",
    ]
    for sub in subject_items:
        wa_lines.append(f"• {sub['name']}: {sub['score']}% ({sub['grade']} - {sub['remark']})")

    if not subject_items:
        wa_lines.append("• No scores recorded yet.")

    wa_lines.extend([
        f"",
        f"🏆 *OVERALL SUMMARY & STANDING:*",
        f"• Average Score: {avg_score}%",
        f"• Overall Grade: {overall_grade}",
        f"• Class Position: {position_str}",
        f"• Conduct: {conduct}",
        f"📝 *Remarks:* {remarks}",
        f"💰 *Fee Balance:* GH₵ {fee_balance:.2f}",
        f"",
        f"🔗 *DIRECT DIGITAL REPORT:*",
        f"/report-card.html?student_id={student.id}",
        f"─────────────────────────────",
        f"📌 _Official document issued by {sch_name}_"
    ])
    wa_payload = "\n".join(wa_lines)

    # Construct Compact SMS Payload
    sms_lines = [
        f"REPORT: {student.full_name} ({class_name})",
        f"{term_lbl} {year_lbl}",
        "---"
    ]
    for sub in subject_items:
        short_name = sub['name'][:8]
        sms_lines.append(f"{short_name}: {sub['score']} ({sub['grade']})")
    
    sms_lines.extend([
        "---",
        f"Avg: {avg_score}% | Grade: {overall_grade}",
        f"Pos: {position_str} | Fees: GHc {fee_balance:.2f}"
    ])
    sms_payload = "\n".join(sms_lines)

    return {
        "student_id": student.id,
        "student_code": student.student_code,
        "full_name": student.full_name,
        "class_name": class_name,
        "guardian_name": guardian_name,
        "phone": phone,
        "avg_score": avg_score,
        "overall_grade": overall_grade,
        "position": position_str,
        "whatsapp_payload": wa_payload,
        "sms_payload": sms_payload,
        "subject_count": len(subject_items),
        "report_card_data": report_data
    }


# ── POST /send-log ────────────────────────────────────────────────────────────

@router.post("/send-log")
def log_sent_message(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    student_id = payload.get("student_id")
    msg_type = payload.get("message_type", "GENERAL")

    existing_pending = None
    if student_id:
        existing_pending = db.query(MessageLog).filter(
            MessageLog.student_id == student_id,
            MessageLog.message_type == msg_type,
            MessageLog.status == "PENDING"
        ).order_by(MessageLog.id.desc()).first()

    if existing_pending:
        existing_pending.sender_id = current_user.id
        existing_pending.recipient_name = payload.get("recipient_name", existing_pending.recipient_name)
        existing_pending.recipient_phone = payload.get("recipient_phone", existing_pending.recipient_phone)
        existing_pending.channel = payload.get("channel", existing_pending.channel)
        existing_pending.message_body = payload.get("message_body", existing_pending.message_body)
        existing_pending.overall_grade = payload.get("overall_grade", existing_pending.overall_grade)
        existing_pending.status = payload.get("status", "SENT")
        db.commit()
        db.refresh(existing_pending)
        return {"status": "success", "id": existing_pending.id}

    msg_log = MessageLog(
        sender_id=current_user.id,
        student_id=student_id,
        recipient_name=payload.get("recipient_name"),
        recipient_phone=payload.get("recipient_phone"),
        channel=payload.get("channel", "SMS"),
        message_type=msg_type,
        message_body=payload.get("message_body", ""),
        overall_grade=payload.get("overall_grade"),
        status=payload.get("status", "SENT"),
    )
    db.add(msg_log)
    db.commit()
    db.refresh(msg_log)
    return {"status": "success", "id": msg_log.id}


# ── POST /batch-log ───────────────────────────────────────────────────────────

@router.post("/batch-log")
def log_batch_messages(
    payload: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    logs_to_add = []
    for item in payload:
        student_id = item.get("student_id")
        msg_type = item.get("message_type", "GENERAL")

        existing_pending = None
        if student_id:
            existing_pending = db.query(MessageLog).filter(
                MessageLog.student_id == student_id,
                MessageLog.message_type == msg_type,
                MessageLog.status == "PENDING"
            ).order_by(MessageLog.id.desc()).first()

        if existing_pending:
            existing_pending.sender_id = current_user.id
            existing_pending.recipient_name = item.get("recipient_name", existing_pending.recipient_name)
            existing_pending.recipient_phone = item.get("recipient_phone", existing_pending.recipient_phone)
            existing_pending.channel = item.get("channel", existing_pending.channel)
            existing_pending.message_body = item.get("message_body", existing_pending.message_body)
            existing_pending.overall_grade = item.get("overall_grade", existing_pending.overall_grade)
            existing_pending.status = item.get("status", "SENT")
        else:
            logs_to_add.append(MessageLog(
                sender_id=current_user.id,
                student_id=student_id,
                recipient_name=item.get("recipient_name"),
                recipient_phone=item.get("recipient_phone"),
                channel=item.get("channel", "SMS"),
                message_type=msg_type,
                message_body=item.get("message_body", ""),
                overall_grade=item.get("overall_grade"),
                status=item.get("status", "SENT"),
            ))

    if logs_to_add:
        db.add_all(logs_to_add)

    db.commit()
    return {"status": "success", "count": len(payload)}


# ── GET /logs ─────────────────────────────────────────────────────────────────

@router.get("/logs")
def get_message_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    roles = _get_user_roles(current_user)
    is_admin = ("admin" in roles or "headmaster" in roles)

    query = db.query(MessageLog)
    if not is_admin:
        query = query.filter(MessageLog.sender_id == current_user.id)

    logs = query.order_by(MessageLog.created_at.desc()).limit(100).all()

    return [{
        "id": l.id,
        "sender_name": l.sender.username if l.sender else "System",
        "student_name": l.student.full_name if l.student else "—",
        "recipient_name": l.recipient_name or "—",
        "recipient_phone": l.recipient_phone or "—",
        "channel": l.channel,
        "message_type": l.message_type,
        "overall_grade": l.overall_grade or "—",
        "status": l.status,
        "created_at": l.created_at.strftime("%Y-%m-%d %H:%M") if l.created_at else "—"
    } for l in logs]


# ── GET /gateway-settings ─────────────────────────────────────────────────────

@router.get("/gateway-settings")
def get_gateway_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _check_messaging_permission(current_user):
        raise HTTPException(status_code=403, detail="Not authorized to manage gateway settings")
    return CommunicationService.get_gateway_config(db)


# ── POST /gateway-settings ────────────────────────────────────────────────────

@router.post("/gateway-settings")
def save_gateway_settings(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    roles = _get_user_roles(current_user)
    if not ("admin" in roles or "headmaster" in roles or "super_admin" in roles):
        raise HTTPException(status_code=403, detail="Administrator permissions required to update gateway settings")

    CommunicationService.save_gateway_config(db, payload)
    return {"status": "success", "message": "Gateway configuration saved successfully"}


# ── POST /test-gateway ────────────────────────────────────────────────────────

@router.post("/test-gateway")
def test_gateway_delivery(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _check_messaging_permission(current_user):
        raise HTTPException(status_code=403, detail="Not authorized to test gateway")

    channel = (payload.get("channel") or "SMS").upper()
    recipient = payload.get("recipient", "").strip()
    test_msg = payload.get("message") or "Test message from School Management System Communication Gateway."

    if not recipient:
        raise HTTPException(status_code=400, detail="Recipient phone number or email is required")

    if channel == "SMS":
        result = CommunicationService.send_sms(
            db=db,
            to_phone=recipient,
            message=test_msg,
            recipient_name="Gateway Test Recipient",
            sender_id_user=current_user.id,
            message_type="TEST_GATEWAY"
        )
        return result

    elif channel == "WHATSAPP":
        result = CommunicationService.send_whatsapp(
            db=db,
            to_phone=recipient,
            message=test_msg,
            recipient_name="Gateway Test Recipient",
            sender_id_user=current_user.id,
            message_type="TEST_GATEWAY"
        )
        return result

    elif channel == "EMAIL":
        result = CommunicationService.send_email(
            db=db,
            to_email=recipient,
            subject="Gateway Test Notification",
            body_text=test_msg,
            body_html=f"<h3>Gateway Test</h3><p>{test_msg}</p><p><small>School Management System</small></p>",
            recipient_name="Gateway Test Recipient",
            sender_id_user=current_user.id
        )
        return result

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported channel: {channel}")


# ── POST /broadcast-class-reports ─────────────────────────────────────────────

@router.post("/broadcast-class-reports")
def broadcast_class_reports(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _check_messaging_permission(current_user):
        raise HTTPException(status_code=403, detail="Not authorized to broadcast reports")

    class_id = payload.get("class_section_id") or payload.get("class_id")
    semester_id = payload.get("semester_id")
    send_live_sms = payload.get("send_live_sms", False)

    if not class_id:
        raise HTTPException(status_code=400, detail="class_id is required")

    students = db.query(Student).filter(
        Student.class_section_id == class_id,
        Student.is_active == True
    ).order_by(Student.full_name).all()

    if not students:
        return {"count": 0, "dispatched": 0, "results": []}

    results = []
    dispatched_count = 0

    for st in students:
        phone = st.phone or ""
        guardian_name = st.guardian_name or (st.parent.username if st.parent else "Parent/Guardian")
        
        # Generate payload
        res_payload = generate_report_payload({"student_id": st.id, "semester_id": semester_id}, db, current_user)
        sms_text = res_payload.get("sms_payload", "")
        wa_text = res_payload.get("whatsapp_payload", "")
        
        item_status = "READY_FOR_INTENT"
        if send_live_sms and phone:
            send_res = CommunicationService.send_sms(
                db=db,
                to_phone=phone,
                message=sms_text,
                student_id=st.id,
                recipient_name=guardian_name,
                sender_id_user=current_user.id,
                message_type="TERMINAL_REPORT"
            )
            item_status = send_res.get("status", "SENT")
            if send_res.get("success"):
                dispatched_count += 1
        
        clean_p = CommunicationService._clean_phone(phone)
        intent_url = f"https://wa.me/{clean_p}?text={urllib.parse.quote(wa_text)}" if clean_p else ""

        results.append({
            "student_id": st.id,
            "student_name": st.full_name,
            "student_code": st.student_code,
            "guardian_name": guardian_name,
            "phone": phone,
            "avg_score": res_payload.get("avg_score", 0.0),
            "overall_grade": res_payload.get("overall_grade", "N/A"),
            "status": item_status,
            "whatsapp_intent_url": intent_url,
            "sms_payload": sms_text
        })

    return {
        "count": len(students),
        "dispatched_live": dispatched_count,
        "results": results
    }

