from sqlalchemy.orm import Session
from typing import List, Optional
from ..models import Student, Subject, Score, Semester, AcademicYear, Program, ElectiveCombination

class SubjectEnrollmentService:
    @staticmethod
    def get_enrolled_subjects_for_student(db: Session, student: Student) -> List[Subject]:
        """
        Resolves the exact subjects a student is enrolled in:
        1. Track Core Subjects (from student.program.core_subjects or default cores)
        2. Elective Combination Subjects (from student.elective_combination_rel.subjects)
        """
        enrolled_subjects = []
        seen_subject_ids = set()

        # 1. Track Core Subjects
        if student.program and student.program.core_subjects:
            for sub in student.program.core_subjects:
                if sub.id not in seen_subject_ids:
                    enrolled_subjects.append(sub)
                    seen_subject_ids.add(sub.id)
        else:
            # Fallback default core subjects for SHS
            default_cores = db.query(Subject).filter(Subject.is_core == True).all()
            for sub in default_cores:
                if sub.id not in seen_subject_ids:
                    enrolled_subjects.append(sub)
                    seen_subject_ids.add(sub.id)

        # 2. Elective Combination Subjects
        if student.elective_combination_rel and student.elective_combination_rel.subjects:
            for sub in student.elective_combination_rel.subjects:
                if sub.id not in seen_subject_ids:
                    enrolled_subjects.append(sub)
                    seen_subject_ids.add(sub.id)

        return enrolled_subjects

    @classmethod
    def enroll_student_in_track_subjects(
        cls,
        db: Session,
        student: Student,
        semester_id: Optional[int] = None
    ) -> List[Score]:
        """
        Auto-generates / ensures Score records exist for all enrolled subjects
        for this student in the given semester.
        """
        if not semester_id:
            current_sem = db.query(Semester).filter(Semester.is_current == True).first()
            if not current_sem:
                current_sem = db.query(Semester).order_by(Semester.id.desc()).first()
            if not current_sem:
                return []
            semester_id = current_sem.id

        enrolled_subjects = cls.get_enrolled_subjects_for_student(db, student)
        created_scores = []

        for sub in enrolled_subjects:
            existing = db.query(Score).filter(
                Score.student_id == student.id,
                Score.subject_id == sub.id,
                Score.semester_id == semester_id
            ).first()

            if not existing:
                score = Score(
                    student_id=student.id,
                    subject_id=sub.id,
                    semester_id=semester_id,
                    class_score=0.0,
                    exam_score=0.0,
                    total_score=0.0,
                    grade="F9" if getattr(sub, "is_core", True) else "F9",
                    remark="Ungraded"
                )
                db.add(score)
                created_scores.append(score)

        if created_scores:
            db.commit()

        return created_scores
