from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..database import get_db
from ..models import Asset, TextbookAllocation, UniformItem, UniformDisbursement, Student, Subject, User
from ..schemas import AssetCreate, AssetResponse, TextbookIssueRequest, UniformItemCreate, UniformDisburseRequest
from ..dependencies import get_current_user, get_school_id

router = APIRouter()

def _check_storekeeper_or_admin(current_user: User):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    roles = [r.name.lower() for r in current_user.roles]
    if not any(r in roles for r in ["admin", "super_admin", "storekeeper", "assistant_headmaster_admin", "assistant_head_admin"]):
        raise HTTPException(status_code=403, detail="Access Denied: Storekeeper or Admin privileges required.")

# ── 1. Institutional Assets ─────────────────────────────────────────────────

@router.get("/", response_model=List[AssetResponse])
def list_assets(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    school_id = get_school_id(current_user)
    query = db.query(Asset)
    if school_id is not None:
        query = query.filter((Asset.school_id == school_id) | (Asset.school_id.is_(None)))
    if category:
        query = query.filter(Asset.category == category)
    return query.order_by(Asset.id.desc()).all()

@router.post("/", response_model=AssetResponse)
def create_asset(
    payload: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_storekeeper_or_admin(current_user)
    school_id = get_school_id(current_user)
    
    asset = Asset(
        name=payload.name,
        category=payload.category,
        serial_number=payload.serial_number,
        quantity=payload.quantity,
        unit_cost=payload.unit_cost,
        location=payload.location,
        status=payload.status,
        school_id=school_id
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset

@router.delete("/{asset_id}")
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_storekeeper_or_admin(current_user)
    school_id = get_school_id(current_user)
    asset_q = db.query(Asset).filter(Asset.id == asset_id)
    if school_id is not None:
        asset_q = asset_q.filter(Asset.school_id == school_id)
    asset = asset_q.first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found in your school")
    db.delete(asset)
    db.commit()
    return {"status": "success", "message": "Asset deleted"}

# ── 2. Textbook Allocations ──────────────────────────────────────────────────

@router.get("/textbooks")
def list_textbook_allocations(
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    school_id = get_school_id(current_user)
    query = db.query(TextbookAllocation)
    if school_id is not None:
        query = query.filter((TextbookAllocation.school_id == school_id) | (TextbookAllocation.school_id.is_(None)))
    if student_id:
        query = query.filter(TextbookAllocation.student_id == student_id)
        
    records = query.order_by(TextbookAllocation.id.desc()).all()
    results = []
    for r in records:
        results.append({
            "id": r.id,
            "book_title": r.book_title,
            "barcode_id": r.barcode_id,
            "subject_name": r.subject.name if r.subject else "General",
            "student_id": r.student_id,
            "student_name": r.student.full_name if r.student else f"Student {r.student_id}",
            "student_code": r.student.student_code if r.student else "",
            "issued_date": r.issued_date,
            "expected_return_date": r.expected_return_date,
            "actual_return_date": r.actual_return_date,
            "status": r.status
        })
    return results

@router.post("/textbooks/issue")
def issue_textbook(
    payload: TextbookIssueRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_storekeeper_or_admin(current_user)
    school_id = get_school_id(current_user)
    
    st_q = db.query(Student).filter(Student.id == payload.student_id)
    if school_id is not None:
        st_q = st_q.filter(Student.school_id == school_id)
    student = st_q.first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found in your school")
        
    # Check if barcode is already issued
    existing = db.query(TextbookAllocation).filter(
        TextbookAllocation.barcode_id == payload.barcode_id,
        TextbookAllocation.status == "Issued"
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Textbook barcode '{payload.barcode_id}' is already issued to student {existing.student.full_name}.")

    ret_date = None
    if payload.expected_return_date:
        try:
            ret_date = datetime.fromisoformat(payload.expected_return_date.replace("Z", ""))
        except Exception:
            pass

    alloc = TextbookAllocation(
        book_title=payload.book_title,
        barcode_id=payload.barcode_id,
        subject_id=payload.subject_id,
        student_id=payload.student_id,
        expected_return_date=ret_date,
        status="Issued",
        school_id=school_id
    )
    db.add(alloc)
    db.commit()
    db.refresh(alloc)
    return {"status": "success", "message": "Textbook issued", "id": alloc.id}

@router.patch("/textbooks/{alloc_id}/return")
def return_textbook(
    alloc_id: int,
    status: str = Query("Returned"), # Returned | Lost | Damaged
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_storekeeper_or_admin(current_user)
    school_id = get_school_id(current_user)
    alloc_q = db.query(TextbookAllocation).filter(TextbookAllocation.id == alloc_id)
    if school_id is not None:
        alloc_q = alloc_q.filter(TextbookAllocation.school_id == school_id)
    alloc = alloc_q.first()
    if not alloc:
        raise HTTPException(status_code=404, detail="Textbook allocation record not found in your school")
        
    alloc.status = status
    alloc.actual_return_date = datetime.now()
    db.commit()
    return {"status": "success", "message": f"Textbook marked as {status}"}

# ── 3. Uniform Inventory & Disbursement ────────────────────────────────────

@router.get("/uniforms")
def list_uniform_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    school_id = get_school_id(current_user)
    query = db.query(UniformItem)
    if school_id is not None:
        query = query.filter((UniformItem.school_id == school_id) | (UniformItem.school_id.is_(None)))
    return query.order_by(UniformItem.item_name).all()

@router.post("/uniforms")
def create_uniform_item(
    payload: UniformItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_storekeeper_or_admin(current_user)
    school_id = get_school_id(current_user)
    
    item = UniformItem(
        item_name=payload.item_name,
        size=payload.size,
        quantity_in_stock=payload.quantity_in_stock,
        unit_price=payload.unit_price,
        school_id=school_id
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.post("/uniforms/disburse")
def disburse_uniform(
    payload: UniformDisburseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _check_storekeeper_or_admin(current_user)
    school_id = get_school_id(current_user)
    
    st_q = db.query(Student).filter(Student.id == payload.student_id)
    if school_id is not None:
        st_q = st_q.filter(Student.school_id == school_id)
    student = st_q.first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found in your school")
        
    it_q = db.query(UniformItem).filter(UniformItem.id == payload.item_id)
    if school_id is not None:
        it_q = it_q.filter(UniformItem.school_id == school_id)
    item = it_q.first()
    if not item:
        raise HTTPException(status_code=404, detail="Uniform item not found in your school")
        
    if item.quantity_in_stock < payload.quantity:
        raise HTTPException(status_code=400, detail=f"Insufficient stock for {item.item_name} (Size: {item.size}). Available: {item.quantity_in_stock}")
        
    item.quantity_in_stock -= payload.quantity
    disbursement = UniformDisbursement(
        student_id=payload.student_id,
        item_id=payload.item_id,
        quantity=payload.quantity,
        remarks=payload.remarks,
        school_id=school_id
    )
    db.add(disbursement)
    db.commit()
    return {"status": "success", "message": "Uniform disbursed successfully"}

@router.get("/uniforms/disbursements")
def list_disbursements(
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    school_id = get_school_id(current_user)
    query = db.query(UniformDisbursement)
    if school_id is not None:
        query = query.filter((UniformDisbursement.school_id == school_id) | (UniformDisbursement.school_id.is_(None)))
    if student_id:
        query = query.filter(UniformDisbursement.student_id == student_id)
        
    disbursements = query.order_by(UniformDisbursement.id.desc()).all()
    results = []
    for d in disbursements:
        results.append({
            "id": d.id,
            "student_id": d.student_id,
            "student_name": d.student.full_name if d.student else f"Student {d.student_id}",
            "student_code": d.student.student_code if d.student else "",
            "item_name": d.item.item_name if d.item else "Uniform",
            "size": d.item.size if d.item else "",
            "quantity": d.quantity,
            "disbursed_date": d.disbursed_date,
            "remarks": d.remarks
        })
    return results
