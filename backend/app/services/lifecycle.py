from sqlalchemy.orm import Session
from ..models import Student, SchoolStage

class LifecycleService:
    @staticmethod
    def promote_students(db: Session, stage_id: int = None) -> dict:
        """
        Promotes all active students to the next form.
        If a student is at the maximum form for their stage (e.g. JHS 3), 
        they are marked as 'Graduated' or moved to a 'Pending' state.
        """
        query = db.query(Student).filter(Student.is_active == True)
        if stage_id:
            query = query.join(Student.class_section).filter(Student.class_section.stage_id == stage_id)
            
        students = query.all()
        promoted_count = 0
        graduated_count = 0
        
        for student in students:
            # Simple logic: increase Form
            # SHS typically has Form 1, 2, 3
            # Basic has Class 1-6, JHS 1-3
            max_form = 3 if student.class_section.stage.name in ["JHS", "SHS"] else 6
            
            if student.form is None:
                student.form = 1

            if student.form < max_form:
                student.form += 1
                promoted_count += 1
            else:
                # Graduate or move to next stage (manual intervention often required)
                student.is_active = False # Mark as inactive (graduated) for now
                graduated_count += 1
                
        db.commit()
        return {
            "status": "success",
            "promoted": promoted_count,
            "graduated": graduated_count
        }
