from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..models import ClassSection, SchoolStage, Setting, Subject, User, School
from ..schemas import ClassSectionCreate, SchoolStageCreate
from ..dependencies import get_current_user, get_school_id

router = APIRouter()

def _get_school_mode(db: Session, school_id: Optional[int] = None) -> str:
    if school_id:
        sch = db.query(School).filter(School.id == school_id).first()
        if sch and sch.school_mode:
            return sch.school_mode
    setting = db.query(Setting).filter(Setting.key == "school_mode").first()
    return setting.value if setting and setting.value else "COMBINED"

# --- Stages ---
@router.get("/stages")
def list_stages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    mode = _get_school_mode(db, school_id)
    query = db.query(SchoolStage)
    if school_id is not None and hasattr(SchoolStage, "school_id"):
        query = query.filter(SchoolStage.school_id == school_id)
    if mode == "BASIC_ONLY":
        query = query.filter(SchoolStage.school_type == "Basic")
    elif mode == "SHS_ONLY":
        query = query.filter(SchoolStage.school_type == "SHS")
    return query.all()

@router.post("/stages")
def create_stage(
    payload: SchoolStageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    data = payload.dict()
    if school_id is not None and hasattr(SchoolStage, "school_id"):
        data["school_id"] = school_id
    db_stage = SchoolStage(**data)
    db.add(db_stage)
    db.commit()
    db.refresh(db_stage)
    return db_stage

# --- Sections ---
@router.get("/my-classes")
def get_my_classes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from ..dependencies import get_user_assigned_scope
    scope = get_user_assigned_scope(current_user, db)
    if scope["is_admin"]:
        return list_sections(db=db, current_user=current_user)
    if not scope["class_ids"]:
        return []
    sections = db.query(ClassSection).filter(ClassSection.id.in_(scope["class_ids"])).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "stage_id": s.stage_id,
            "stage_name": s.stage.name if s.stage else None,
            "school_type": s.stage.school_type if s.stage else None,
            "program_id": s.program_id,
            "program_name": s.program.name if s.program else None,
            "form_master_id": s.form_master_id,
            "form_master_name": s.form_master.username if s.form_master else None,
        }
        for s in sections
    ]


