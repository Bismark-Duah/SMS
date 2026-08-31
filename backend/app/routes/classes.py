from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..models import ClassSection, SchoolStage, Setting, Subject, User, School, Program, Student, Score, Attendance
from ..schemas import ClassSectionCreate, SchoolStageCreate, BatchArmCreate, SmartGenerateRequest
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
    
    subjects = list(section.subjects)
    if not raw and not subjects and section.program_id and section.program:
        from ..models import ElectiveCombination
        
        collected_subs = {}
        # 1. Program Cores
        for cs in section.program.core_subjects:
            collected_subs[cs.id] = cs
            
        # 2. Stream Elective Package
        stream_combo = db.query(ElectiveCombination).filter(
            ElectiveCombination.program_id == section.program_id,
            ElectiveCombination.class_section_id == section.id,
            ElectiveCombination.is_active == True
        ).first()
        if stream_combo:
            for es in stream_combo.subjects:
                collected_subs[es.id] = es
                
        # 3. Fallback to legacy program.subjects if no cores or combos
        if not collected_subs and section.program.subjects:
            for ps in section.program.subjects:
                collected_subs[ps.id] = ps
                
        subjects = list(collected_subs.values())
        
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
    subjects = db.query(Subject).filter(Subject.id.in_(payload)).all() if payload else []
    
    # Associate directly with class section
    section.subjects = subjects
    
    # ── Enterprise Bi-Directional Synchronization with Academic Programs & Elective Packages ──
    if section.program_id and section.program:
        from ..models import ElectiveCombination
        
        elective_subs = [s for s in subjects if not s.is_core]
        core_subs = [s for s in subjects if s.is_core]
        
        # 1. Sync Elective Package for this stream
        if elective_subs:
            existing_combo = db.query(ElectiveCombination).filter(
                ElectiveCombination.program_id == section.program_id,
                ElectiveCombination.class_section_id == section.id
            ).first()
            
            if existing_combo:
                existing_combo.subjects = elective_subs
                existing_combo.is_active = True
            else:
                base_code = section.program.code or "PROG"
                combo_code = f"{base_code}-{section.name.replace(' ', '')}"
                combo_name = f"{section.program.name} ({section.name})"
                new_combo = ElectiveCombination(
                    name=combo_name,
                    code=combo_code,
                    program_id=section.program_id,
                    class_section_id=section.id,
                    capacity=60,
                    is_active=True,
                    subjects=elective_subs
                )
                if school_id is not None and hasattr(ElectiveCombination, "school_id"):
                    new_combo.school_id = school_id
                db.add(new_combo)
        
        # 2. Sync Program Core Subjects if program currently has no custom cores
        if core_subs and not section.program.core_subjects:
            section.program.core_subjects = core_subs
            
    db.commit()
    return {"message": f"Subjects updated for class {section.name} and synchronized with Program"}

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
    
    # ── Enterprise Dependency Guard: Check if students are enrolled ───────────
    from ..models import Student, Score, Attendance
    student_count = db.query(Student).filter(Student.class_section_id == section_id).count()
    if student_count > 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot delete class section '{item.name}' because {student_count} student(s) "
                f"are currently enrolled in it. Please reassign or transfer students before deleting this class."
            )
        )
    
    # Clean up associations safely
    item.subjects.clear()
    db.delete(item)
    db.commit()
    return {"status": "success", "message": f"Class section '{item.name}' deleted successfully."}


# ── Enterprise Smart Class & Arm Generators ───────────────────────────────────

from ..schemas import BatchArmCreate, SmartGenerateRequest
import math


