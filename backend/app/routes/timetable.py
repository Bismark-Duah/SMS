from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel

from ..database import get_db
from ..models import Timetable, ClassSection, Subject, User, Semester, Program
from ..dependencies import get_current_user, get_school_id

router = APIRouter()

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def require_admin(current_user: User):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if "admin" not in [r.name for r in current_user.roles]:
        raise HTTPException(status_code=403, detail="Admin access required")


def _check_class_school(cs: ClassSection, school_id: Optional[int]) -> bool:
    if not cs:
        return False
    if school_id is None:
        return True
    if hasattr(cs, "school_id") and cs.school_id is not None:
        return cs.school_id == school_id
    if cs.program and hasattr(cs.program, "school_id") and cs.program.school_id is not None:
        return cs.program.school_id == school_id
    return True



def _enrich(slot: Timetable) -> dict:
    return {
        "id": slot.id,
        "class_section_id": slot.class_section_id,
        "class_name": slot.class_section.name if slot.class_section else None,
        "subject_id": slot.subject_id,
        "subject_name": slot.subject.name if slot.subject else None,
        "teacher_id": slot.teacher_id,
        "teacher_name": slot.teacher.username if slot.teacher else None,
        "semester_id": slot.semester_id,
        "day_of_week": slot.day_of_week,
        "day_name": DAYS[slot.day_of_week] if 0 <= slot.day_of_week <= 4 else "Unknown",
        "period_number": slot.period_number,
        "start_time": slot.start_time,
        "end_time": slot.end_time,
        "room": slot.room,
    }


# ── Schemas ───────────────────────────────────────────────────────────────────

class SlotCreate(BaseModel):
    class_section_id: int
    subject_id: int
    teacher_id: Optional[int] = None
    semester_id: Optional[int] = None
    day_of_week: int          # 0=Mon … 4=Fri
    period_number: int        # 1-based
    start_time: Optional[str] = None   # "08:00"
    end_time: Optional[str] = None     # "09:00"
    room: Optional[str] = None


class SlotUpdate(BaseModel):
    subject_id: Optional[int] = None
    teacher_id: Optional[int] = None
    semester_id: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    room: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/class/{class_section_id}")
