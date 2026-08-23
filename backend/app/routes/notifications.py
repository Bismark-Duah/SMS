from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ..database import get_db
from ..models import Notification, Student, User
from ..dependencies import get_current_user, get_school_id

router = APIRouter()


# ---------- Pydantic schemas ----------

class NotificationCreate(BaseModel):
    message: str
    type: str = "General"
    target_role: Optional[str] = None   # None = broadcast to all students
    student_ids: Optional[List[int]] = None  # explicit list overrides role filter


class NotificationOut(BaseModel):
    id: int
    student_id: int
    message: str
    type: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Helper ----------

def require_admin(current_user: User):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    role_names = [r.name for r in current_user.roles]
    if "admin" not in role_names and "super_admin" not in role_names:
        raise HTTPException(status_code=403, detail="Only administrators can send notifications")


# ---------- Endpoints ----------

@router.get("/", response_model=List[NotificationOut])
def list_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: list all notifications (most recent first)."""
    require_admin(current_user)
    school_id = get_school_id(current_user)
    query = db.query(Notification)
    if school_id is not None:
        query = query.join(Notification.student).filter(Student.school_id == school_id)
    return query.order_by(desc(Notification.created_at)).limit(500).all()


@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get total unread notification count for all students (admin overview)."""
    role_names = [r.name for r in current_user.roles]
    school_id = get_school_id(current_user)
    if "admin" in role_names:
        query = db.query(Notification).filter(Notification.is_read == False)
        if school_id is not None:
            query = query.join(Notification.student).filter(Student.school_id == school_id)
        count = query.count()
    else:
        student_ids = [s.id for s in current_user.children] if current_user.children else []
        count = db.query(Notification).filter(
            Notification.student_id.in_(student_ids),
            Notification.is_read == False
        ).count() if student_ids else 0
    return {"unread_count": count}


@router.get("/my", response_model=List[NotificationOut])
def get_my_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Student/parent: get notifications for the logged-in user's linked students."""
    # For a student user, return notifications for their own student record(s)
    student_ids = [s.id for s in current_user.children] if current_user.children else []

    # If the user IS a student (i.e. has a username that matches student_code)
    # we also check direct student matches. Simple approach: query by parent_id.
    if not student_ids:
        # Try finding student by parent link or raise empty list
        return []

    return (
        db.query(Notification)
        .filter(Notification.student_id.in_(student_ids))
        .order_by(desc(Notification.created_at))
        .limit(200)
        .all()
    )


@router.get("/student/{student_id}", response_model=List[NotificationOut])
def get_student_notifications(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get notifications for a specific student (admin or parent of student)."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    role_names = [r.name for r in current_user.roles]
    is_admin = "admin" in role_names
    is_parent = student.parent_id == current_user.id

    if not is_admin and not is_parent:
        raise HTTPException(status_code=403, detail="Access denied")

    return (
        db.query(Notification)
        .filter(Notification.student_id == student_id)
        .order_by(desc(Notification.created_at))
        .all()
    )


@router.post("/broadcast", status_code=201)
def broadcast_notification(
    payload: NotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: send a notification to specific students or all active students."""
    require_admin(current_user)

    if payload.student_ids:
        students = db.query(Student).filter(
            Student.id.in_(payload.student_ids),
            Student.is_active == True
        ).all()
    else:
        students = db.query(Student).filter(Student.is_active == True).all()

    if not students:
        raise HTTPException(status_code=404, detail="No active students found for the given criteria")

    notifications = [
        Notification(
            student_id=s.id,
            message=payload.message,
            type=payload.type,
        )
        for s in students
    ]
    db.add_all(notifications)
    db.commit()
    return {"message": f"Notification sent to {len(notifications)} student(s)", "count": len(notifications)}


@router.post("/{notification_id}/read")
def mark_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a notification as read."""
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"status": "updated"}


@router.post("/mark-all-read/{student_id}")
def mark_all_read(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all notifications for a student as read."""
    db.query(Notification).filter(
        Notification.student_id == student_id,
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"status": "all marked as read"}


@router.delete("/{notification_id}", status_code=204)
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: delete a notification."""
    require_admin(current_user)
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.delete(notif)
    db.commit()