@router.post("/batch-create-arms")
def batch_create_arms(
    payload: BatchArmCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enterprise Batch Class & Arm Provisioner.
    Generates multiple arms for a stage/program in 1 click (e.g. Form 1 Science 1, 2, 3 or KG 1A, 1B).
    """
    school_id = get_school_id(current_user)
    stage = db.query(SchoolStage).filter(SchoolStage.id == payload.stage_id).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Selected stage not found")

    program = None
    if payload.program_id:
        program = db.query(Program).filter(Program.id == payload.program_id).first()

    created_classes = []
    skipped_existing = []

    for i in range(1, payload.number_of_arms + 1):
        if payload.naming_style == "LETTERS":
            suffix = chr(64 + i)  # A, B, C...
        else:
            suffix = str(i)  # 1, 2, 3...

        # Build clean enterprise naming convention
        if stage.school_type == "SHS" and program:
            base = payload.base_name.strip() if payload.base_name else program.name.replace("General ", "").replace("Technical", "Tech").strip()
            class_name = f"{stage.name} {base} {suffix}"
        elif stage.school_type == "Basic":
            base = payload.base_name.strip() if payload.base_name else stage.name
            class_name = f"{base}{suffix}" if payload.naming_style == "LETTERS" else f"{base} {suffix}"
        else:
            base = payload.base_name.strip() if payload.base_name else (program.name if program else stage.name)
            class_name = f"{stage.name} {base} {suffix}"

        # Check existing
        existing_query = db.query(ClassSection).filter(
            ClassSection.name == class_name,
            ClassSection.stage_id == stage.id
        )
        if school_id is not None and hasattr(ClassSection, "school_id"):
            existing_query = existing_query.filter(ClassSection.school_id == school_id)
        
        existing = existing_query.first()
        if existing:
            skipped_existing.append(class_name)
            continue

        section_kwargs = {
            "name": class_name,
            "stage_id": stage.id,
            "program_id": program.id if program else None,
        }
        if school_id is not None and hasattr(ClassSection, "school_id"):
            section_kwargs["school_id"] = school_id

        new_section = ClassSection(**section_kwargs)
        db.add(new_section)
        db.flush()

        # Automatically link program subjects if available
        if program and program.subjects:
            new_section.subjects = list(program.subjects)

        created_classes.append({
            "id": new_section.id,
            "name": new_section.name,
            "stage_name": stage.name,
            "program_name": program.name if program else None
        })

    db.commit()
    return {
        "status": "success",
        "created_count": len(created_classes),
        "created_classes": created_classes,
        "skipped_existing": skipped_existing,
        "message": f"Successfully provisioned {len(created_classes)} class section(s)."
    }


@router.get("/smart-preview")
def smart_class_preview(
    target_capacity: int = 45,
    naming_style: str = "AUTO",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Simulates and previews capacity-driven class allocations based on real student enrollment counts,
    active school mode, programs, and elective combinations.
    """
    from ..models import Student, Program
    school_id = get_school_id(current_user)
    mode = _get_school_mode(db, school_id)

    students_query = db.query(Student)
    if school_id is not None and hasattr(Student, "school_id"):
        students_query = students_query.filter((Student.school_id == school_id) | (Student.school_id.is_(None)))

    all_students = students_query.all()
    target_capacity = max(10, min(100, target_capacity))

    proposals = []
    total_unassigned_students = 0

    if mode == "BASIC_ONLY":
        # Group by standard Basic stages (KG 1, KG 2, Primary 1..6, JHS 1..3)
        stages = db.query(SchoolStage).filter(SchoolStage.school_type == "Basic").all()
        stage_map = {s.name.lower(): s for s in stages}

        # Cluster students by class_name or stage
        basic_clusters = {}
        for st in all_students:
            c_name = (st.class_name or "").strip()
            # Determine stage name
            assigned_stage_name = "Primary 1"
            for s_name in stage_map.keys():
                if s_name in c_name.lower():
                    assigned_stage_name = stage_map[s_name].name
                    break
            if assigned_stage_name not in basic_clusters:
                basic_clusters[assigned_stage_name] = []
            basic_clusters[assigned_stage_name].append(st)

        for stage_name, s_list in basic_clusters.items():
            count = len(s_list)
            needed_arms = max(1, math.ceil(count / target_capacity))
            st_obj = stage_map.get(stage_name.lower())
            
            arm_names = []
            for a_idx in range(1, needed_arms + 1):
                suffix = chr(64 + a_idx) if naming_style in ["AUTO", "LETTERS"] else str(a_idx)
                arm_names.append(f"{stage_name}{suffix}" if naming_style in ["AUTO", "LETTERS"] else f"{stage_name} {suffix}")

            proposals.append({
                "stage_name": stage_name,
                "stage_id": st_obj.id if st_obj else None,
                "program_name": None,
                "program_id": None,
                "elective_combination": None,
                "student_count": count,
                "needed_arms": needed_arms,
                "proposed_classes": arm_names,
                "students_per_arm": math.ceil(count / needed_arms) if count else 0,
                "student_ids": [s.id for s in s_list]
            })

    elif mode == "SHS_ONLY":
        # Group by (Form 1..3) x Program x Elective Combination
        shs_stages = db.query(SchoolStage).filter(SchoolStage.school_type == "SHS").all()
        default_stage = shs_stages[0] if shs_stages else None

        programs = db.query(Program).all()
        prog_map = {p.id: p for p in programs}

        shs_clusters = {}
        for st in all_students:
            form_num = st.form or 1
            form_label = f"Form {form_num}"
            prog_id = st.program_id
            prog_name = prog_map[prog_id].name if prog_id and prog_id in prog_map else "General"
            combo = (st.elective_combination or "Standard").strip()

            key = (form_label, prog_id, prog_name, combo)
            if key not in shs_clusters:
                shs_clusters[key] = []
            shs_clusters[key].append(st)

        for (form_label, prog_id, prog_name, combo), s_list in shs_clusters.items():
            count = len(s_list)
            needed_arms = max(1, math.ceil(count / target_capacity))
            base_prog_clean = prog_name.replace("General ", "").replace("Technical", "Tech").strip()

            arm_names = []
            for a_idx in range(1, needed_arms + 1):
                suffix = str(a_idx)
                combo_tag = f" ({combo})" if combo and combo not in ["Standard", "Default", "None"] else ""
                arm_names.append(f"{form_label} {base_prog_clean} {suffix}{combo_tag}")

            proposals.append({
                "stage_name": form_label,
                "stage_id": default_stage.id if default_stage else None,
                "program_name": prog_name,
                "program_id": prog_id,
                "elective_combination": combo,
                "student_count": count,
                "needed_arms": needed_arms,
                "proposed_classes": arm_names,
                "students_per_arm": math.ceil(count / needed_arms) if count else 0,
                "student_ids": [s.id for s in s_list]
            })

    else:
        # COMBINED mode - returns both
        proposals.append({
            "stage_name": "Combined Mode",
            "stage_id": None,
            "program_name": "All Programs",
            "program_id": None,
            "elective_combination": None,
            "student_count": len(all_students),
            "needed_arms": max(1, math.ceil(len(all_students) / target_capacity)),
            "proposed_classes": ["Stream A", "Stream B"],
            "students_per_arm": math.ceil(len(all_students) / max(1, math.ceil(len(all_students) / target_capacity))),
            "student_ids": [s.id for s in all_students]
        })

    return {
        "school_mode": mode,
        "total_enrolled_students": len(all_students),
        "target_capacity_per_class": target_capacity,
        "proposals": proposals
    }


@router.post("/smart-generate")
def smart_class_generate(
    payload: SmartGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Executes the capacity-driven and elective-combination-aware class generator.
    Creates class sections and automatically balances student rosters evenly across the arms.
    """
    preview_data = smart_class_preview(
        target_capacity=payload.target_capacity,
        naming_style=payload.naming_style,
        db=db,
        current_user=current_user
    )

    school_id = get_school_id(current_user)
    proposals = preview_data["proposals"]

    created_classes_total = 0
    assigned_students_total = 0

    from ..models import Student, Subject

    for prop in proposals:
        stage_id = prop.get("stage_id")
        if not stage_id:
            # Fallback find or create stage
            st = db.query(SchoolStage).filter(SchoolStage.name == prop["stage_name"]).first()
            if not st:
                st = SchoolStage(name=prop["stage_name"], school_type="Basic" if preview_data["school_mode"] == "BASIC_ONLY" else "SHS")
                db.add(st)
                db.flush()
            stage_id = st.id

        created_section_objs = []
        for class_name in prop["proposed_classes"]:
            existing = db.query(ClassSection).filter(
                ClassSection.name == class_name,
                ClassSection.stage_id == stage_id
            ).first()

            if not existing:
                sec_kwargs = {
                    "name": class_name,
                    "stage_id": stage_id,
                    "program_id": prop.get("program_id"),
                }
                if school_id is not None and hasattr(ClassSection, "school_id"):
                    sec_kwargs["school_id"] = school_id
                sec = ClassSection(**sec_kwargs)
                db.add(sec)
                db.flush()

                # Link program subjects if applicable
                if prop.get("program_id"):
                    prog = db.query(Program).filter(Program.id == prop["program_id"]).first()
                    if prog and prog.subjects:
                        sec.subjects = list(prog.subjects)

                created_section_objs.append(sec)
                created_classes_total += 1
            else:
                created_section_objs.append(existing)

        # Distribute and balance students evenly across the provisioned arms
        if payload.assign_students and prop.get("student_ids") and created_section_objs:
            s_ids = prop["student_ids"]
            num_arms = len(created_section_objs)
            
            for idx, sid in enumerate(s_ids):
                assigned_section = created_section_objs[idx % num_arms]
                st_obj = db.query(Student).filter(Student.id == sid).first()
                if st_obj:
                    st_obj.class_section_id = assigned_section.id
                    st_obj.class_name = assigned_section.name
                    assigned_students_total += 1

    db.commit()
    return {
        "status": "success",
        "created_classes": created_classes_total,
        "assigned_students": assigned_students_total,
        "message": f"Successfully created {created_classes_total} balanced class section(s) and assigned {assigned_students_total} student(s)."
    }


@router.post("/presets")
def seed_presets(db: Session = Depends(get_db)):
    """
    Seed standard national GES stages and core class progression.
    Respects active school mode:
      • BASIC_ONLY: KG 1-2, Primary 1-6, JHS 1-3
      • SHS_ONLY: Form 1, Form 2, Form 3
      • COMBINED: All stages
    """
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


from pydantic import BaseModel
from typing import List

class ProvisionBasicStreamsRequest(BaseModel):
    stream_mode: str = "SINGLE" # "SINGLE", "TWO_ARMS_AB", "THREE_ARMS_ABC", "FOUR_ARMS_ABCD", "CUSTOM"
    custom_arms: Optional[List[str]] = None
    include_creche: bool = True
    include_nursery: bool = True
    include_kg: bool = True
    include_primary: bool = True
    include_jhs: bool = True
    school_id: Optional[int] = None


@router.post("/provision-ges-basic-streams")
def provision_ges_basic_streams(
    payload: ProvisionBasicStreamsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Auto-provisions standard GES Basic School stages (Creche, Nursery, KG, Primary, JHS),
    creates stream sections (Single stream vs. Arms A, B, C, D), and automatically binds
    standard NaCCA curriculum core subjects.
    """
    target_sch_id = payload.school_id or get_school_id(current_user)

    # 1. Resolve or create Standard GES Basic stages for this school
    stages_to_ensure = [
        {"name": "Creche & Nursery", "school_type": "Basic"},
        {"name": "Kindergarten (KG 1 - KG 2)", "school_type": "Basic"},
        {"name": "Primary School (Class 1 - Class 6)", "school_type": "Basic"},
        {"name": "Junior High School (JHS 1 - JHS 3)", "school_type": "Basic"},
    ]
    created_stages = {}
    for st_info in stages_to_ensure:
        st_query = db.query(SchoolStage).filter(SchoolStage.name == st_info["name"])
        if target_sch_id is not None and hasattr(SchoolStage, "school_id"):
            st_query = st_query.filter(SchoolStage.school_id == target_sch_id)
        stage_obj = st_query.first()
        if not stage_obj:
            stage_kwargs = {"name": st_info["name"], "school_type": st_info["school_type"]}
            if target_sch_id is not None and hasattr(SchoolStage, "school_id"):
                stage_kwargs["school_id"] = target_sch_id
            stage_obj = SchoolStage(**stage_kwargs)
            db.add(stage_obj)
            db.flush()
        created_stages[st_info["name"]] = stage_obj

    # 2. Determine Arm Suffixes
    sm = (payload.stream_mode or "SINGLE").upper().strip()
    if sm == "TWO_ARMS_AB":
        arms = ["A", "B"]
    elif sm == "THREE_ARMS_ABC":
        arms = ["A", "B", "C"]
    elif sm == "FOUR_ARMS_ABCD":
        arms = ["A", "B", "C", "D"]
    elif sm == "CUSTOM" and payload.custom_arms:
        arms = [a.strip() for a in payload.custom_arms if a.strip()]
        if not arms:
            arms = [""]
    else:  # SINGLE
        arms = [""]

    # 3. Build Base Classes List
    grade_blueprints = []
    if payload.include_creche:
        grade_blueprints.append(("Creche & Nursery", "Creche", "Early_Years"))
    if payload.include_nursery:
        grade_blueprints.append(("Creche & Nursery", "Nursery 1", "Early_Years"))
        grade_blueprints.append(("Creche & Nursery", "Nursery 2", "Early_Years"))
    if payload.include_kg:
        grade_blueprints.append(("Kindergarten (KG 1 - KG 2)", "KG 1", "Early_Years"))
        grade_blueprints.append(("Kindergarten (KG 1 - KG 2)", "KG 2", "Early_Years"))
    if payload.include_primary:
        for i in range(1, 7):
            grade_blueprints.append(("Primary School (Class 1 - Class 6)", f"Class {i}", "Primary"))
    if payload.include_jhs:
        for i in range(1, 4):
            grade_blueprints.append(("Junior High School (JHS 1 - JHS 3)", f"JHS {i}", "JHS"))

    # Fetch active NaCCA basic subjects
    all_basic_subs = db.query(Subject).filter(
        (Subject.school_level.ilike("Basic%")) | (Subject.school_level == None)
    ).all()
    early_subs = [s for s in all_basic_subs if any(k in (s.name or "").lower() for k in ["rhymes", "numeracy", "sensory", "play", "motor", "literacy", "language", "people", "physical"])]
    primary_subs = [s for s in all_basic_subs if not any(k in (s.name or "").lower() for k in ["sensory", "play", "motor"])]
    jhs_subs = [s for s in all_basic_subs if not any(k in (s.name or "").lower() for k in ["sensory", "play", "motor"])]

    created_classes = []
    skipped_classes = []

    for stage_key, base_name, category in grade_blueprints:
        stage_obj = created_stages.get(stage_key)
        if not stage_obj:
            continue

        for arm in arms:
            class_name = f"{base_name} {arm}".strip() if arm else base_name
            # Check existing
            chk_q = db.query(ClassSection).filter(ClassSection.name == class_name)
            if target_sch_id is not None and hasattr(ClassSection, "school_id"):
                chk_q = chk_q.filter(ClassSection.school_id == target_sch_id)
            existing = chk_q.first()
            if existing:
                skipped_classes.append(class_name)
                continue

            sec_kwargs = {
                "name": class_name,
                "stage_id": stage_obj.id
            }
            if target_sch_id is not None and hasattr(ClassSection, "school_id"):
                sec_kwargs["school_id"] = target_sch_id

            new_sec = ClassSection(**sec_kwargs)
            db.add(new_sec)
            db.flush()

            # Attach relevant NaCCA subjects
            if category == "Early_Years" and early_subs:
                new_sec.subjects = list(early_subs)
            elif category == "Primary" and primary_subs:
                new_sec.subjects = list(primary_subs)
            elif category == "JHS" and jhs_subs:
                new_sec.subjects = list(jhs_subs)

            created_classes.append({
                "id": new_sec.id,
                "name": new_sec.name,
                "stage_name": stage_obj.name,
                "subjects_linked": len(new_sec.subjects) if new_sec.subjects else 0
            })

    db.commit()
    return {
        "status": "success",
        "created_count": len(created_classes),
        "created_classes": created_classes,
        "skipped_existing": skipped_classes,
        "message": f"Successfully provisioned {len(created_classes)} GES Basic class stream(s)."
    }


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


