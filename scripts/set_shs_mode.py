import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database import SessionLocal
from backend.app.models import Setting

def update_mode():
    db = SessionLocal()
    setting = db.query(Setting).filter(Setting.key == "school_mode").first()
    if not setting:
        setting = Setting(key="school_mode", value="SHS_ONLY")
        db.add(setting)
    else:
        print(f"Updating school_mode from '{setting.value}' -> 'SHS_ONLY'")
        setting.value = "SHS_ONLY"
    
    db.commit()
    print("[PASS] System school_mode successfully updated to SHS_ONLY in school.db!")

if __name__ == "__main__":
    update_mode()
