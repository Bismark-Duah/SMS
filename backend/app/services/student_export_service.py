"""
student_export_service.py - Enterprise Academic Student Export Wizard Engine.
Provides filtered, preset-driven exports for:
1. Academic Class Roster (Classes, Programs, Elective Subjects)
2. Boarding & House Directory (Houses, Dormitories, Residential Status)
3. CSSPS & WAEC Audit Roster (BECE Index, JHS Attended, Scores)
4. Guardian & Communications Directory (Guardian details, Phones, Addresses)
5. Campus Health & Medical Desk (Blood Group, Allergies, Medical Conditions)
6. Master Institutional Archive (Full dataset)

Supports both styled .xlsx (openpyxl) and universal .csv with strict school-level isolation.
100% Offline-First.
"""

import io
import csv
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from ..models import Student, ClassSection, Program, House, Dormitory, StudentHealth, School
from ..dependencies import get_user_assigned_scope


PRESET_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "academic": {
        "title": "Academic_Class_Roster",
        "description": "Class enrolment, programs, and subject electives for academic management.",
        "columns": [
            ("Student ID / Code", "student_code"),
            ("Full Name", "full_name"),
            ("Gender", "gender"),
            ("Form / Year", "form"),
            ("Class Section", "class_name"),
            ("Program / Track", "program_name"),
            ("Subject", "electives")
        ]
    },
    "boarding": {
        "title": "Boarding_House_Directory",
        "description": "Residential status, house allocations, dormitories, and emergency contacts.",
        "columns": [
            ("Student Code", "student_code"),
            ("Full Name", "full_name"),
            ("Gender", "gender"),
            ("Class Section", "class_name"),
            ("Residential Status", "residential_status"),
            ("Boarding House", "house_name"),
            ("Dormitory / Room", "dormitory_name"),
            ("Emergency Phone", "phone")
        ]
    },
    "cssps": {
        "title": "CSSPS_WAEC_Audit_Roster",
        "description": "BECE index numbers, placement scores, and prior school history for exams and audits.",
        "columns": [
            ("Student Code", "student_code"),
            ("BECE Index No", "bece_index_number"),
            ("Full Name", "full_name"),
            ("Gender", "gender"),
            ("Date of Birth", "date_of_birth"),
            ("JHS Attended", "jhs_attended"),
            ("BECE Raw Score", "bece_raw_score"),
            ("BECE Aggregate", "bece_aggregate"),
            ("Enrolled Program", "program_name"),
            ("Residential Status", "residential_status")
        ]
    },
    "guardian": {
        "title": "Guardian_Communications_Roster",
        "description": "Guardian names, contact numbers, and physical residential addresses for notices.",
        "columns": [
            ("Student Code", "student_code"),
            ("Full Name", "full_name"),
            ("Gender", "gender"),
            ("Class Section", "class_name"),
            ("Guardian Name", "guardian_name"),
            ("Contact Phone", "phone"),
            ("Residential Address", "address")
        ]
    },
    "health": {
        "title": "Campus_Health_Infirmary_Profile",
        "description": "Blood groups, documented allergies, chronic conditions, and medical contacts.",
        "columns": [
            ("Student Code", "student_code"),
            ("Full Name", "full_name"),
            ("Gender", "gender"),
            ("Class Section", "class_name"),
            ("Boarding House", "house_name"),
            ("Blood Group", "blood_group"),
            ("Known Allergies", "allergies"),
            ("Chronic Conditions", "chronic_conditions"),
            ("Emergency Contact", "emergency_contact")
        ]
    },
    "master": {
        "title": "Institutional_Master_Archive",
        "description": "Complete, comprehensive institutional ledger containing all academic, pastoral, and bio records.",
        "columns": [
            ("System ID", "id"),
            ("Student Code", "student_code"),
            ("BECE Index No", "bece_index_number"),
            ("Full Name", "full_name"),
            ("Gender", "gender"),
            ("Date of Birth", "date_of_birth"),
            ("Form / Year", "form"),
            ("Class Section", "class_name"),
            ("Program / Track", "program_name"),
            ("Subject", "electives"),
            ("Residential Status", "residential_status"),
            ("Boarding House", "house_name"),
            ("Dormitory / Room", "dormitory_name"),
            ("Guardian Name", "guardian_name"),
            ("Contact Phone", "phone"),
            ("Residential Address", "address"),
            ("JHS Attended", "jhs_attended"),
            ("BECE Raw Score", "bece_raw_score"),
            ("BECE Aggregate", "bece_aggregate"),
            ("Blood Group", "blood_group"),
            ("Known Allergies", "allergies"),
            ("Chronic Conditions", "chronic_conditions"),
            ("Emergency Contact", "emergency_contact")
        ]
    }
}


