import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database import SessionLocal
from backend.app.models import Subject

def fix_levels():
    db = SessionLocal()
    basic_codes = [
        "SMS-KG", "RPL-KG", "NUM-KG", "CPD-KG", "LIT-KG", "OWOP-BAS", "PD-KG",
        "ENG-BAS", "MATH-BAS", "SCI-BAS", "SOC-BAS", "RME-BAS", "HIST-BAS",
        "COMP-BAS", "CAD-BAS", "CT-BAS", "GHL-BAS", "FRE-BAS", "PEH-BAS"
    ]
    basic_names = [
        "Sensory & Motor Skills", "Rhymes, Phonics & Language", "Early Numeracy",
        "Creative Play & Drawing", "Language and Literacy", "Our World Our People",
        "Physical Development", "English Language", "Mathematics", "Science",
        "Social Studies", "Religious and Moral Education", "History of Ghana",
        "Computing", "Creative Arts and Design", "Career Technology",
        "Ghanaian Language", "French", "Physical and Health Education"
    ]
    
    updated_count = 0
    all_subjects = db.query(Subject).all()
    for subj in all_subjects:
        if (subj.code and subj.code in basic_codes) or (subj.name in basic_names):
            if subj.school_level != "Basic":
                print(f"Updating '{subj.name}' ({subj.code}) from '{subj.school_level}' -> 'Basic'")
                subj.school_level = "Basic"
                updated_count += 1
                
    db.commit()
    print(f"Done! Updated {updated_count} subjects to school_level = 'Basic'.")

if __name__ == "__main__":
    fix_levels()
