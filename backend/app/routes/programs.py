from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Program, Subject, User
from ..schemas import ProgramCreate
from ..dependencies import get_current_user, get_school_id

router = APIRouter()

@router.get("/")
def list_programs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(Program)
    if school_id is not None and hasattr(Program, "school_id"):
        query = query.filter(Program.school_id == school_id)
    return query.all()

@router.post("/")
def create_program(
    payload: ProgramCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    data = payload.dict()
    if school_id is not None and hasattr(Program, "school_id"):
        data["school_id"] = school_id
    db_program = Program(**data)
    db.add(db_program)
    db.commit()
    db.refresh(db_program)
    return db_program

@router.get("/{program_id}")
def get_program(
    program_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(Program).filter(Program.id == program_id)
    if school_id is not None and hasattr(Program, "school_id"):
        query = query.filter(Program.school_id == school_id)
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Program not found")
    return item

@router.delete("/{program_id}")
def delete_program(
    program_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(Program).filter(Program.id == program_id)
    if school_id is not None and hasattr(Program, "school_id"):
        query = query.filter(Program.school_id == school_id)
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Program not found")
    db.delete(item)
    db.commit()
    return {"message": "Program deleted"}

@router.get("/{program_id}/subjects")
def get_program_subjects(
    program_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(Program).filter(Program.id == program_id)
    if school_id is not None and hasattr(Program, "school_id"):
        query = query.filter(Program.school_id == school_id)
    program = query.first()
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    return [
        {
            "id": sub.id,
            "name": sub.name,
            "code": sub.code,
            "is_core": sub.is_core
        }
        for sub in program.subjects
    ]

@router.post("/{program_id}/subjects")
def set_program_subjects(
    program_id: int,
    payload: list[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(Program).filter(Program.id == program_id)
    if school_id is not None and hasattr(Program, "school_id"):
        query = query.filter(Program.school_id == school_id)
    program = query.first()
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    
    # Load the subjects from database
    subjects = db.query(Subject).filter(Subject.id.in_(payload)).all()
    
    # Associate them
    program.subjects = subjects
    db.commit()
    return {"message": f"Subjects updated for program {program.name}"}
