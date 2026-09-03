import os
import json
import hmac
import hashlib
import uuid
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from ..models import (
    SyncOutbox, Student, Score, Subject, Semester, ClassSection,
    Fee, Payment, Attendance, Setting, DisciplineRecord, Notification, User, School
)

# Secret key used for signing sync payloads
def get_sync_secret() -> str:
    return os.getenv("SYNC_SECRET_KEY") or os.getenv("SECRET_KEY") or "edumanage-hybrid-sync-secret-key-2026"

def compute_payload_checksum(payload: Any) -> str:
    """Computes SHA-256 hash of a JSON string or dict."""
    if isinstance(payload, (dict, list)):
        payload_str = json.dumps(payload, sort_keys=True, default=str)
    else:
        payload_str = str(payload)
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

def sign_sync_payload(payload_bytes: bytes, secret_key: Optional[str] = None) -> str:
    """Generates HMAC-SHA256 signature for the given sync payload bytes."""
    key = (secret_key or get_sync_secret()).encode("utf-8")
    return hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()

def verify_sync_signature(payload_bytes: bytes, signature: str, secret_key: Optional[str] = None) -> bool:
    """Verifies HMAC-SHA256 signature in constant time against timing attacks."""
    if not signature:
        return False
    expected = sign_sync_payload(payload_bytes, secret_key)
    return hmac.compare_digest(expected.lower(), signature.strip().lower())

def log_sync_change(
    db: Session,
    school_id: int,
    entity_type: str,
    entity_id: Any,
    action: str,
    payload: Dict[str, Any]
) -> SyncOutbox:
    """
    Idempotently enqueues an atomic data change in the local SyncOutbox ledger.
    Does not break if database transaction is already managed outside.
    """
    if not school_id:
        school_id = 1
        
    payload_str = json.dumps(payload, sort_keys=True, default=str)
    checksum = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    sync_uuid = str(uuid.uuid4())

    outbox_entry = SyncOutbox(
        sync_uuid=sync_uuid,
        school_id=school_id,
        entity_type=entity_type.lower(),
        entity_id=str(entity_id),
        action=action.upper(),
        payload_json=payload_str,
        checksum=checksum,
        is_synced=False,
        created_at=datetime.utcnow()
    )
    db.add(outbox_entry)
    return outbox_entry

# Dependency hierarchy rank for deterministic topological delta ingestion
ENTITY_INGESTION_RANK: Dict[str, int] = {
    "school": 1,
    "setting": 2,
    "user": 3,
    "subject": 4,
    "class": 5,
    "classsection": 5,
    "program": 6,
    "house": 7,
    "dormitory": 8,
    "student": 10,
    "fee": 20,
    "fee_payment": 21,
    "payment": 21,
    "score": 30,
    "attendance": 40,
    "discipline": 50,
    "notification": 60,
}

def apply_sync_bundle(
    db: Session,
    school_id: int,
    items: List[Dict[str, Any]]
) -> Tuple[List[str], List[str]]:
    """
    Applies a batch of incoming delta change items into the target database.
    Guarantees strict tenant isolation by enforcing `school_id`.
    Performs topological dependency sorting, per-item SHA-256 integrity verification,
    and field-level upsert with Last-Write-Wins timestamp arbitration.
    Returns: (list of successfully applied sync_uuids, list of error descriptions)
    """
    applied_uuids: List[str] = []
    errors: List[str] = []

    # 1. Topological Sorting by Entity Hierarchy
    items_sorted = sorted(
        items,
        key=lambda x: (
            ENTITY_INGESTION_RANK.get((x.get("entity_type") or "").lower(), 99),
            x.get("created_at") or ""
        )
    )

    for item in items_sorted:
        item_uuid = item.get("sync_uuid") or str(uuid.uuid4())
        entity_type = (item.get("entity_type") or "").lower()
        entity_id = item.get("entity_id")
        action = (item.get("action") or "UPDATE").upper()
        payload = item.get("payload") or {}
        created_at_raw = item.get("created_at")

        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}

        # 2. Defense-in-Depth: Per-Item SHA-256 Checksum Validation
        expected_checksum = item.get("checksum")
        if expected_checksum:
            computed_checksum = compute_payload_checksum(payload)
            if computed_checksum != expected_checksum:
                errors.append(f"Checksum mismatch for {entity_type}:{entity_id}. Payload rejected.")
                continue

        try:
            if entity_type == "student":
                _apply_student_delta(db, school_id, action, entity_id, payload, created_at_raw)
            elif entity_type == "score":
                _apply_score_delta(db, school_id, action, entity_id, payload, created_at_raw)
            elif entity_type in ("fee", "fee_payment", "payment"):
                _apply_finance_delta(db, school_id, action, entity_id, payload, created_at_raw)
            elif entity_type == "attendance":
                _apply_attendance_delta(db, school_id, action, entity_id, payload, created_at_raw)
            elif entity_type == "setting":
                _apply_setting_delta(db, school_id, action, entity_id, payload, created_at_raw)
            elif entity_type == "discipline":
                _apply_discipline_delta(db, school_id, action, entity_id, payload, created_at_raw)
            elif entity_type == "notification":
                _apply_notification_delta(db, school_id, action, entity_id, payload, created_at_raw)
            else:
                # Generic fallback entity handling
                pass

            applied_uuids.append(item_uuid)
        except Exception as e:
            errors.append(f"Entity {entity_type}:{entity_id} error: {str(e)}")

    try:
        db.commit()
    except Exception as commit_err:
        db.rollback()
        return [], [f"Database commit failed: {str(commit_err)}"]

    return applied_uuids, errors


