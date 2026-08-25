import io
import hashlib
from xhtml2pdf import pisa
from sqlalchemy.orm import Session
from ..models import (
    Student, Score, Subject, AcademicYear, Semester, Setting, StudentSemesterSummary, Attendance,
    ClassSectionReportStatus, User
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
        try:
            if student.class_section and student.class_section.stage:
                if student.class_section.stage.school_type == "SHS":
                    aggregate = GradingService.calculate_shs_aggregate(scores)
        except Exception:
            pass

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
            rows_html += f"""
                <tr>
                    <td>{row['subject']}</td>
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
            aggregate_html = f"<p style='margin: 4px 0;'><strong>WASSCE Aggregate (Best 6):</strong> {data['aggregate']}</p>"

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
