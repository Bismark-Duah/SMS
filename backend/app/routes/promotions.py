from datetime import datetime
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
    """
    Evaluates students in a class section with annual academic averages,
    attendance rates, and automated GES promotion recommendations.
    """
    from ..models import Score, Attendance

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

        # Compute academic scores average
        scores = db.query(Score).filter(Score.student_id == s.id).all()
        score_vals = [sc.total_score for sc in scores if sc.total_score is not None]
        avg_score = round(sum(score_vals) / len(score_vals), 1) if score_vals else 0.0

        # Compute attendance rate
        att_recs = db.query(Attendance).filter(Attendance.student_id == s.id).all()
        total_days = len(att_recs)
        present_days = sum(1 for a in att_recs if a.status.upper() in ["PRESENT", "LATE"])
        att_rate = round((present_days / total_days * 100), 1) if total_days > 0 else 100.0

        rec = "Promoted"
        remarks = ""
        if summary and summary.form_teacher_remarks:
            remarks = summary.form_teacher_remarks

        if summary and summary.promoted_to:
            prom_val = (summary.promoted_to or "").lower()
            if "repeat" in prom_val:
                rec = "Repeat"
            elif "graduate" in prom_val or "completed" in prom_val:
                rec = "Graduated"
            elif "probation" in prom_val:
                rec = "Probation"
            elif "form" in prom_val or "promoted" in prom_val:
                rec = "Promoted"
        else:
            # Automated GES Decision Rules
            if s.form and s.form >= 3:
                rec = "Graduated" if avg_score >= 50.0 else "Repeat"
            elif avg_score >= 50.0 and att_rate >= 70.0:
                rec = "Promoted"
            elif avg_score >= 45.0:
                rec = "Probation"
            else:
                rec = "Repeat"

        candidates.append({
            "id": s.id,
            "student_code": s.student_code,
            "full_name": s.full_name,
            "form": s.form or 1,
            "average_score": avg_score,
            "attendance_rate": att_rate,
            "recommendation": rec,
            "remarks": remarks
        })

    return candidates