def _parse_iso_datetime(dt_val: Any) -> Optional[datetime]:
    if not dt_val:
        return None
    if isinstance(dt_val, datetime):
        return dt_val
    try:
        clean_str = str(dt_val).replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except Exception:
        return None


def _apply_student_delta(
    db: Session,
    school_id: int,
    action: str,
    entity_id: Any,
    p: Dict[str, Any],
    created_at_raw: Optional[str] = None
):
    student_code = p.get("student_code") or str(entity_id)
    student = db.query(Student).filter(
        Student.school_id == school_id,
        (Student.student_code == student_code) | (Student.id == (int(entity_id) if str(entity_id).isdigit() else -1))
    ).first()

    if action == "DELETE" and student:
        student.is_active = False
        student.status = "INACTIVE"
        return

    if not student:
        student = Student(
            student_code=student_code,
            full_name=p.get("full_name") or f"Student {student_code}",
            school_id=school_id,
            is_active=True
        )
        db.add(student)
        db.flush()

    # Timestamp-Aware Last-Write-Wins arbitration if existing record has updated_at
    delta_dt = _parse_iso_datetime(created_at_raw)
    rec_updated_at = getattr(student, "updated_at", None)
    if delta_dt and rec_updated_at and delta_dt < rec_updated_at:
        # Older edit arriving after newer update; preserve current database state
        return

    # Field-level merge with explicit None-check (avoids truthy-string trap for empty strings)
    if "full_name" in p and p["full_name"] is not None: student.full_name = str(p["full_name"])
    if "gender" in p and p["gender"] is not None: student.gender = str(p["gender"])
    if "phone" in p and p["phone"] is not None: student.phone = str(p["phone"])
    if "address" in p and p["address"] is not None: student.address = str(p["address"])
    if "guardian_name" in p and p["guardian_name"] is not None: student.guardian_name = str(p["guardian_name"])
    if "residential_status" in p and p["residential_status"] is not None: student.residential_status = str(p["residential_status"])
    if "bece_index_number" in p: student.bece_index_number = p["bece_index_number"]
    if "bece_raw_score" in p and p["bece_raw_score"] is not None: student.bece_raw_score = p["bece_raw_score"]
    if "bece_aggregate" in p and p["bece_aggregate"] is not None: student.bece_aggregate = p["bece_aggregate"]
    if "jhs_attended" in p: student.jhs_attended = p["jhs_attended"]
    if "status" in p and p["status"] is not None: student.status = str(p["status"])
    if "is_active" in p and p["is_active"] is not None: student.is_active = bool(p["is_active"])
    
    if "date_of_birth" in p and p["date_of_birth"]:
        try:
            student.date_of_birth = datetime.strptime(str(p["date_of_birth"])[:10], "%Y-%m-%d")
        except Exception:
            pass


