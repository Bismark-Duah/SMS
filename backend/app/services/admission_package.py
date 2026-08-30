"""
Official Admission Package & Prospectus PDF Generation Service.
Generates GES/WAEC-standard printable and downloadable PDFs for student admission letters,
dynamic itemized prospectus checklists, medical fitness forms, and honor pledges.
"""
import io
import os
from sqlalchemy.orm import Session
from xhtml2pdf import pisa

from ..models import Student, School, Setting, StudentHealth


class AdmissionPackageService:
    @staticmethod
    def generate_admission_letter_pdf(student_id: int, db: Session) -> bytes | None:
        """
        Generates a complete multi-page Official Admission Letter & Prospectus Package PDF.
        Returns raw PDF bytes or None on failure.
        """
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return None

        school = student.school
        school_name = school.name if school else "SENIOR HIGH SCHOOL"
        
        def _setting(key: str, default: str = "") -> str:
            s = db.query(Setting).filter(Setting.key == key).first()
            return s.value if s else default

        school_address = _setting("school_address", "Ghana, West Africa")
        school_phone = _setting("school_phone", "")
        school_email = _setting("school_email", "")
        headmaster_name = _setting("report_headmaster", "Headmaster / Principal")
        report_motto = _setting("report_motto", "Knowledge, Integrity & Excellence")
        academic_year = student.academic_year or "2025/2026"
        
        prog_name = student.program.name if student.program else "General Science"
        gender = student.gender or "Male"
        is_boarder = (student.residential_status or "B").upper().startswith("B")
        class_name = student.class_section.name if student.class_section else "Form 1"
        house_name = student.house.name if student.house else "Day Student"
        dorm_name = student.dormitory.name if student.dormitory else "N/A"

        # Health info
        health = db.query(StudentHealth).filter(StudentHealth.student_id == student.id).first()
        blood_group = health.blood_group if health and health.blood_group else "O+"
        allergies = health.allergies if health and health.allergies else "None Reported"
        med_conditions = health.chronic_conditions if health and health.chronic_conditions else "None Reported"

        # Dynamic Prospectus Item Lists
        academic_items = [
            "1 Oxford Mathematical Set (Original with compass & divider)",
            "1 Casio FX-991ES Plus / FX-991EX Scientific Calculator",
            "1 English Dictionary (Oxford Advanced Learner's or Longman)",
            "1 Holy Bible (RSV / NIV) or Holy Quran",
            "10 Hardcover Exercise Books (200 & 400 pages)",
            "Standard stationery: Blue/Black pens, HB pencils, 30cm ruler, eraser, sharpener"
        ]

        boarding_items = []
        if is_boarder:
            boarding_items = [
                "1 Single Mattress Cover / Mackintosh Sheet (2.5ft x 6ft)",
                "2 Pairs of House Color-Coded Bedsheets (Light Blue / White / Pink)",
                "1 Pillow & 2 Pillow Cases (Matching House colors)",
                "1 Heavy Blanket or Duvet",
                "1 Treated Mosquito Net (Box or Bell shape)",
                "1 Plastic Bucket & 1 Washing Basin (Medium size)",
                "Toiletries: Bath Soap (4 bars), Soap Dish, Washing Powder, Toothbrush & Paste (2 tubes), 2 Bath Towels, 1 Pack Toilet Rolls (10 pcs)",
                "Sanitation: 1 Native/Ceiling Broom, 1 Scrubbing Brush, 1 Mop & Bucket, 1 Bottle Disinfectant (Dettol/Parazone)",
                "Mess Utensils: 1 Stainless Steel Cutlery Set, 1 Covered Plate & Soup Bowl, 1 Insulated Water Bottle/Flask"
            ]

        if gender.startswith("M") or gender.startswith("m"):
            clothing_items = [
                "3 White Short-Sleeved Official Shirts",
                "2 School Trousers (School color)",
                "1 Black Formal Leather Belt",
                "2 Sets House Jersey & Shorts",
                "2 Pairs Pyjamas for sleeping",
                "1 Pair Black Formal Leather Shoes & 3 Pairs Black Socks",
                "1 Pair White Canvas / Sports Shoes & White Socks (for PE)",
                "1 Pair Bathroom Flip-Flops",
                "Hair Clipper / Pocket Comb (Compliant with GES low haircut guideline)"
            ]
        else:
            clothing_items = [
                "3 School Official Dresses (Below-the-knee length)",
                "2 White Short-Sleeved Blouses & School Skirts",
                "2 House Slips / House Dresses (Below-the-knee length)",
                "2 Night Gowns or Pyjamas",
                "1 Pair Black Flat Leather Shoes (Low heel) & 3 Pairs White Socks",
                "1 Pair White Canvas / Sports Shoes & White Socks (for PE)",
                "1 Pair Bathroom Flip-Flops",
                "4 Packs Sanitary Pads & Personal Hygiene Supplies",
                "Black Hair Ribbons / Hair Bands"
            ]

        program_items = []
        prog_lower = prog_name.lower()
        if "home" in prog_lower or "econ" in prog_lower:
            program_items = [
                "1 White Kitchen Apron & Chef Cap",
                "3 Kitchen Towels & Oven Gloves",
                "1 Measuring Tape, Fabric Scissors & Pins (Clothing & Textiles)"
            ]
        elif "sci" in prog_lower or "agric" in prog_lower or "stem" in prog_lower:
            program_items = [
                "1 White Knee-Length Laboratory Coat (Cotton)",
                "1 Safety Goggles",
                "1 Pair Wellington Boots (Agriculture practicals)"
            ]
        elif "art" in prog_lower or "tech" in prog_lower or "engineer" in prog_lower:
            program_items = [
                "1 A2 Drawing Board & T-Square",
                "Set Squares (45° & 60°), French Curves",
                "Drawing Pencils (HB, 2B, 4B, 6B) & Drawing Pad",
                "Protective Work Apron & Safety Boots"
            ]
        elif "bus" in prog_lower:
            program_items = [
                "3-Column Financial Accounting Ledger Notebooks"
            ]
        else:
            program_items = [
                "1 Literature Anthology Reader & English Grammar Reference"
            ]

        conduct_rules = _setting(
            "code_of_conduct_text",
            "1. ATTENDANCE & PUNCTUALITY: All students must attend morning assemblies, lessons, and school gatherings punctually.\n"
            "2. DISCIPLINE & RESPECT: Absolute respect must be accorded to school prefects, teaching staff, and non-teaching personnel.\n"
            "3. EXAMINATIONS: Malpractice of any form will result in immediate suspension or expulsion in line with GES regulations.\n"
            "4. CAMPUS BOUNDARIES: No student is permitted to leave school compound without a duly approved Exeat Pass."
        )
        honor_pledge = _setting(
            "student_pledge_text",
            "I solemnly pledge on my honor to abide by all the rules and regulations of this institution, "
            "to pursue academic excellence diligently, and to bring honor and pride to my school, family, and country."
        )

        verification_code = f"VERIFIED-{student.student_code}-{student.bece_index_number}"

        # HTML formatting for list items
        def _render_list(items):
            if not items:
                return "<p style='color:#666; font-style:italic;'>No specific items required for this section.</p>"
            return "<ul style='margin:4px 0 8px 18px; padding:0;'>" + "".join([f"<li style='margin-bottom:3px;'>{it}</li>" for it in items]) + "</ul>"

        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: a4 portrait;
                    margin: 1.2cm 1.2cm 1.2cm 1.2cm;
                }}
                body {{
                    font-family: Helvetica, Arial, sans-serif;
                    font-size: 10px;
                    color: #111827;
                    line-height: 1.45;
                }}
                .page-break {{
                    page-break-after: always;
                }}
                .header-table {{
                    width: 100%;
                    border-bottom: 2px solid #0f172a;
                    padding-bottom: 8px;
                    margin-bottom: 12px;
                }}
                .header-title {{
                    font-size: 17px;
                    font-weight: bold;
                    text-transform: uppercase;
                    color: #0f172a;
                    margin: 0;
                }}
                .sub-header {{
                    font-size: 9px;
                    color: #475569;
                    font-weight: bold;
                    text-transform: uppercase;
                    margin-top: 2px;
                }}
                .docket-box {{
                    width: 100%;
                    border-collapse: collapse;
                    border: 1px solid #94a3b8;
                    margin: 10px 0;
                    background: #f8fafc;
                }}
                .docket-box td {{
                    padding: 5px 8px;
                    border: 1px solid #cbd5e1;
                    font-size: 9.5px;
                }}
                .section-title {{
                    font-size: 11px;
                    font-weight: bold;
                    color: #0369a1;
                    text-transform: uppercase;
                    border-bottom: 1px solid #cbd5e1;
                    padding-bottom: 3px;
                    margin-top: 10px;
                    margin-bottom: 4px;
                }}
                .sig-box {{
                    width: 100%;
                    border-top: 1px dashed #64748b;
                    margin-top: 18px;
                    padding-top: 8px;
                }}
            </style>
        </head>
        <body>

            <!-- ── PAGE 1: OFFICIAL ADMISSION LETTER ──────────────────────────── -->
            <table class="header-table">
                <tr>
                    <td style="text-align:center;">
                        <div class="header-title">{school_name}</div>
                        <div class="sub-header">MINISTRY OF EDUCATION &bull; GHANA EDUCATION SERVICE (GES)</div>
                        <div style="font-size:8.5px; color:#64748b; margin-top:2px;">{school_address} &bull; Tel: {school_phone or 'General Office'} &bull; {school_email}</div>
                        <div style="font-size:10.5px; font-weight:bold; color:#0369a1; margin-top:6px; text-transform:uppercase;">
                            OFFICIAL STUDENT ADMISSION LETTER &bull; ACADEMIC YEAR {academic_year}
                        </div>
                    </td>
                </tr>
            </table>

            <table class="docket-box">
                <tr>
                    <td style="width:50%;"><strong>Student Name:</strong> {student.full_name}</td>
                    <td style="width:50%;"><strong>BECE Index Number:</strong> {student.bece_index_number}</td>
                </tr>
                <tr>
                    <td><strong>Assigned Student ID:</strong> <span style="color:#0369a1; font-weight:bold;">{student.student_code}</span></td>
                    <td><strong>Gender / Age:</strong> {gender}</td>
                </tr>
                <tr>
                    <td><strong>Program of Study:</strong> <strong>{prog_name}</strong></td>
                    <td><strong>Assigned Class Stream:</strong> <strong>{class_name}</strong></td>
                </tr>
                <tr>
                    <td><strong>Residential Status:</strong> {'Boarding Student' if is_boarder else 'Day Student'}</td>
                    <td><strong>Boarding House & Dorm:</strong> {house_name} ({dorm_name})</td>
                </tr>
            </table>

            <p style="margin: 10px 0; text-align:justify; font-size:10px;">
                Dear <strong>{student.full_name}</strong>,<br/><br/>
                We are delighted to inform you that following your selection via the Ministry of Education Computerized School Selection & Placement System (CSSPS) and completion of your online registration, you have been officially offered admission into <strong>{school_name}</strong> for the <strong>{academic_year}</strong> Academic Session.
            </p>

            <p style="margin: 8px 0; text-align:justify; font-size:10px;">
                Your enrollment is conditional upon compliance with institutional standards, completion of the attached medical fitness certification, submission of the signed Code of Conduct honor declaration, and presentation of the required prospectus provisions on reporting day.
            </p>

            <div style="background:#f1f5f9; border-left:3px solid #0369a1; padding:8px 10px; margin:12px 0; font-size:9px;">
                <strong>Reporting Instructions:</strong> All admitted Form 1 students are required to report in person at the school campus on the official GES reopening date. Present this printed document package along with 4 passport-size photographs and your original BECE Result Slip to the Admissions Secretariat.
            </div>

            <table style="width:100%; margin-top:35px; border:none;">
                <tr>
                    <td style="width:50%; vertical-align:top;">
                        <div style="border-bottom:1px solid #000; width:180px; height:24px; margin-bottom:4px;"></div>
                        <strong>{headmaster_name}</strong><br/>
                        <span style="font-size:8.5px; color:#475569;">Headmaster / Principal</span><br/>
                        <span style="font-size:7.5px; color:#94a3b8;">[ Official Institutional Seal Attached ]</span>
                    </td>
                    <td style="width:50%; text-align:right; vertical-align:top;">
                        <div style="display:inline-block; border:1px solid #0284c7; background:#e0f2fe; padding:6px 12px; border-radius:4px; text-align:center;">
                            <span style="font-size:8px; color:#0369a1; font-weight:bold;">GES AUTHENTICATION TOKEN</span><br/>
                            <span style="font-family:monospace; font-size:10px; font-weight:bold; color:#0f172a;">{verification_code}</span>
                        </div>
                    </td>
                </tr>
            </table>

            <div class="page-break"></div>

            <!-- ── PAGE 2: OFFICIAL PROSPECTUS & ITEM CHECKLIST ──────────────── -->
            <table class="header-table">
                <tr>
                    <td style="text-align:center;">
                        <div class="header-title">{school_name}</div>
                        <div class="sub-header">OFFICIAL GES FORM 1 PROSPECTUS &bull; PROGRAM: {prog_name.upper()}</div>
                        <div style="font-size:8.5px; color:#64748b;">Candidate: {student.full_name} &bull; ID: {student.student_code} &bull; Status: {'BOARDER' if is_boarder else 'DAY'}</div>
                    </td>
                </tr>
            </table>

            <div class="section-title">1. Core Academic Supplies (All Students)</div>
            {_render_list(academic_items)}

            {'<div class="section-title">2. Boarding House & Personal Sanitation Supplies</div>' if is_boarder else ''}
            {_render_list(boarding_items) if is_boarder else ''}

            <div class="section-title">{'3. Uniforms, Clothing & Grooming Supplies' if is_boarder else '2. Uniforms & Grooming Supplies'}</div>
            {_render_list(clothing_items)}

            <div class="section-title">{'4. Program Practical Tools & Special Equipment' if is_boarder else '3. Program Practical Tools & Special Equipment'}</div>
            {_render_list(program_items)}

            <!-- Code of Conduct & Honor Pledge -->
            <div style="margin-top:14px; padding:8px 10px; background:#f8fafc; border:1px solid #cbd5e1; border-radius:4px;">
                <div style="font-weight:bold; color:#0369a1; font-size:9.5px; margin-bottom:4px;">CODE OF CONDUCT & HONOR DECLARATION</div>
                <div style="font-size:8px; color:#334155; margin-bottom:8px; white-space:pre-line;">{conduct_rules}</div>
                <div style="font-style:italic; font-size:8px; color:#0f172a; border-left:2px solid #0284c7; padding-left:6px; margin-bottom:10px;">
                    "{honor_pledge}"
                </div>
                <table style="width:100%; border:none; font-size:8.5px;">
                    <tr>
                        <td style="width:50%;">
                            <div style="border-bottom:1px solid #000; width:160px; height:16px; margin-bottom:2px;"></div>
                            Candidate Signature & Date
                        </td>
                        <td style="width:50%; text-align:right;">
                            <div style="border-bottom:1px solid #000; width:160px; height:16px; margin-bottom:2px; margin-left:auto;"></div>
                            Parent / Guardian Signature & Date
                        </td>
                    </tr>
                </table>
            </div>

            <div class="page-break"></div>

            <!-- ── PAGE 3: OFFICIAL MEDICAL FITNESS EXAMINATION ──────────────── -->
            <table class="header-table">
                <tr>
                    <td style="text-align:center;">
                        <div class="header-title">{school_name}</div>
                        <div class="sub-header">OFFICIAL GES STUDENT HEALTH & MEDICAL FITNESS EXAMINATION CERTIFICATE</div>
                        <div style="font-size:8.5px; color:#dc2626; font-weight:bold; margin-top:2px;">
                            (To be completed, signed, and stamped by a Certified Medical Practitioner)
                        </div>
                    </td>
                </tr>
            </table>

            <table class="docket-box">
                <tr>
                    <td style="width:50%;"><strong>Candidate Name:</strong> {student.full_name}</td>
                    <td style="width:50%;"><strong>BECE Index:</strong> {student.bece_index_number}</td>
                </tr>
                <tr>
                    <td><strong>Blood Group:</strong> {blood_group}</td>
                    <td><strong>Gender:</strong> {gender}</td>
                </tr>
                <tr>
                    <td><strong>Declared Allergies:</strong> {allergies}</td>
                    <td><strong>Chronic Medical Conditions:</strong> {med_conditions}</td>
                </tr>
            </table>

            <div class="section-title">Clinical Findings & Physical Examination</div>
            <table style="width:100%; border-collapse:collapse; margin-top:6px; font-size:9px;">
                <tr>
                    <td style="padding:6px; border:1px solid #cbd5e1; width:50%;"><strong>Visual Acuity:</strong> Right: _________ &nbsp; Left: _________</td>
                    <td style="padding:6px; border:1px solid #cbd5e1; width:50%;"><strong>Cardiovascular / BP:</strong> ________________________</td>
                </tr>
                <tr>
                    <td style="padding:6px; border:1px solid #cbd5e1;"><strong>Respiratory / Chest:</strong> ________________________</td>
                    <td style="padding:6px; border:1px solid #cbd5e1;"><strong>Abdomen / Hernia:</strong> ___________________________</td>
                </tr>
                <tr>
                    <td style="padding:6px; border:1px solid #cbd5e1;"><strong>Hearing / ENT:</strong> ______________________________</td>
                    <td style="padding:6px; border:1px solid #cbd5e1;"><strong>Skin / Communicable:</strong> _______________________</td>
                </tr>
                <tr>
                    <td colspan="2" style="padding:6px; border:1px solid #cbd5e1;">
                        <strong>Physical Disability / Special Care Needs:</strong> __________________________________________________
                    </td>
                </tr>
            </table>

            <div style="margin-top:14px; padding:8px 10px; background:#f8fafc; border:1px solid #cbd5e1;">
                <strong>Medical Officer's Assessment & Recommendation:</strong><br/>
                <div style="margin-top:6px; font-size:9.5px;">
                    [ &nbsp; ] I certify that the candidate is <strong>FIT</strong> for normal academic, sports, and boarding activities.<br/>
                    [ &nbsp; ] Candidate requires <strong>SPECIAL DIETARY / PHYSICAL CARE</strong> as noted above.
                </div>
            </div>

            <table style="width:100%; margin-top:30px; border:none; font-size:9px;">
                <tr>
                    <td style="width:50%;">
                        <div>Medical Officer: ___________________________________</div>
                        <div style="margin-top:6px;">Signature & Reg No: _____________________________</div>
                        <div style="margin-top:6px;">Date: _________________________________________</div>
                    </td>
                    <td style="width:50%; text-align:right;">
                        <div>Hospital / Health Facility: ___________________________</div>
                        <div style="margin-top:20px; font-weight:bold; color:#64748b;">
                            [ OFFICIAL HOSPITAL / CLINIC STAMP ]
                        </div>
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
