"""
exeat_export_service.py - Enterprise Pastoral & Exeat Gate Operations Export Engine.
Provides filtered, preset-driven exports for:
1. Active Out-of-Campus Manifest (Security Gate Check Roster)
2. Historical Exeat Ledger (Date-Range Audit Log)
3. Overdue Exeats & Truancy / Absentee Alert Roster
4. Boarding House & Dormitory Allocation Register

Supports both styled .xlsx (openpyxl) and universal .csv with strict school-level isolation.
100% Offline-First.
"""

import io
import csv
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, desc

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from ..models import ExeatRecord, Student, House, Dormitory, ClassSection, School, User
from .import_export_service import sanitize_csv_cell


def build_filtered_exeat_query(
    db: Session,
    school_id: Optional[int],
    filters: Optional[Dict[str, Any]] = None
):
    """
    Builds a tenant-isolated query for Exeat records.
    """
    filters = filters or {}
    query = db.query(ExeatRecord).join(Student, ExeatRecord.student_id == Student.id).options(
        joinedload(ExeatRecord.student).joinedload(Student.class_section),
        joinedload(ExeatRecord.student).joinedload(Student.house),
        joinedload(ExeatRecord.student).joinedload(Student.dormitory),
        joinedload(ExeatRecord.approved_by),
        joinedload(ExeatRecord.gate_out_by),
        joinedload(ExeatRecord.gate_in_by)
    )

    if school_id is not None:
        query = query.filter(Student.school_id == school_id)

    # 1. House filter
    house_id = filters.get("house_id")
    if house_id is not None and str(house_id).strip() != "":
        try:
            query = query.filter(Student.house_id == int(house_id))
        except (ValueError, TypeError):
            pass

    # 2. Exeat Type
    exeat_type = filters.get("exeat_type")
    if exeat_type and str(exeat_type).strip().lower() not in ("all", ""):
        query = query.filter(ExeatRecord.exeat_type.ilike(f"%{str(exeat_type).strip()}%"))

    # 3. Status filter
    status = filters.get("status")
    if status and str(status).strip().lower() not in ("all", ""):
        sf = str(status).strip().lower()
        if sf in ("out", "departed", "active_out"):
            query = query.filter(ExeatRecord.status.in_(["Departed", "Overdue"]))
        elif sf in ("overdue", "overdue_only"):
            query = query.filter(ExeatRecord.status == "Overdue")
        else:
            query = query.filter(ExeatRecord.status.ilike(str(status).strip()))

    # 4. Date Range (Departure / Creation Date)
    start_date = filters.get("start_date")
    if start_date and str(start_date).strip() != "":
        try:
            dt_start = datetime.strptime(str(start_date).strip()[:10], "%Y-%m-%d")
            query = query.filter(ExeatRecord.expected_departure >= dt_start)
        except ValueError:
            pass

    end_date = filters.get("end_date")
    if end_date and str(end_date).strip() != "":
        try:
            dt_end = datetime.strptime(str(end_date).strip()[:10] + " 23:59:59", "%Y-%m-%d %H:%M:%S")
            query = query.filter(ExeatRecord.expected_departure <= dt_end)
        except ValueError:
            pass

    return query.order_by(desc(ExeatRecord.id))


