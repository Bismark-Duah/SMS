import os
import sys

sys.path.insert(0, os.path.abspath("backend"))

from app.database import SessionLocal
from app.models import User, ClassSection, Subject
from app.routes.classes import list_sections, get_class_subjects, set_class_subjects
from app.routes.subjects import list_subjects

def main():
    print("=== Running Association API Verification ===")
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.username == "admin").first()
        
        # 1. Fetch class sections
        sections = list_sections(db=db, current_user=admin_user)
        print(f"[OK] Fetched {len(sections)} sections.")
        if sections:
            first_sec = sections[0]
            sec_dict = first_sec if isinstance(first_sec, dict) else first_sec.__dict__
            print(f"Sample section: {first_sec}")
            assert hasattr(first_sec, "school_type") or "school_type" in sec_dict, "school_type missing in response"
            assert hasattr(first_sec, "stage_name") or "stage_name" in sec_dict, "stage_name missing in response"
            print("[OK] school_type and stage_name are present in list_sections response.")
            
            section_id = first_sec.id if hasattr(first_sec, "id") else first_sec["id"]
            
            # 2. Assign subjects to the first class section
            subjects = list_subjects(db=db, current_user=admin_user)
            print(f"[OK] Fetched {len(subjects)} subjects.")
            if subjects:
                subject_ids = [sub.id if hasattr(sub, "id") else sub["id"] for sub in subjects]
                print(f"Associating subjects {subject_ids} to class section {section_id}")
                
                post_res = set_class_subjects(section_id=section_id, payload=subject_ids, db=db, current_user=admin_user)
                print(f"[OK] Subject association result: {post_res}")
                
                # 3. Retrieve associated subjects
                assoc_subjects = get_class_subjects(section_id=section_id, db=db, current_user=admin_user)
                print(f"[OK] Associated subjects count: {len(assoc_subjects)}")
                assoc_ids = [sub.id if hasattr(sub, "id") else sub["id"] for sub in assoc_subjects]
                print(f"Associated IDs: {assoc_ids}")
                
                for sid in subject_ids:
                    assert sid in assoc_ids, f"Subject ID {sid} was not successfully associated!"
                print("[OK] All subjects associated and retrieved successfully.")
            else:
                print("[SKIP] No subjects available to associate.")
        else:
            print("[SKIP] No sections available to test.")
        
        print("=== Verification Successful ===")
    except Exception as e:
        print(f"[FAIL] Verification failed: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
