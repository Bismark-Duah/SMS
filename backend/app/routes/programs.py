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

def _auto_sync_program_from_class_sections(p: Program, db: Session, school_id: Optional[int] = None):
    sections = db.query(ClassSection).filter(ClassSection.program_id == p.id).all()
    changed = False
    for sec in sections:
        if sec.subjects:
            elective_subs = [s for s in sec.subjects if not s.is_core]
            core_subs = [s for s in sec.subjects if s.is_core]

            if elective_subs:
                existing_combo = db.query(ElectiveCombination).filter(
                    ElectiveCombination.program_id == p.id,
                    ElectiveCombination.class_section_id == sec.id
                ).first()
                if not existing_combo:
                    base_code = p.code or "PROG"
                    combo_code = f"{base_code}-{sec.name.replace(' ', '')}"
                    combo_name = f"{p.name} ({sec.name})"
                    new_combo = ElectiveCombination(
                        name=combo_name,
                        code=combo_code,
                        program_id=p.id,
                        class_section_id=sec.id,
                        capacity=60,
                        is_active=True,
                        subjects=elective_subs
                    )
                    if school_id is not None and hasattr(ElectiveCombination, "school_id"):
                        new_combo.school_id = school_id
                    db.add(new_combo)
                    changed = True
                else:
                    if not existing_combo.subjects or len(existing_combo.subjects) != len(elective_subs):
                        existing_combo.subjects = elective_subs
                        changed = True

            if core_subs and not p.core_subjects:
                p.core_subjects = core_subs
                changed = True
    if changed:
        db.commit()
        db.refresh(p)

@router.get("/")
def list_programs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    if school_id:
        sch = db.query(School).filter(School.id == school_id).first()
        if sch and sch.school_mode == "BASIC_ONLY":
            return []

    query = db.query(Program)
    if school_id is not None and hasattr(Program, "school_id"):
        query = query.filter(Program.school_id == school_id)
    programs = query.order_by(Program.name.asc()).all()

    result = []
    for p in programs:
        # Retroactively auto-heal any packages from configured class sections
        _auto_sync_program_from_class_sections(p, db, school_id)

        combos = p.elective_combinations or []
        cores = p.core_subjects or []
        
        all_elective_sub_ids = set()
        packages_summary = []
        for c in combos:
            sub_names = [s.name for s in c.subjects]
            all_elective_sub_ids.update(s.id for s in c.subjects)
            packages_summary.append({
                "id": c.id,
                "name": c.name,
                "stream": c.class_section.name if c.class_section else "Unassigned",
                "subject_count": len(c.subjects),
                "subjects": sub_names
            })
            
        result.append({
            "id": p.id,
            "name": p.name,
            "code": p.code,
            "core_count": len(cores),
            "core_subjects": [{"id": s.id, "name": s.name, "code": s.code} for s in cores],
            "package_count": len(combos),
            "unique_electives_count": len(all_elective_sub_ids),
            "packages_summary": packages_summary
        })
    return result

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

    _auto_sync_program_from_class_sections(program, db, school_id)

    # Filter strictly for Senior High School (SHS/STEM) subjects, excluding Basic & KG
    shs_filter = [
        (Subject.school_level.in_(["SHS", "STEM"]) | (Subject.school_level == None)),
        ~Subject.code.ilike("%-BAS"),
        ~Subject.code.ilike("%-KG"),
        ~Subject.code.ilike("%-PRIM"),
        ~Subject.code.ilike("%-JHS"),
    ]

    # Core subjects: if not custom-configured yet, default to SHS core subjects
    configured_cores = program.core_subjects
    if not configured_cores:
        default_cores_query = db.query(Subject).filter(Subject.is_core == True, *shs_filter)
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

    # Available subjects for selection (SHS & STEM only)
    sub_query = db.query(Subject).filter(*shs_filter)
    if school_id is not None and hasattr(Subject, "school_id"):
        from ..models import School
        sch = db.query(School).filter(School.id == school_id).first()
        if sch and sch.active_subjects:
            active_ids = [s.id for s in sch.active_subjects]
            sub_query = sub_query.filter((Subject.id.in_(active_ids)) | (Subject.school_id == school_id))
        else:
            sub_query = sub_query.filter((Subject.school_id == school_id) | (Subject.school_id == None))
    all_subjects = sub_query.order_by(Subject.name).all()

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
            {"id": s.id, "name": s.name, "code": s.code, "is_core": s.is_core, "category": getattr(s, "category", "General"), "school_level": getattr(s, "school_level", "SHS")}
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

@router.post("/{program_id}/quick-stream")
def create_quick_stream(
    program_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    program = db.query(Program).filter(Program.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
        
    stream_name = payload.get("name", "").strip()
    if not stream_name:
        raise HTTPException(status_code=400, detail="Stream name is required")
        
    stage_id = payload.get("stage_id")
    if not stage_id:
        from ..models import SchoolStage
        shs_stage = db.query(SchoolStage).filter(
            (SchoolStage.name.ilike("%Form 1%")) | (SchoolStage.name.ilike("%SHS%")) | (SchoolStage.school_type == "SHS")
        ).first()
        if shs_stage:
            stage_id = shs_stage.id
            
    new_section = ClassSection(
        name=stream_name,
        stage_id=stage_id,
        program_id=program_id
    )
    if school_id is not None and hasattr(ClassSection, "school_id"):
        new_section.school_id = school_id
        
    db.add(new_section)
    db.commit()
    db.refresh(new_section)
    
    return {
        "id": new_section.id,
        "name": new_section.name,
        "program_id": new_section.program_id,
        "stage_id": new_section.stage_id
    }

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
        
    subjects = list(program.subjects)
    if not subjects:
        # Collect from core subjects and combinations
        collected = {}
        for cs in program.core_subjects:
            collected[cs.id] = cs
        for ec in program.elective_combinations:
            for es in ec.subjects:
                collected[es.id] = es
        subjects = list(collected.values())
        
    return [
        {
            "id": sub.id,
            "name": sub.name,
            "code": sub.code,
            "is_core": sub.is_core
        }
        for sub in subjects
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
