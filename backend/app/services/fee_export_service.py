"""
fee_export_service.py - Enterprise Financial & Bursar Desk Export Engine.
Provides filtered, preset-driven exports for:
1. Fee Defaulters & Arrears Recovery Roster
2. Daily & Date-Range Collections / Audit Ledger
3. Class Fee Reconciliation & Collection Rate Summary

Supports both styled .xlsx (openpyxl) and universal .csv with strict school-level isolation.
100% Offline-First.
"""

import io
import csv
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_, desc

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from ..models import Fee, Payment, Student, ClassSection, School, User
from .import_export_service import sanitize_csv_cell


def build_filtered_fee_query(
    db: Session,
    school_id: Optional[int],
    filters: Optional[Dict[str, Any]] = None
):
    """
    Builds a tenant-isolated query for Fee records.
    """
    filters = filters or {}
    query = db.query(Fee).join(Student, Fee.student_id == Student.id).options(
        joinedload(Fee.student).joinedload(Student.class_section),
        joinedload(Fee.student).joinedload(Student.house),
        joinedload(Fee.payments)
    )

    if school_id is not None:
        query = query.filter(Student.school_id == school_id)

    # 1. Class filter
    class_id = filters.get("class_id")
    if class_id is not None and str(class_id).strip() != "":
        try:
            query = query.filter(Student.class_section_id == int(class_id))
        except (ValueError, TypeError):
            pass

    # 2. Form filter
    form_val = filters.get("form")
    if form_val is not None and str(form_val).strip() != "":
        try:
            query = query.filter(Student.form == int(form_val))
        except (ValueError, TypeError):
            pass

    # 3. Fee Type
    fee_type = filters.get("fee_type")
    if fee_type and str(fee_type).strip().lower() not in ("all", ""):
        query = query.filter(Fee.fee_type.ilike(f"%{str(fee_type).strip()}%"))

    # 4. Academic Year & Term
    academic_year = filters.get("academic_year")
    if academic_year and str(academic_year).strip() != "":
        query = query.filter(Fee.academic_year == str(academic_year).strip())

    term = filters.get("term")
    if term and str(term).strip() != "":
        query = query.filter(Fee.term == str(term).strip())

    # 5. Status / Defaulter Filter
    status_filter = filters.get("status")
    if status_filter:
        sf = str(status_filter).strip().lower()
        if sf in ("owing", "defaulters", "unpaid"):
            query = query.filter(Fee.amount > Fee.amount_paid)
        elif sf == "paid":
            query = query.filter(Fee.amount_paid >= Fee.amount)
        elif sf == "partial":
            query = query.filter(and_(Fee.amount_paid > 0, Fee.amount_paid < Fee.amount))

    return query


def build_filtered_payment_query(
    db: Session,
    school_id: Optional[int],
    filters: Optional[Dict[str, Any]] = None
):
    """
    Builds a tenant-isolated query for Payment records.
    """
    filters = filters or {}
    query = db.query(Payment).join(Fee, Payment.fee_id == Fee.id)\
                             .join(Student, Fee.student_id == Student.id)\
                             .options(
                                 joinedload(Payment.fee).joinedload(Fee.student).joinedload(Student.class_section),
                                 joinedload(Payment.recorder)
                             )

    if school_id is not None:
        query = query.filter(Student.school_id == school_id)

    # 1. Class filter
    class_id = filters.get("class_id")
    if class_id is not None and str(class_id).strip() != "":
        try:
            query = query.filter(Student.class_section_id == int(class_id))
        except (ValueError, TypeError):
            pass

    # 2. Payment Method
    method = filters.get("payment_method")
    if method and str(method).strip().lower() not in ("all", ""):
        query = query.filter(Payment.payment_method.ilike(f"%{str(method).strip()}%"))

    # 3. Date Range (Start Date & End Date)
    start_date = filters.get("start_date")
    if start_date and str(start_date).strip() != "":
        try:
            dt_start = datetime.strptime(str(start_date).strip()[:10], "%Y-%m-%d")
            query = query.filter(Payment.payment_date >= dt_start)
        except ValueError:
            pass

    end_date = filters.get("end_date")
    if end_date and str(end_date).strip() != "":
        try:
            dt_end = datetime.strptime(str(end_date).strip()[:10] + " 23:59:59", "%Y-%m-%d %H:%M:%S")
            query = query.filter(Payment.payment_date <= dt_end)
        except ValueError:
            pass

    query = query.order_by(desc(Payment.payment_date), desc(Payment.id))
    return query


