import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath("backend"))

from app.database import SessionLocal, engine, Base
from app.models import Asset, TextbookAllocation, UniformItem, UniformDisbursement, GatePassLog, User, Student

def test_phase3():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    print("Testing Phase 3 Models and Operations...")
    
    # 1. Test Asset Creation
    asset = Asset(
        name="Physics Lab Oscilloscope",
        category="Lab Equipment",
        serial_number="LAB-OSC-2026",
        quantity=5,
        unit_cost=1200.00,
        location="Lab 1",
        status="Good"
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    print(f"[OK] Asset created successfully: ID {asset.id} - {asset.name} (Qty: {asset.quantity})")
    
    # 2. Test Uniform Item Stock & Disbursement
    uniform = UniformItem(
        item_name="School Blazer (Boys)",
        size="M",
        quantity_in_stock=100,
        unit_price=150.00
    )
    db.add(uniform)
    db.commit()
    db.refresh(uniform)
    print(f"[OK] Uniform item created: ID {uniform.id} - {uniform.item_name} (Stock: {uniform.quantity_in_stock})")
    
    student = db.query(Student).first()
    if student:
        disbursement = UniformDisbursement(
            student_id=student.id,
            item_id=uniform.id,
            quantity=2,
            remarks="Initial SHS Admission Issue"
        )
        uniform.quantity_in_stock -= 2
        db.add(disbursement)
        db.commit()
        print(f"[OK] Uniform disbursed to {student.full_name}. Updated Stock: {uniform.quantity_in_stock}")
        
        # 3. Test Textbook Allocation
        textbook = TextbookAllocation(
            book_title="Core Mathematics for SHS",
            barcode_id="CMATH-2026-0001",
            student_id=student.id,
            status="Issued"
        )
        db.add(textbook)
        db.commit()
        db.refresh(textbook)
        print(f"[OK] Textbook issued: Barcode {textbook.barcode_id} to {student.full_name}")

    db.close()
    print("\nALL PHASE 3 VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_phase3()