def build_filtered_student_query(
    db: Session,
    school_id: Optional[int],
    current_user: Any,
    filters: Optional[Dict[str, Any]] = None
):
    """
    Builds an isolated, scoped SQLAlchemy query for students based on active school,
    user permissions, and wizard filter criteria.
    """
    filters = filters or {}
    query = db.query(Student).options(
        joinedload(Student.class_section),
        joinedload(Student.program),
        joinedload(Student.house),
        joinedload(Student.dormitory),
        joinedload(Student.health_profile),
        joinedload(Student.school)
    )

    # Multi-tenancy isolation
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)

    # Active status filter (default: active only)
    if not filters.get("include_inactive", False):
        query = query.filter(Student.is_active == True)

    # Role-based scoping for non-administrators
    scope = get_user_assigned_scope(current_user, db)
    if not scope["is_admin"]:
        role_names = [r.name.lower() for r in current_user.roles] if hasattr(current_user, "roles") else []
        if "parent" in role_names:
            query = query.filter(Student.parent_id == current_user.id)
        else:
            role_filters = []
            if scope["class_ids"]:
                role_filters.append(Student.class_section_id.in_(scope["class_ids"]))
            if scope["house_ids"]:
                role_filters.append(Student.house_id.in_(scope["house_ids"]))
            if role_filters:
                query = query.filter(or_(*role_filters))
            else:
                return query.filter(Student.id == -1)

    # ── Wizard Scoping Filters ──
    # 1. Form / Level
    form_val = filters.get("form")
    if form_val is not None and str(form_val).strip() != "":
        try:
            query = query.filter(Student.form == int(form_val))
        except (ValueError, TypeError):
            pass

    # 2. Class Section
    class_id = filters.get("class_id")
    if class_id is not None and str(class_id).strip() != "":
        try:
            query = query.filter(Student.class_section_id == int(class_id))
        except (ValueError, TypeError):
            pass

    # 3. Program / Track
    program_id = filters.get("program_id")
    if program_id is not None and str(program_id).strip() != "":
        try:
            query = query.filter(Student.program_id == int(program_id))
        except (ValueError, TypeError):
            pass

    # 4. Residential Status (Boarding / Day)
    res_status = filters.get("residential_status")
    if res_status and str(res_status).strip().lower() not in ("all", ""):
        query = query.filter(Student.residential_status.ilike(f"%{str(res_status).strip()}%"))

    # 5. House
    house_id = filters.get("house_id")
    if house_id is not None and str(house_id).strip() != "":
        try:
            query = query.filter(Student.house_id == int(house_id))
        except (ValueError, TypeError):
            pass

    # 6. Gender
    gender_val = filters.get("gender")
    if gender_val and str(gender_val).strip().lower() not in ("all", ""):
        g = str(gender_val).strip().lower()
        if g in ("m", "male"):
            query = query.filter(Student.gender.ilike("male"))
        elif g in ("f", "female"):
            query = query.filter(Student.gender.ilike("female"))

    # Clean academic ordering
    query = query.outerjoin(ClassSection, Student.class_section_id == ClassSection.id)\
                 .order_by(ClassSection.name.asc(), Student.full_name.asc())

    return query