def generate_fee_export_dataset(
    db: Session,
    school_id: Optional[int],
    preset_key: str = "defaulters",
    file_format: str = "xlsx",
    filters: Optional[Dict[str, Any]] = None
) -> Tuple[bytes, str, str]:
    """
    Generates preset-driven financial exports:
    - defaulters
    - collections
    - reconciliation
    """
    filters = filters or {}
    school = db.query(School).filter(School.id == school_id).first() if school_id else None
    school_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", school.name if school else "Institutional")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    # ── Presets Definition & Execution ──
    if preset_key == "collections":
        title = "Fee_Collections_Audit_Ledger"
        columns = [
            ("Receipt No", "receipt_number"),
            ("Payment Date", "payment_date"),
            ("Student Code", "student_code"),
            ("Student Full Name", "full_name"),
            ("Class Section", "class_name"),
            ("Fee Category", "fee_type"),
            ("Amount Paid (GHS)", "amount_paid"),
            ("Payment Mode", "payment_method"),
            ("Reference / Trx No", "reference_no"),
            ("Received By / Cashier", "recorder_name"),
            ("Notes", "notes")
        ]

        query = build_filtered_payment_query(db, school_id, filters)
        payments = query.all()

        rows_data = []
        for p in payments:
            st = p.fee.student if (p.fee and p.fee.student) else None
            cls_name = st.class_section.name if (st and st.class_section) else ""
            rows_data.append({
                "receipt_number": p.receipt_number or f"REC-{p.id}",
                "payment_date": p.payment_date.strftime("%Y-%m-%d %H:%M") if p.payment_date else "",
                "student_code": st.student_code if st else "",
                "full_name": st.full_name if st else "",
                "class_name": cls_name,
                "fee_type": p.fee.fee_type if p.fee else "",
                "amount_paid": round(p.amount_paid or 0.0, 2),
                "payment_method": p.payment_method or "Cash",
                "reference_no": p.reference_no or "",
                "recorder_name": p.recorder.full_name or p.recorder.username if p.recorder else "System / Direct",
                "notes": p.notes or ""
            })

    elif preset_key == "reconciliation":
        title = "Class_Fee_Reconciliation_Summary"
        columns = [
            ("Class Section", "class_name"),
            ("Form / Year", "form"),
            ("Enrolled Students", "enrolled_count"),
            ("Total Expected (GHS)", "total_billed"),
            ("Total Collected (GHS)", "total_paid"),
            ("Outstanding Arrears (GHS)", "total_arrears"),
            ("Collection Rate (%)", "collection_rate"),
            ("Defaulters Count", "defaulters_count")
        ]

        # Aggregate by class section
        class_query = db.query(ClassSection)
        if school_id is not None:
            class_query = class_query.filter(ClassSection.school_id == school_id)
        classes = class_query.order_by(ClassSection.name.asc()).all()

        rows_data = []
        for c in classes:
            # Query active students in class
            st_query = db.query(Student).filter(Student.class_section_id == c.id, Student.is_active == True)
            if school_id is not None:
                st_query = st_query.filter(Student.school_id == school_id)
            cls_students = st_query.all()
            enrolled = len(cls_students)
            if enrolled == 0:
                continue

            st_ids = [s.id for s in cls_students]
            fees = db.query(Fee).filter(Fee.student_id.in_(st_ids)).all()
            total_billed = sum(f.amount for f in fees)
            total_paid = sum(f.amount_paid for f in fees)
            total_arrears = max(0.0, total_billed - total_paid)
            rate = round((total_paid / total_billed * 100.0), 1) if total_billed > 0 else 100.0

            # Count distinct students with arrears > 0
            student_balances = {}
            for f in fees:
                student_balances[f.student_id] = student_balances.get(f.student_id, 0.0) + (f.amount - (f.amount_paid or 0.0))
            defaulters_count = sum(1 for bal in student_balances.values() if bal > 0.5)

            form_val = cls_students[0].form if (cls_students and cls_students[0].form) else ""

            rows_data.append({
                "class_name": c.name,
                "form": form_val,
                "enrolled_count": enrolled,
                "total_billed": round(total_billed, 2),
                "total_paid": round(total_paid, 2),
                "total_arrears": round(total_arrears, 2),
                "collection_rate": f"{rate}%",
                "defaulters_count": defaulters_count
            })

    else:
        # Default: Fee Defaulters & Arrears Recovery Roster
        title = "Fee_Defaulters_Arrears_Recovery"
        columns = [
            ("Student Code", "student_code"),
            ("Full Name", "full_name"),
            ("Gender", "gender"),
            ("Class Section", "class_name"),
            ("Form / Year", "form"),
            ("Fee Category", "fee_type"),
            ("Total Billed (GHS)", "amount"),
            ("Total Paid (GHS)", "amount_paid"),
            ("Outstanding Arrears (GHS)", "arrears"),
            ("Due Date", "due_date"),
            ("Status", "status"),
            ("Guardian Name", "guardian_name"),
            ("Primary Phone", "phone"),
            ("Residential Status", "residential_status")
        ]

        query = build_filtered_fee_query(db, school_id, filters)
        # Ensure only owing fees if defaulters preset
        query = query.filter(Fee.amount > Fee.amount_paid)
        fees = query.order_by(Student.full_name.asc()).all()

        rows_data = []
        for f in fees:
            st = f.student
            arrears = max(0.0, (f.amount or 0.0) - (f.amount_paid or 0.0))
            cls_name = st.class_section.name if (st and st.class_section) else ""
            rows_data.append({
                "student_code": st.student_code if st else "",
                "full_name": st.full_name if st else "",
                "gender": st.gender if st else "",
                "class_name": cls_name,
                "form": st.form if (st and st.form is not None) else "",
                "fee_type": f.fee_type or "",
                "amount": round(f.amount or 0.0, 2),
                "amount_paid": round(f.amount_paid or 0.0, 2),
                "arrears": round(arrears, 2),
                "due_date": f.due_date.strftime("%Y-%m-%d") if f.due_date else "",
                "status": f.status or "Pending",
                "guardian_name": st.guardian_name if st else "",
                "phone": st.phone if st else "",
                "residential_status": st.residential_status if st else ""
            })

    filename_base = f"{title}_{school_slug}_{timestamp}"

    # ── 1. XLSX Generation ──
    if file_format.lower() == "xlsx":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Financial_Report"
        ws.views.sheetView[0].showGridLines = True

        header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        cell_font = Font(name="Segoe UI", size=10)
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")
        right_align = Alignment(horizontal="right", vertical="center")
        thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1")
        )
        zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

        # Header Row
        ws.row_dimensions[1].height = 26
        for col_idx, (col_label, col_key) in enumerate(columns, start=1):
            cell = ws.cell(row=1, column=col_idx, value=col_label)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border

        # Data Rows
        numeric_keys = {"amount", "amount_paid", "arrears", "total_billed", "total_paid", "total_arrears", "enrolled_count", "defaulters_count"}
        center_keys = {"student_code", "receipt_number", "gender", "form", "due_date", "payment_date", "payment_method", "status", "collection_rate"}

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

                if col_key in numeric_keys and isinstance(val, (int, float)):
                    cell.alignment = right_align
                    if col_key not in ("enrolled_count", "defaulters_count"):
                        cell.number_format = "#,##0.00"
                elif col_key in center_keys:
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
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue(), f"{filename_base}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # ── 2. CSV Generation ──
    else:
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([c[0] for c in columns])

        for r in rows_data:
            row_vals = [sanitize_csv_cell(r.get(c[1], "")) for c in columns]
            writer.writerow(row_vals)

        csv_bytes = output.getvalue().encode("utf-8-sig")
        return csv_bytes, f"{filename_base}.csv", "text/csv; charset=utf-8"
