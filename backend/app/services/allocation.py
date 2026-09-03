"""
allocation.py — Automatic House & Dormitory Allocation Service
Handles gender-matched, balanced round-robin allocation of Students into Houses and Dormitories.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models import Student, House, Dormitory


def allocate_student_house_and_dorm(db: Session, student: Student) -> dict:
    """
    Automatically allocates a House and (if Boarder) a Dormitory for a student.
    Respects gender (Male/Female/Co-ed) and residential status (Boarding vs Day).
    """
    gender_str = (student.gender or "M").strip().upper()
    is_female = gender_str.startswith("F")
    is_boarder = (student.residential_status or "B").strip().upper().startswith("B")

    # 1. House Allocation (if student has no house_id)
    if not student.house_id:
        # Filter houses by gender compatibility and tenant school_id
        house_query = db.query(House)
        if getattr(student, "school_id", None) is not None:
            house_query = house_query.filter((House.school_id == student.school_id) | (House.school_id == None))
        all_houses = house_query.all()

        if all_houses:
            eligible_houses = []
            for h in all_houses:
                hg = (h.gender or "Co-ed").strip().lower()
                if hg in ["co-ed", "coed", "mixed"]:
                    eligible_houses.append(h)
                elif is_female and hg in ["female", "girls", "female only"]:
                    eligible_houses.append(h)
                elif not is_female and hg in ["male", "boys", "male only"]:
                    eligible_houses.append(h)

            if not eligible_houses:
                eligible_houses = all_houses

            # Find house with least number of students
            house_counts = []
            for h in eligible_houses:
                cnt = db.query(func.count(Student.id)).filter(Student.house_id == h.id).scalar() or 0
                house_counts.append((cnt, h))

            house_counts.sort(key=lambda x: x[0])
            chosen_house = house_counts[0][1]
            student.house_id = chosen_house.id

    # 2. Dormitory Allocation (if student is Boarder and has no dormitory_id)
    if is_boarder and student.house_id and not student.dormitory_id:
        dorms = db.query(Dormitory).filter(Dormitory.house_id == student.house_id).all()
        if not dorms:
            # Fallback: Search dormitories in gender-compatible houses
            house_q = db.query(House)
            if getattr(student, "school_id", None) is not None:
                house_q = house_q.filter((House.school_id == student.school_id) | (House.school_id == None))
            all_candidate_houses = house_q.all()
            eligible_house_ids = []
            for h in all_candidate_houses:
                hg = (h.gender or "Co-ed").strip().lower()
                if hg in ["co-ed", "coed", "mixed"]:
                    eligible_house_ids.append(h.id)
                elif is_female and hg in ["female", "girls", "female only"]:
                    eligible_house_ids.append(h.id)
                elif not is_female and hg in ["male", "boys", "male only"]:
                    eligible_house_ids.append(h.id)
            dorms = db.query(Dormitory).filter(Dormitory.house_id.in_(eligible_house_ids)).all() if eligible_house_ids else []

        if dorms:
            available_dorms = []
            for d in dorms:
                cnt = db.query(func.count(Student.id)).filter(Student.dormitory_id == d.id).scalar() or 0
                max_cap = d.capacity if d.capacity is not None else 30
                if cnt < max_cap:
                    available_dorms.append((cnt, max_cap - cnt, d))

            if available_dorms:
                # Sort by least occupied (cnt) and most free beds (max_cap - cnt)
                available_dorms.sort(key=lambda x: (x[0], -x[1]))
                chosen_dorm = available_dorms[0][2]
                student.dormitory_id = chosen_dorm.id

    return {
        "student_id": student.id,
        "house_id": student.house_id,
        "dormitory_id": student.dormitory_id
    }


def auto_allocate_all_unassigned(db: Session) -> dict:
    """
    Bulk allocates all unassigned students in the system.
    Returns summary statistics of allocated students.
    """
    # Unassigned houses or unassigned boarder dormitories
    unassigned = db.query(Student).filter(
        (Student.house_id == None) |
        ((Student.dormitory_id == None) & (Student.residential_status.ilike("B%")))
    ).all()

    allocated_count = 0
    houses_assigned = set()
    dorms_assigned = set()

    for s in unassigned:
        res = allocate_student_house_and_dorm(db, s)
        if res["house_id"]:
            houses_assigned.add(res["house_id"])
        if res["dormitory_id"]:
            dorms_assigned.add(res["dormitory_id"])
        allocated_count += 1

    db.commit()

    return {
        "allocated_count": allocated_count,
        "houses_used": len(houses_assigned),
        "dorms_used": len(dorms_assigned)
    }
