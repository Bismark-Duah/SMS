from fastapi import APIRouter, Depends, HTTPException, Header, Request, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Dict, Any, List
import json
import os
import urllib.request
import urllib.error
from datetime import datetime

from ..database import get_db
from ..models import User, School, SyncOutbox, Student, Score, Setting
from ..dependencies import get_current_user, get_school_id
from ..services.sync_engine import (
    sign_sync_payload,
    verify_sync_signature,
    compute_payload_checksum,
    log_sync_change,
    apply_sync_bundle,
    generate_school_snapshot,
    get_sync_secret
)

router = APIRouter()

# ── Helper for role verification ───────────────────────────────────────────────
def _require_admin_or_ict(user: User):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    role_names = [r.name.lower() for r in user.roles] if hasattr(user, 'roles') and user.roles else []
    allowed = {
        "admin", "super_admin", "headmaster", "headmistress",
        "assistant_headmaster_academic", "assistant_head_academic",
        "assistant_headmaster_admin", "assistant_head_admin",
        "ict_coordinator", "school_administrator", "secretary"
    }
    if not any(r in allowed for r in role_names):
        raise HTTPException(status_code=403, detail="Permission denied: ICT Coordinator or Administrator access required.")


# ── GET /status — Sync Health and Queue Telemetry ──────────────────────────────
@router.get("/status")
def get_sync_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    school_id = get_school_id(current_user) or 1
    
    pending_count = db.query(SyncOutbox).filter(
        SyncOutbox.school_id == school_id,
        SyncOutbox.is_synced == False
    ).count()

    total_synced = db.query(SyncOutbox).filter(
        SyncOutbox.school_id == school_id,
        SyncOutbox.is_synced == True
    ).count()

    last_synced_entry = db.query(SyncOutbox).filter(
        SyncOutbox.school_id == school_id,
        SyncOutbox.is_synced == True
    ).order_by(SyncOutbox.synced_at.desc()).first()

    cloud_sync_url = os.getenv("CLOUD_SYNC_URL", "").strip()
    is_cloud_configured = bool(cloud_sync_url)

    # Check recent outbox items for audit trail
    recent_outbox = db.query(SyncOutbox).filter(
        SyncOutbox.school_id == school_id
    ).order_by(SyncOutbox.created_at.desc()).limit(15).all()

    return {
        "status": "healthy",
        "school_id": school_id,
        "sync_mode": "STORE_AND_FORWARD_DELTA",
        "pending_count": pending_count,
        "total_synced_count": total_synced,
        "last_synced_at": last_synced_entry.synced_at.isoformat() if (last_synced_entry and last_synced_entry.synced_at) else None,
        "cloud_sync_url": cloud_sync_url or "Direct Cloud DB / Localhost Loopback",
        "is_cloud_configured": is_cloud_configured,
        "recent_activity": [
            {
                "uuid": o.sync_uuid,
                "entity": o.entity_type,
                "action": o.action,
                "entity_id": o.entity_id,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "is_synced": o.is_synced,
                "synced_at": o.synced_at.isoformat() if o.synced_at else None
            }
            for o in recent_outbox
        ]
    }


