"""
backend/app/routes/onboarding.py
Guided School Onboarding Subsystem (Prompt 26).
Provides progressive guidance, first-use milestone tracking, and onboarding checklist
resolution for new schools and administrators.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import (
    User, School, AcademicYear, Semester, ClassSection,
    Subject, Student, Fee, Setting, Role
)

router = APIRouter(tags=["onboarding"])


@router.get("/status")
def get_school_onboarding_status(
    school_id: Optional[int] = Query(None, description="Optional school ID for Super-Admin inspection"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Evaluates the 10 core progressive setup milestones for a school:
    1. School Profile & Information
    2. Initial Admin & Account Security
    3. Academic Year & Active Term
    4. Class Sections & Streams
    5. Subject Curriculum
    6. Staff & Teacher Accounts
    7. Student Enrollment
    8. Fee Schedule & Billing
    9. Grading Scale & SBA Weights
    10. Role & Privilege Assignments
    """
    # Tenant boundary enforcement
    is_super_admin = any(getattr(r, "name", "") == "super_admin" for r in getattr(current_user, "roles", []))
    target_school_id = current_user.school_id

    if is_super_admin and school_id is not None:
        target_school_id = school_id
    elif not target_school_id:
        target_school_id = school_id or 1

    school = db.query(School).filter(School.id == target_school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")

    # 1. School Profile Milestone
    has_profile = bool(school.name and school.code and (school.address or school.phone or school.email))
    
    # 2. Initial Admin & Account Security Milestone
    admin_users = db.query(User).filter(User.school_id == target_school_id).all()
    has_admin = any(
        any(r.name in ("admin", "super_admin") for r in u.roles) and bool(u.email)
        for u in admin_users
    ) if admin_users else bool(is_super_admin)

    # 3. Academic Year & Active Term Milestone
    academic_years = db.query(AcademicYear).all()
    semesters = db.query(Semester).all()
    has_academic = len(academic_years) > 0 and len(semesters) > 0

    # 4. Classes Milestone
    class_count = db.query(ClassSection).filter(ClassSection.school_id == target_school_id).count()
    has_classes = class_count > 0

    # 5. Subjects Milestone
    subject_count = db.query(Subject).filter(
        (Subject.school_id == target_school_id) | (Subject.school_id == None)
    ).count()
    has_subjects = subject_count > 0

    # 6. Staff Milestone
    staff_count = db.query(User).filter(
        User.school_id == target_school_id,
        User.roles.any(Role.name.in_(["teacher", "form_master", "accountant", "staff", "headmaster"]))
    ).count()
    has_staff = staff_count > 0

    # 7. Students Milestone
    student_count = db.query(Student).filter(Student.school_id == target_school_id).count()
    has_students = student_count > 0

    # 8. Fees Milestone
    fee_count = db.query(Fee).join(Student, Fee.student_id == Student.id).filter(Student.school_id == target_school_id).count()
    has_fees = fee_count > 0

    # 9. Grading Milestone
    grading_setting = db.query(Setting).filter(
        Setting.school_id == target_school_id,
        Setting.key.in_(["grading_standard", "sba_weight", "exam_weight"])
    ).first()
    has_grading = grading_setting is not None

    # 10. User Roles Milestone
    has_roles = len(admin_users) > 0 and all(len(u.roles) > 0 for u in admin_users)

    # Check if banner was explicitly dismissed by this school
    dismissed_setting = db.query(Setting).filter(
        Setting.school_id == target_school_id,
        Setting.key == "onboarding_banner_dismissed"
    ).first()
    is_dismissed = (dismissed_setting.value.lower() == "true") if dismissed_setting else False

    # Milestone Registry
    milestones = [
        {
            "id": "profile",
            "title": "School Profile & Details",
            "description": "Configure school official name, code, contact info, and badge.",
            "href": "settings.html",
            "is_completed": has_profile,
            "badge": "Identity",
            "hint": "Set contact phone, physical location, and crest in General Settings."
        },
        {
            "id": "admin_security",
            "title": "Admin Credentials & Security",
            "description": "Establish a secure school administrator login with verified email.",
            "href": "users.html",
            "is_completed": has_admin,
            "badge": "Security",
            "hint": "Verify administrator email address for password recovery."
        },
        {
            "id": "academic_calendar",
            "title": "Academic Year & Active Term",
            "description": "Create the current academic year and set the active semester/term.",
            "href": "academic.html",
            "is_completed": has_academic,
            "badge": "Calendar",
            "hint": "Create academic year (e.g., 2026/2027) and mark Term 1 active."
        },
        {
            "id": "classes",
            "title": "Class Sections & Streams",
            "description": "Add school class levels and stream designations.",
            "href": "classes.html",
            "is_completed": has_classes,
            "badge": "Structure",
            "hint": "Add at least one class section (e.g., SHS 1 Science A or Class 1A)."
        },
        {
            "id": "subjects",
            "title": "Curriculum & Active Subjects",
            "description": "Confirm accredited subjects mapped to your school's operating mode.",
            "href": "subjects.html",
            "is_completed": has_subjects,
            "badge": "Curriculum",
            "hint": "Review the NCCA/WAEC subject catalogue and activate offerings."
        },
        {
            "id": "staff",
            "title": "Teaching & Administrative Staff",
            "description": "Create accounts for teachers, accountants, and form masters.",
            "href": "users.html",
            "is_completed": has_staff,
            "badge": "Staffing",
            "hint": "Add at least one teacher account to assign classes and subjects."
        },
        {
            "id": "students",
            "title": "Student Enrollment",
            "description": "Enrol students individually or import an initial class roster via CSV.",
            "href": "students.html",
            "is_completed": has_students,
            "badge": "Students",
            "hint": "Add initial students or use CSV bulk import to seed records."
        },
        {
            "id": "fees",
            "title": "Fee Structure & Billing",
            "description": "Establish term fee items and billing templates for student accounts.",
            "href": "fees.html",
            "is_completed": has_fees,
            "badge": "Finance",
            "hint": "Generate term billings so ledger and payment receipts can be tracked."
        },
        {
            "id": "grading",
            "title": "Grading Scale & SBA Weighting",
            "description": "Configure terminal continuous assessment (SBA 30% / Exam 70%).",
            "href": "settings.html",
            "is_completed": has_grading,
            "badge": "Academics",
            "hint": "Review SBA class mark vs final examination percentages in Academic Settings."
        },
        {
            "id": "roles",
            "title": "Role & Privilege Boundaries",
            "description": "Confirm user permission boundaries for offline security.",
            "href": "users.html",
            "is_completed": has_roles,
            "badge": "Governance",
            "hint": "Ensure staff have the least-privilege roles necessary for their duties."
        }
    ]

    completed_count = sum(1 for m in milestones if m["is_completed"])
    progress_percent = int((completed_count / len(milestones)) * 100)
    is_complete = completed_count == len(milestones)

    # Identify the next uncompleted step
    next_step = next((m for m in milestones if not m["is_completed"]), None)

    return {
        "school_id": school.id,
        "school_name": school.name,
        "school_code": school.code,
        "school_mode": school.school_mode,
        "completed_count": completed_count,
        "total_steps": len(milestones),
        "overall_progress_percent": progress_percent,
        "is_complete": is_complete,
        "is_dismissed": is_dismissed,
        "next_step": next_step,
        "milestones": milestones
    }


@router.post("/dismiss")
def dismiss_onboarding_banner(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Dismisses the progressive setup checklist on the dashboard."""
    school_id = current_user.school_id or 1
    setting = db.query(Setting).filter(
        Setting.school_id == school_id,
        Setting.key == "onboarding_banner_dismissed"
    ).first()

    if not setting:
        setting = Setting(school_id=school_id, key="onboarding_banner_dismissed", value="true")
        db.add(setting)
    else:
        setting.value = "true"

    db.commit()
    return {"status": "success", "message": "Onboarding checklist dismissed."}


@router.post("/reset")
def reset_onboarding_banner(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Re-enables the progressive setup checklist on the dashboard."""
    school_id = current_user.school_id or 1
    setting = db.query(Setting).filter(
        Setting.school_id == school_id,
        Setting.key == "onboarding_banner_dismissed"
    ).first()

    if setting:
        setting.value = "false"
        db.commit()

    return {"status": "success", "message": "Onboarding checklist restored."}
