"""
One-time synchronization script to backfill teacher competencies, primary subjects,
qualified subjects, and active semester assignments from JAK_STEM_Staff_Onboarding_54.xlsx.
"""
import sys
import os
import openpyxl
from sqlalchemy import func

sys.path.insert(0, os.path.abspath('.'))

from backend.app.database import SessionLocal
from backend.app.models import (
    User, Subject, Department, ClassSection, Semester, TeacherAssignment, School
)

def sync_staff_from_excel(excel_path="JAK_STEM_Staff_Onboarding_54.xlsx"):
    if not os.path.exists(excel_path):
        print(f"Error: {excel_path} not found.")
        return

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        print("No data rows found in workbook.")
        return

    headers = [str(c).strip().lower() if c else "" for c in rows[0]]
    print("Detected headers:", headers)

    col_idx = {h: i for i, h in enumerate(headers) if h}

    db = SessionLocal()
    try:
        school = db.query(School).filter(School.id == 1).first()
        if not school:
            print("School 1 not found.")
            return

        cur_sem = db.query(Semester).filter(Semester.school_id == 1, Semester.is_current == True).first()
        if not cur_sem:
            cur_sem = db.query(Semester).filter(Semester.school_id == 1).first()
        print(f"Active Semester: ID={cur_sem.id if cur_sem else None}, Name={cur_sem.name if cur_sem else None}")

        updated_competencies = 0
        created_assignments = 0

        for r_num, row in enumerate(rows[1:], start=2):
            full_name = str(row[col_idx.get("full_name", 0)] or "").strip()
            if not full_name:
                continue

            # Look up teacher in School 1 by full_name, first+last token, or exact row index (ID = r_num + 60)
            teacher = db.query(User).filter(
                User.school_id == 1,
                (func.lower(User.username) == full_name.lower()) |
                (func.lower(User.username) == full_name.lower().replace(" ", "_"))
            ).first()

            if not teacher:
                # Try first name + last name (e.g. David Atta Boateng -> david boateng)
                parts = [p.replace("-", " ").strip() for p in full_name.lower().split() if p.strip()]
                if len(parts) >= 2:
                    first_last = f"{parts[0]} {parts[-1].split()[-1]}"
                    teacher = db.query(User).filter(
                        User.school_id == 1,
                        func.lower(User.username) == first_last
                    ).first()

            if not teacher:
                # Try 1-to-1 row offset ID fallback (Row 2 = ID 62, Row 3 = ID 63, etc.)
                expected_id = r_num + 60
                cand_by_id = db.query(User).filter(User.id == expected_id, User.school_id == 1).first()
                if cand_by_id:
                    teacher = cand_by_id

            if not teacher:
                print(f"Row {r_num}: Could not find user '{full_name}' in School 1.")
                continue

            # Check if teacher is Headmaster
            t_roles = [r.name.lower() for r in teacher.roles] if teacher.roles else []
            is_head = getattr(teacher, "responsibility_role", "") == "HEADMASTER" or any(r in ["headmaster", "headmistress", "principal"] for r in t_roles)

            # Department binding
            dept_name = str(row[col_idx.get("department", 5)] or "").strip()
            if dept_name and not teacher.department_id:
                dept = db.query(Department).filter(
                    Department.school_id == 1,
                    func.lower(Department.name) == dept_name.lower()
                ).first()
                if dept:
                    teacher.department_id = dept.id

            # Subject binding
            subj_name = str(row[col_idx.get("subject", 6)] or "").strip()
            matched_subj = None
            if subj_name:
                matched_subj = db.query(Subject).filter(
                    (func.lower(Subject.name) == subj_name.lower()) |
                    (func.lower(Subject.code) == subj_name.lower())
                ).first()

                if matched_subj:
                    teacher.primary_subject_id = matched_subj.id
                    if matched_subj not in teacher.qualified_subjects:
                        teacher.qualified_subjects.append(matched_subj)
                    updated_competencies += 1
                else:
                    print(f"Row {r_num}: Subject '{subj_name}' not matched in DB.")

            # Form class & initial assignment binding
            class_name = str(row[col_idx.get("form_class", 7)] or "").strip()
            if class_name:
                matched_cls = db.query(ClassSection).filter(
                    ClassSection.school_id == 1,
                    (func.lower(ClassSection.name) == class_name.lower()) |
                    (func.lower(ClassSection.name) == f"form 1 {class_name.lower()}")
                ).first()

                if matched_cls:
                    # Link Form Master if not already linked
                    if not matched_cls.form_master_id:
                        matched_cls.form_master_id = teacher.id

                    # Create TeacherAssignment if teacher teaches a subject and is not exempt headmaster
                    if matched_subj and cur_sem and not is_head:
                        existing_ta = db.query(TeacherAssignment).filter(
                            TeacherAssignment.teacher_id == teacher.id,
                            TeacherAssignment.subject_id == matched_subj.id,
                            TeacherAssignment.class_section_id == matched_cls.id,
                            TeacherAssignment.semester_id == cur_sem.id
                        ).first()

                        if not existing_ta:
                            new_ta = TeacherAssignment(
                                teacher_id=teacher.id,
                                subject_id=matched_subj.id,
                                class_section_id=matched_cls.id,
                                semester_id=cur_sem.id
                            )
                            db.add(new_ta)
                            created_assignments += 1
                else:
                    print(f"Row {r_num}: Class '{class_name}' not found for School 1.")

        db.commit()
        print(f"\n[SYNC COMPLETED]")
        print(f"Teachers updated with primary/qualified subjects: {updated_competencies}")
        print(f"Initial TeacherAssignment rows created: {created_assignments}")

    except Exception as e:
        db.rollback()
        print(f"Sync failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    sync_staff_from_excel()