# ── POST /push — Outbox Delta Dispatch ────────────────────────────────────────
@router.post("/push")
def push_pending_sync(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    school_id = get_school_id(current_user) or 1
    
    # Fetch pending items (batch of up to 250)
    pending_items = db.query(SyncOutbox).filter(
        SyncOutbox.school_id == school_id,
        SyncOutbox.is_synced == False
    ).order_by(SyncOutbox.created_at.asc()).limit(250).all()

    if not pending_items:
        return {
            "status": "success",
            "message": "Outbox is clear. All local changes are fully synchronized.",
            "synced_count": 0,
            "ack_uuids": []
        }

    # Prepare bundle payload
    bundle_items = []
    for item in pending_items:
        bundle_items.append({
            "sync_uuid": item.sync_uuid,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "action": item.action,
            "payload": json.loads(item.payload_json) if item.payload_json else {},
            "checksum": item.checksum,
            "created_at": item.created_at.isoformat() if item.created_at else datetime.utcnow().isoformat()
        })

    payload_data = {
        "school_id": school_id,
        "pushed_by_user": current_user.username,
        "timestamp": datetime.utcnow().isoformat(),
        "items_count": len(bundle_items),
        "items": bundle_items
    }

    payload_bytes = json.dumps(payload_data, sort_keys=True).encode("utf-8")
    signature = sign_sync_payload(payload_bytes)

    cloud_sync_url = os.getenv("CLOUD_SYNC_URL", "").strip()

    # If an external cloud URL is defined, transmit over HTTPS
    if cloud_sync_url and not cloud_sync_url.startswith("http://127.0.0.1") and not cloud_sync_url.startswith("http://localhost"):
        endpoint = f"{cloud_sync_url.rstrip('/')}/api/sync/receive"
        req = urllib.request.Request(
            endpoint,
            data=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Sync-Signature": signature,
                "X-School-Id": str(school_id),
                "User-Agent": "EduManage360-OfflineSyncEngine/4.2"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_body = resp.read().decode("utf-8")
                resp_json = json.loads(resp_body)
                ack_uuids = set(resp_json.get("ack_uuids", []))
        except Exception as net_err:
            raise HTTPException(
                status_code=502,
                detail=f"Cloud server sync failed: {str(net_err)}"
            )
    else:
        # Local loopback / self-contained direct merge
        applied_uuids, errs = apply_sync_bundle(db, school_id, bundle_items)
        ack_uuids = set(applied_uuids)

    # Mark acknowledged items as synced locally
    now = datetime.utcnow()
    synced_count = 0
    for item in pending_items:
        if item.sync_uuid in ack_uuids or not cloud_sync_url:
            item.is_synced = True
            item.synced_at = now
            synced_count += 1

    db.commit()

    return {
        "status": "success",
        "message": f"Successfully synchronized {synced_count} delta records to the cloud.",
        "synced_count": synced_count,
        "ack_uuids": list(ack_uuids)
    }


# ── POST /receive — Cloud-Side Ingestion Gateway ──────────────────────────────
@router.post("/receive")
async def receive_sync_bundle(
    request: Request,
    db: Session = Depends(get_db),
    x_sync_signature: Optional[str] = Header(None, alias="X-Sync-Signature"),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id")
):
    """
    Zero-Trust ingestion endpoint on the central cloud server.
    Verifies cryptographic HMAC-SHA256 signature and merges delta items safely.
    """
    raw_body = await request.body()
    if not raw_body:
        raise HTTPException(status_code=400, detail="Empty payload.")

    # 1. Cryptographic HMAC Verification
    if not verify_sync_signature(raw_body, x_sync_signature or ""):
        # Fallback check inside payload if not in header
        try:
            parsed = json.loads(raw_body.decode("utf-8"))
            body_sig = parsed.get("signature", "")
            # Recreate body without signature key
            items_copy = {k: v for k, v in parsed.items() if k != "signature"}
            clean_bytes = json.dumps(items_copy, sort_keys=True).encode("utf-8")
            if not verify_sync_signature(clean_bytes, body_sig):
                raise HTTPException(status_code=401, detail="Cryptographic signature verification failed: Payload rejected.")
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid HMAC-SHA256 signature. Sync bundle rejected.")

    try:
        data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    school_id = data.get("school_id") or (int(x_school_id) if x_school_id and x_school_id.isdigit() else 1)
    items = data.get("items") or []

    if not items:
        return {"status": "success", "applied_count": 0, "ack_uuids": [], "errors": []}

    applied_uuids, errors = apply_sync_bundle(db, school_id, items)

    return {
        "status": "success",
        "school_id": school_id,
        "applied_count": len(applied_uuids),
        "ack_uuids": applied_uuids,
        "errors": errors
    }


# ── POST /pull-snapshot — Disaster Recovery / New PC Onboarding Snapshot ──────
@router.post("/pull-snapshot")
def pull_school_snapshot(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_admin_or_ict(current_user)
    school_id = get_school_id(current_user) or 1
    
    snapshot = generate_school_snapshot(db, school_id)
    return {
        "status": "success",
        "school_id": school_id,
        "snapshot": snapshot
    }


# ── POST /restore-snapshot — Restore School Dataset from Snapshot ─────────────
@router.post("/restore-snapshot")
def restore_school_snapshot(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_admin_or_ict(current_user)
    school_id = get_school_id(current_user) or 1
    
    snapshot = payload.get("snapshot") or payload
    students_data = snapshot.get("students") or []
    scores_data = snapshot.get("scores") or []
    settings_data = snapshot.get("settings") or []

    restored_students = 0
    for s_raw in students_data:
        code = s_raw.get("student_code")
        if not code: continue
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

    # Restore settings
    for sett in settings_data:
        k, v = sett.get("key"), str(sett.get("value", ""))
        if not k: continue
        existing_s = db.query(Setting).filter(Setting.school_id == school_id, Setting.key == k).first()
        if not existing_s:
            db.add(Setting(school_id=school_id, key=k, value=v))
        else:
            existing_s.value = v

    db.commit()

    return {
        "status": "success",
        "message": f"Successfully restored snapshot for school {school_id}. {restored_students} new students added.",
        "restored_students_count": restored_students
    }


# ── POST /log-change — Outbox Queueing Helper ─────────────────────────────────
@router.post("/log-change")
def log_client_change(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    school_id = get_school_id(current_user) or 1
    entity_type = payload.get("entity_type", "custom")
    entity_id = payload.get("entity_id", "0")
    action = payload.get("action", "UPDATE")
    data = payload.get("data", {})

    entry = log_sync_change(db, school_id, entity_type, entity_id, action, data)
    db.commit()

    return {
        "status": "success",
        "sync_uuid": entry.sync_uuid,
        "is_synced": False
    }


# ── Super Admin Multi-Tenant Sync Telemetry & Orchestration ─────────────────

def _require_super_admin(user: User):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    role_names = [r.name.lower() for r in user.roles] if hasattr(user, 'roles') and user.roles else []
    if "super_admin" not in role_names and getattr(user, 'username', '').lower() != "superadmin":
        raise HTTPException(status_code=403, detail="Super-Admin privileges required.")


@router.get("/super-admin/overview")
def get_super_admin_sync_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_super_admin(current_user)
    
    schools = db.query(School).order_by(School.id.asc()).all()
    
    school_telemetry = []
    total_network_pending = 0
    total_network_synced = 0
    
    for s in schools:
        pending_cnt = db.query(SyncOutbox).filter(
            SyncOutbox.school_id == s.id,
            SyncOutbox.is_synced == False
        ).count()
        
        synced_cnt = db.query(SyncOutbox).filter(
            SyncOutbox.school_id == s.id,
            SyncOutbox.is_synced == True
        ).count()
        
        last_sync = db.query(SyncOutbox).filter(
            SyncOutbox.school_id == s.id,
            SyncOutbox.is_synced == True
        ).order_by(SyncOutbox.synced_at.desc()).first()
        
        total_network_pending += pending_cnt
        total_network_synced += synced_cnt
        
        # Determine status state
        if pending_cnt > 0:
            health_state = "PENDING_SYNC"
        elif synced_cnt > 0:
            health_state = "HEALTHY"
        else:
            health_state = "IDLE"
            
        school_telemetry.append({
            "school_id": s.id,
            "school_name": s.name,
            "school_code": s.code,
            "school_mode": s.school_mode or "COMBINED",
            "school_status": s.status or "ACTIVE",
            "pending_count": pending_cnt,
            "total_synced_count": synced_cnt,
            "last_synced_at": last_sync.synced_at.isoformat() if (last_sync and last_sync.synced_at) else None,
            "health_state": health_state
        })
        
    cloud_sync_url = os.getenv("CLOUD_SYNC_URL", "").strip()
    
    return {
        "status": "success",
        "total_schools": len(schools),
        "total_network_pending": total_network_pending,
        "total_network_synced": total_network_synced,
        "cloud_sync_url": cloud_sync_url or "Direct Cloud DB / Localhost Loopback",
        "is_cloud_configured": bool(cloud_sync_url),
        "schools": school_telemetry
    }


@router.post("/super-admin/trigger-school/{school_id}")
def trigger_school_sync(
    school_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_super_admin(current_user)
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail=f"School {school_id} not found.")
        
    pending_items = db.query(SyncOutbox).filter(
        SyncOutbox.school_id == school_id,
        SyncOutbox.is_synced == False
    ).order_by(SyncOutbox.created_at.asc()).limit(250).all()
    
    if not pending_items:
        return {
            "status": "success",
            "school_id": school_id,
            "school_name": school.name,
            "message": f"{school.name} outbox is clear. All records are in sync.",
            "synced_count": 0,
            "ack_uuids": []
        }
        
    bundle_items = []
    for item in pending_items:
        bundle_items.append({
            "sync_uuid": item.sync_uuid,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "action": item.action,
            "payload": json.loads(item.payload_json) if item.payload_json else {},
            "checksum": item.checksum,
            "created_at": item.created_at.isoformat() if item.created_at else datetime.utcnow().isoformat()
        })
        
    applied_uuids, errs = apply_sync_bundle(db, school_id, bundle_items)
    ack_set = set(applied_uuids)
    
    now = datetime.utcnow()
    synced_count = 0
    for item in pending_items:
        if item.sync_uuid in ack_set:
            item.is_synced = True
            item.synced_at = now
            synced_count += 1
            
    db.commit()
    
    return {
        "status": "success",
        "school_id": school_id,
        "school_name": school.name,
        "message": f"Successfully synchronized {synced_count} delta records for {school.name}.",
        "synced_count": synced_count,
        "ack_uuids": list(ack_set),
        "errors": errs
    }


@router.post("/super-admin/trigger-all")
def trigger_all_schools_sync(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_super_admin(current_user)
    schools = db.query(School).all()
    
    results = []
    total_synced_all = 0
    now = datetime.utcnow()
    
    for s in schools:
        pending_items = db.query(SyncOutbox).filter(
            SyncOutbox.school_id == s.id,
            SyncOutbox.is_synced == False
        ).all()
        
        if not pending_items:
            continue
            
        bundle_items = [
            {
                "sync_uuid": item.sync_uuid,
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "action": item.action,
                "payload": json.loads(item.payload_json) if item.payload_json else {},
                "checksum": item.checksum,
                "created_at": item.created_at.isoformat() if item.created_at else now.isoformat()
            }
            for item in pending_items
        ]
        
        applied_uuids, _ = apply_sync_bundle(db, s.id, bundle_items)
        ack_set = set(applied_uuids)
        
        synced_count = 0
        for item in pending_items:
            if item.sync_uuid in ack_set:
                item.is_synced = True
                item.synced_at = now
                synced_count += 1
                
        total_synced_all += synced_count
        results.append({
            "school_id": s.id,
            "school_name": s.name,
            "synced_count": synced_count
        })
        
    db.commit()
    
    return {
        "status": "success",
        "message": f"Global network synchronization complete. {total_synced_all} total delta records processed across {len(results)} schools.",
        "total_synced": total_synced_all,
        "details": results
    }