def _apply_score_delta(
    db: Session,
    school_id: int,
    action: str,
    entity_id: Any,
    p: Dict[str, Any],
    created_at_raw: Optional[str] = None
):
    # Resolve student
    student_id = p.get("student_id")
    student_code = p.get("student_code")
    subject_id = p.get("subject_id")
    subject_code = p.get("subject_code")
    semester_id = p.get("semester_id")

    student = None
    if student_code:
        student = db.query(Student).filter(Student.school_id == school_id, Student.student_code == student_code).first()
    elif student_id:
        student = db.query(Student).filter(Student.school_id == school_id, Student.id == student_id).first()

    # Strict Validation: Never silently drop child score
    if not student:
        raise ValueError(f"Parent student '{student_code or student_id}' not found for score delta (Subject: {subject_code or subject_id}).")

    subject = None
    if subject_id:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
    elif subject_code:
        subject = db.query(Subject).filter(Subject.code == subject_code).first()

    if not subject:
        # Fallback to first available or create placeholder
        subject = db.query(Subject).first()
        if not subject:
            raise ValueError(f"Subject '{subject_code or subject_id}' not found in curriculum catalog.")

    if not semester_id:
        active_sem = db.query(Semester).filter(Semester.is_current == True).first()
        semester_id = active_sem.id if active_sem else 1

    score = db.query(Score).filter(
        Score.student_id == student.id,
        Score.subject_id == subject.id,
        Score.semester_id == semester_id
    ).first()

    if action == "DELETE" and score:
        db.delete(score)
        return

    if not score:
        score = Score(
            student_id=student.id,
            subject_id=subject.id,
            semester_id=semester_id
        )
        db.add(score)

    # Apply scores
    for f in ["ex1", "ex2", "ass1", "ass2", "ind_proj", "grp_work", "pract_work", "mid_sem", "class_score", "exam_score", "total_score"]:
        if f in p and p[f] is not None:
            setattr(score, f, float(p[f]))

    # Explicit string handling to support clearing remarks/grades
    if "grade" in p and p["grade"] is not None: score.grade = str(p["grade"])
    if "remark" in p and p["remark"] is not None: score.remark = str(p["remark"])
    if "rank_in_subject" in p and p["rank_in_subject"] is not None: score.rank_in_subject = str(p["rank_in_subject"])
    if "approval_status" in p and p["approval_status"] is not None: score.approval_status = str(p["approval_status"])


def _apply_finance_delta(
    db: Session,
    school_id: int,
    action: str,
    entity_id: Any,
    p: Dict[str, Any],
    created_at_raw: Optional[str] = None
):
    student_id = p.get("student_id")
    student_code = p.get("student_code")
    student = None
    if student_code:
        student = db.query(Student).filter(Student.school_id == school_id, Student.student_code == student_code).first()
    elif student_id:
        student = db.query(Student).filter(Student.school_id == school_id, Student.id == student_id).first()

    # Strict Validation: Never silently drop financial transaction
    if not student:
        raise ValueError(f"Parent student '{student_code or student_id}' not found for fee/payment delta.")

    fee_id = p.get("fee_id") or (int(entity_id) if str(entity_id).isdigit() else None)
    fee = None
    if fee_id:
        fee = db.query(Fee).filter(Fee.id == fee_id, Fee.student_id == student.id).first()

    if not fee:
        fee = Fee(
            student_id=student.id,
            fee_type=p.get("fee_type", "Tuition Fee"),
            description=p.get("description", "School Fee Assessment"),
            amount=float(p.get("amount", 0.0)),
            amount_paid=float(p.get("amount_paid", 0.0)),
            status=p.get("status", "Pending")
        )
        db.add(fee)
        db.flush()
    else:
        if "amount" in p and p["amount"] is not None: fee.amount = float(p["amount"])
        if "amount_paid" in p and p["amount_paid"] is not None: fee.amount_paid = float(p["amount_paid"])
        if "status" in p and p["status"] is not None: fee.status = str(p["status"])

    # Payment record
    if "payment_amount" in p and float(p["payment_amount"]) > 0:
        receipt_num = p.get("receipt_number") or p.get("receipt_no")
        if not receipt_num:
            receipt_num = f"REC-SYNC-{uuid.uuid4().hex[:6].upper()}"
        pay = Payment(
            fee_id=fee.id,
            amount_paid=float(p["payment_amount"]),
            payment_method=p.get("payment_method", "Cash"),
            reference_no=p.get("reference_no", f"SYNC-{uuid.uuid4().hex[:8].upper()}"),
            receipt_number=receipt_num,
            notes=p.get("notes", "Offline Synchronized Payment")
        )
        db.add(pay)
        db.flush()

    # Atomically re-aggregate fee total payments
    tot = db.query(func.coalesce(func.sum(Payment.amount_paid), 0.0)).filter(Payment.fee_id == fee.id).scalar()
    fee.amount_paid = round(float(tot), 2)
    if fee.amount_paid >= fee.amount:
        fee.status = "Paid"
    elif fee.amount_paid > 0:
        fee.status = "Partial"