def generate_exeat_export_dataset(
    db: Session,
    school_id: Optional[int],
    preset_key: str = "active_out",
    file_format: str = "xlsx",
    filters: Optional[Dict[str, Any]] = None
) -> Tuple[bytes, str, str]:
    """
    Generates preset-driven exeat and boarding exports:
    - active_out
    - history
    - overdue
    - dorm_allocation
    """
    filters = filters or {}
    school = db.query(School).filter(School.id == school_id).first() if school_id else None
    school_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", school.name if school else "Institutional")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    now = datetime.now()

    # ── Preset 1: Dormitory Allocation Register ──
    if preset_key == "dorm_allocation":
        title = "Boarding_House_Dormitory_Register"
        columns = [
            ("Boarding House", "house_name"),
            ("Dormitory / Room", "dorm_name"),
            ("Student Code", "student_code"),
            ("Full Name", "full_name"),
            ("Gender", "gender"),
            ("Form / Year", "form"),
            ("Class Section", "class_name"),
            ("Emergency Phone", "phone")
        ]

        st_query = db.query(Student).filter(
            Student.is_active == True,
            Student.residential_status.ilike("%boarding%")
        ).options(
            joinedload(Student.house),
            joinedload(Student.dormitory),
            joinedload(Student.class_section)
        )
        if school_id is not None:
            st_query = st_query.filter(Student.school_id == school_id)

        house_id = filters.get("house_id")
        if house_id:
            try:
                st_query = st_query.filter(Student.house_id == int(house_id))
            except (ValueError, TypeError):
                pass

        students = st_query.order_by(Student.house_id.asc(), Student.dormitory_id.asc(), Student.full_name.asc()).all()
        rows_data = []
        for s in students:
            rows_data.append({
                "house_name": s.house.name if s.house else "Unassigned House",
                "dorm_name": s.dormitory.name if s.dormitory else "Unassigned Dorm",
                "student_code": s.student_code or "",
                "full_name": s.full_name or "",
                "gender": s.gender or "",
                "form": s.form if s.form is not None else "",
                "class_name": s.class_section.name if s.class_section else "",
                "phone": s.phone or ""
            })

        return _render_exeat_dataset(rows_data, columns, f"{title}_{school_slug}_{timestamp}", file_format)

    # ── Preset 2: Overdue Exeats Alert Roster ──
    elif preset_key == "overdue":
        title = "Overdue_Exeats_Truancy_Alert"
        columns = [
            ("Student Code", "student_code"),
            ("Full Name", "full_name"),
            ("Gender", "gender"),
            ("Class Section", "class_name"),
            ("Boarding House", "house_name"),
            ("Expected Return", "expected_return"),
            ("Hours Overdue", "hours_overdue"),
            ("Destination", "destination"),
            ("Parent Name", "parent_name"),
            ("Parent Phone", "phone"),
            ("Approving Officer", "approver")
        ]

        query = build_filtered_exeat_query(db, school_id, filters)
        # Filter for overdue or departed past return time
        query = query.filter(
            or_(
                ExeatRecord.status == "Overdue",
                and_(ExeatRecord.status == "Departed", ExeatRecord.expected_return < now)
            )
        )
        exeats = query.all()

        rows_data = []
        for ex in exeats:
            st = ex.student
            overdue_hrs = 0
            if ex.expected_return and now > ex.expected_return:
                delta = now - ex.expected_return
                overdue_hrs = int(delta.total_seconds() // 3600)

            rows_data.append({
                "student_code": st.student_code if st else "",
                "full_name": st.full_name if st else "",
                "gender": st.gender if st else "",
                "class_name": st.class_section.name if (st and st.class_section) else "",
                "house_name": st.house.name if (st and st.house) else "",
                "expected_return": ex.expected_return.strftime("%Y-%m-%d %H:%M") if ex.expected_return else "",
                "hours_overdue": f"{overdue_hrs} hrs",
                "destination": ex.destination or "",
                "parent_name": st.guardian_name if st else "",
                "phone": ex.parent_contact or (st.phone if st else ""),
                "approver": ex.approved_by.full_name or ex.approved_by.username if ex.approved_by else "Staff"
            })

        return _render_exeat_dataset(rows_data, columns, f"{title}_{school_slug}_{timestamp}", file_format)

    # ── Preset 3: Historical Exeat Ledger ──
    elif preset_key == "history":
        title = "Historical_Exeat_Audit_Ledger"
        columns = [
            ("Student Code", "student_code"),
            ("Full Name", "full_name"),
            ("Gender", "gender"),
            ("Class Section", "class_name"),
            ("House", "house_name"),
            ("Exeat Type", "exeat_type"),
            ("Reason / Purpose", "reason"),
            ("Destination", "destination"),
            ("Departure Time", "actual_departure"),
            ("Return Time", "actual_return"),
            ("Return Status", "status"),
            ("Approved By", "approver"),
            ("Gate Out Officer", "gate_out"),
            ("Gate In Officer", "gate_in")
        ]

        query = build_filtered_exeat_query(db, school_id, filters)
        exeats = query.all()

        rows_data = []
        for ex in exeats:
            st = ex.student
            rows_data.append({
                "student_code": st.student_code if st else "",
                "full_name": st.full_name if st else "",
                "gender": st.gender if st else "",
                "class_name": st.class_section.name if (st and st.class_section) else "",
                "house_name": st.house.name if (st and st.house) else "",
                "exeat_type": ex.exeat_type or "Day",
                "reason": ex.reason or "",
                "destination": ex.destination or "",
                "actual_departure": ex.actual_departure.strftime("%Y-%m-%d %H:%M") if ex.actual_departure else (ex.expected_departure.strftime("%Y-%m-%d %H:%M") if ex.expected_departure else ""),
                "actual_return": ex.actual_return.strftime("%Y-%m-%d %H:%M") if ex.actual_return else (ex.expected_return.strftime("%Y-%m-%d %H:%M") if ex.expected_return else ""),
                "status": ex.status or "Pending",
                "approver": ex.approved_by.full_name or ex.approved_by.username if ex.approved_by else "-",
                "gate_out": ex.gate_out_by.full_name or ex.gate_out_by.username if ex.gate_out_by else "-",
                "gate_in": ex.gate_in_by.full_name or ex.gate_in_by.username if ex.gate_in_by else "-"
            })

        return _render_exeat_dataset(rows_data, columns, f"{title}_{school_slug}_{timestamp}", file_format)

    # ── Preset 4 (Default): Active Out-of-Campus Security Manifest ──
    else:
        title = "Active_Out_Of_Campus_Gate_Manifest"
        columns = [
            ("Student Code", "student_code"),
            ("Full Name", "full_name"),
            ("Gender", "gender"),
            ("Class Section", "class_name"),
            ("Boarding House", "house_name"),
            ("Dormitory / Room", "dorm_name"),
            ("Exeat Type", "exeat_type"),
            ("Destination", "destination"),
            ("Departure Time", "departure_time"),
            ("Expected Return", "expected_return"),
            ("Status", "status"),
            ("Emergency Phone", "phone"),
            ("Approving Officer", "approver")
        ]

        query = build_filtered_exeat_query(db, school_id, filters)
        # Active out = Departed or Overdue
        query = query.filter(ExeatRecord.status.in_(["Departed", "Overdue"]))
        exeats = query.all()

        rows_data = []
        for ex in exeats:
            st = ex.student
            dep_time = ex.actual_departure.strftime("%Y-%m-%d %H:%M") if ex.actual_departure else (ex.expected_departure.strftime("%Y-%m-%d %H:%M") if ex.expected_departure else "")
            ret_time = ex.expected_return.strftime("%Y-%m-%d %H:%M") if ex.expected_return else ""

            rows_data.append({
                "student_code": st.student_code if st else "",
                "full_name": st.full_name if st else "",
                "gender": st.gender if st else "",
                "class_name": st.class_section.name if (st and st.class_section) else "",
                "house_name": st.house.name if (st and st.house) else "",
                "dorm_name": st.dormitory.name if (st and st.dormitory) else "",
                "exeat_type": ex.exeat_type or "Day",
                "destination": ex.destination or "",
                "departure_time": dep_time,
                "expected_return": ret_time,
                "status": ex.status or "Departed",
                "phone": ex.parent_contact or (st.phone if st else ""),
                "approver": ex.approved_by.full_name or ex.approved_by.username if ex.approved_by else "Staff"
            })

        return _render_exeat_dataset(rows_data, columns, f"{title}_{school_slug}_{timestamp}", file_format)


def _render_exeat_dataset(
    rows_data: List[Dict[str, Any]],
    columns: List[Tuple[str, str]],
    filename_base: str,
    file_format: str
) -> Tuple[bytes, str, str]:
    """Helper to render styled Excel or CSV for exeat and boarding rosters."""
    if file_format.lower() == "xlsx":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Exeat_Manifest"
        ws.views.sheetView[0].showGridLines = True

        header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        cell_font = Font(name="Segoe UI", size=10)
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")
        thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1")
        )
        zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

        # Header
        ws.row_dimensions[1].height = 26
        for col_idx, (col_label, col_key) in enumerate(columns, start=1):
            cell = ws.cell(row=1, column=col_idx, value=col_label)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border

        # Data rows
        center_keys = {"student_code", "gender", "form", "exeat_type", "departure_time", "actual_departure", "expected_return", "actual_return", "status", "hours_overdue", "phone"}

        for row_idx, r in enumerate(rows_data, start=2):
            ws.row_dimensions[row_idx].height = 20
            is_even = (row_idx % 2 == 0)

            for col_idx, (col_label, col_key) in enumerate(columns, start=1):
                val = r.get(col_key, "")
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = cell_font
                cell.border = thin_border
                if is_even:
                    cell.fill = zebra_fill

                if col_key in center_keys:
                    cell.alignment = center_align
                else:
                    cell.alignment = left_align

                # Highlight Overdue status in soft red
                if col_key == "status" and str(val).lower() == "overdue":
                    cell.font = Font(name="Segoe UI", size=10, bold=True, color="DC2626")

        # Auto-fit columns
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or "")
                if len(val_str) > max_len:
                    max_len = len(val_str)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue(), f"{filename_base}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    else:
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([c[0] for c in columns])

        for r in rows_data:
            row_vals = [sanitize_csv_cell(r.get(c[1], "")) for c in columns]
            writer.writerow(row_vals)

        csv_bytes = output.getvalue().encode("utf-8-sig")
        return csv_bytes, f"{filename_base}.csv", "text/csv; charset=utf-8"
