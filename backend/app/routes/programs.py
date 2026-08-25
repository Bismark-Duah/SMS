from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..models import Program, Subject, User, ClassSection, ElectiveCombination
from ..schemas import (
    ProgramCreate,
    ProgramCoreSubjectsUpdate,
    ElectiveCombinationCreate,
    ElectiveCombinationUpdate,
)
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

# --- Program Curriculum & Core Subjects ---

@router.get("/{program_id}/curriculum")
def get_program_curriculum(
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

    # Core subjects: if not custom-configured yet, default to all core subjects
    configured_cores = program.core_subjects
    if not configured_cores:
        default_cores_query = db.query(Subject).filter(Subject.is_core == True)
        if school_id is not None and hasattr(Subject, "school_id"):
            default_cores_query = default_cores_query.filter((Subject.school_id == school_id) | (Subject.school_id == None))
        configured_cores = default_cores_query.all()

    # Combinations
    combinations = []
    for combo in program.elective_combinations:
        combinations.append({
            "id": combo.id,
            "name": combo.name,
            "code": combo.code,
            "class_section_id": combo.class_section_id,
            "class_section_name": combo.class_section.name if combo.class_section else "Unassigned",
            "capacity": combo.capacity,
            "is_active": combo.is_active,
            "subjects": [
                {"id": s.id, "name": s.name, "code": s.code, "is_core": s.is_core}
                for s in combo.subjects
            ],
        })

    # Available subjects for selection
    sub_query = db.query(Subject)
    if school_id is not None and hasattr(Subject, "school_id"):
        sub_query = sub_query.filter((Subject.school_id == school_id) | (Subject.school_id == None))
    all_subjects = sub_query.all()

    # Available class sections for this program
    sec_query = db.query(ClassSection).filter((ClassSection.program_id == program_id) | (ClassSection.program_id == None))
    if school_id is not None and hasattr(ClassSection, "school_id"):
        sec_query = sec_query.filter(ClassSection.school_id == school_id)
    available_sections = sec_query.all()

    return {
        "program_id": program.id,
        "program_name": program.name,
        "program_code": program.code,
        "core_subjects": [
            {"id": s.id, "name": s.name, "code": s.code, "is_core": s.is_core}
            for s in configured_cores
        ],
        "elective_combinations": combinations,
        "all_subjects": [
            {"id": s.id, "name": s.name, "code": s.code, "is_core": s.is_core, "category": getattr(s, "category", "General")}
            for s in all_subjects
        ],
        "available_sections": [
            {"id": sec.id, "name": sec.name, "program_id": sec.program_id}
            for sec in available_sections
        ],
    }

@router.post("/{program_id}/core-subjects")
def set_program_core_subjects(
    program_id: int,
    payload: ProgramCoreSubjectsUpdate,
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

    subjects = db.query(Subject).filter(Subject.id.in_(payload.subject_ids)).all()
    program.core_subjects = subjects
    db.commit()
    return {
        "message": f"Updated core subjects for {program.name}",
        "core_subjects": [{"id": s.id, "name": s.name, "code": s.code} for s in program.core_subjects]
    }

# --- Elective Combinations CRUD ---

@router.get("/{program_id}/elective-combinations")
def list_elective_combinations(
    program_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ElectiveCombination).filter(ElectiveCombination.program_id == program_id)
    school_id = get_school_id(current_user)
    if school_id is not None and hasattr(ElectiveCombination, "school_id"):
        query = query.filter((ElectiveCombination.school_id == school_id) | (ElectiveCombination.school_id == None))
    
    combos = query.all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "code": c.code,
            "class_section_id": c.class_section_id,
            "class_section_name": c.class_section.name if c.class_section else "Unassigned",
            "capacity": c.capacity,
            "is_active": c.is_active,
            "subjects": [{"id": s.id, "name": s.name, "code": s.code} for s in c.subjects]
        }
        for c in combos
    ]

@router.post("/{program_id}/elective-combinations")
def create_elective_combination(
    program_id: int,
    payload: ElectiveCombinationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    prog = db.query(Program).filter(Program.id == program_id).first()
    if not prog:
        raise HTTPException(status_code=404, detail="Program not found")

    combo = ElectiveCombination(
        name=payload.name,
        code=payload.code or f"{prog.code or 'PROG'}-{len(prog.elective_combinations) + 1}",
        program_id=program_id,
        class_section_id=payload.class_section_id,
        capacity=payload.capacity or 50,
        is_active=payload.is_active if payload.is_active is not None else True,
        school_id=school_id,
    )

    if payload.subject_ids:
        subjects = db.query(Subject).filter(Subject.id.in_(payload.subject_ids)).all()
        combo.subjects = subjects

    db.add(combo)
    db.commit()
    db.refresh(combo)

    return {
        "id": combo.id,
        "name": combo.name,
        "code": combo.code,
        "class_section_id": combo.class_section_id,
        "class_section_name": combo.class_section.name if combo.class_section else "Unassigned",
        "capacity": combo.capacity,
        "is_active": combo.is_active,
        "subjects": [{"id": s.id, "name": s.name, "code": s.code} for s in combo.subjects]
    }

@router.put("/elective-combinations/{combo_id}")
def update_elective_combination(
    combo_id: int,
    payload: ElectiveCombinationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    combo = db.query(ElectiveCombination).filter(ElectiveCombination.id == combo_id).first()
    if not combo:
        raise HTTPException(status_code=404, detail="Elective combination not found")

    if payload.name is not None:
        combo.name = payload.name
    if payload.code is not None:
        combo.code = payload.code
    if payload.class_section_id is not None:
        combo.class_section_id = payload.class_section_id
    if payload.capacity is not None:
        combo.capacity = payload.capacity
    if payload.is_active is not None:
        combo.is_active = payload.is_active
    if payload.subject_ids is not None:
        subjects = db.query(Subject).filter(Subject.id.in_(payload.subject_ids)).all()
        combo.subjects = subjects

    db.commit()
    db.refresh(combo)

    return {
        "id": combo.id,
        "name": combo.name,
        "code": combo.code,
        "class_section_id": combo.class_section_id,
        "class_section_name": combo.class_section.name if combo.class_section else "Unassigned",
        "capacity": combo.capacity,
        "is_active": combo.is_active,
        "subjects": [{"id": s.id, "name": s.name, "code": s.code} for s in combo.subjects]
    }

@router.delete("/elective-combinations/{combo_id}")
def delete_elective_combination(
    combo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    combo = db.query(ElectiveCombination).filter(ElectiveCombination.id == combo_id).first()
    if not combo:
        raise HTTPException(status_code=404, detail="Elective combination not found")
    
    db.delete(combo)
    db.commit()
    return {"message": "Elective combination deleted"}

# --- Legacy Subject Assignment Compatibility ---

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
    
    subjects = db.query(Subject).filter(Subject.id.in_(payload)).all()
    program.subjects = subjects
    db.commit()
    return {"message": f"Subjects updated for program {program.name}"}