@router.get("/my-form-classes")
def get_my_form_classes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns only the class sections where the logged-in user is assigned as Form Master.
    Admins get all class sections (same as /classes/).
    Used to populate the Daily Register class dropdown on the attendance page.
    """
    from ..dependencies import get_form_master_class_ids
    form_class_ids = get_form_master_class_ids(current_user, db)

    # Admins get all classes
    if form_class_ids is None:
        return list_sections(db=db, current_user=current_user)

    if not form_class_ids:
        return []

    sections = db.query(ClassSection).filter(ClassSection.id.in_(form_class_ids)).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "stage_id": s.stage_id,
            "stage_name": s.stage.name if s.stage else None,
            "school_type": s.stage.school_type if s.stage else None,
            "program_id": s.program_id,
            "program_name": s.program.name if s.program else None,
            "form_master_id": s.form_master_id,
            "form_master_name": s.form_master.username if s.form_master else None,
        }
        for s in sections
    ]


@router.get("/")
def list_sections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from ..dependencies import get_user_assigned_scope

    school_id = get_school_id(current_user)
    mode = _get_school_mode(db, school_id)
    query = db.query(ClassSection).join(ClassSection.stage)
    if school_id is not None and hasattr(ClassSection, "school_id"):
        query = query.filter(ClassSection.school_id == school_id)
    if mode == "BASIC_ONLY":
        query = query.filter(SchoolStage.school_type == "Basic")
    elif mode == "SHS_ONLY":
        query = query.filter(SchoolStage.school_type == "SHS")

    # ── Role-based scoping ─────────────────────────────────────────────────────
    scope = get_user_assigned_scope(current_user, db)
    if not scope["is_admin"]:
        # HODs (dept_ids populated) need school-wide class visibility for assignments management
        is_hod_by_assignment = bool(scope["department_ids"])
        if not is_hod_by_assignment:
            # Regular teachers & form masters: restrict to only their assigned classes
            if scope["class_ids"]:
                query = query.filter(ClassSection.id.in_(scope["class_ids"]))
            else:
                return []

    sections = query.all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "stage_id": s.stage_id,
            "stage_name": s.stage.name if s.stage else None,
            "school_type": s.stage.school_type if s.stage else None,
            "program_id": s.program_id,
            "program_name": s.program.name if s.program else None,
            "form_master_id": s.form_master_id,
            "form_master_name": s.form_master.username if s.form_master else None,
        }
        for s in sections
    ]


@router.post("/")
def create_section(
    payload: ClassSectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    section_kwargs = {
        "name": payload.name,
        "stage_id": payload.stage_id,
        "program_id": payload.program_id,
        "form_master_id": payload.form_master_id,
    }
    if school_id is not None and hasattr(ClassSection, "school_id"):
        section_kwargs["school_id"] = school_id
    db_section = ClassSection(**section_kwargs)
    db.add(db_section)
    db.commit()
    db.refresh(db_section)
    return {
        "id": db_section.id,
        "name": db_section.name,
        "stage_id": db_section.stage_id,
        "stage_name": db_section.stage.name if db_section.stage else None,
        "school_type": db_section.stage.school_type if db_section.stage else None,
        "program_id": db_section.program_id,
        "program_name": db_section.program.name if db_section.program else None,
        "form_master_id": db_section.form_master_id,
        "form_master_name": db_section.form_master.username if db_section.form_master else None,
    }

@router.get("/{section_id}")
def get_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(ClassSection).filter(ClassSection.id == section_id)
    if school_id is not None and hasattr(ClassSection, "school_id"):
        query = query.filter(ClassSection.school_id == school_id)
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Section not found")
    return {
        "id": item.id,
        "name": item.name,
        "stage_id": item.stage_id,
        "stage_name": item.stage.name if item.stage else None,
        "school_type": item.stage.school_type if item.stage else None,
        "program_id": item.program_id,
        "program_name": item.program.name if item.program else None,
        "form_master_id": item.form_master_id,
        "form_master_name": item.form_master.username if item.form_master else None,
    }

@router.put("/{section_id}")
def update_section(
    section_id: int,
    payload: ClassSectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(ClassSection).filter(ClassSection.id == section_id)
    if school_id is not None and hasattr(ClassSection, "school_id"):
        query = query.filter(ClassSection.school_id == school_id)
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Section not found")
    
    item.name = payload.name
    item.stage_id = payload.stage_id
    item.program_id = payload.program_id
    item.form_master_id = payload.form_master_id
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "name": item.name,
        "stage_id": item.stage_id,
        "stage_name": item.stage.name if item.stage else None,
        "school_type": item.stage.school_type if item.stage else None,
        "program_id": item.program_id,
        "program_name": item.program.name if item.program else None,
        "form_master_id": item.form_master_id,
        "form_master_name": item.form_master.username if item.form_master else None,
    }

@router.get("/{section_id}/subjects")
def get_class_subjects(
    section_id: int,
    raw: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(ClassSection).filter(ClassSection.id == section_id)
    if school_id is not None and hasattr(ClassSection, "school_id"):
        query = query.filter(ClassSection.school_id == school_id)
    section = query.first()
    if not section:
        raise HTTPException(status_code=404, detail="Class section not found")
    
    subjects = section.subjects
    if not raw and not subjects and section.program_id:
        subjects = section.program.subjects
        
    return [
        {
            "id": sub.id,
            "name": sub.name,
            "code": sub.code,
            "is_core": sub.is_core
        }
        for sub in subjects
    ]

@router.post("/{section_id}/subjects")
def set_class_subjects(
    section_id: int,
    payload: list[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(ClassSection).filter(ClassSection.id == section_id)
    if school_id is not None and hasattr(ClassSection, "school_id"):
        query = query.filter(ClassSection.school_id == school_id)
    section = query.first()
    if not section:
        raise HTTPException(status_code=404, detail="Class section not found")
    
    # Load the subjects from database
    subjects = db.query(Subject).filter(Subject.id.in_(payload)).all()
    
    # Associate them
    section.subjects = subjects
    db.commit()
    return {"message": f"Subjects updated for class {section.name}"}

@router.delete("/{section_id}")
def delete_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = get_school_id(current_user)
    query = db.query(ClassSection).filter(ClassSection.id == section_id)
    if school_id is not None and hasattr(ClassSection, "school_id"):
        query = query.filter(ClassSection.school_id == school_id)
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Section not found")
    db.delete(item)
    db.commit()
    return {"message": "Section deleted"}

@router.post("/presets")
def seed_presets(db: Session = Depends(get_db)):
    mode = _get_school_mode(db)
    stages_data = [
        {"name": "Creche", "school_type": "Basic"},
        {"name": "Nursery", "school_type": "Basic"},
        {"name": "KG", "school_type": "Basic"},
        {"name": "Primary", "school_type": "Basic"},
        {"name": "JHS", "school_type": "Basic"},
        {"name": "SHS", "school_type": "SHS"},
    ]
    if mode == "BASIC_ONLY":
        stages_data = [s for s in stages_data if s["school_type"] == "Basic"]
    elif mode == "SHS_ONLY":
        stages_data = [s for s in stages_data if s["school_type"] == "SHS"]

    created_stages = {}
    for stage_info in stages_data:
        st = db.query(SchoolStage).filter(SchoolStage.name == stage_info["name"]).first()
        if not st:
            st = SchoolStage(name=stage_info["name"], school_type=stage_info["school_type"])
            db.add(st)
            db.commit()
            db.refresh(st)
        created_stages[stage_info["name"]] = st

    classes_data = [
        ("Creche", "Creche"),
        ("Nursery", "Nursery 1"),
        ("Nursery", "Nursery 2"),
        ("KG", "KG 1"),
        ("KG", "KG 2"),
        ("Primary", "Primary 1"),
        ("Primary", "Primary 2"),
        ("Primary", "Primary 3"),
        ("Primary", "Primary 4"),
        ("Primary", "Primary 5"),
        ("Primary", "Primary 6"),
        ("JHS", "JHS 1"),
        ("JHS", "JHS 2"),
        ("JHS", "JHS 3"),
        ("SHS", "Form 1"),
        ("SHS", "Form 2"),
        ("SHS", "Form 3"),
    ]
    if mode == "BASIC_ONLY":
        classes_data = [c for c in classes_data if c[0] != "SHS"]
    elif mode == "SHS_ONLY":
        classes_data = [c for c in classes_data if c[0] == "SHS"]
    added_count = 0
    for stage_name, class_name in classes_data:
        st = created_stages.get(stage_name)
        if st:
            exists = db.query(ClassSection).filter(ClassSection.name == class_name, ClassSection.stage_id == st.id).first()
            if not exists:
                db.add(ClassSection(name=class_name, stage_id=st.id))
                added_count += 1
    db.commit()
    return {"message": f"Successfully loaded preset stages and created {added_count} standard classes"}

def seed_default_stages(db: Session):
    defaults = [
        {"name": "Creche", "school_type": "Basic"},
        {"name": "Nursery", "school_type": "Basic"},
        {"name": "KG", "school_type": "Basic"},
        {"name": "Primary", "school_type": "Basic"},
        {"name": "JHS", "school_type": "Basic"},
        {"name": "SHS", "school_type": "SHS"},
    ]
    for stage in defaults:
        if not db.query(SchoolStage).filter(SchoolStage.name == stage["name"]).first():
            db.add(SchoolStage(name=stage["name"], school_type=stage["school_type"]))
    db.commit()