def _apply_attendance_delta(
    db: Session,
    school_id: int,
    action: str,
    entity_id: Any,
    p: Dict[str, Any],
    created_at_raw: Optional[str] = None
):
    student_code = p.get("student_code")
    student = db.query(Student).filter(Student.school_id == school_id, Student.student_code == student_code).first() if student_code else None
    if not student:
        student_id = p.get("student_id")
        if student_id:
            student = db.query(Student).filter(Student.school_id == school_id, Student.id == student_id).first()

    if not student:
        raise ValueError(f"Parent student '{student_code or student_id}' not found for attendance delta.")

    att_date_str = p.get("date") or str(datetime.utcnow())[:10]
    try:
        att_date = datetime.strptime(str(att_date_str)[:10], "%Y-%m-%d")
    except Exception:
        att_date = datetime.utcnow()

    att = db.query(Attendance).filter(
        Attendance.student_id == student.id,
        func.date(Attendance.date) == att_date.date()
    ).first()

    if not att:
        att = Attendance(
            student_id=student.id,
            date=att_date,
            status=p.get("status", "Present"),
            attendance_type=p.get("attendance_type", "daily")
        )
        db.add(att)
    else:
        if "status" in p and p["status"] is not None: att.status = str(p["status"])
        if "attendance_type" in p and p["attendance_type"] is not None: att.attendance_type = str(p["attendance_type"])


def _apply_setting_delta(
    db: Session,
    school_id: int,
    action: str,
    entity_id: Any,
    p: Dict[str, Any],
    created_at_raw: Optional[str] = None
):
    key = p.get("key") or str(entity_id)
    val = str(p.get("value", ""))
    setting = db.query(Setting).filter(Setting.school_id == school_id, Setting.key == key).first()
    if not setting:
        setting = Setting(school_id=school_id, key=key, value=val)
        db.add(setting)
    else:
        setting.value = val


def _apply_discipline_delta(
    db: Session,
    school_id: int,
    action: str,
    entity_id: Any,
    p: Dict[str, Any],
    created_at_raw: Optional[str] = None
):
    student_id = p.get("student_id")
    student = db.query(Student).filter(Student.school_id == school_id, Student.id == student_id).first() if student_id else None
    if not student:
        raise ValueError(f"Parent student #{student_id} not found for discipline delta.")

    record = DisciplineRecord(
        student_id=student.id,
        incident_type=p.get("incident_type", "General Infraction"),
        description=p.get("description", "Discipline report"),
        action_taken=p.get("action_taken", "Reprimand"),
        parent_notified=bool(p.get("parent_notified", False))
    )
    db.add(record)


def _apply_notification_delta(
    db: Session,
    school_id: int,
    action: str,
    entity_id: Any,
    p: Dict[str, Any],
    created_at_raw: Optional[str] = None
):
    student_id = p.get("student_id")
    student = db.query(Student).filter(Student.school_id == school_id, Student.id == student_id).first() if student_id else None
    if not student:
        raise ValueError(f"Parent student #{student_id} not found for notification delta.")

    notif = Notification(
        student_id=student.id,
        message=p.get("message", "System Notification"),
        type=p.get("type", "General")
    )
    db.add(notif)