def extract_student_row_dict(s: Student) -> Dict[str, Any]:
    """Flattens a Student entity and related associations into a clean dictionary."""
    hp = s.health_profile
    cls_name = s.class_section.name if s.class_section else ""
    prog_name = s.program.name if s.program else ""
    house_name = s.house.name if s.house else ""
    dorm_name = s.dormitory.name if s.dormitory else ""

    # Subject / Electives
    electives_str = s.elective_combination or ""
    if not electives_str and hasattr(s, "elective_combination_id") and s.elective_combination_id:
        electives_str = f"Option #{s.elective_combination_id}"

    return {
        "id": s.id,
        "student_code": s.student_code or "",
        "bece_index_number": s.bece_index_number or "",
        "full_name": s.full_name or "",
        "gender": s.gender or "",
        "date_of_birth": str(s.date_of_birth)[:10] if s.date_of_birth else "",
        "form": s.form if s.form is not None else "",
        "class_name": cls_name,
        "program_name": prog_name,
        "electives": electives_str,
        "residential_status": s.residential_status or "",
        "house_name": house_name,
        "dormitory_name": dorm_name,
        "guardian_name": s.guardian_name or "",
        "phone": s.phone or "",
        "address": s.address or "",
        "jhs_attended": s.jhs_attended or "",
        "bece_raw_score": s.bece_raw_score if s.bece_raw_score is not None else "",
        "bece_aggregate": s.bece_aggregate if s.bece_aggregate is not None else "",
        "blood_group": hp.blood_group if (hp and hp.blood_group) else "",
        "allergies": hp.allergies if (hp and hp.allergies) else "",
        "chronic_conditions": hp.chronic_conditions if (hp and hp.chronic_conditions) else "",
        "emergency_contact": hp.emergency_contact if (hp and hp.emergency_contact) else ""
    }


def generate_student_export_dataset(
    db: Session,
    school_id: Optional[int],
    current_user: Any,
    preset_key: str = "academic",
    file_format: str = "xlsx",
    filters: Optional[Dict[str, Any]] = None
) -> Tuple[bytes, str, str]:
    """
    Executes filtered query, builds preset-driven rows, and serializes
    into either formatted Excel (.xlsx) or universal CSV (.csv).
    Returns (file_bytes, filename, mime_type).
    """
    preset = PRESET_DEFINITIONS.get(preset_key.lower()) or PRESET_DEFINITIONS["academic"]
    columns = preset["columns"]

    query = build_filtered_student_query(db, school_id, current_user, filters)
    students = query.all()

    school = db.query(School).filter(School.id == school_id).first() if school_id else None
    school_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", school.name if school else "Institutional")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    base_filename = f"{preset['title']}_{school_slug}_{timestamp}"

    # ── 1. Excel (.xlsx) Generation ──
    if file_format.lower() == "xlsx":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Students"
        ws.views.sheetView[0].showGridLines = True

        header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        cell_font = Font(name="Segoe UI", size=10)
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")
        thin_border = Border(
            left=Side(style="thin", color="E2E8F0"),
            right=Side(style="thin", color="E2E8F0"),
            top=Side(style="thin", color="E2E8F0"),
            bottom=Side(style="thin", color="E2E8F0")
        )

        # Header Row
        ws.row_dimensions[1].height = 26
        for col_idx, (header_label, field_key) in enumerate(columns, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header_label)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border

        # Data Rows
        zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        for row_idx, s in enumerate(students, start=2):
            ws.row_dimensions[row_idx].height = 20
            row_dict = extract_student_row_dict(s)
            is_even = (row_idx % 2 == 0)

            for col_idx, (header_label, field_key) in enumerate(columns, start=1):
                val = row_dict.get(field_key, "")
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = cell_font
                cell.border = thin_border
                if is_even:
                    cell.fill = zebra_fill

                # Alignment rules
                if field_key in ("gender", "form", "date_of_birth", "blood_group", "bece_aggregate", "bece_raw_score"):
                    cell.alignment = center_align
                else:
                    cell.alignment = left_align

        # Auto-fit Column Widths
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or "")
                if len(val_str) > max_len:
                    max_len = len(val_str)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

        # Enable AutoFilter on Headers
        ws.auto_filter.ref = ws.dimensions

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"{base_filename}.xlsx"
        mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return output.getvalue(), filename, mime_type

    # ── 2. CSV (.csv) Generation ──
    else:
        out_stream = io.StringIO()
        writer = csv.writer(out_stream, quoting=csv.QUOTE_MINIMAL)

        # Header Row
        writer.writerow([col[0] for col in columns])

        # Data Rows
        for s in students:
            row_dict = extract_student_row_dict(s)
            writer.writerow([row_dict.get(col[1], "") for col in columns])

        csv_bytes = out_stream.getvalue().encode("utf-8-sig")
        filename = f"{base_filename}.csv"
        mime_type = "text/csv; charset=utf-8"
        return csv_bytes, filename, mime_type