def get_class_timetable(
    class_section_id: int,
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the full weekly timetable for a class section."""
    school_id = get_school_id(current_user)
    cs = db.query(ClassSection).options(joinedload(ClassSection.program)).filter(ClassSection.id == class_section_id).first()
    if not cs or not _check_class_school(cs, school_id):
        raise HTTPException(status_code=404, detail="Class section not found")

    query = db.query(Timetable).options(
        joinedload(Timetable.class_section),
        joinedload(Timetable.subject),
        joinedload(Timetable.teacher)
    ).filter(Timetable.class_section_id == class_section_id)
    if semester_id:
        query = query.filter(Timetable.semester_id == semester_id)
    slots = query.order_by(Timetable.day_of_week, Timetable.period_number).all()
    return [_enrich(s) for s in slots]


@router.get("/teacher/{teacher_id}")
def get_teacher_timetable(
    teacher_id: int,
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a teacher's complete teaching schedule across all classes."""
    query = db.query(Timetable).options(
        joinedload(Timetable.class_section),
        joinedload(Timetable.subject),
        joinedload(Timetable.teacher)
    ).filter(Timetable.teacher_id == teacher_id)
    if semester_id:
        query = query.filter(Timetable.semester_id == semester_id)
    slots = query.order_by(Timetable.day_of_week, Timetable.period_number).all()
    return [_enrich(s) for s in slots]


@router.get("/conflicts")
def check_conflicts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: find all teacher and room/lab double-booking conflicts."""
    require_admin(current_user)

    school_id = get_school_id(current_user)
    query = db.query(Timetable).options(
        joinedload(Timetable.class_section),
        joinedload(Timetable.subject),
        joinedload(Timetable.teacher)
    ).join(Timetable.class_section).outerjoin(ClassSection.program)
    if school_id is not None:
        if hasattr(ClassSection, "school_id"):
            query = query.filter((ClassSection.school_id == school_id) | (Program.school_id == school_id))
        else:
            query = query.filter(Program.school_id == school_id)

    all_slots = query.all()

    seen_teacher = {}
    conflicts = []
    for slot in all_slots:
        if slot.teacher_id:
            key = (slot.teacher_id, slot.day_of_week, slot.period_number)
            if key in seen_teacher:
                conflicts.append({
                    "type": "teacher",
                    "teacher_id": slot.teacher_id,
                    "teacher_name": slot.teacher.username if slot.teacher else None,
                    "day": DAYS[slot.day_of_week],
                    "period": slot.period_number,
                    "slot_1": _enrich(seen_teacher[key]),
                    "slot_2": _enrich(slot),
                })
            else:
                seen_teacher[key] = slot

    seen_room = {}
    for slot in all_slots:
        if slot.room and slot.room.strip():
            key = (slot.room.strip().lower(), slot.day_of_week, slot.period_number)
            if key in seen_room:
                conflicts.append({
                    "type": "room",
                    "room": slot.room,
                    "day": DAYS[slot.day_of_week],
                    "period": slot.period_number,
                    "slot_1": _enrich(seen_room[key]),
                    "slot_2": _enrich(slot),
                })
            else:
                seen_room[key] = slot

    return conflicts


@router.get("/")
def list_all_slots(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: list all timetable entries."""
    require_admin(current_user)
    slots = db.query(Timetable).options(
        joinedload(Timetable.class_section),
        joinedload(Timetable.subject),
        joinedload(Timetable.teacher)
    ).order_by(
        Timetable.class_section_id, Timetable.day_of_week, Timetable.period_number
    ).all()
    return [_enrich(s) for s in slots]


@router.post("/", status_code=201)
def create_slot(
    payload: SlotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: create a timetable slot. Enforces no double-booking for teachers."""
    require_admin(current_user)

    if payload.day_of_week < 0 or payload.day_of_week > 4:
        raise HTTPException(status_code=400, detail="day_of_week must be 0 (Mon) to 4 (Fri)")
    if payload.period_number < 1:
        raise HTTPException(status_code=400, detail="period_number must be >= 1")

    # Check class already has something in this slot
    existing_class = db.query(Timetable).filter(
        Timetable.class_section_id == payload.class_section_id,
        Timetable.day_of_week == payload.day_of_week,
        Timetable.period_number == payload.period_number,
    ).first()
    if existing_class:
        raise HTTPException(
            status_code=409,
            detail=f"This class already has a subject assigned to {DAYS[payload.day_of_week]} Period {payload.period_number}"
        )

    # Check teacher conflict (if teacher supplied)
    if payload.teacher_id:
        existing_teacher = db.query(Timetable).filter(
            Timetable.teacher_id == payload.teacher_id,
            Timetable.day_of_week == payload.day_of_week,
            Timetable.period_number == payload.period_number,
        ).first()
        if existing_teacher:
            teacher = db.query(User).filter(User.id == payload.teacher_id).first()
            tname = teacher.username if teacher else f"Teacher #{payload.teacher_id}"
            raise HTTPException(
                status_code=409,
                detail=f"{tname} is already assigned to another class on {DAYS[payload.day_of_week]} Period {payload.period_number}"
            )

    # Check room/lab collision
    if payload.room and payload.room.strip():
        existing_room = db.query(Timetable).filter(
            Timetable.room == payload.room.strip(),
            Timetable.day_of_week == payload.day_of_week,
            Timetable.period_number == payload.period_number,
        ).first()
        if existing_room:
            cls_name = existing_room.class_section.name if existing_room.class_section else f"Class #{existing_room.class_section_id}"
            raise HTTPException(
                status_code=409,
                detail=f"Room/Lab '{payload.room.strip()}' is already allocated to {cls_name} on {DAYS[payload.day_of_week]} Period {payload.period_number}"
            )

    slot = Timetable(**payload.model_dump())
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return _enrich(slot)


@router.put("/{slot_id}")
def update_slot(
    slot_id: int,
    payload: SlotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: update subject, teacher, time, or room for an existing slot."""
    require_admin(current_user)
    slot = db.query(Timetable).filter(Timetable.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Timetable slot not found")

    # If changing teacher, check conflicts
    new_teacher_id = payload.teacher_id if payload.teacher_id is not None else slot.teacher_id
    if new_teacher_id and new_teacher_id != slot.teacher_id:
        conflict = db.query(Timetable).filter(
            Timetable.teacher_id == new_teacher_id,
            Timetable.day_of_week == slot.day_of_week,
            Timetable.period_number == slot.period_number,
            Timetable.id != slot_id,
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Teacher conflict: already assigned in this period")

    # If changing room, check conflicts
    new_room = payload.room.strip() if payload.room is not None and payload.room.strip() else (slot.room.strip() if slot.room else None)
    if new_room and new_room != (slot.room or "").strip():
        room_conflict = db.query(Timetable).filter(
            Timetable.room == new_room,
            Timetable.day_of_week == slot.day_of_week,
            Timetable.period_number == slot.period_number,
            Timetable.id != slot_id,
        ).first()
        if room_conflict:
            cls_name = room_conflict.class_section.name if room_conflict.class_section else f"Class #{room_conflict.class_section_id}"
            raise HTTPException(status_code=409, detail=f"Room/Lab '{new_room}' is already allocated to {cls_name} in this period")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(slot, field, value)

    db.commit()
    db.refresh(slot)
    return _enrich(slot)


@router.delete("/{slot_id}", status_code=204)
def delete_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: remove a timetable slot."""
    require_admin(current_user)
    slot = db.query(Timetable).filter(Timetable.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Timetable slot not found")
    db.delete(slot)
    db.commit()


@router.delete("/class/{class_section_id}", status_code=204)
def clear_class_timetable(
    class_section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: wipe all timetable slots for a class section."""
    require_admin(current_user)
    db.query(Timetable).filter(Timetable.class_section_id == class_section_id).delete()
    db.commit()


@router.get("/class/{class_section_id}/pdf")
def get_class_timetable_pdf(
    class_section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates and streams an official A4 Landscape Class Weekly Timetable PDF.
    """
    import io
    from datetime import datetime
    from fastapi.responses import Response
    from xhtml2pdf import pisa
    from ..models import Setting, School

    school_id = get_school_id(current_user)
    cs = db.query(ClassSection).filter(ClassSection.id == class_section_id).first()
    if not cs or not _check_class_school(cs, school_id):
        raise HTTPException(status_code=404, detail="Class section not found")

    slots = db.query(Timetable).filter(Timetable.class_section_id == class_section_id).all()
    slot_map = {(s.day_of_week, s.period_number): s for s in slots}

    school_name_s = db.query(Setting).filter(Setting.key == "school_name").first()
    school_name = school_name_s.value if school_name_s and school_name_s.value else "SENIOR HIGH SCHOOL"
    now_str = datetime.now().strftime("%d %B %Y")

    periods_config = [
        {"period": 1, "time": "08:00 - 08:45"},
        {"period": 2, "time": "08:45 - 09:30"},
        {"is_break": True, "title": "SNACK &amp; BREAKFAST BREAK (09:30 - 09:50)"},
        {"period": 3, "time": "09:50 - 10:35"},
        {"period": 4, "time": "10:35 - 11:20"},
        {"is_break": True, "title": "MID-DAY LUNCH BREAK (11:20 - 12:00)"},
        {"period": 5, "time": "12:00 - 12:45"},
        {"period": 6, "time": "12:45 - 01:30"},
        {"period": 7, "time": "01:30 - 02:15"},
    ]

    rows_html = ""
    for item in periods_config:
        if item.get("is_break"):
            rows_html += f"""
            <tr style="background:#f1f5f9; text-align:center; font-weight:bold; color:#475569; font-size:7.5px;">
                <td colspan="6" style="padding:4px; border:1px solid #94a3b8; letter-spacing:1px;">&mdash; {item['title']} &mdash;</td>
            </tr>
            """
        else:
            p_num = item["period"]
            p_time = item["time"]
            cols_html = f'<td style="text-align:center; font-weight:bold; background:#f8fafc; border:1px solid #94a3b8; font-size:8px;">Period {p_num}<br/><span style="font-size:7px; color:#64748b; font-weight:normal;">{p_time}</span></td>'

            for day_idx in range(5):
                slot = slot_map.get((day_idx, p_num))
                if slot:
                    sub_name = slot.subject.name if slot.subject else "Subject"
                    t_name = slot.teacher.username if slot.teacher else ""
                    room_str = f" [{slot.room}]" if slot.room else ""
                    is_core = slot.subject.is_core if slot.subject else True
                    badge_color = "#0369a1" if is_core else "#059669"

                    cols_html += f"""
                    <td style="border:1px solid #94a3b8; padding:4px 6px; vertical-align:top; background:rgba(255,255,255,0.7);">
                        <div style="font-weight:bold; font-size:8px; color:{badge_color};">{sub_name}</div>
                        <div style="font-size:7px; color:#475569; margin-top:2px;">{t_name}{room_str}</div>
                    </td>
                    """
                else:
                    cols_html += '<td style="border:1px solid #94a3b8; padding:4px; text-align:center; font-size:7px; color:#cbd5e1;">&mdash;</td>'

            rows_html += f"<tr>{cols_html}</tr>"

    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: a4 landscape; margin: 0.8cm; }}
            body {{ font-family: Helvetica, Arial, sans-serif; font-size: 8px; color: #0f172a; }}
            .header-table {{ width: 100%; border-bottom: 2px solid #0f172a; padding-bottom: 6px; margin-bottom: 8px; }}
            .grid-table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
            .grid-table th, .grid-table td {{ border: 1px solid #94a3b8; }}
            .grid-table th {{ background: #0f172a; color: #ffffff; font-weight: bold; text-align: center; padding: 6px; font-size: 8.5px; }}
        </style>
    </head>
    <body>
        <table class="header-table">
            <tr>
                <td style="width:70%;">
                    <div style="font-size:7.5px; font-weight:bold; color:#475569; letter-spacing:1px; text-transform:uppercase;">GHANA EDUCATION SERVICE &bull; ACADEMIC TIMETABLE BOARD</div>
                    <div style="font-size:14px; font-weight:900; color:#0f172a; text-transform:uppercase; margin-top:2px;">{school_name}</div>
                    <div style="font-size:10px; font-weight:bold; color:#0369a1; margin-top:2px; text-transform:uppercase;">OFFICIAL CLASS WEEKLY TIMETABLE &bull; {cs.name}</div>
                </td>
                <td style="width:30%; text-align:right; vertical-align:top;">
                    <div style="font-size:9.5px; font-weight:bold; color:#0f172a;">CLASS: {cs.name}</div>
                    <div style="font-size:7.5px; color:#64748b;">EFFECTIVE: 2025/2026 ACADEMIC SESSION</div>
                    <div style="font-size:7.5px; color:#64748b;">DATE: {now_str}</div>
                </td>
            </tr>
        </table>

        <table class="grid-table">
            <thead>
                <tr>
                    <th style="width:85px;">Period / Time</th>
                    <th>Monday</th>
                    <th>Tuesday</th>
                    <th>Wednesday</th>
                    <th>Thursday</th>
                    <th>Friday</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>

        <table style="width:100%; margin-top:16px; border:none; font-size:8px;">
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
        raise HTTPException(status_code=500, detail="Failed to compile class timetable PDF")

    clean_cls_name = (cs.name or f"Class_{class_section_id}").replace(" ", "_")
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Timetable_{clean_cls_name}.pdf"'
        }
    )


@router.get("/teacher/{teacher_id}/pdf")
def get_teacher_timetable_pdf(
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates and streams an official A4 Landscape Teacher Schedule Docket PDF.
    """
    import io
    from datetime import datetime
    from fastapi.responses import Response
    from xhtml2pdf import pisa
    from ..models import Setting, School

    teacher = db.query(User).filter(User.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    slots = db.query(Timetable).filter(Timetable.teacher_id == teacher_id).all()
    slot_map = {(s.day_of_week, s.period_number): s for s in slots}

    school_name_s = db.query(Setting).filter(Setting.key == "school_name").first()
    school_name = school_name_s.value if school_name_s and school_name_s.value else "SENIOR HIGH SCHOOL"
    now_str = datetime.now().strftime("%d %B %Y")

    periods_config = [
        {"period": 1, "time": "08:00 - 08:45"},
        {"period": 2, "time": "08:45 - 09:30"},
        {"is_break": True, "title": "SNACK &amp; BREAKFAST BREAK (09:30 - 09:50)"},
        {"period": 3, "time": "09:50 - 10:35"},
        {"period": 4, "time": "10:35 - 11:20"},
        {"is_break": True, "title": "MID-DAY LUNCH BREAK (11:20 - 12:00)"},
        {"period": 5, "time": "12:00 - 12:45"},
        {"period": 6, "time": "12:45 - 01:30"},
        {"period": 7, "time": "01:30 - 02:15"},
    ]

    rows_html = ""
    for item in periods_config:
        if item.get("is_break"):
            rows_html += f"""
            <tr style="background:#f1f5f9; text-align:center; font-weight:bold; color:#475569; font-size:7.5px;">
                <td colspan="6" style="padding:4px; border:1px solid #94a3b8; letter-spacing:1px;">&mdash; {item['title']} &mdash;</td>
            </tr>
            """
        else:
            p_num = item["period"]
            p_time = item["time"]
            cols_html = f'<td style="text-align:center; font-weight:bold; background:#f8fafc; border:1px solid #94a3b8; font-size:8px;">Period {p_num}<br/><span style="font-size:7px; color:#64748b; font-weight:normal;">{p_time}</span></td>'

            for day_idx in range(5):
                slot = slot_map.get((day_idx, p_num))
                if slot:
                    sub_name = slot.subject.name if slot.subject else "Subject"
                    cls_name = slot.class_section.name if slot.class_section else ""
                    room_str = f" [{slot.room}]" if slot.room else ""

                    cols_html += f"""
                    <td style="border:1px solid #94a3b8; padding:4px 6px; vertical-align:top; background:rgba(255,255,255,0.7);">
                        <div style="font-weight:bold; font-size:8px; color:#0369a1;">{sub_name}</div>
                        <div style="font-size:7px; color:#059669; font-weight:bold; margin-top:2px;">{cls_name}{room_str}</div>
                    </td>
                    """
                else:
                    cols_html += '<td style="border:1px solid #94a3b8; padding:4px; text-align:center; font-size:7px; color:#cbd5e1;">&mdash;</td>'

            rows_html += f"<tr>{cols_html}</tr>"

    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: a4 landscape; margin: 0.8cm; }}
            body {{ font-family: Helvetica, Arial, sans-serif; font-size: 8px; color: #0f172a; }}
            .header-table {{ width: 100%; border-bottom: 2px solid #0f172a; padding-bottom: 6px; margin-bottom: 8px; }}
            .grid-table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
            .grid-table th, .grid-table td {{ border: 1px solid #94a3b8; }}
            .grid-table th {{ background: #0369a1; color: #ffffff; font-weight: bold; text-align: center; padding: 6px; font-size: 8.5px; }}
        </style>
    </head>
    <body>
        <table class="header-table">
            <tr>
                <td style="width:70%;">
                    <div style="font-size:7.5px; font-weight:bold; color:#475569; letter-spacing:1px; text-transform:uppercase;">GHANA EDUCATION SERVICE &bull; ACADEMIC TIMETABLE BOARD</div>
                    <div style="font-size:14px; font-weight:900; color:#0f172a; text-transform:uppercase; margin-top:2px;">{school_name}</div>
                    <div style="font-size:10px; font-weight:bold; color:#0369a1; margin-top:2px; text-transform:uppercase;">INSTRUCTOR TEACHING SCHEDULE &bull; {teacher.username.upper()}</div>
                </td>
                <td style="width:30%; text-align:right; vertical-align:top;">
                    <div style="font-size:9.5px; font-weight:bold; color:#0f172a;">TEACHER: {teacher.username}</div>
                    <div style="font-size:7.5px; color:#059669; font-weight:bold;">TOTAL WORKLOAD: {len(slots)} PERIODS / WEEK</div>
                    <div style="font-size:7.5px; color:#64748b;">DATE: {now_str}</div>
                </td>
            </tr>
        </table>

        <table class="grid-table">
            <thead>
                <tr>
                    <th style="width:85px;">Period / Time</th>
                    <th>Monday</th>
                    <th>Tuesday</th>
                    <th>Wednesday</th>
                    <th>Thursday</th>
                    <th>Friday</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>

        <table style="width:100%; margin-top:16px; border:none; font-size:8px;">
            <tr>
                <td style="width:50%; text-align:center;">
                    <div style="border-bottom:1px solid #000; width:140px; margin:0 auto 4px;"></div>
                    <strong>Teacher / Instructor</strong>
                    <div style="font-size:7px; color:#64748b;">Signature &amp; Date</div>
                </td>
                <td style="width:50%; text-align:center;">
                    <div style="border-bottom:1px solid #000; width:140px; margin:0 auto 4px;"></div>
                    <strong>Head of Department / Academic Head</strong>
                    <div style="font-size:7px; color:#64748b;">Official Confirmation</div>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)
    if pisa_status.err:
        raise HTTPException(status_code=500, detail="Failed to compile teacher schedule PDF")

    clean_tname = teacher.username.replace(" ", "_")
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Teacher_Schedule_{clean_tname}.pdf"'
        }
    )

