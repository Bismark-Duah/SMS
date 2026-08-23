from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import House, Dormitory, User, Student
from ..schemas import HouseCreate, HouseResponse, DormitoryCreate, DormitoryResponse
from ..dependencies import get_current_user, get_school_id
from ..services.allocation import auto_allocate_all_unassigned

router = APIRouter()

def _check_admin(current_user: User):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    role_names = [r.name for r in current_user.roles]
    if "admin" not in role_names and "super_admin" not in role_names:
        raise HTTPException(status_code=403, detail="Only administrators can manage houses and dormitories")

@router.post("/auto-allocate")
def trigger_auto_allocation(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _check_admin(current_user)
    stats = auto_allocate_all_unassigned(db)
    return {
        "message": f"Successfully auto-allocated {stats['allocated_count']} student(s) across {stats['houses_used']} House(s) and {stats['dorms_used']} Dormitory(ies)!",
        "stats": stats
    }

@router.get("/", response_model=List[HouseResponse])
def list_houses(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from ..dependencies import get_user_assigned_scope
    school_id = get_school_id(current_user)
    query = db.query(House)
    if school_id is not None and hasattr(House, "school_id"):
        query = query.filter((House.school_id == school_id) | (House.school_id == 1) | (House.school_id.is_(None)))

    # ── Role-based scoping ─────────────────────────────────────────────────────
    scope = get_user_assigned_scope(current_user, db)
    if not scope["is_admin"]:
        role_names = [r.name.lower() for r in current_user.roles] if hasattr(current_user, "roles") and current_user.roles else []
        HOUSE_STAFF_ROLES = {
            "senior_housemaster", "senior_housemistress", "senior_house_master", "senior_house_mistress",
            "house_master", "house_mistress", "assistant_house_master", "assistant_house_mistress"
        }
        is_house_staff = any(r in HOUSE_STAFF_ROLES for r in role_names)
        if is_house_staff:
            # Return only houses where this user is listed as any house role
            house_ids = set()
            for h in query.all():
                assigned = {h.senior_in_charge_id, h.house_master_id, h.assistant_house_master_id,
                            h.senior_in_charge_girls_id, h.house_master_girls_id, h.assistant_house_master_girls_id}
                if current_user.id in assigned:
                    house_ids.add(h.id)
            if house_ids:
                query = query.filter(House.id.in_(house_ids))
            else:
                return []
        else:
            # No house assignment — return empty (sidebar link hidden anyway)
            return []

    houses = query.all()
    results = []
    for h in houses:
        senior_name = h.senior_in_charge.username if h.senior_in_charge else None
        house_master_name = h.house_master.username if h.house_master else None
        assistant_house_master_name = h.assistant_house_master.username if h.assistant_house_master else None
        senior_girls_name = h.senior_in_charge_girls.username if h.senior_in_charge_girls else None
        house_master_girls_name = h.house_master_girls.username if h.house_master_girls else None
        assistant_house_master_girls_name = h.assistant_house_master_girls.username if h.assistant_house_master_girls else None
        
        # Count students in this house
        student_count = db.query(Student).filter(Student.house_id == h.id).count()
        boarder_count = db.query(Student).filter(Student.house_id == h.id, Student.residential_status.ilike("B%")).count()
        day_count = db.query(Student).filter(Student.house_id == h.id, Student.residential_status.ilike("D%")).count()

        # Build dorm responses
        dorm_responses = []
        for d in h.dormitories:
            master_name = d.housemaster.username if d.housemaster else None
            occ_count = db.query(Student).filter(Student.dormitory_id == d.id).count()
            dorm_responses.append(
                DormitoryResponse(
                    id=d.id,
                    name=d.name,
                    house_id=d.house_id,
                    housemaster_id=d.housemaster_id,
                    housemaster_name=master_name,
                    capacity=d.capacity if d.capacity is not None else 30,
                    occupied_count=occ_count
                )
            )
        
        results.append(
            HouseResponse(
                id=h.id,
                name=h.name,
                gender=h.gender,
                senior_in_charge_id=h.senior_in_charge_id,
                senior_in_charge_name=senior_name,
                house_master_id=h.house_master_id,
                house_master_name=house_master_name,
                assistant_house_master_id=h.assistant_house_master_id,
                assistant_house_master_name=assistant_house_master_name,
                senior_in_charge_girls_id=h.senior_in_charge_girls_id,
                senior_in_charge_girls_name=senior_girls_name,
                house_master_girls_id=h.house_master_girls_id,
                house_master_girls_name=house_master_girls_name,
                assistant_house_master_girls_id=h.assistant_house_master_girls_id,
                assistant_house_master_girls_name=assistant_house_master_girls_name,
                dormitories=dorm_responses,
                student_count=student_count,
                boarder_count=boarder_count,
                day_count=day_count
            )
        )
    return results

@router.post("/", response_model=HouseResponse)
def create_house(
    payload: HouseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_admin(current_user)

    # Check unique constraints
    school_id = get_school_id(current_user)
    check_query = db.query(House).filter(House.name == payload.name)
    if school_id is not None and hasattr(House, "school_id"):
        check_query = check_query.filter(House.school_id == school_id)
    if check_query.first():
        raise HTTPException(status_code=400, detail="House name already exists")

    # Validate Senior in charge
    if payload.senior_in_charge_id:
        senior = db.query(User).filter(User.id == payload.senior_in_charge_id).first()
        if not senior:
            raise HTTPException(status_code=404, detail="Senior in charge user not found")

    # Validate House master
    if payload.house_master_id:
        hm = db.query(User).filter(User.id == payload.house_master_id).first()
        if not hm:
            raise HTTPException(status_code=404, detail="House master user not found")

    # Validate Assistant House master
    if payload.assistant_house_master_id:
        ahm = db.query(User).filter(User.id == payload.assistant_house_master_id).first()
        if not ahm:
            raise HTTPException(status_code=404, detail="Assistant house master user not found")

    # Validate Senior in charge Girls
    if payload.senior_in_charge_girls_id:
        senior_g = db.query(User).filter(User.id == payload.senior_in_charge_girls_id).first()
        if not senior_g:
            raise HTTPException(status_code=404, detail="Senior in charge (Girls) user not found")

    # Validate House mistress
    if payload.house_master_girls_id:
        hm_g = db.query(User).filter(User.id == payload.house_master_girls_id).first()
        if not hm_g:
            raise HTTPException(status_code=404, detail="House mistress user not found")

    # Validate Assistant House mistress
    if payload.assistant_house_master_girls_id:
        ahm_g = db.query(User).filter(User.id == payload.assistant_house_master_girls_id).first()
        if not ahm_g:
            raise HTTPException(status_code=404, detail="Assistant house mistress user not found")

    db_house = House(
        name=payload.name,
        gender=payload.gender,
        school_id=school_id,
        senior_in_charge_id=payload.senior_in_charge_id,
        house_master_id=payload.house_master_id,
        assistant_house_master_id=payload.assistant_house_master_id,
        senior_in_charge_girls_id=payload.senior_in_charge_girls_id,
        house_master_girls_id=payload.house_master_girls_id,
        assistant_house_master_girls_id=payload.assistant_house_master_girls_id
    )
    db.add(db_house)
    db.commit()
    db.refresh(db_house)

    senior_name = db_house.senior_in_charge.username if db_house.senior_in_charge else None
    house_master_name = db_house.house_master.username if db_house.house_master else None
    assistant_house_master_name = db_house.assistant_house_master.username if db_house.assistant_house_master else None
    senior_girls_name = db_house.senior_in_charge_girls.username if db_house.senior_in_charge_girls else None
    house_master_girls_name = db_house.house_master_girls.username if db_house.house_master_girls else None
    assistant_house_master_girls_name = db_house.assistant_house_master_girls.username if db_house.assistant_house_master_girls else None
    
    return HouseResponse(
        id=db_house.id,
        name=db_house.name,
        gender=db_house.gender,
        senior_in_charge_id=db_house.senior_in_charge_id,
        senior_in_charge_name=senior_name,
        house_master_id=db_house.house_master_id,
        house_master_name=house_master_name,
        assistant_house_master_id=db_house.assistant_house_master_id,
        assistant_house_master_name=assistant_house_master_name,
        senior_in_charge_girls_id=db_house.senior_in_charge_girls_id,
        senior_in_charge_girls_name=senior_girls_name,
        house_master_girls_id=db_house.house_master_girls_id,
        house_master_girls_name=house_master_girls_name,
        assistant_house_master_girls_id=db_house.assistant_house_master_girls_id,
        assistant_house_master_girls_name=assistant_house_master_girls_name,
        dormitories=[],
        student_count=0
    )

@router.put("/{id}", response_model=HouseResponse)
def update_house(
    id: int,
    payload: HouseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_admin(current_user)

    db_house = db.query(House).filter(House.id == id).first()
    if not db_house:
        raise HTTPException(status_code=404, detail="House not found")

    # Check unique constraints
    school_id = get_school_id(current_user)
    dup_query = db.query(House).filter(House.name == payload.name, House.id != id)
    if school_id is not None and hasattr(House, "school_id"):
        dup_query = dup_query.filter(House.school_id == school_id)
    if dup_query.first():
        raise HTTPException(status_code=400, detail="House name already exists")

    # Validate Senior in charge
    if payload.senior_in_charge_id:
        senior = db.query(User).filter(User.id == payload.senior_in_charge_id).first()
        if not senior:
            raise HTTPException(status_code=404, detail="Senior in charge user not found")

    # Validate House master
    if payload.house_master_id:
        hm = db.query(User).filter(User.id == payload.house_master_id).first()
        if not hm:
            raise HTTPException(status_code=404, detail="House master user not found")

    # Validate Assistant House master
    if payload.assistant_house_master_id:
        ahm = db.query(User).filter(User.id == payload.assistant_house_master_id).first()
        if not ahm:
            raise HTTPException(status_code=404, detail="Assistant house master user not found")

    # Validate Senior in charge Girls
    if payload.senior_in_charge_girls_id:
        senior_g = db.query(User).filter(User.id == payload.senior_in_charge_girls_id).first()
        if not senior_g:
            raise HTTPException(status_code=404, detail="Senior in charge (Girls) user not found")

    # Validate House mistress
    if payload.house_master_girls_id:
        hm_g = db.query(User).filter(User.id == payload.house_master_girls_id).first()
        if not hm_g:
            raise HTTPException(status_code=404, detail="House mistress user not found")

    # Validate Assistant House mistress
    if payload.assistant_house_master_girls_id:
        ahm_g = db.query(User).filter(User.id == payload.assistant_house_master_girls_id).first()
        if not ahm_g:
            raise HTTPException(status_code=404, detail="Assistant house mistress user not found")

    db_house.name = payload.name
    db_house.gender = payload.gender
    db_house.senior_in_charge_id = payload.senior_in_charge_id
    db_house.house_master_id = payload.house_master_id
    db_house.assistant_house_master_id = payload.assistant_house_master_id
    db_house.senior_in_charge_girls_id = payload.senior_in_charge_girls_id
    db_house.house_master_girls_id = payload.house_master_girls_id
    db_house.assistant_house_master_girls_id = payload.assistant_house_master_girls_id

    db.commit()
    db.refresh(db_house)

    # Count students
    student_count = db.query(Student).filter(Student.house_id == id).count()

    # Build dorm responses
    dorm_responses = []
    for d in db_house.dormitories:
        master_name = d.housemaster.username if d.housemaster else None
        occ_count = db.query(Student).filter(Student.dormitory_id == d.id).count()
        dorm_responses.append(
            DormitoryResponse(
                id=d.id,
                name=d.name,
                house_id=d.house_id,
                housemaster_id=d.housemaster_id,
                housemaster_name=master_name,
                capacity=d.capacity if d.capacity is not None else 30,
                occupied_count=occ_count
            )
        )

    senior_name = db_house.senior_in_charge.username if db_house.senior_in_charge else None
    house_master_name = db_house.house_master.username if db_house.house_master else None
    assistant_house_master_name = db_house.assistant_house_master.username if db_house.assistant_house_master else None
    senior_girls_name = db_house.senior_in_charge_girls.username if db_house.senior_in_charge_girls else None
    house_master_girls_name = db_house.house_master_girls.username if db_house.house_master_girls else None
    assistant_house_master_girls_name = db_house.assistant_house_master_girls.username if db_house.assistant_house_master_girls else None
    
    return HouseResponse(
        id=db_house.id,
        name=db_house.name,
        gender=db_house.gender,
        senior_in_charge_id=db_house.senior_in_charge_id,
        senior_in_charge_name=senior_name,
        house_master_id=db_house.house_master_id,
        house_master_name=house_master_name,
        assistant_house_master_id=db_house.assistant_house_master_id,
        assistant_house_master_name=assistant_house_master_name,
        senior_in_charge_girls_id=db_house.senior_in_charge_girls_id,
        senior_in_charge_girls_name=senior_girls_name,
        house_master_girls_id=db_house.house_master_girls_id,
        house_master_girls_name=house_master_girls_name,
        assistant_house_master_girls_id=db_house.assistant_house_master_girls_id,
        assistant_house_master_girls_name=assistant_house_master_girls_name,
        dormitories=dorm_responses,
        student_count=student_count
    )

@router.delete("/{id}")
def delete_house(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_admin(current_user)

    db_house = db.query(House).filter(House.id == id).first()
    if not db_house:
        raise HTTPException(status_code=404, detail="House not found")

    # Unset house and dorm references for students in this house
    students = db.query(Student).filter(Student.house_id == id).all()
    for s in students:
        s.house_id = None
        s.dormitory_id = None

    db.delete(db_house)
    db.commit()
    return {"message": "House deleted successfully"}

# --- Dormitory Endpoints ---

@router.post("/{house_id}/dormitories", response_model=DormitoryResponse)
def create_dormitory(
    house_id: int,
    payload: DormitoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_admin(current_user)

    # Check house exists
    house = db.query(House).filter(House.id == house_id).first()
    if not house:
        raise HTTPException(status_code=404, detail="House not found")

    # Validate Housemaster
    if payload.housemaster_id:
        master = db.query(User).filter(User.id == payload.housemaster_id).first()
        if not master:
            raise HTTPException(status_code=404, detail="Housemaster user not found")

    db_dorm = Dormitory(
        name=payload.name,
        house_id=house_id,
        capacity=payload.capacity if payload.capacity is not None else 30,
        housemaster_id=payload.housemaster_id
    )
    db.add(db_dorm)
    db.commit()
    db.refresh(db_dorm)

    master_name = db_dorm.housemaster.username if db_dorm.housemaster else None
    occ = db.query(Student).filter(Student.dormitory_id == db_dorm.id).count()
    return DormitoryResponse(
        id=db_dorm.id,
        name=db_dorm.name,
        house_id=db_dorm.house_id,
        housemaster_id=db_dorm.housemaster_id,
        housemaster_name=master_name,
        capacity=db_dorm.capacity if db_dorm.capacity is not None else 30,
        occupied_count=occ
    )

@router.put("/dormitories/{dorm_id}", response_model=DormitoryResponse)
def update_dormitory(
    dorm_id: int,
    payload: DormitoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_admin(current_user)

    db_dorm = db.query(Dormitory).filter(Dormitory.id == dorm_id).first()
    if not db_dorm:
        raise HTTPException(status_code=404, detail="Dormitory not found")

    # Validate Housemaster
    if payload.housemaster_id:
        master = db.query(User).filter(User.id == payload.housemaster_id).first()
        if not master:
            raise HTTPException(status_code=404, detail="Housemaster user not found")

    db_dorm.name = payload.name
    if payload.capacity is not None:
        db_dorm.capacity = payload.capacity
    db_dorm.housemaster_id = payload.housemaster_id

    db.commit()
    db.refresh(db_dorm)

    master_name = db_dorm.housemaster.username if db_dorm.housemaster else None
    occ = db.query(Student).filter(Student.dormitory_id == db_dorm.id).count()
    return DormitoryResponse(
        id=db_dorm.id,
        name=db_dorm.name,
        house_id=db_dorm.house_id,
        housemaster_id=db_dorm.housemaster_id,
        housemaster_name=master_name,
        capacity=db_dorm.capacity if db_dorm.capacity is not None else 30,
        occupied_count=occ
    )

@router.delete("/dormitories/{dorm_id}")
def delete_dormitory(
    dorm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_admin(current_user)

    db_dorm = db.query(Dormitory).filter(Dormitory.id == dorm_id).first()
    if not db_dorm:
        raise HTTPException(status_code=404, detail="Dormitory not found")

    # Unset dormitory reference for students in this dormitory
    students = db.query(Student).filter(Student.dormitory_id == dorm_id).all()
    for s in students:
        s.dormitory_id = None

    db.delete(db_dorm)
    db.commit()
    return {"message": "Dormitory deleted successfully"}
