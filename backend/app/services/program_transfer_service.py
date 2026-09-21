from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import (
    Student, Program, ClassSection, ElectiveCombination, Subject, Score,
    Semester, School, User, AuditLog, AcademicYear
)
from .subject_enrollment import SubjectEnrollmentService

ADMIN_ROLES = {
    "admin", "super_admin", "proprietor", "headmaster", "headmistress",
    "assistant_headmaster_academic", "assistant_head_academic",
    "assistant_headmaster_admin", "assistant_head_admin"
}


class ProgramTransferService:
    @staticmethod
    def get_program_capacities(db: Session, school_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Returns live enrollment statistics and capacity matrices for all active programs in the school.
        """
        prog_query = db.query(Program)
        if school_id:
            prog_query = prog_query.filter(Program.school_id == school_id)
        programs = prog_query.order_by(Program.name).all()

        results = []
        for p in programs:
            # Count active students in Form 1 for this program
            enrolled_f1 = db.query(Student).filter(
                Student.program_id == p.id,
                Student.form == 1,
                Student.is_active == True
            ).count()

            # Active elective combinations
            combos = db.query(ElectiveCombination).filter(
                ElectiveCombination.program_id == p.id,
                ElectiveCombination.is_active == True
            ).all()

            combo_list = []
            for c in combos:
                combo_enrolled = db.query(Student).filter(
                    Student.elective_combination_id == c.id,
                    Student.is_active == True
                ).count()
                cap = c.capacity or 50
                remaining = max(0, cap - combo_enrolled)
                combo_list.append({
                    "id": c.id,
                    "name": c.name,
                    "code": c.code,
                    "capacity": cap,
                    "enrolled_count": combo_enrolled,
                    "remaining_seats": remaining,
                    "is_full": combo_enrolled >= cap,
                    "class_section_id": c.class_section_id,
                    "class_section_name": c.class_section.name if c.class_section else None,
                    "subjects": [{"id": s.id, "name": s.name, "code": s.code} for s in c.subjects]
                })

            results.append({
                "program_id": p.id,
                "program_name": p.name,
                "program_code": p.code,
                "form1_enrolled": enrolled_f1,
                "combinations": combo_list
            })

        return results

    @classmethod
    def reassign_student_program(
        cls,
        db: Session,
        student_id: int,
        new_program_id: int,
        new_elective_combination_id: Optional[int] = None,
        new_class_section_id: Optional[int] = None,
        approving_officer: Optional[str] = None,
        reason: Optional[str] = None,
        force_override: bool = False,
        current_user: Optional[User] = None,
        school_id: Optional[int] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Atomically executes an Academic Program Reassignment for a student.
        Handles class section relocation, elective package reconfiguration,
        score scoresheet realignments, and regulatory audit logging.
        """
        # 1. Role Authorization Check
        if current_user:
            role_names = [r.name.lower() for r in current_user.roles] if hasattr(current_user, 'roles') and current_user.roles else []
            if not any(r in ADMIN_ROLES for r in role_names):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied: Only Head of Academics, Headmaster/Headmistress, or Administrators can authorize a program reassignment."
                )

        # 2. Fetch Student with Tenant Check
        stud_query = db.query(Student).filter(Student.id == student_id)
        if school_id:
            stud_query = stud_query.filter(Student.school_id == school_id)
        student = stud_query.first()

        if not student:
            raise HTTPException(status_code=404, detail="Student record not found.")

        # 3. School Mode Enforcement
        if student.school_id:
            sc = db.query(School).filter(School.id == student.school_id).first()
            if sc and sc.school_mode == "BASIC_ONLY":
                raise HTTPException(
                    status_code=400,
                    detail="Academic Program reassignment is only applicable to Senior High / STEM / Technical institutions."
                )

        # 4. Fetch Target Program
        target_prog = db.query(Program).filter(Program.id == new_program_id).first()
        if not target_prog:
            raise HTTPException(status_code=404, detail="Target academic program not found.")

        if student.school_id and target_prog.school_id and target_prog.school_id != student.school_id:
            raise HTTPException(status_code=400, detail="Target program does not belong to the student's registered institution.")

        # Record Previous State for Audit & Tracking
        old_prog_id = student.program_id
        old_prog_name = student.program.name if student.program else "Unassigned"
        old_class_name = student.class_section.name if student.class_section else "Unassigned"
        old_combo_name = student.elective_combination or "None"

        # 5. Resolve Elective Combination & Validate Capacity
        target_combo = None
        if new_elective_combination_id:
            target_combo = db.query(ElectiveCombination).filter(
                ElectiveCombination.id == new_elective_combination_id,
                ElectiveCombination.program_id == new_program_id
            ).first()
            if not target_combo:
                raise HTTPException(
                    status_code=400,
                    detail="Selected Elective Combination does not belong to the target academic program."
                )
        else:
            # Pick first active combination under target program
            target_combo = db.query(ElectiveCombination).filter(
                ElectiveCombination.program_id == new_program_id,
                ElectiveCombination.is_active == True
            ).first()

        if target_combo:
            cap = target_combo.capacity or 50
            current_count = db.query(Student).filter(
                Student.elective_combination_id == target_combo.id,
                Student.is_active == True,
                Student.id != student.id
            ).count()

            if current_count >= cap and not force_override:
                raise HTTPException(
                    status_code=400,
                    detail=f"Target Elective Package '{target_combo.name}' has reached its maximum seat capacity ({cap} seats). Headmaster / Academic Head override is required to exceed capacity."
                )

        # 6. Resolve Target Class Stream
        target_sec = None
        if new_class_section_id:
            target_sec = db.query(ClassSection).filter(
                ClassSection.id == new_class_section_id,
                ClassSection.program_id == new_program_id
            ).first()
        elif target_combo and target_combo.class_section_id:
            target_sec = db.query(ClassSection).filter(ClassSection.id == target_combo.class_section_id).first()

        if not target_sec:
            # Fallback: Find open Form 1 stream for target program
            target_sec = db.query(ClassSection).filter(
                ClassSection.program_id == new_program_id
            ).first()

        # 7. Apply Atomic State Changes
        officer_name = (
            approving_officer.strip() if approving_officer and approving_officer.strip()
            else (getattr(current_user, "full_name", None) or getattr(current_user, "username", "Head of Academics"))
        )
        reason_text = reason.strip() if reason and reason.strip() else "Academic counseling & parental appeal"

        now_dt = datetime.now()
        student.program_id = new_program_id
        student.program_reassigned_at = now_dt
        student.program_reassigned_by = officer_name

        if target_combo:
            student.elective_combination_id = target_combo.id
            student.elective_combination = target_combo.name

        if target_sec:
            student.class_section_id = target_sec.id

        # 8. Realign Continuous Assessment Scoresheets
        # Retain core subjects; replace old electives with new electives
        sem_ids_to_process = set()
        active_sem_ids = [r[0] for r in db.query(Score.semester_id).filter(Score.student_id == student.id).distinct().all()]
        if active_sem_ids:
            sem_ids_to_process.update(active_sem_ids)
        else:
            sem_q = db.query(Semester).filter(Semester.is_current == True)
            if student.academic_year:
                sem_q = sem_q.join(AcademicYear).filter(AcademicYear.label == student.academic_year)
            current_sem = sem_q.order_by(Semester.id.desc()).first()
            if not current_sem:
                current_sem = db.query(Semester).filter(Semester.is_current == True).order_by(Semester.id.desc()).first()
            if not current_sem:
                current_sem = db.query(Semester).order_by(Semester.id.desc()).first()
            if current_sem:
                sem_ids_to_process.add(current_sem.id)

        if sem_ids_to_process:
            # Get new target subject IDs
            new_subjects = SubjectEnrollmentService.get_enrolled_subjects_for_student(db, student)
            new_subject_ids = {s.id for s in new_subjects}

            for s_id in sem_ids_to_process:
                # Find existing scores for student in this semester
                existing_scores = db.query(Score).filter(
                    Score.student_id == student.id,
                    Score.semester_id == s_id
                ).all()

                for sc_rec in existing_scores:
                    # If this score's subject is an old elective not in the new track
                    if sc_rec.subject_id not in new_subject_ids:
                        db.delete(sc_rec)

                # Auto-enroll in new track subjects for this semester
                SubjectEnrollmentService.enroll_student_in_track_subjects(db, student, s_id)

        # 9. Log Immutable Audit Record
        new_class_display = target_sec.name if target_sec else "Unassigned"
        new_combo_display = target_combo.name if target_combo else "Standard"

        audit_details = (
            f"Student '{student.full_name}' ({student.student_code or student.bece_index_number or student.id}): "
            f"Program reassigned: '{old_prog_name}' → '{target_prog.name}'. "
            f"Class Stream: '{old_class_name}' → '{new_class_display}'. "
            f"Elective: '{old_combo_name}' → '{new_combo_display}'. "
            f"Approving Authority: {officer_name}. "
            f"Reason: {reason_text}. "
            f"Override: {'Yes' if force_override else 'No'}."
        )

        audit_entry = AuditLog(
            action="PROGRAM_REASSIGNMENT",
            entity_type="student",
            entity_id=student.id,
            details=audit_details,
            actor_id=current_user.id if current_user else None,
            actor_username=current_user.username if current_user else "Secretariat",
            actor_role=current_user.roles[0].name if (current_user and current_user.roles) else "admin",
            school_id=student.school_id,
            ip_address=ip_address or "127.0.0.1",
            created_at=now_dt
        )
        db.add(audit_entry)

        db.commit()
        db.refresh(student)

        return {
            "success": True,
            "message": f"Successfully reassigned {student.full_name} from {old_prog_name} to {target_prog.name}!",
            "student_id": student.id,
            "full_name": student.full_name,
            "bece_index_number": student.bece_index_number,
            "previous_program": old_prog_name,
            "new_program": target_prog.name,
            "new_program_id": target_prog.id,
            "new_class_name": new_class_display,
            "new_class_section_id": student.class_section_id,
            "new_elective_combination": new_combo_display,
            "approving_officer": officer_name,
            "reassigned_at": now_dt.isoformat()
        }
