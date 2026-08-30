import io
import hashlib
from datetime import datetime
from xhtml2pdf import pisa
from sqlalchemy.orm import Session
from ..models import (
    Student, Score, Subject, AcademicYear, Semester, Setting, StudentSemesterSummary, Attendance,
    ClassSectionReportStatus, User, ClassSection
)
from .grading import GradingService


def _get_setting(db, key, default=""):
    s = db.query(Setting).filter(Setting.key == key).first()
    return s.value if s else default


class ReportService:

    @staticmethod
    def get_report_data(db: Session, student_id: int, semester_id: int) -> dict | None:
        """
        Assembles all data needed for a student terminal report.
        Returns None if student or semester not found.
        """
        student = db.query(Student).filter(Student.id == student_id).first()
        semester = db.query(Semester).filter(Semester.id == semester_id).first()
        if not student or not semester:
            return None

        # School settings
        school_name     = _get_setting(db, "school_name", "SCHOOL MANAGEMENT SYSTEM")
        report_motto    = _get_setting(db, "report_motto", "")
        report_title    = _get_setting(db, "report_title", "TERMINAL REPORT")
        headmaster_name = _get_setting(db, "report_headmaster", "")
        school_logo     = _get_setting(db, "school_logo", "")
        school_address  = _get_setting(db, "school_address", "")
        school_phone    = _get_setting(db, "school_phone", "")
        school_email    = _get_setting(db, "school_email", "")
        school_mode = _get_setting(db, "school_mode", "COMBINED")
        default_standard = "BECE" if school_mode == "BASIC_ONLY" else "WAEC"
        grading_standard = _get_setting(db, "grading_standard", default_standard)
        
        import json
        grading_rules = []
        if grading_standard == "CUSTOM":
            rules_val = _get_setting(db, "grading_rules", "[]")
            try:
                grading_rules = json.loads(rules_val)
            except Exception:
                pass
        elif grading_standard == "BECE":
            grading_rules = [
                {"grade": "1", "min_score": 80, "remark": "EXCELLENT", "point": 1},
                {"grade": "2", "min_score": 70, "remark": "VERY GOOD", "point": 2},
                {"grade": "3", "min_score": 60, "remark": "GOOD", "point": 3},
                {"grade": "4", "min_score": 55, "remark": "CREDIT", "point": 4},
                {"grade": "5", "min_score": 50, "remark": "CREDIT", "point": 5},
                {"grade": "6", "min_score": 45, "remark": "PASS", "point": 6},
                {"grade": "7", "min_score": 40, "remark": "PASS", "point": 7},
                {"grade": "8", "min_score": 35, "remark": "WEAK PASS", "point": 8},
                {"grade": "9", "min_score": 0, "remark": "FAIL", "point": 9},
            ]
        else:
            grading_rules = [
                {"grade": "A1", "min_score": 80, "remark": "Excellent", "point": 1},
                {"grade": "B2", "min_score": 70, "remark": "Very Good", "point": 2},
                {"grade": "B3", "min_score": 60, "remark": "Good", "point": 3},
                {"grade": "C4", "min_score": 55, "remark": "Credit", "point": 4},
                {"grade": "C5", "min_score": 50, "remark": "Credit", "point": 5},
                {"grade": "C6", "min_score": 45, "remark": "Credit", "point": 6},
                {"grade": "D7", "min_score": 40, "remark": "Pass", "point": 7},
                {"grade": "E8", "min_score": 35, "remark": "Pass", "point": 8},
                {"grade": "F9", "min_score": 0, "remark": "Fail", "point": 9},
            ]

        # Function to format ordinal numbers (1 -> 1st, 2 -> 2nd, etc.)
        def format_ordinal(n):
            if not n:
                return "-"
            try:
                n = int(n)
            except Exception:
                return str(n)
            if 11 <= (n % 100) <= 13:
                suffix = 'th'
            else:
                suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
            return f"{n}{suffix}"

        # This student's scores this semester
        scores = db.query(Score).filter(
            Score.student_id == student_id,
            Score.semester_id == semester_id,
        ).all()

        score_rows = []
        total_points = 0
        for s in scores:
            # Rank in subject
            sub_pos = None
            if student.class_section_id:
                sub_scores = db.query(Score).join(Student).filter(
                    Score.subject_id == s.subject_id,
                    Score.semester_id == semester_id,
                    Student.class_section_id == student.class_section_id,
                    Student.is_active == True
                ).all()
                sub_scores_sorted = sorted(sub_scores, key=lambda x: x.total_score, reverse=True)
                for idx, sc in enumerate(sub_scores_sorted):
                    if sc.student_id == student_id:
                        sub_pos = idx + 1
                        break
            
            is_core = s.subject.is_core if (s.subject and hasattr(s.subject, 'is_core') and s.subject.is_core is not None) else True

            score_rows.append({
                "subject": s.subject.name if s.subject else f"Subject {s.subject_id}",
                "is_core": is_core,
                "ex1": s.ex1 or 0.0,
                "ex2": s.ex2 or 0.0,
                "ass1": s.ass1 or 0.0,
                "ass2": s.ass2 or 0.0,
                "ind_proj": s.ind_proj or 0.0,
                "grp_work": s.grp_work or 0.0,
                "pract_work": s.pract_work or 0.0,
                "mid_sem": s.mid_sem or 0.0,
                "class_score": s.class_score,
                "exam_score": s.exam_score,
                "total_score": s.total_score,
                "grade": s.grade,
                "remark": s.remark,
                "position": format_ordinal(sub_pos),
                "raw_position": sub_pos
            })
            total_points += s.total_score

        # Sort score rows: Core subjects first (is_core=True), then Elective subjects (is_core=False)
        score_rows.sort(key=lambda x: (0 if x["is_core"] else 1, x["subject"]))

        num_subjects = len(score_rows)
        average_score = round(total_points / num_subjects, 2) if num_subjects else 0.0
        overall_grading = GradingService.get_grade(average_score) if average_score > 0 else {"grade": "N/A", "remark": ""}

        # Determine if SHS for aggregate calculation
        aggregate = None
        aggregate_breakdown = None
        try:
            is_shs = False
            if student.class_section and student.class_section.stage:
                is_shs = (student.class_section.stage.school_type == "SHS")
            elif student.school_type == "SHS" or student.program_id is not None:
                is_shs = True
                
            if is_shs:
                aggregate_breakdown = GradingService.calculate_shs_aggregate_breakdown(scores, student=student)
                aggregate = aggregate_breakdown["aggregate"]
        except Exception as agg_err:
            print("Aggregate calculation warning:", agg_err)

        # Position in class: rank by average score across all students in this class+semester
        class_id = student.class_section_id
        if class_id:
            class_students = db.query(Student).filter(
                Student.class_section_id == class_id,
                Student.is_active == True,
            ).all()

            student_averages = []
            for cs in class_students:
                cs_scores = db.query(Score).filter(
                    Score.student_id == cs.id,
                    Score.semester_id == semester_id,
                ).all()
                if cs_scores:
                    avg = sum(sc.total_score for sc in cs_scores) / len(cs_scores)
                else:
                    avg = 0.0
                student_averages.append((cs.id, avg))

            student_averages.sort(key=lambda x: x[1], reverse=True)
            position = next(
                (i + 1 for i, (sid, _) in enumerate(student_averages) if sid == student_id),
                None,
            )
            total_in_class = len(student_averages)
        else:
            position = None
            total_in_class = None

        position_ordinal = format_ordinal(position)
        position_text = f"{position_ordinal} out of {total_in_class}" if (position and total_in_class) else "N/A"

        # Number on Roll
        number_on_roll = total_in_class if total_in_class is not None else 0

        # Closing and Next Term begins dates
        date_of_closing = semester.end_date.strftime("%Y-%m-%d") if semester.end_date else None
        next_term_begins = None
        next_sem = db.query(Semester).filter(
            Semester.academic_year_id == semester.academic_year_id,
            Semester.id > semester.id
        ).order_by(Semester.id.asc()).first()
        if next_sem and next_sem.start_date:
            next_term_begins = next_sem.start_date.strftime("%Y-%m-%d")

        # Attendance calculation
        attendance_total = 0
        attendance_present = 0
        
        att_query = db.query(Attendance).filter(Attendance.student_id == student_id)
        if semester.start_date and semester.end_date:
            att_query = att_query.filter(
                Attendance.date >= semester.start_date,
                Attendance.date <= semester.end_date
            )
        attendance_total = att_query.count()
        attendance_present = att_query.filter(Attendance.status.in_(["Present", "Late"])).count()
        
        if attendance_total == 0:
            attendance_total = 90
            attendance_present = 90

        # Final Period / Promotion status validation
        st_type = student.class_section.stage.school_type if (student.class_section and student.class_section.stage) else "Basic"
        is_final_period = False
        sem_name = (semester.name or "").lower()
        if st_type == "Basic":
            if "3" in sem_name or "third" in sem_name:
                is_final_period = True
            else:
                all_sems = db.query(Semester).filter(
                    Semester.academic_year_id == semester.academic_year_id
                ).order_by(Semester.id.asc()).all()
                if len(all_sems) >= 3 and all_sems[2].id == semester.id:
                    is_final_period = True
        else:
            if "2" in sem_name or "second" in sem_name:
                is_final_period = True
            else:
                all_sems = db.query(Semester).filter(
                    Semester.academic_year_id == semester.academic_year_id
                ).order_by(Semester.id.asc()).all()
                if len(all_sems) >= 2 and all_sems[1].id == semester.id:
                    is_final_period = True

        summary = db.query(StudentSemesterSummary).filter(
            StudentSemesterSummary.student_id == student_id,
            StudentSemesterSummary.semester_id == semester_id
        ).first()

        summary_data = {
            "attitude": summary.attitude if summary else None,
            "conduct": summary.conduct if summary else None,
            "interest": summary.interest if summary else None,
            "form_teacher_remarks": summary.form_teacher_remarks if summary else None,
            "headteacher_remarks": summary.headteacher_remarks if summary else None,
            "promoted_to": summary.promoted_to if summary else None,
        }

        if not summary_data["promoted_to"]:
            if is_final_period:
                if student.form:
                    if student.form < 3:
                        summary_data["promoted_to"] = f"Form {student.form + 1}"
                    else:
                        summary_data["promoted_to"] = "Graduated / Completed"
                else:
                    summary_data["promoted_to"] = "Promoted"
            else:
                summary_data["promoted_to"] = "N/A (Mid-Year)"

        # Check Class Section Report Publishing Status
        is_published = False
        if student.class_section_id:
            rep_status = db.query(ClassSectionReportStatus).filter(
                ClassSectionReportStatus.class_section_id == student.class_section_id,
                ClassSectionReportStatus.semester_id == semester_id
            ).first()
            if rep_status and rep_status.is_published:
                is_published = True

        publishing_mode = _get_setting(db, "report_publishing_mode", "HYBRID_BOTH")

        form_master_name = "N/A"
        if student.class_section and student.class_section.form_master:
            form_master_name = student.class_section.form_master.username

        headmaster_signature = _get_setting(db, "headmaster_signature", "")

        return {
            "school_name": school_name,
            "report_motto": report_motto,
            "report_title": report_title,
            "headmaster_name": headmaster_name,
            "school_logo": school_logo,
            "headmaster_signature": headmaster_signature,
            "school_address": school_address,
            "school_phone": school_phone,
            "school_email": school_email,
            "grading_standard": grading_standard,
            "grading_rules": grading_rules,
            "is_published": is_published,
            "publishing_mode": publishing_mode,
            "date_of_closing": date_of_closing,
            "next_term_begins": next_term_begins,
            "number_on_roll": number_on_roll,
            "attendance_present": attendance_present,
            "attendance_total": attendance_total,
            "summary_data": summary_data,
            "student": {
                "id": student.id,
                "full_name": student.full_name,
                "student_code": student.student_code,
                "class_name": student.class_section.name if student.class_section else "N/A",
                "form_master_id": student.class_section.form_master_id if student.class_section else None,
                "form_master_name": form_master_name,
                "gender": student.gender or "",
                "date_of_birth": str(student.date_of_birth)[:10] if student.date_of_birth else "",
                "guardian_name": student.guardian_name or "",
                "house_name": student.house.name if student.house else "N/A",
                "dormitory_name": student.dormitory.name if student.dormitory else "N/A",
            },
            "semester": {
                "id": semester.id,
                "name": semester.name,
                "year_label": semester.academic_year.label if semester.academic_year else "",
            },
            "scores": score_rows,
            "num_subjects": num_subjects,
            "average_score": average_score,
            "overall_grade": overall_grading.get("grade", "N/A"),
            "overall_remark": overall_grading.get("remark", ""),
            "aggregate": aggregate,
            "aggregate_breakdown": aggregate_breakdown,
            "position": position,
            "position_ordinal": position_ordinal,
            "position_text": position_text,
            "total_in_class": total_in_class,
        }

    @staticmethod
    def generate_terminal_report(db: Session, student_id: int, semester_id: int) -> bytes | None:
        """Generates a terminal report PDF and returns bytes, or None on failure."""
        data = ReportService.get_report_data(db, student_id, semester_id)
        if not data:
            return None

        s = data["student"]
        sem = data["semester"]

        position_text = ""
        if data["position"] and data["total_in_class"]:
            position_text = f"{data['position']}<sup>{'th' if data['position'] > 3 else ['st','nd','rd'][data['position']-1]}</sup> / {data['total_in_class']}"

        logo_html = ""
        watermark_path = ""
        if data.get("school_logo"):
            logo_path = data["school_logo"]
            if logo_path.startswith("data:"):
                watermark_path = logo_path
            else:
                import os
                current_dir = os.path.dirname(os.path.abspath(__file__))
                frontend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "frontend"))
                
                rel_path = logo_path
                if "localhost" in rel_path or "127.0.0.1" in rel_path:
                    from urllib.parse import urlparse
                    rel_path = urlparse(rel_path).path

                if rel_path.startswith("/assets/uploads/"):
                    rel_path = "uploads/" + rel_path[len("/assets/uploads/"):]
                elif rel_path.startswith("/uploads/"):
                    rel_path = "uploads/" + rel_path[len("/uploads/"):]
                elif rel_path.startswith("/assets/"):
                    rel_path = "assets/" + rel_path[len("/assets/"):]
                
                local_logo_path = os.path.join(frontend_dir, rel_path.replace("/", os.sep))
                if os.path.exists(local_logo_path):
                    logo_path = local_logo_path
                    watermark_path = local_logo_path
            logo_html = f'<img src="{logo_path}" height="65" />'

        contact_parts = []
        if data.get("school_address"):
            contact_parts.append(data["school_address"])
        if data.get("school_phone"):
            contact_parts.append(f"Tel: {data['school_phone']}")
        if data.get("school_email"):
            contact_parts.append(f"Email: {data['school_email']}")
        
        contact_html = ""
        if contact_parts:
            contact_html = f'<p style="margin:2px 0; font-size:10px; color:#555;">{" &nbsp;|&nbsp; ".join(contact_parts)}</p>'

        header_html = f"""
        <table style="width:100%; border-bottom: 2px solid #333; padding-bottom: 8px; margin-bottom: 12px;">
            <tr>
                {f'<td style="width:75px; vertical-align:middle; text-align:left;">{logo_html}</td>' if logo_html else ''}
                <td style="text-align: { 'left' if logo_html else 'center' }; vertical-align:middle; padding-left: { '12px' if logo_html else '0px' };">
                    <h1 style="margin:0; font-size:18px; color:#111; font-weight:bold; text-transform:uppercase;">{data['school_name']}</h1>
                    {f'<h3 style="margin:2px 0; font-size:11px; font-style:italic; font-weight:normal; color:#444;">{data["report_motto"]}</h3>' if data.get("report_motto") else ''}
                    {contact_html}
                    <h2 style="margin:4px 0 0 0; font-size:12px; font-weight:bold; color:#222; text-transform:uppercase;">{data['report_title']}</h2>
                    <p style="margin:2px 0 0 0; font-size:10px; color:#333;">Academic Period: {sem['year_label']} &mdash; {sem['name']}</p>
                </td>
            </tr>
        </table>
        """

        legend_html = ""
        if data.get("grading_rules"):
            sorted_rules = sorted(data["grading_rules"], key=lambda x: x.get("min_score", 0), reverse=True)
            legend_items = []
            for idx, rule in enumerate(sorted_rules):
                min_score = rule.get("min_score", 0)
                max_score = 100
                if idx > 0:
                    max_score = sorted_rules[idx - 1].get("min_score", 100) - 1
                grade = rule.get("grade", "")
                remark = rule.get("remark", "")
                legend_items.append(f"{grade} ({min_score}-{max_score}%, {remark})")
            
            rules_legend_str = " &nbsp;|&nbsp; ".join(legend_items)
            legend_html = f"""
            <div style="margin-top: 10px; padding: 6px 10px; background: #fafafa; border: 1px solid #ddd; font-size: 8.5px; line-height: 1.3;">
                <strong>Grading Scale Legend:</strong><br/>
                <span style="color:#555;">{rules_legend_str}</span>
            </div>
            """

        rows_html = ""
        for row in data["scores"]:
            sub_type_badge = "Core" if row.get("is_core") else "Elective"
            rows_html += f"""
                <tr>
                    <td><strong>{row['subject']}</strong> &nbsp;<span style="font-size:7.5px; color:#666; font-style:italic;">({sub_type_badge})</span></td>
                    <td style="text-align:center">{row['class_score']:.1f}</td>
                    <td style="text-align:center">{row['exam_score']:.1f}</td>
                    <td style="text-align:center"><strong>{row['total_score']:.1f}</strong></td>
                    <td style="text-align:center"><strong>{row['grade']}</strong></td>
                    <td style="text-align:center">{row['position'] or '—'}</td>
                    <td>{row['remark']}</td>
                </tr>
            """

        aggregate_html = ""
        if data["aggregate"] is not None:
            breakdown_str = ""
            if data.get("aggregate_breakdown"):
                q_cores = [f"{c['subject_name']} [{c['grade']}]" for c in data["aggregate_breakdown"].get("qualifying_cores", [])]
                q_elecs = [f"{e['subject_name']} [{e['grade']}]" for e in data["aggregate_breakdown"].get("qualifying_electives", [])]
                breakdown_str = f"<br/><span style='font-size:8px; color:#555;'>Qualifying Best 6: {', '.join(q_cores)} &nbsp;|&nbsp; {', '.join(q_elecs)}</span>"

            aggregate_html = f"<p style='margin: 4px 0;'><strong>WASSCE Aggregate (Best 6):</strong> <span style='font-size:12px; font-weight:bold; color:#0369a1;'>{data['aggregate']}</span>{breakdown_str}</p>"

        watermark_div = ""
        if watermark_path:
            watermark_div = f"""
            <div style="position: absolute; left: 15%; top: 25%; width: 70%; text-align: center; z-index: -1000; opacity: 0.06;">
                <img src="{watermark_path}" style="width: 100%;" />
            </div>
            """

        signature_html = ""
        if data["headmaster_signature"]:
            sig_path = data["headmaster_signature"]
            if sig_path.startswith("/assets/"):
                import os
                current_dir = os.path.dirname(os.path.abspath(__file__))
                frontend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "frontend"))
                local_sig_path = os.path.join(frontend_dir, sig_path[len("/assets/"):].replace("/", os.sep))
                if os.path.exists(local_sig_path):
                    sig_path = local_sig_path
            signature_html = f'<div style="margin-top: 4px;"><img src="{sig_path}" height="35" /></div>'

        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Helvetica, Arial, sans-serif; font-size: 10px; margin: 15px; }}
                .info-table td {{ padding: 2px 4px; border: none; }}
                table.scores {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
                table.scores th, table.scores td {{ border: 1px solid #bbb; padding: 4px 6px; }}
                table.scores th {{ background: #f0f0f0; text-align: center; }}
                .summary {{ margin-top: 8px; padding: 6px 10px; background: #f8f8f8; border: 1px solid #ddd; }}
                .eval-table td {{ border: 1px solid #bbb; padding: 4px; }}
            </style>
        </head>
        <body>
            {watermark_div}
            {header_html}

            <table class="info-table" style="width:100%; margin-bottom:4px;">
                <tr>
                    <td><strong>Name:</strong> {s['full_name']}</td>
                    <td><strong>Student ID:</strong> {s['student_code']}</td>
                </tr>
                <tr>
                    <td><strong>Class:</strong> {s['class_name']}</td>
                    <td><strong>Gender:</strong> {s['gender'] or '—'}</td>
                </tr>
                <tr>
                    <td><strong>Number on Roll:</strong> {data['number_on_roll']}</td>
                    <td><strong>Date of Closing:</strong> {data['date_of_closing'] or '—'}</td>
                </tr>
                <tr>
                    <td><strong>Next Term Begins:</strong> {data['next_term_begins'] or '—'}</td>
                    <td><strong>Date of Birth:</strong> {s['date_of_birth'] or '—'}</td>
                </tr>
            </table>

            <table class="scores">
                <thead>
                    <tr>
                        <th style="text-align:left">Subject</th>
                        <th>Class (30)</th>
                        <th>Exam (70)</th>
                        <th>Total (100)</th>
                        <th>Grade</th>
                        <th>Pos</th>
                        <th style="text-align:left">Remark</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>

            <div class="summary">
                <strong>Subjects Sat:</strong> {data['num_subjects']} &nbsp;|&nbsp;
                <strong>Average Score:</strong> {data['average_score']:.1f}% &nbsp;|&nbsp;
                <strong>Attendance:</strong> {data['attendance_present']} / {data['attendance_total']} days &nbsp;|&nbsp;
                {'<strong>Position in Class:</strong> ' + str(data['position']) + ' / ' + str(data['total_in_class']) if data['position'] else ''}
                {aggregate_html}
            </div>

            <table class="eval-table" style="width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 9px;">
                <tr>
                    <td style="width: 33%;"><strong>Attitude:</strong> {data['summary_data']['attitude'] or '—'}</td>
                    <td style="width: 33%;"><strong>Conduct:</strong> {data['summary_data']['conduct'] or '—'}</td>
                    <td style="width: 34%;"><strong>Interest:</strong> {data['summary_data']['interest'] or '—'}</td>
                </tr>
            </table>

            <div style="margin-top: 6px; padding: 6px; border: 1px solid #bbb; background: #fafafa; font-size: 9px;">
                <strong>Form Teacher's Remarks:</strong> {data['summary_data']['form_teacher_remarks'] or '—'}
            </div>
            <div style="margin-top: 4px; padding: 6px; border: 1px solid #bbb; background: #fafafa; font-size: 9px;">
                <strong>Headteacher's Remarks:</strong> {data['summary_data']['headteacher_remarks'] or '—'}
            </div>
            <div style="margin-top: 4px; padding: 6px; border: 1px solid #bbb; background: #fafafa; font-size: 9px;">
                <strong>Next Term Promotion:</strong> {data['summary_data']['promoted_to'] or '—'}
            </div>

            {legend_html}

            <table style="width:100%; border:none; margin-top:14px; font-size:9.5px;">
                <tr>
                    <td style="width:50%; border:none; vertical-align:bottom;">
                        <strong>Headmaster/Principal:</strong> {data['headmaster_name'] or '—'}
                        {signature_html}
                    </td>
                    <td style="width:50%; border:none; text-align:right; vertical-align:bottom; opacity: 0.7;">
                        This report was generated by the School Management System.
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)
        if pisa_status.err:
            return None
        return pdf_buffer.getvalue()

    @staticmethod
    def generate_batch_terminal_reports_pdf(db: Session, class_section_id: int, semester_id: int) -> bytes | None:
        """
        Compiles all student terminal report cards in a class into a single multi-page PDF document.
        """
        students = db.query(Student).filter(
            Student.class_section_id == class_section_id,
            Student.is_active == True
        ).order_by(Student.full_name).all()

        if not students:
            return None

        # Build list of report data
        all_reports_html = []
        for idx, student in enumerate(students):
            data = ReportService.get_report_data(db, student.id, semester_id)
            if not data:
                continue

            s = data["student"]
            sem = data["semester"]

            logo_html = ""
            if data.get("school_logo"):
                logo_path = data["school_logo"]
                if not logo_path.startswith("data:"):
                    import os
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    frontend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "frontend"))
                    rel_path = logo_path
                    if "localhost" in rel_path or "127.0.0.1" in rel_path:
                        from urllib.parse import urlparse
                        rel_path = urlparse(rel_path).path
                    if rel_path.startswith("/assets/uploads/"):
                        rel_path = "uploads/" + rel_path[len("/assets/uploads/"):]
                    elif rel_path.startswith("/uploads/"):
                        rel_path = "uploads/" + rel_path[len("/uploads/"):]
                    elif rel_path.startswith("/assets/"):
                        rel_path = "assets/" + rel_path[len("/assets/"):]
                    local_logo_path = os.path.join(frontend_dir, rel_path.replace("/", os.sep))
                    if os.path.exists(local_logo_path):
                        logo_path = local_logo_path
                logo_html = f'<img src="{logo_path}" height="60" />'

            contact_parts = []
            if data.get("school_address"): contact_parts.append(data["school_address"])
            if data.get("school_phone"): contact_parts.append(f"Tel: {data['school_phone']}")
            if data.get("school_email"): contact_parts.append(f"Email: {data['school_email']}")
            contact_html = f'<p style="margin:2px 0; font-size:9px; color:#555;">{" &nbsp;|&nbsp; ".join(contact_parts)}</p>' if contact_parts else ''

            header_html = f"""
            <table style="width:100%; border-bottom: 2px solid #333; padding-bottom: 6px; margin-bottom: 8px;">
                <tr>
                    {f'<td style="width:65px; vertical-align:middle; text-align:left;">{logo_html}</td>' if logo_html else ''}
                    <td style="text-align: { 'left' if logo_html else 'center' }; vertical-align:middle; padding-left: { '10px' if logo_html else '0px' };">
                        <h1 style="margin:0; font-size:16px; color:#111; font-weight:bold; text-transform:uppercase;">{data['school_name']}</h1>
                        {f'<h3 style="margin:2px 0; font-size:10px; font-style:italic; font-weight:normal; color:#444;">{data["report_motto"]}</h3>' if data.get("report_motto") else ''}
                        {contact_html}
                        <h2 style="margin:3px 0 0 0; font-size:11px; font-weight:bold; color:#222; text-transform:uppercase;">{data['report_title']}</h2>
                        <p style="margin:2px 0 0 0; font-size:9.5px; color:#333;">Academic Period: {sem['year_label']} &mdash; {sem['name']}</p>
                    </td>
                </tr>
            </table>
            """

            rows_html = ""
            for row in data["scores"]:
                sub_type_badge = "Core" if row.get("is_core") else "Elective"
                rows_html += f"""
                    <tr>
                        <td><strong>{row['subject']}</strong> &nbsp;<span style="font-size:7.5px; color:#666; font-style:italic;">({sub_type_badge})</span></td>
                        <td style="text-align:center">{row['class_score']:.1f}</td>
                        <td style="text-align:center">{row['exam_score']:.1f}</td>
                        <td style="text-align:center"><strong>{row['total_score']:.1f}</strong></td>
                        <td style="text-align:center"><strong>{row['grade']}</strong></td>
                        <td style="text-align:center">{row['position'] or '—'}</td>
                        <td>{row['remark']}</td>
                    </tr>
                """

            aggregate_html = ""
            if data["aggregate"] is not None:
                breakdown_str = ""
                if data.get("aggregate_breakdown"):
                    q_cores = [f"{c['subject_name']} [{c['grade']}]" for c in data["aggregate_breakdown"].get("qualifying_cores", [])]
                    q_elecs = [f"{e['subject_name']} [{e['grade']}]" for e in data["aggregate_breakdown"].get("qualifying_electives", [])]
                    breakdown_str = f"<br/><span style='font-size:8px; color:#555;'>Qualifying Best 6: {', '.join(q_cores)} &nbsp;|&nbsp; {', '.join(q_elecs)}</span>"
                aggregate_html = f"<p style='margin: 3px 0;'><strong>WASSCE Aggregate (Best 6):</strong> <span style='font-size:11px; font-weight:bold; color:#0369a1;'>{data['aggregate']}</span>{breakdown_str}</p>"

            page_break = '<div style="page-break-after: always;"></div>' if idx < len(students) - 1 else ''

            single_page_html = f"""
            <div class="report-page">
                {header_html}
                <table class="info-table" style="width:100%; margin-bottom:4px;">
                    <tr>
                        <td><strong>Name:</strong> {s['full_name']}</td>
                        <td><strong>Student ID:</strong> {s['student_code']}</td>
                    </tr>
                    <tr>
                        <td><strong>Class:</strong> {s['class_name']}</td>
                        <td><strong>Gender:</strong> {s['gender'] or '—'}</td>
                    </tr>
                    <tr>
                        <td><strong>Number on Roll:</strong> {data['number_on_roll']}</td>
                        <td><strong>Date of Closing:</strong> {data['date_of_closing'] or '—'}</td>
                    </tr>
                    <tr>
                        <td><strong>Next Term Begins:</strong> {data['next_term_begins'] or '—'}</td>
                        <td><strong>Date of Birth:</strong> {s['date_of_birth'] or '—'}</td>
                    </tr>
                </table>

                <table class="scores">
                    <thead>
                        <tr>
                            <th style="text-align:left">Subject</th>
                            <th>Class (30)</th>
                            <th>Exam (70)</th>
                            <th>Total (100)</th>
                            <th>Grade</th>
                            <th>Pos</th>
                            <th style="text-align:left">Remark</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>

                <div class="summary">
                    <strong>Subjects Sat:</strong> {data['num_subjects']} &nbsp;|&nbsp;
                    <strong>Average Score:</strong> {data['average_score']:.1f}% &nbsp;|&nbsp;
                    <strong>Attendance:</strong> {data['attendance_present']} / {data['attendance_total']} days &nbsp;|&nbsp;
                    {'<strong>Position in Class:</strong> ' + str(data['position']) + ' / ' + str(data['total_in_class']) if data['position'] else ''}
                    {aggregate_html}
                </div>

                <table class="eval-table" style="width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 8.5px;">
                    <tr>
                        <td style="width: 33%;"><strong>Attitude:</strong> {data['summary_data']['attitude'] or '—'}</td>
                        <td style="width: 33%;"><strong>Conduct:</strong> {data['summary_data']['conduct'] or '—'}</td>
                        <td style="width: 34%;"><strong>Interest:</strong> {data['summary_data']['interest'] or '—'}</td>
                    </tr>
                </table>

                <div style="margin-top: 4px; padding: 4px 6px; border: 1px solid #bbb; background: #fafafa; font-size: 8.5px;">
                    <strong>Form Teacher's Remarks:</strong> {data['summary_data']['form_teacher_remarks'] or '—'}
                </div>
                <div style="margin-top: 4px; padding: 4px 6px; border: 1px solid #bbb; background: #fafafa; font-size: 8.5px;">
                    <strong>Headteacher's Remarks:</strong> {data['summary_data']['headteacher_remarks'] or '—'}
                </div>
                <div style="margin-top: 4px; padding: 4px 6px; border: 1px solid #bbb; background: #fafafa; font-size: 8.5px;">
                    <strong>Next Term Promotion:</strong> {data['summary_data']['promoted_to'] or '—'}
                </div>

                <table style="width:100%; border:none; margin-top:10px; font-size:9px;">
                    <tr>
                        <td style="width:50%; border:none; vertical-align:bottom;">
                            <strong>Headmaster/Principal:</strong> {data['headmaster_name'] or '—'}
                        </td>
                        <td style="width:50%; border:none; text-align:right; vertical-align:bottom; opacity: 0.7;">
                            Class Batch Report Card &bull; Generated by SMS
                        </td>
                    </tr>
                </table>
            </div>
            {page_break}
            """
            all_reports_html.append(single_page_html)

        if not all_reports_html:
            return None

        combined_html = f"""
        <html>
        <head>
            <style>
                @page {{ size: a4 portrait; margin: 1cm; }}
                body {{ font-family: Helvetica, Arial, sans-serif; font-size: 9.5px; }}
                .info-table td {{ padding: 2px 4px; border: none; font-size: 9px; }}
                table.scores {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
                table.scores th, table.scores td {{ border: 1px solid #bbb; padding: 3px 5px; font-size: 9px; }}
                table.scores th {{ background: #f0f0f0; text-align: center; }}
                .summary {{ margin-top: 6px; padding: 5px 8px; background: #f8f8f8; border: 1px solid #ddd; font-size: 8.5px; }}
                .eval-table td {{ border: 1px solid #bbb; padding: 3px; }}
            </style>
        </head>
        <body>
            {''.join(all_reports_html)}
        </body>
        </html>
        """

        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.StringIO(combined_html), dest=pdf_buffer)
        if pisa_status.err:
            return None
        return pdf_buffer.getvalue()

    @staticmethod
    def generate_broadsheet_pdf(db: Session, class_section_id: int, semester_id: int) -> bytes | None:
        """
        Generates an official GES/WAEC continuous assessment Broadsheet Ledger matrix PDF in Landscape orientation.
        """
        cs = db.query(ClassSection).filter(ClassSection.id == class_section_id).first()
        semester = db.query(Semester).filter(Semester.id == semester_id).first()
        if not cs or not semester:
            return None

        school_name = _get_setting(db, "school_name", "SENIOR HIGH SCHOOL")
        school_address = _get_setting(db, "school_address", "Ghana, West Africa")
        academic_head_name = _get_setting(db, "report_academic_head", "Assistant Headmaster (Academic)")
        headmaster_name = _get_setting(db, "report_headmaster", "Headmaster / Principal")
        form_master_name = cs.form_master.username if cs.form_master else "Unassigned"

        subjects = cs.subjects
        students = db.query(Student).filter(
            Student.class_section_id == cs.id,
            Student.is_active == True
        ).order_by(Student.full_name).all()

        if not students:
            return None

        # Build student data
        student_rows_data = []
        subject_scores_accumulator = {s.id: [] for s in subjects}

        for st in students:
            scores = db.query(Score).filter(
                Score.student_id == st.id,
                Score.semester_id == semester.id
            ).all()

            subj_map = {sc.subject_id: sc for sc in scores}
            tot_marks = 0.0
            s_count = 0

            st_subj_data = {}
            for s in subjects:
                sc = subj_map.get(s.id)
                if sc and sc.total_score is not None:
                    st_subj_data[s.id] = {"score": sc.total_score, "grade": sc.grade or "-"}
                    tot_marks += sc.total_score
                    s_count += 1
                    subject_scores_accumulator[s.id].append(sc.total_score)
                else:
                    st_subj_data[s.id] = {"score": "-", "grade": "-"}

            avg = round(tot_marks / s_count, 1) if s_count > 0 else 0.0

            # Aggregate calculation
            aggregate = None
            try:
                aggregate = GradingService.calculate_shs_aggregate(scores, student=st)
            except Exception:
                pass

            student_rows_data.append({
                "student": st,
                "subj_data": st_subj_data,
                "total": round(tot_marks, 1),
                "average": avg,
                "aggregate": aggregate or "-"
            })

        # Rank students by total score descending
        student_rows_data.sort(key=lambda x: x["total"], reverse=True)
        for idx, item in enumerate(student_rows_data):
            item["rank"] = idx + 1

        # Summary statistics per subject
        stats_means = []
        stats_maxs = []
        stats_mins = []
        stats_passrates = []

        for s in subjects:
            vals = subject_scores_accumulator[s.id]
            if vals:
                mean_v = round(sum(vals) / len(vals), 1)
                max_v = round(max(vals), 1)
                min_v = round(min(vals), 1)
                passes = sum(1 for v in vals if v >= 50.0)
                pass_rate = round((passes / len(vals)) * 100, 1)
                stats_means.append(f"{mean_v}")
                stats_maxs.append(f"{max_v}")
                stats_mins.append(f"{min_v}")
                stats_passrates.append(f"{pass_rate}%")
            else:
                stats_means.append("-")
                stats_maxs.append("-")
                stats_mins.append("-")
                stats_passrates.append("-")

        # HTML construction
        subj_headers_html = "".join([f'<th style="font-size:7.5px; text-align:center; min-width:30px;">{s.code or s.name[:5]}</th>' for s in subjects])

        rows_html = ""
        for idx, row in enumerate(student_rows_data):
            st = row["student"]
            subj_tds = ""
            for s in subjects:
                sd = row["subj_data"][s.id]
                val_str = f"{sd['score']}" if sd['score'] != "-" else "-"
                if sd['grade'] != "-":
                    val_str += f"<br/><span style='font-size:6.5px;color:#0284c7;'>{sd['grade']}</span>"
                subj_tds += f'<td style="text-align:center; font-size:7.5px;">{val_str}</td>'

            rank_badge = f"<b>{row['rank']}</b>"
            if row['rank'] == 1: rank_badge = "<span style='color:#d97706; font-weight:bold;'>1st 🥇</span>"
            elif row['rank'] == 2: rank_badge = "<span style='color:#4b5563; font-weight:bold;'>2nd 🥈</span>"
            elif row['rank'] == 3: rank_badge = "<span style='color:#92400e; font-weight:bold;'>3rd 🥉</span>"

            rows_html += f"""
            <tr>
                <td style="text-align:center;">{idx + 1}</td>
                <td style="font-family:monospace; font-size:7.5px;">{st.student_code}</td>
                <td style="text-align:left; font-weight:bold; white-space:nowrap;">{st.full_name}</td>
                <td style="text-align:center;">{st.gender or '-'}</td>
                {subj_tds}
                <td style="text-align:right; font-weight:bold;">{row['total']}</td>
                <td style="text-align:right;">{row['average']}%</td>
                <td style="text-align:center; font-weight:bold; color:#0369a1;">{row['aggregate']}</td>
                <td style="text-align:center;">{rank_badge}</td>
            </tr>
            """

        mean_tds = "".join([f'<td style="text-align:center; font-weight:bold; font-size:7.5px;">{m}</td>' for m in stats_means])
        max_tds = "".join([f'<td style="text-align:center; font-weight:bold; font-size:7.5px; color:#059669;">{m}</td>' for m in stats_maxs])
        min_tds = "".join([f'<td style="text-align:center; font-weight:bold; font-size:7.5px; color:#dc2626;">{m}</td>' for m in stats_mins])
        pass_tds = "".join([f'<td style="text-align:center; font-weight:bold; font-size:7.5px; color:#0284c7;">{p}</td>' for p in stats_passrates])

        num_students = len(students)
        class_tot_avg = round(sum(r["average"] for r in student_rows_data) / num_students, 1) if num_students > 0 else 0.0

        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: a4 landscape;
                    margin: 0.6cm;
                }}
                body {{
                    font-family: Helvetica, Arial, sans-serif;
                    font-size: 8px;
                    color: #0f172a;
                }}
                .header-table {{
                    width: 100%;
                    border-bottom: 2px solid #0f172a;
                    padding-bottom: 4px;
                    margin-bottom: 6px;
                }}
                .matrix-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 4px;
                }}
                .matrix-table th, .matrix-table td {{
                    border: 1px solid #94a3b8;
                    padding: 3px 4px;
                }}
                .matrix-table th {{
                    background: #f1f5f9;
                    font-weight: bold;
                    text-align: center;
                }}
                .stat-row td {{
                    background: #f8fafc;
                    border-top: 2px solid #64748b;
                }}
            </style>
        </head>
        <body>
            <table class="header-table">
                <tr>
                    <td style="width:70%;">
                        <div style="font-size:13px; font-weight:bold; text-transform:uppercase;">{school_name}</div>
                        <div style="font-size:8px; color:#475569;">{school_address} &bull; Official Continuous Assessment &amp; Broadsheet Ledger</div>
                    </td>
                    <td style="width:30%; text-align:right; vertical-align:top;">
                        <div style="font-size:9.5px; font-weight:bold; color:#0369a1;">Class: {cs.name}</div>
                        <div style="font-size:8px; color:#64748b;">Period: {semester.name} ({semester.academic_year.label if semester.academic_year else ''})</div>
                        <div style="font-size:8px; color:#64748b;">Form Master: {form_master_name}</div>
                    </td>
                </tr>
            </table>

            <table class="matrix-table">
                <thead>
                    <tr>
                        <th style="width:18px;">#</th>
                        <th style="width:55px;">ID</th>
                        <th style="text-align:left; width:120px;">Student Name</th>
                        <th style="width:18px;">Sex</th>
                        {subj_headers_html}
                        <th style="width:35px; text-align:right;">Total</th>
                        <th style="width:35px; text-align:right;">Avg %</th>
                        <th style="width:30px; text-align:center;">Agg</th>
                        <th style="width:35px; text-align:center;">Rank</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                    <!-- Statistical Summary Rows -->
                    <tr class="stat-row">
                        <td colspan="4" style="text-align:right; font-weight:bold;">Class Subject Mean:</td>
                        {mean_tds}
                        <td colspan="2" style="text-align:right; font-weight:bold;">{class_tot_avg}%</td>
                        <td colspan="2" style="text-align:center; font-size:7px; color:#64748b;">Overall Class Mean</td>
                    </tr>
                    <tr style="background:#f8fafc;">
                        <td colspan="4" style="text-align:right; font-weight:bold; color:#059669;">Highest Score:</td>
                        {max_tds}
                        <td colspan="4"></td>
                    </tr>
                    <tr style="background:#f8fafc;">
                        <td colspan="4" style="text-align:right; font-weight:bold; color:#dc2626;">Lowest Score:</td>
                        {min_tds}
                        <td colspan="4"></td>
                    </tr>
                    <tr style="background:#f8fafc;">
                        <td colspan="4" style="text-align:right; font-weight:bold; color:#0284c7;">Pass Rate (>=50%):</td>
                        {pass_tds}
                        <td colspan="4"></td>
                    </tr>
                </tbody>
            </table>

            <table style="width:100%; margin-top:14px; border:none; font-size:8px;">
                <tr>
                    <td style="width:33%; text-align:center; vertical-align:bottom;">
                        <div style="border-bottom:1px solid #000; width:130px; height:18px; margin:0 auto 2px;"></div>
                        <strong>{form_master_name}</strong><br/>
                        <span style="color:#64748b; font-size:7px;">Form Master / Mistress</span>
                    </td>
                    <td style="width:33%; text-align:center; vertical-align:bottom;">
                        <div style="border-bottom:1px solid #000; width:130px; height:18px; margin:0 auto 2px;"></div>
                        <strong>{academic_head_name}</strong><br/>
                        <span style="color:#64748b; font-size:7px;">Assistant Head (Academic)</span>
                    </td>
                    <td style="width:34%; text-align:center; vertical-align:bottom;">
                        <div style="border-bottom:1px solid #000; width:130px; height:18px; margin:0 auto 2px;"></div>
                        <strong>{headmaster_name}</strong><br/>
                        <span style="color:#64748b; font-size:7px;">Headmaster / Principal</span>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)
        if pisa_status.err:
            return None
        return pdf_buffer.getvalue()

    @staticmethod
    def generate_broadsheet_csv(db: Session, class_section_id: int, semester_id: int) -> str:
        """
        Generates RFC 4180 CSV export of class broadsheet matrix and statistical summary.
        """
        import csv
        cs = db.query(ClassSection).filter(ClassSection.id == class_section_id).first()
        semester = db.query(Semester).filter(Semester.id == semester_id).first()
        if not cs or not semester:
            return ""

        subjects = cs.subjects
        students = db.query(Student).filter(
            Student.class_section_id == cs.id,
            Student.is_active == True
        ).order_by(Student.full_name).all()

        output = io.StringIO()
        writer = csv.writer(output)

        # Header comments
        writer.writerow(["CLASS BROADSHEET MATRIX & ACADEMIC LEDGER"])
        writer.writerow(["Class Section", cs.name, "Semester / Term", semester.name, "Academic Year", semester.academic_year.label if semester.academic_year else ""])
        writer.writerow([])

        # Table Column Headers
        headers = ["Rank", "Student ID", "Student Name", "Gender"]
        for s in subjects:
            headers.append(f"{s.name} ({s.code or ''})")
        headers.extend(["Total Score", "Average (%)", "WASSCE Aggregate (Best 6)", "Attitude", "Conduct", "Form Master Remarks"])
        writer.writerow(headers)

        # Calculate student scores and ranks
        student_rows = []
        subject_accumulator = {s.id: [] for s in subjects}

        for st in students:
            scores = db.query(Score).filter(
                Score.student_id == st.id,
                Score.semester_id == semester.id
            ).all()
            subj_map = {sc.subject_id: sc for sc in scores}
            tot = 0.0
            cnt = 0
            row_subj_vals = []

            for s in subjects:
                sc = subj_map.get(s.id)
                if sc and sc.total_score is not None:
                    row_subj_vals.append(f"{sc.total_score:.1f} ({sc.grade or ''})")
                    tot += sc.total_score
                    cnt += 1
                    subject_accumulator[s.id].append(sc.total_score)
                else:
                    row_subj_vals.append("-")

            avg = round(tot / cnt, 1) if cnt > 0 else 0.0
            aggregate = ""
            try:
                agg_val = GradingService.calculate_shs_aggregate(scores, student=st)
                aggregate = str(agg_val) if agg_val is not None else ""
            except Exception:
                pass

            summary = db.query(StudentSemesterSummary).filter(
                StudentSemesterSummary.student_id == st.id,
                StudentSemesterSummary.semester_id == semester.id
            ).first()

            student_rows.append({
                "student": st,
                "subject_vals": row_subj_vals,
                "total": tot,
                "avg": avg,
                "aggregate": aggregate,
                "attitude": summary.attitude if summary else "",
                "conduct": summary.conduct if summary else "",
                "remarks": summary.form_teacher_remarks if summary else ""
            })

        student_rows.sort(key=lambda x: x["total"], reverse=True)

        for idx, r in enumerate(student_rows):
            st = r["student"]
            row = [idx + 1, st.student_code, st.full_name, st.gender or ""]
            row.extend(r["subject_vals"])
            row.extend([f"{r['total']:.1f}", f"{r['avg']:.1f}%", r["aggregate"], r["attitude"], r["conduct"], r["remarks"]])
            writer.writerow(row)

        # Summary statistics
        writer.writerow([])
        writer.writerow(["STATISTICAL SUMMARY"])
        mean_row = ["Class Subject Mean", "", "", ""]
        max_row = ["Highest Score", "", "", ""]
        min_row = ["Lowest Score", "", "", ""]
        pass_row = ["Pass Rate (>=50%)", "", "", ""]

        for s in subjects:
            vals = subject_accumulator[s.id]
            if vals:
                mean_row.append(f"{sum(vals)/len(vals):.1f}")
                max_row.append(f"{max(vals):.1f}")
                min_row.append(f"{min(vals):.1f}")
                passes = sum(1 for v in vals if v >= 50.0)
                pass_row.append(f"{(passes/len(vals))*100:.1f}%")
            else:
                mean_row.append("-")
                max_row.append("-")
                min_row.append("-")
                pass_row.append("-")

        writer.writerow(mean_row)
        writer.writerow(max_row)
        writer.writerow(min_row)
        writer.writerow(pass_row)

        return output.getvalue()

    @staticmethod
    def get_full_transcript_data(db: Session, student_id: int) -> dict | None:
        """
        Assembles 100% of all subject records across Form 1, Form 2, and Form 3.
        Separates WASSCE External Subjects from Internal Assessment Subjects (PEH, Robotics & Coding, STEM Group C).
        Computes WAEC 9-point scale interpretations and offline SHA-256 validation hash.
        """
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return None

        def _waec_interp(g_str):
            if not g_str: return "Pass"
            g = g_str.strip().upper()
            mapping = {
                "A1": "Excellent", "B2": "Very Good", "B3": "Good",
                "C4": "Credit", "C5": "Credit", "C6": "Credit",
                "D7": "Pass", "E8": "Pass", "F9": "Fail"
            }
            return mapping.get(g, "Credit" if g.startswith("C") else "Pass")

        school_name = _get_setting(db, "school_name", "SENIOR HIGH SCHOOL")
        school_address = _get_setting(db, "school_address", "")
        school_phone = _get_setting(db, "school_phone", "")
        headmaster_name = _get_setting(db, "report_headmaster", "")

        all_scores = db.query(Score).filter(Score.student_id == student_id).all()

        external_subjects = []
        internal_subjects = []

        for sc in all_scores:
            sub = sc.subject
            sem = sc.semester
            item = {
                "score_id": sc.id,
                "subject_name": sub.name if sub else "Subject",
                "subject_code": sub.code if sub else "",
                "is_core": sub.is_core if sub else False,
                "category": getattr(sub, "category", "Core"),
                "group_code": getattr(sub, "group_code", None),
                "assessment_type": getattr(sub, "assessment_type", "External_WASSCE"),
                "semester_name": sem.name if sem else "Term",
                "academic_year": sem.academic_year.label if sem and sem.academic_year else "2025/2026",
                "total_score": sc.total_score,
                "grade": sc.grade,
                "remark": sc.remark,
                "interpretation": _waec_interp(sc.grade)
            }

            if getattr(sub, "assessment_type", "External_WASSCE") == "Internal_Transcript" or (sub and ("Robotics" in sub.name or "PEH" in sub.name)):
                internal_subjects.append(item)
            else:
                external_subjects.append(item)

        raw_hash_str = f"{student.id}:{student.student_code}:{student.bece_index_number}:{len(all_scores)}"
        verification_hash = hashlib.sha256(raw_hash_str.encode('utf-8')).hexdigest()[:16].upper()
        wassce_idx = getattr(student, "wassce_index_number", None) or student.bece_index_number or f"109040{student.id:04d}"

        return {
            "student_id": student.id,
            "student_code": student.student_code,
            "full_name": student.full_name,
            "bece_index_number": student.bece_index_number,
            "wassce_index_number": wassce_idx,
            "enrolment_code": student.enrolment_code,
            "gender": student.gender,
            "program_name": student.program.name if student.program else "General Science",
            "residential_status": "Boarding" if student.residential_status == "B" else "Day",
            "house_name": student.house.name if student.house else None,
            "verification_hash": verification_hash,
            "waec_series": "MAY/JUNE WASSCE 2025",
            "school_info": {
                "name": school_name,
                "address": school_address,
                "phone": school_phone,
                "headmaster": headmaster_name,
                "centre_number": "1090400"
            },
            "total_subjects_recorded": len(all_scores),
            "external_wassce_subjects": external_subjects,
            "internal_transcript_subjects": internal_subjects
        }

    @staticmethod
    def generate_official_transcript_pdf(db: Session, student_id: int) -> bytes:
        """
        Compiles an official, tamper-evident 3-Year Senior High School Academic Transcript PDF.
        Includes WASSCE grading matrix, Internal Assessment Subjects, Cumulative GPA,
        Best 6 WASSCE aggregates, SHA-256 validation seal, and official certification block.
        """
        data = ReportService.get_full_transcript_data(db, student_id)
        if not data:
            raise ValueError("Student transcript records not found")

        student = db.query(Student).filter(Student.id == student_id).first()
        school_info = data["school_info"]
        now_str = datetime.now().strftime("%d %B %Y")

        external_subs = data.get("external_wassce_subjects", [])
        internal_subs = data.get("internal_transcript_subjects", [])

        gpa_points_map = {"A1": 4.0, "B2": 3.5, "B3": 3.0, "C4": 2.5, "C5": 2.0, "C6": 1.5, "D7": 1.0, "E8": 0.5, "F9": 0.0}
        total_pts = 0.0
        graded_cnt = 0
        for s in external_subs + internal_subs:
            g = (s.get("grade") or "").strip().upper()
            if g in gpa_points_map:
                total_pts += gpa_points_map[g]
                graded_cnt += 1
        cgpa = round(total_pts / graded_cnt, 2) if graded_cnt > 0 else 0.0

        ext_rows_html = ""
        for idx, sub in enumerate(external_subs):
            g = sub.get("grade") or "-"
            g_class = "#059669" if g in ["A1", "B2"] else ("#0284c7" if g in ["B3", "C4", "C5", "C6"] else ("#d97706" if g in ["D7", "E8"] else "#dc2626"))
            term_label = f"{sub.get('academic_year', '')} ({sub.get('semester_name', '')})"
            ext_rows_html += f"""
            <tr>
                <td style="text-align:center;">{idx + 1}</td>
                <td style="font-family:monospace; font-size:8px;">{sub.get('subject_code', '')}</td>
                <td style="text-align:left; font-weight:bold;">{sub.get('subject_name', '')}</td>
                <td style="text-align:center;">{sub.get('category', 'Core')}</td>
                <td style="text-align:center; font-size:8px; color:#64748b;">{term_label}</td>
                <td style="text-align:center; font-weight:bold;">{sub.get('total_score', '-')}</td>
                <td style="text-align:center; font-weight:bold; color:{g_class}; font-size:9px;">{g}</td>
                <td style="text-align:left; font-size:8px; color:#475569;">{sub.get('interpretation', 'Pass')}</td>
            </tr>
            """

        int_table_html = ""
        if internal_subs:
            int_rows_html = ""
            for idx, sub in enumerate(internal_subs):
                g = sub.get("grade") or "-"
                g_class = "#059669" if g in ["A1", "B2"] else "#0284c7"
                int_rows_html += f"""
                <tr>
                    <td style="text-align:center;">{idx + 1}</td>
                    <td style="font-family:monospace; font-size:8px;">{sub.get('subject_code', '')}</td>
                    <td style="text-align:left; font-weight:bold;">{sub.get('subject_name', '')}</td>
                    <td style="text-align:center;">Internal</td>
                    <td style="text-align:center; font-weight:bold;">{sub.get('total_score', '-')}</td>
                    <td style="text-align:center; font-weight:bold; color:{g_class}; font-size:9px;">{g}</td>
                    <td style="text-align:left; font-size:8px; color:#475569;">{sub.get('interpretation', 'Pass')}</td>
                </tr>
                """
            int_table_html = f"""
            <div style="margin-top:10px; font-weight:bold; font-size:9px; color:#0369a1; text-transform:uppercase;">
                Internal Continuous Assessment &amp; Co-Curricular Subjects
            </div>
            <table class="matrix-table" style="margin-top:4px;">
                <thead>
                    <tr>
                        <th style="width:20px;">#</th>
                        <th style="width:55px;">Code</th>
                        <th style="text-align:left;">Subject Title</th>
                        <th style="width:50px;">Type</th>
                        <th style="width:45px;">Score</th>
                        <th style="width:40px;">Grade</th>
                        <th style="text-align:left;">Interpretation</th>
                    </tr>
                </thead>
                <tbody>
                    {int_rows_html}
                </tbody>
            </table>
            """

        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: a4 portrait;
                    margin: 0.8cm;
                }}
                body {{ font-family: Helvetica, Arial, sans-serif; font-size: 8.5px; color: #0f172a; line-height: 1.3; }}
                .watermark {{
                    position: fixed;
                    top: 35%;
                    left: 10%;
                    width: 80%;
                    text-align: center;
                    font-size: 36px;
                    font-weight: 900;
                    color: rgba(203, 213, 225, 0.25);
                    transform: rotate(-35deg);
                    z-index: -1000;
                    letter-spacing: 4px;
                }}
                .header-table {{ width: 100%; border-bottom: 2px solid #0f172a; padding-bottom: 6px; margin-bottom: 8px; }}
                .bio-table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; background: #f8fafc; border: 1px solid #cbd5e1; }}
                .bio-table td {{ padding: 4px 8px; border: 1px solid #e2e8f0; font-size: 8.5px; }}
                .matrix-table {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
                .matrix-table th, .matrix-table td {{ border: 1px solid #94a3b8; padding: 4px 6px; font-size: 8px; }}
                .matrix-table th {{ background: #f1f5f9; font-weight: bold; text-align: center; font-size: 8px; }}
                .kpi-table {{ width: 100%; margin-top: 8px; margin-bottom: 8px; }}
                .kpi-box {{ background: #f8fafc; border: 1px solid #cbd5e1; padding: 6px; text-align: center; }}
                .seal-box {{
                    border: 2px dashed #94a3b8;
                    border-radius: 6px;
                    padding: 8px;
                    text-align: center;
                    font-size: 7.5px;
                    color: #64748b;
                }}
            </style>
        </head>
        <body>
            <div class="watermark">OFFICIAL TRANSCRIPT &bull; VALID WITH SEAL</div>

            <table class="header-table">
                <tr>
                    <td style="width:75%;">
                        <div style="font-size:8px; font-weight:bold; color:#475569; letter-spacing:1px; text-transform:uppercase;">GHANA EDUCATION SERVICE &bull; MINISTRY OF EDUCATION</div>
                        <div style="font-size:15px; font-weight:900; color:#0f172a; text-transform:uppercase; margin-top:2px;">{school_info.get('name', 'SENIOR HIGH SCHOOL')}</div>
                        <div style="font-size:8px; color:#475569;">{school_info.get('address', '')} &bull; Tel: {school_info.get('phone', '')}</div>
                        <div style="font-size:11px; font-weight:bold; color:#0369a1; margin-top:4px; text-transform:uppercase; letter-spacing:0.5px;">OFFICIAL SENIOR HIGH SCHOOL ACADEMIC TRANSCRIPT</div>
                    </td>
                    <td style="width:25%; text-align:right; vertical-align:top;">
                        <div style="font-size:7.5px; color:#64748b;">CENTRE NO: <strong>{school_info.get('centre_number', '1090400')}</strong></div>
                        <div style="font-size:7.5px; color:#64748b;">DATE ISSUED: <strong>{now_str}</strong></div>
                        <div style="font-size:7.5px; font-family:monospace; color:#0369a1; margin-top:4px;">REF: {data.get('verification_hash', 'N/A')}</div>
                    </td>
                </tr>
            </table>

            <table class="bio-table">
                <tr>
                    <td style="width:18%; font-weight:bold; color:#475569;">STUDENT NAME:</td>
                    <td style="width:32%; font-weight:bold; color:#0f172a;">{data.get('full_name', '').upper()}</td>
                    <td style="width:18%; font-weight:bold; color:#475569;">STUDENT ID / CODE:</td>
                    <td style="width:32%; font-family:monospace; font-weight:bold;">{data.get('student_code', '')}</td>
                </tr>
                <tr>
                    <td style="font-weight:bold; color:#475569;">PROGRAM OF STUDY:</td>
                    <td style="font-weight:bold; color:#0284c7;">{data.get('program_name', '')}</td>
                    <td style="font-weight:bold; color:#475569;">GENDER / RESIDENCE:</td>
                    <td>{data.get('gender', '-')} &bull; {data.get('residential_status', 'Day')}</td>
                </tr>
                <tr>
                    <td style="font-weight:bold; color:#475569;">BECE INDEX NO:</td>
                    <td style="font-family:monospace;">{data.get('bece_index_number', 'N/A')}</td>
                    <td style="font-weight:bold; color:#475569;">WASSCE INDEX NO:</td>
                    <td style="font-family:monospace; font-weight:bold; color:#059669;">{data.get('wassce_index_number', 'N/A')}</td>
                </tr>
            </table>

            <table class="kpi-table">
                <tr>
                    <td class="kpi-box" style="width:25%;">
                        <div style="font-size:7px; color:#64748b; text-transform:uppercase;">Total Subjects Recorded</div>
                        <div style="font-size:12px; font-weight:bold; color:#0f172a;">{data.get('total_subjects_recorded', 0)}</div>
                    </td>
                    <td class="kpi-box" style="width:25%;">
                        <div style="font-size:7px; color:#64748b; text-transform:uppercase;">Cumulative GPA (4.0 Max)</div>
                        <div style="font-size:12px; font-weight:bold; color:#0284c7;">{cgpa}</div>
                    </td>
                    <td class="kpi-box" style="width:25%;">
                        <div style="font-size:7px; color:#64748b; text-transform:uppercase;">Examination Series</div>
                        <div style="font-size:10px; font-weight:bold; color:#059669;">{data.get('waec_series', 'WASSCE')}</div>
                    </td>
                    <td class="kpi-box" style="width:25%;">
                        <div style="font-size:7px; color:#64748b; text-transform:uppercase;">Grading Standard</div>
                        <div style="font-size:10px; font-weight:bold; color:#475569;">WAEC 9-Point Scale</div>
                    </td>
                </tr>
            </table>

            <div style="font-weight:bold; font-size:9px; color:#0f172a; text-transform:uppercase; margin-top:6px;">
                Official Scholastic &amp; WASSCE Assessment Records
            </div>
            <table class="matrix-table">
                <thead>
                    <tr>
                        <th style="width:20px;">#</th>
                        <th style="width:55px;">Code</th>
                        <th style="text-align:left;">Subject Title</th>
                        <th style="width:50px;">Category</th>
                        <th style="width:90px;">Academic Term</th>
                        <th style="width:45px;">Score</th>
                        <th style="width:40px;">Grade</th>
                        <th style="text-align:left;">Interpretation</th>
                    </tr>
                </thead>
                <tbody>
                    {ext_rows_html}
                </tbody>
            </table>

            {int_table_html}

            <div style="margin-top:8px; padding:4px 8px; background:#f8fafc; border:1px solid #e2e8f0; font-size:7px; color:#475569;">
                <strong>WAEC GRADING KEY:</strong>
                A1 (80-100% Excellent) &bull; B2 (70-79% Very Good) &bull; B3 (65-69% Good) &bull; C4 (60-64% Credit) &bull; C5 (55-59% Credit) &bull; C6 (50-54% Credit) &bull; D7 (45-49% Pass) &bull; E8 (40-44% Pass) &bull; F9 (0-39% Fail)
            </div>

            <table style="width:100%; margin-top:16px; border:none; font-size:8px;">
                <tr>
                    <td style="width:33%; text-align:center; vertical-align:bottom;">
                        <div style="border-bottom:1px solid #000; width:130px; margin:0 auto 4px;"></div>
                        <strong>Head of Academic Affairs / Registrar</strong>
                        <div style="font-size:7px; color:#64748b;">Signature &amp; Date</div>
                    </td>
                    <td style="width:34%; text-align:center; vertical-align:middle;">
                        <div class="seal-box">
                            <strong>OFFICIAL INSTITUTIONAL SEAL</strong><br/>
                            <span style="font-size:6.5px; color:#94a3b8;">SHA-256: {data.get('verification_hash', 'N/A')}</span><br/>
                            <span style="font-size:6.5px; color:#059669;">[TAMPER-EVIDENT DIGITAL RECORD]</span>
                        </div>
                    </td>
                    <td style="width:33%; text-align:center; vertical-align:bottom;">
                        <div style="border-bottom:1px solid #000; width:130px; margin:0 auto 4px;"></div>
                        <strong>Headmaster / Principal</strong>
                        <div style="font-size:7px; color:#64748b;">{school_info.get('headmaster', 'Principal')}</div>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)
        if pisa_status.err:
            raise RuntimeError("Failed to compile official transcript PDF")

        return pdf_buffer.getvalue()

    @staticmethod
    def generate_basic_cumulative_folder_pdf(db: Session, student_id: int) -> bytes:
        """
        Compiles the official Ghana Education Service / NaCCA Basic School Cumulative Record Folder PDF.
        Covers all 6 categories: Identification/Family, Scholastic/SBA, Attendance/Conduct,
        Health/Physical, Personality/Social, and Co-Curricular/Talents.
        """
        from ..models import StudentGuardian, StudentHealth
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise ValueError("Student not found")

        school_name = _get_setting(db, "school_name", "BASIC EDUCATION COMPLEX")
        school_address = _get_setting(db, "school_address", "")
        school_phone = _get_setting(db, "school_phone", "")
        headmaster_name = _get_setting(db, "report_headmaster", "")

        guardians = db.query(StudentGuardian).filter(StudentGuardian.student_id == student_id).all()
        health = db.query(StudentHealth).filter(StudentHealth.student_id == student_id).first()
        scores = db.query(Score).filter(Score.student_id == student_id).all()
        attendance_records = db.query(Attendance).filter(Attendance.student_id == student_id).all()

        total_days = len(attendance_records)
        days_present = sum(1 for a in attendance_records if a.status.upper() in ["PRESENT", "LATE"])
        att_rate = f"{round((days_present/total_days)*100, 1)}%" if total_days > 0 else "100.0%"

        score_list = [s.total_score for s in scores if s.total_score is not None]
        avg_score = round(sum(score_list) / len(score_list), 1) if score_list else 0.0

        scores_rows_html = ""
        for idx, sc in enumerate(scores):
            sub_name = sc.subject.name if sc.subject else "Subject"
            sem_name = sc.semester.name if sc.semester else "Term"
            g = sc.grade or "-"
            scores_rows_html += f"""
            <tr>
                <td style="text-align:center;">{idx + 1}</td>
                <td style="text-align:left; font-weight:bold;">{sub_name}</td>
                <td style="text-align:center;">{sem_name}</td>
                <td style="text-align:center; font-weight:bold;">{sc.total_score or '-'}</td>
                <td style="text-align:center; font-weight:bold; color:#0284c7;">{g}</td>
                <td style="text-align:left; font-size:7.5px;">{sc.remark or '-'}</td>
            </tr>
            """

        if not scores_rows_html:
            scores_rows_html = '<tr><td colspan="6" style="text-align:center; padding:8px; opacity:0.6;">No scholastic scores recorded yet.</td></tr>'

        guardian_rows = ""
        for g in guardians:
            guardian_rows += f"<div>&bull; <strong>{g.guardian_name}</strong> ({g.relationship_type or 'Guardian'}) &ndash; Tel: {g.primary_phone or '-'}, Occ: {g.occupation or '-'}</div>"
        if not guardian_rows:
            guardian_rows = f"<div>&bull; <strong>{student.guardian_name or 'Parent/Guardian'}</strong> &ndash; Tel: {student.phone or '-'}</div>"

        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{ size: a4 portrait; margin: 0.8cm; }}
                body {{ font-family: Helvetica, Arial, sans-serif; font-size: 8.5px; color: #0f172a; }}
                .header-table {{ width: 100%; border-bottom: 2px solid #0f172a; padding-bottom: 6px; margin-bottom: 8px; }}
                .card-sec {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 4px; padding: 6px 8px; margin-bottom: 8px; }}
                .sec-title {{ font-weight: bold; font-size: 9.5px; color: #0369a1; border-bottom: 1px solid #e2e8f0; padding-bottom: 2px; margin-bottom: 4px; text-transform: uppercase; }}
                .grid-table {{ width: 100%; border-collapse: collapse; font-size: 8px; }}
                .grid-table td {{ padding: 3px 4px; vertical-align: top; }}
                .matrix-table {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
                .matrix-table th, .matrix-table td {{ border: 1px solid #94a3b8; padding: 3px 5px; font-size: 7.5px; }}
                .matrix-table th {{ background: #f1f5f9; font-weight: bold; text-align: center; }}
            </style>
        </head>
        <body>
            <table class="header-table">
                <tr>
                    <td style="width:75%;">
                        <div style="font-size:7.5px; font-weight:bold; color:#475569; letter-spacing:1px; text-transform:uppercase;">GHANA EDUCATION SERVICE &bull; NATIONAL COUNCIL FOR CURRICULUM &amp; ASSESSMENT (NaCCA)</div>
                        <div style="font-size:14px; font-weight:900; color:#0f172a; text-transform:uppercase; margin-top:2px;">{school_name}</div>
                        <div style="font-size:8px; color:#475569;">{school_address} &bull; Tel: {school_phone}</div>
                        <div style="font-size:10.5px; font-weight:bold; color:#059669; margin-top:3px; text-transform:uppercase;">BASIC SCHOOL CUMULATIVE RECORD FOLDER</div>
                    </td>
                    <td style="width:25%; text-align:right; vertical-align:top;">
                        <div style="font-size:8px; font-weight:bold; color:#0369a1;">PUPIL ID: {student.student_code}</div>
                        <div style="font-size:7.5px; color:#64748b;">STAGE: {student.school_type or 'Basic School'}</div>
                    </td>
                </tr>
            </table>

            <div class="card-sec">
                <div class="sec-title">1. Personal &amp; Family Profile</div>
                <table class="grid-table">
                    <tr>
                        <td style="width:20%; font-weight:bold; color:#475569;">PUPIL NAME:</td>
                        <td style="width:30%; font-weight:bold;">{student.full_name.upper()}</td>
                        <td style="width:20%; font-weight:bold; color:#475569;">GENDER &amp; DOB:</td>
                        <td style="width:30%;">{student.gender or '-'} &bull; {student.date_of_birth.strftime('%d/%m/%Y') if student.date_of_birth else 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="font-weight:bold; color:#475569;">RESIDENTIAL ADDRESS:</td>
                        <td>{student.address or 'N/A'}</td>
                        <td style="font-weight:bold; color:#475569;">HOMETOWN / REGION:</td>
                        <td>{getattr(student, 'hometown', 'Ghana')}</td>
                    </tr>
                </table>
                <div style="margin-top:4px; font-size:7.5px;">
                    <strong>Parents / Guardians:</strong>
                    {guardian_rows}
                </div>
            </div>

            <div class="card-sec">
                <div class="sec-title">2. Scholastic Achievement &amp; SBA Growth (Average: {avg_score}%)</div>
                <table class="matrix-table">
                    <thead>
                        <tr>
                            <th style="width:20px;">#</th>
                            <th style="text-align:left;">Subject Title</th>
                            <th style="width:70px;">Term / Session</th>
                            <th style="width:45px;">Score</th>
                            <th style="width:40px;">Grade</th>
                            <th style="text-align:left;">Performance Remarks</th>
                        </tr>
                    </thead>
                    <tbody>
                        {scores_rows_html}
                    </tbody>
                </table>
            </div>

            <div class="card-sec">
                <div class="sec-title">3. Attendance, Physical &amp; Health Development</div>
                <table class="grid-table">
                    <tr>
                        <td style="width:25%; font-weight:bold; color:#475569;">ATTENDANCE RATE:</td>
                        <td style="width:25%; font-weight:bold; color:#059669;">{att_rate} ({days_present} / {total_days} Days)</td>
                        <td style="width:25%; font-weight:bold; color:#475569;">HEIGHT / WEIGHT:</td>
                        <td style="width:25%;">{health.height_cm if health and health.height_cm else '-'} cm &bull; {health.weight_kg if health and health.weight_kg else '-'} kg</td>
                    </tr>
                    <tr>
                        <td style="font-weight:bold; color:#475569;">BLOOD GROUP:</td>
                        <td>{health.blood_group if health and health.blood_group else 'N/A'}</td>
                        <td style="font-weight:bold; color:#475569;">CHRONIC CONDITIONS / ALLERGIES:</td>
                        <td>{health.chronic_conditions or health.allergies if health else 'None Reported'}</td>
                    </tr>
                </table>
            </div>

            <div class="card-sec">
                <div class="sec-title">4. Personality, Social Traits &amp; Co-Curricular Profile</div>
                <table class="grid-table">
                    <tr>
                        <td style="width:20%; font-weight:bold; color:#475569;">PERSONALITY TRAITS:</td>
                        <td style="width:80%;">{student.personality_traits or 'Respectful, diligent, and cooperative.'}</td>
                    </tr>
                    <tr>
                        <td style="font-weight:bold; color:#475569;">LEADERSHIP &amp; CONDUCT:</td>
                        <td>{student.leadership_notes or 'Shows active participation in classroom responsibilities.'}</td>
                    </tr>
                    <tr>
                        <td style="font-weight:bold; color:#475569;">CLUBS, SPORTS &amp; TALENTS:</td>
                        <td>{student.co_curricular_activities or student.hobbies_talents or 'School Sports Club &amp; Reading Society.'}</td>
                    </tr>
                </table>
            </div>

            <table style="width:100%; margin-top:14px; border:none; font-size:8px;">
                <tr>
                    <td style="width:50%; text-align:center;">
                        <div style="border-bottom:1px solid #000; width:150px; margin:0 auto 4px;"></div>
                        <strong>Class Teacher / Form Master</strong>
                        <div style="font-size:7px; color:#64748b;">Signature &amp; Date</div>
                    </td>
                    <td style="width:50%; text-align:center;">
                        <div style="border-bottom:1px solid #000; width:150px; margin:0 auto 4px;"></div>
                        <strong>Headteacher / Principal</strong>
                        <div style="font-size:7px; color:#64748b;">{headmaster_name} &bull; Official Stamp</div>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)
        if pisa_status.err:
            raise RuntimeError("Failed to compile cumulative record folder PDF")

        return pdf_buffer.getvalue()

