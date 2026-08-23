import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from backend.app.database import SessionLocal
from backend.app.models import Subject
from backend.app.routes.subjects import list_subjects

def test_filtering():
    db = SessionLocal()
    
    shs_and_stem_subs = list_subjects(school_level=None, exclude_basic=True, db=db)
    basic_subs = list_subjects(school_level="Basic", db=db)
    shs_subs = list_subjects(school_level="SHS", db=db)
    stem_subs = list_subjects(school_level="STEM", db=db)
    
    print(f"SHS & STEM Subjects (SHS_ONLY mode default): {len(shs_and_stem_subs)}")
    print(f"Basic Subjects: {len(basic_subs)}")
    print(f"SHS Subjects:   {len(shs_subs)}")
    print(f"STEM Subjects:  {len(stem_subs)}")
    
    assert len(basic_subs) >= 15, "Basic subjects filter failed!"
    assert len(shs_subs) >= 20, "SHS subjects filter failed!"
    assert len(stem_subs) >= 5, "STEM subjects filter failed!"
    assert len(shs_subs) + len(stem_subs) == len(shs_and_stem_subs), "Sum of SHS and STEM subjects does not equal SHS_ONLY mode total!"
    
    print("[PASS] All subject level filtering tests passed cleanly!")

if __name__ == "__main__":
    test_filtering()