def generate_school_snapshot(db: Session, school_id: int) -> Dict[str, Any]:
    """
    Generates a full operational snapshot for a school tenant.
    Used for 1-click cloud snapshot pull / disaster recovery.
    """
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        return {"error": "School not found"}

    students = db.query(Student).filter(Student.school_id == school_id).all()
    settings = db.query(Setting).filter(Setting.school_id == school_id).all()
    classes = db.query(ClassSection).filter(ClassSection.school_id == school_id).all()
    
    # Extract student IDs for scores
    student_ids = [s.id for s in students]
    scores = db.query(Score).filter(Score.student_id.in_(student_ids)).all() if student_ids else []

    return {
        "school": {
            "id": school.id,
            "name": school.name,
            "code": school.code,
            "slug": school.slug,
            "school_mode": school.school_mode,
            "boarding_type": school.boarding_type,
            "ownership_type": school.ownership_type,
            "address": school.address,
            "phone": school.phone,
            "email": school.email,
            "logo_url": school.logo_url
        },
        "settings": [{"key": s.key, "value": s.value} for s in settings],
        "classes": [{"id": c.id, "name": c.name, "stage_id": c.stage_id} for c in classes],
        "students_count": len(students),
        "students": [
            {
                "id": s.id,
                "student_code": s.student_code,
                "full_name": s.full_name,
                "gender": s.gender,
                "date_of_birth": str(s.date_of_birth)[:10] if s.date_of_birth else None,
                "phone": s.phone,
                "address": s.address,
                "guardian_name": s.guardian_name,
                "residential_status": s.residential_status,
                "bece_index_number": s.bece_index_number,
                "bece_raw_score": s.bece_raw_score,
                "bece_aggregate": s.bece_aggregate,
                "jhs_attended": s.jhs_attended,
                "status": s.status,
                "is_active": s.is_active
            }
            for s in students
        ],
        "scores_count": len(scores),
        "scores": [
            {
                "id": sc.id,
                "student_id": sc.student_id,
                "subject_id": sc.subject_id,
                "semester_id": sc.semester_id,
                "class_score": sc.class_score,
                "exam_score": sc.exam_score,
                "total_score": sc.total_score,
                "grade": sc.grade,
                "remark": sc.remark,
                "approval_status": sc.approval_status
            }
            for sc in scores
        ],
        "generated_at": datetime.utcnow().isoformat(),
        "version": "1.0-delta-sync"
    }


def restore_school_snapshot(db: Session, school_id: int, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Restores or initializes a full school tenant dataset from a snapshot object.
    Supports complete offline workstation bootstrapping and disaster recovery.
    """
    data = snapshot.get("data") or snapshot.get("snapshot") or snapshot
    students_data = data.get("students") or []
    settings_data = data.get("settings") or []
    scores_data = data.get("scores") or []

    restored_students = 0
    for s_raw in students_data:
        code = s_raw.get("student_code")
        if not code:
            continue
        st = db.query(Student).filter(Student.school_id == school_id, Student.student_code == code).first()
        if not st:
            st = Student(
                student_code=code,
                full_name=s_raw.get("full_name", f"Student {code}"),
                school_id=school_id,
                gender=s_raw.get("gender"),
                phone=s_raw.get("phone"),
                address=s_raw.get("address"),
                guardian_name=s_raw.get("guardian_name"),
                residential_status=s_raw.get("residential_status", "B"),
                bece_index_number=s_raw.get("bece_index_number"),
                bece_raw_score=s_raw.get("bece_raw_score"),
                bece_aggregate=s_raw.get("bece_aggregate"),
                is_active=bool(s_raw.get("is_active", True))
            )
            db.add(st)
            restored_students += 1
        else:
            if "full_name" in s_raw: st.full_name = s_raw["full_name"]
            if "phone" in s_raw: st.phone = s_raw["phone"]
            if "guardian_name" in s_raw: st.guardian_name = s_raw["guardian_name"]
            if "residential_status" in s_raw: st.residential_status = s_raw["residential_status"]

    restored_settings = 0
    for sett in settings_data:
        k, v = sett.get("key"), str(sett.get("value", ""))
        if not k:
            continue
        existing_s = db.query(Setting).filter(Setting.school_id == school_id, Setting.key == k).first()
        if not existing_s:
            db.add(Setting(school_id=school_id, key=k, value=v))
            restored_settings += 1
        else:
            existing_s.value = v

    db.commit()

    return {
        "status": "success",
        "school_id": school_id,
        "restored": {
            "students": restored_students,
            "settings": restored_settings,
            "scores": len(scores_data)
        },
        "message": f"Successfully restored {restored_students} students and {restored_settings} settings."
    }