@router.get("/docket-pdf/{class_section_id}")
def get_promotion_docket_pdf(
    class_section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generates an official GES End-of-Year Class Promotion Decision Docket PDF.
    """
    import io
    from fastapi.responses import Response
    from xhtml2pdf import pisa
    from ..models import Setting, School

    check_promotion_permission(current_user)
    school_id = get_school_id(current_user)

    cs = db.query(ClassSection).filter(ClassSection.id == class_section_id).first()
    if not cs or (school_id is not None and hasattr(cs, "school_id") and cs.school_id and cs.school_id != school_id):
        raise HTTPException(status_code=404, detail="Class section not found")

    candidates = get_promotion_candidates(class_section_id, db, current_user)
    if not candidates:
        raise HTTPException(status_code=404, detail="No active students found in class section")

    promoted_cnt = sum(1 for c in candidates if c["recommendation"] == "Promoted")
    probation_cnt = sum(1 for c in candidates if c["recommendation"] == "Probation")
    repeat_cnt = sum(1 for c in candidates if c["recommendation"] == "Repeat")
    grad_cnt = sum(1 for c in candidates if c["recommendation"] == "Graduated")

    school_name_s = db.query(Setting).filter(Setting.key == "school_name").first()
    school_name = school_name_s.value if school_name_s and school_name_s.value else "SENIOR HIGH SCHOOL"
    now_str = datetime.now().strftime("%d %B %Y")

    rows_html = ""
    for idx, c in enumerate(candidates):
        rec = c["recommendation"]
        badge_color = "#059669" if rec in ["Promoted", "Graduated"] else ("#d97706" if rec == "Probation" else "#dc2626")
        rows_html += f"""
        <tr>
            <td style="text-align:center;">{idx + 1}</td>
            <td style="font-family:monospace; font-size:8px;">{c['student_code']}</td>
            <td style="text-align:left; font-weight:bold;">{c['full_name']}</td>
            <td style="text-align:center;">Form {c['form']}</td>
            <td style="text-align:center; font-weight:bold;">{c['average_score']}%</td>
            <td style="text-align:center;">{c['attendance_rate']}%</td>
            <td style="text-align:center; font-weight:bold; color:{badge_color};">{rec.upper()}</td>
            <td style="text-align:left; font-size:7.5px; color:#475569;">{c['remarks'] or '-'}</td>
        </tr>
        """

    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: a4 portrait; margin: 0.8cm; }}
            body {{ font-family: Helvetica, Arial, sans-serif; font-size: 8.5px; color: #0f172a; }}
            .header-table {{ width: 100%; border-bottom: 2px solid #0f172a; padding-bottom: 6px; margin-bottom: 8px; }}
            .matrix-table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
            .matrix-table th, .matrix-table td {{ border: 1px solid #94a3b8; padding: 4px 6px; font-size: 8px; }}
            .matrix-table th {{ background: #f1f5f9; font-weight: bold; text-align: center; }}
            .kpi-table {{ width: 100%; margin-top: 8px; margin-bottom: 8px; }}
            .kpi-box {{ background: #f8fafc; border: 1px solid #cbd5e1; padding: 6px; text-align: center; }}
        </style>
    </head>
    <body>
        <table class="header-table">
            <tr>
                <td style="width:70%;">
                    <div style="font-size:7.5px; font-weight:bold; color:#475569; letter-spacing:1px; text-transform:uppercase;">GHANA EDUCATION SERVICE &bull; ACADEMIC BOARD</div>
                    <div style="font-size:14px; font-weight:900; color:#0f172a; text-transform:uppercase; margin-top:2px;">{school_name}</div>
                    <div style="font-size:10px; font-weight:bold; color:#0369a1; margin-top:2px; text-transform:uppercase;">OFFICIAL END-OF-YEAR CLASS PROMOTION DECISION DOCKET</div>
                </td>
                <td style="width:30%; text-align:right; vertical-align:top;">
                    <div style="font-size:10px; font-weight:bold; color:#0369a1;">Class: {cs.name}</div>
                    <div style="font-size:8px; color:#64748b;">Date: {now_str}</div>
                </td>
            </tr>
        </table>

        <table class="kpi-table">
            <tr>
                <td class="kpi-box" style="width:20%;">
                    <div style="font-size:7px; color:#64748b; text-transform:uppercase;">Total Evaluated</div>
                    <div style="font-size:12px; font-weight:bold; color:#0f172a;">{len(candidates)}</div>
                </td>
                <td class="kpi-box" style="width:20%;">
                    <div style="font-size:7px; color:#64748b; text-transform:uppercase;">Promoted</div>
                    <div style="font-size:12px; font-weight:bold; color:#059669;">{promoted_cnt}</div>
                </td>
                <td class="kpi-box" style="width:20%;">
                    <div style="font-size:7px; color:#64748b; text-transform:uppercase;">On Probation</div>
                    <div style="font-size:12px; font-weight:bold; color:#d97706;">{probation_cnt}</div>
                </td>
                <td class="kpi-box" style="width:20%;">
                    <div style="font-size:7px; color:#64748b; text-transform:uppercase;">Repeat Class</div>
                    <div style="font-size:12px; font-weight:bold; color:#dc2626;">{repeat_cnt}</div>
                </td>
                <td class="kpi-box" style="width:20%;">
                    <div style="font-size:7px; color:#64748b; text-transform:uppercase;">Graduated</div>
                    <div style="font-size:12px; font-weight:bold; color:#0284c7;">{grad_cnt}</div>
                </td>
            </tr>
        </table>

        <table class="matrix-table">
            <thead>
                <tr>
                    <th style="width:20px;">#</th>
                    <th style="width:65px;">Student ID</th>
                    <th style="text-align:left;">Student Full Name</th>
                    <th style="width:45px;">Level</th>
                    <th style="width:45px;">Avg Score</th>
                    <th style="width:50px;">Att Rate</th>
                    <th style="width:75px;">Decision</th>
                    <th style="text-align:left;">Academic Head Remarks</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>

        <table style="width:100%; margin-top:20px; border:none; font-size:8px;">
            <tr>
                <td style="width:33%; text-align:center;">
                    <div style="border-bottom:1px solid #000; width:130px; margin:0 auto 4px;"></div>
                    <strong>Form Master / Mistress</strong>
                    <div style="font-size:7px; color:#64748b;">Signature &amp; Date</div>
                </td>
                <td style="width:33%; text-align:center;">
                    <div style="border-bottom:1px solid #000; width:130px; margin:0 auto 4px;"></div>
                    <strong>Head of Academic Affairs</strong>
                    <div style="font-size:7px; color:#64748b;">Signature &amp; Date</div>
                </td>
                <td style="width:34%; text-align:center;">
                    <div style="border-bottom:1px solid #000; width:130px; margin:0 auto 4px;"></div>
                    <strong>Headmaster / Principal</strong>
                    <div style="font-size:7px; color:#64748b;">Official Approval &amp; Stamp</div>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)
    if pisa_status.err:
        raise HTTPException(status_code=500, detail="Failed to compile promotion docket PDF")

    clean_cls_name = (cs.name or f"Class_{class_section_id}").replace(" ", "_")
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Promotion_Docket_{clean_cls_name}.pdf"'
        }
    )



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
