from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Header
from sqlalchemy.orm import Session
import json
import os
import time
import shutil
import base64
import io
import mimetypes
from ..database import get_db
from typing import Optional
from ..models import Setting, User, AcademicYear, Semester, School
from ..dependencies import get_current_user, get_current_user_optional

try:
    from PIL import Image
except ImportError:
    Image = None

router = APIRouter()

def _process_image_to_base64(file_bytes: bytes, filename: str, max_size=(360, 360), quality=85) -> str:
    """
    Compress and convert an image to a self-contained Base64 Data URI.
    Ensures images survive cloud restarts, works 100% offline, and prevents 404s.
    """
    ext = os.path.splitext(filename)[1].lower()
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = "image/png" if ext == ".png" else "image/jpeg"

    if Image and ext in [".png", ".jpg", ".jpeg", ".webp"]:
        try:
            img = Image.open(io.BytesIO(file_bytes))
            # Preserve transparency if available
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                resample = getattr(Image, "Resampling", None)
                filter_mode = resample.LANCZOS if resample else Image.ANTIALIAS
                img.thumbnail(max_size, filter_mode)
                out_io = io.BytesIO()
                img.save(out_io, format="PNG", optimize=True)
                b64_str = base64.b64encode(out_io.getvalue()).decode("utf-8")
                return f"data:image/png;base64,{b64_str}"
            else:
                img = img.convert("RGB")
                resample = getattr(Image, "Resampling", None)
                filter_mode = resample.LANCZOS if resample else Image.ANTIALIAS
                img.thumbnail(max_size, filter_mode)
                out_io = io.BytesIO()
                img.save(out_io, format="JPEG", quality=quality, optimize=True)
                b64_str = base64.b64encode(out_io.getvalue()).decode("utf-8")
                return f"data:image/jpeg;base64,{b64_str}"
        except Exception as e:
            print(f"PIL processing warning: {e}")

    # Fallback direct base64 encoding
    b64_str = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{b64_str}"

@router.get("/")
def get_settings(db: Session = Depends(get_db), current_user: Optional[User] = Depends(get_current_user_optional), x_school_id: Optional[str] = Header(None, alias="X-School-Id")):
    settings_list = db.query(Setting).all()
    res = {s.key: s.value for s in settings_list}

    target_school_id = None
    if isinstance(x_school_id, str) and x_school_id.strip():
        try:
            target_school_id = int(x_school_id.strip())
        except ValueError:
            pass
    elif isinstance(x_school_id, (int, float)):
        target_school_id = int(x_school_id)
    elif isinstance(current_user, User) and current_user.school_id:
        target_school_id = current_user.school_id

    if target_school_id:
        school = db.query(School).filter(School.id == target_school_id).first()
        if school:
            res["school_name"] = school.name
            res["school_code"] = school.code
            res["school_abbreviation"] = school.code
            if school.logo_url:
                res["school_logo"] = school.logo_url
            if school.school_mode:
                res["school_mode"] = school.school_mode
    elif isinstance(current_user, User) and current_user.school:
        res["school_name"] = current_user.school.name
        res["school_code"] = current_user.school.code
        res["school_abbreviation"] = current_user.school.code
        if current_user.school.logo_url:
            res["school_logo"] = current_user.school.logo_url
        if current_user.school.school_mode:
            res["school_mode"] = current_user.school.school_mode

    curr_year = db.query(AcademicYear).filter(AcademicYear.is_current == True).first()
    curr_sem = db.query(Semester).filter(Semester.is_current == True).first()

    res["active_year_label"] = curr_year.label if curr_year else res.get("active_year_label", "")
    res["active_term_name"] = curr_sem.name if curr_sem else res.get("active_term_name", "")
    res["active_academic_year_id"] = str(curr_year.id) if curr_year else res.get("active_academic_year_id", "")
    res["active_semester_id"] = str(curr_sem.id) if curr_sem else res.get("active_semester_id", "")
    res["system_theme"] = res.get("system_theme", "midnight")
    res["school_mode"] = res.get("school_mode", "COMBINED")
    if res["school_mode"] == "BASIC_ONLY":
        res["grading_standard"] = res.get("grading_standard") if res.get("grading_standard") in ("BECE", "PRIMARY") else "BECE"
    elif res["school_mode"] == "SHS_ONLY":
        res["grading_standard"] = res.get("grading_standard") if res.get("grading_standard") in ("WAEC", "WASSCE") else "WAEC"
    else:
        res["grading_standard"] = res.get("grading_standard", "WAEC")
    res["boarding_status"] = res.get("boarding_status", "BOARDING_AND_DAY")
    # Auto-derive boarding_hierarchy_mode from school_mode — never stored manually.
    # BASIC_ONLY schools use a 2-tier structure (no Senior In-Charge tier).
    # SHS_ONLY and COMBINED use the full 3-tier SHS hierarchy.
    _mode_for_hierarchy = res.get("school_mode", "COMBINED").upper()
    res["boarding_hierarchy_mode"] = (
        "BASIC_TWO_TIER" if _mode_for_hierarchy == "BASIC_ONLY" else "SHS_THREE_TIER"
    )
    try:
        res["class_score_weight"] = int(res.get("class_score_weight", 30))
    except Exception:
        res["class_score_weight"] = 30
    try:
        res["exam_score_weight"] = int(res.get("exam_score_weight", 70))
    except Exception:
        res["exam_score_weight"] = 70

    return res

@router.put("/")
def update_settings(payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    role_names = [r.name for r in current_user.roles]
    if "admin" not in role_names and "super_admin" not in role_names:
        raise HTTPException(status_code=403, detail="Only administrators can change system configuration")

    if "active_academic_year_id" in payload and payload["active_academic_year_id"]:
        try:
            y_id = int(payload["active_academic_year_id"])
            db.query(AcademicYear).update({"is_current": False})
            yr = db.query(AcademicYear).filter(AcademicYear.id == y_id).first()
            if yr:
                yr.is_current = True
        except Exception:
            pass

    if "active_semester_id" in payload and payload["active_semester_id"]:
        try:
            s_id = int(payload["active_semester_id"])
            db.query(Semester).update({"is_current": False})
            sem = db.query(Semester).filter(Semester.id == s_id).first()
            if sem:
                sem.is_current = True
        except Exception:
            pass

    is_super_admin = "super_admin" in role_names
    is_admin = "admin" in role_names or is_super_admin
    if not is_admin:
        for locked_key in ["school_name", "school_code", "school_abbreviation", "school_mode", "boarding_status", "boarding_hierarchy_mode"]:
            if locked_key in payload:
                del payload[locked_key]

    target_sch_id = getattr(current_user, 'school_id', None) or 1
    if target_sch_id:
        sch = db.query(School).filter(School.id == target_sch_id).first()
        if sch:
            if "school_mode" in payload and payload["school_mode"]:
                new_mode = str(payload["school_mode"]).upper()
                sch.school_mode = new_mode
                # Auto-derive and persist boarding_hierarchy_mode whenever school_mode changes
                auto_hierarchy = "BASIC_TWO_TIER" if new_mode == "BASIC_ONLY" else "SHS_THREE_TIER"
                hierarchy_setting = db.query(Setting).filter(
                    Setting.key == "boarding_hierarchy_mode"
                ).first()
                if hierarchy_setting:
                    hierarchy_setting.value = auto_hierarchy
                else:
                    db.add(Setting(key="boarding_hierarchy_mode", value=auto_hierarchy))
            if "boarding_status" in payload and payload["boarding_status"]:
                sch.boarding_type = str(payload["boarding_status"]).upper()

    for key, value in payload.items():
        if isinstance(value, (list, dict)):
            val_str = json.dumps(value)
        else:
            val_str = str(value)
            
        setting = db.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = val_str
        else:
            new_setting = Setting(key=key, value=val_str)
            db.add(new_setting)
    
    db.commit()
    return {"status": "success"}

@router.post("/upload-logo")
async def upload_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    role_names = [r.name for r in current_user.roles]
    if "admin" not in role_names and "super_admin" not in role_names:
        raise HTTPException(status_code=403, detail="Only administrators can upload school logos")

    # Validate file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Only images are allowed.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Convert to Base64 data URI (persistent & works offline / on cloud)
    data_uri = _process_image_to_base64(file_bytes, file.filename, max_size=(360, 360))

    # Determine paths for local caching
    current_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "frontend"))
    upload_dir = os.path.join(frontend_dir, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # Delete existing school logo files in uploads to save space
    try:
        for filename in os.listdir(upload_dir):
            if filename.startswith("school_logo_"):
                os.remove(os.path.join(upload_dir, filename))
    except Exception as e:
        print(f"Error cleaning old logo files: {e}")

    # Save new logo with a timestamp to avoid caching
    timestamp = int(time.time())
    new_filename = f"school_logo_{timestamp}{ext}"
    file_path = os.path.join(upload_dir, new_filename)

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file_bytes)
    except Exception as e:
        print(f"Warning saving local logo cache: {e}")

    web_path = f"/uploads/{new_filename}"

    # Save/update setting with persistent Data URI
    setting = db.query(Setting).filter(Setting.key == "school_logo").first()
    if setting:
        setting.value = data_uri
    else:
        new_setting = Setting(key="school_logo", value=data_uri)
        db.add(new_setting)

    # Sync with associated School model if available
    target_sch_id = getattr(current_user, 'school_id', None)
    if target_sch_id:
        sch = db.query(School).filter(School.id == target_sch_id).first()
        if sch:
            sch.logo_url = data_uri

    db.commit()

    return {"logo_url": data_uri, "web_path": web_path}

@router.delete("/logo")
def delete_logo(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    role_names = [r.name for r in current_user.roles]
    if "admin" not in role_names and "super_admin" not in role_names:
        raise HTTPException(status_code=403, detail="Only administrators can remove school logos")

    setting = db.query(Setting).filter(Setting.key == "school_logo").first()
    if setting:
        setting.value = ""

    target_sch_id = getattr(current_user, 'school_id', None)
    if target_sch_id:
        sch = db.query(School).filter(School.id == target_sch_id).first()
        if sch:
            sch.logo_url = None

    db.commit()
    return {"status": "success", "message": "School logo reset to default"}

@router.post("/upload-signature")
async def upload_signature(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    role_names = [r.name for r in current_user.roles]
    if "admin" not in role_names and "super_admin" not in role_names:
        raise HTTPException(status_code=403, detail="Only administrators can upload headmaster signatures")

    # Validate file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Only images are allowed.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    data_uri = _process_image_to_base64(file_bytes, file.filename, max_size=(400, 160))

    # Determine paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "frontend"))
    upload_dir = os.path.join(frontend_dir, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # Delete existing signature files in uploads to save space
    try:
        for filename in os.listdir(upload_dir):
            if filename.startswith("headmaster_signature_"):
                os.remove(os.path.join(upload_dir, filename))
    except Exception as e:
        print(f"Error cleaning old signature files: {e}")

    # Save new signature with a timestamp to avoid caching
    timestamp = int(time.time())
    new_filename = f"headmaster_signature_{timestamp}{ext}"
    file_path = os.path.join(upload_dir, new_filename)

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file_bytes)
    except Exception as e:
        print(f"Warning saving local signature cache: {e}")

    web_path = f"/uploads/{new_filename}"

    # Save/update setting
    setting = db.query(Setting).filter(Setting.key == "headmaster_signature").first()
    if setting:
        setting.value = data_uri
    else:
        new_setting = Setting(key="headmaster_signature", value=data_uri)
        db.add(new_setting)
    db.commit()

    return {"signature_url": data_uri, "web_path": web_path}


@router.post("/upload-code-of-conduct")
def upload_code_of_conduct(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload official School Code of Conduct document (PDF or Image).
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    role_names = [r.name for r in current_user.roles]
    if "admin" not in role_names and "super_admin" not in role_names and "headmaster" not in role_names:
        raise HTTPException(status_code=403, detail="Only administrators can upload the Code of Conduct document")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".png", ".jpg", ".jpeg", ".webp"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF and image files are allowed.")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "frontend"))
    upload_dir = os.path.join(frontend_dir, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    timestamp = int(time.time())
    new_filename = f"code_of_conduct_{timestamp}{ext}"
    file_path = os.path.join(upload_dir, new_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    web_path = f"/assets/uploads/{new_filename}"
    
    setting = db.query(Setting).filter(Setting.key == "code_of_conduct_pdf_url").first()
    if setting:
        setting.value = web_path
    else:
        db.add(Setting(key="code_of_conduct_pdf_url", value=web_path))
    db.commit()

    return {"document_url": web_path}


# Initialize default settings if they don't exist
def seed_default_settings(db: Session):
    default_conduct = """1. ATTENDANCE & PUNCTUALITY: All students must attend all morning assemblies, classes, and official school gatherings on time.
2. UNIFORM & DRESS CODE: Students must wear prescribed, neat school uniforms at all times. Low haircuts are mandatory for all students in accordance with GES guidelines.
3. MOBILE DEVICES & ELECTRONICS: Mobile phones, smart watches, and unauthorized electronic gadgets are strictly prohibited on school premises.
4. EXAMINATION ETHICS: Any form of examination malpractice or dishonesty will result in immediate dismissal and reporting to WAEC.
5. SUBSTANCE PROHIBITION: Possession or consumption of alcohol, tobacco, narcotics, or illicit substances is strictly forbidden.
6. RESPECT & PROPERTY: Vandalism, bullying, cyber-harassment, and disrespect toward staff or fellow students will attract severe disciplinary action."""

    default_pledge = """I, as a student of this Senior High School, solemnly pledge to uphold the highest standards of academic integrity, personal discipline, and respect for school rules and regulations. I accept that admission to this institution is a privilege, and I agree to abide fully by the School Code of Conduct. I acknowledge that breach of these rules may lead to disciplinary sanctions including suspension or withdrawal."""

    defaults = {
        "school_name": "My School",
        "school_abbreviation": "eduManage360",
        "school_logo": "",
        "code_of_conduct_text": default_conduct,
        "student_pledge_text": default_pledge,
        "code_of_conduct_pdf_url": "",
        "paystack_public_key": "",
        "paystack_secret_key": "",
        "paystack_enabled": "false",
        "grading_standard": "WAEC",
        "grading_rules": json.dumps([
            {"grade": "A1", "min_score": 80, "remark": "Excellent", "point": 1},
            {"grade": "B2", "min_score": 70, "remark": "Very Good", "point": 2},
            {"grade": "B3", "min_score": 60, "remark": "Good", "point": 3},
            {"grade": "C4", "min_score": 55, "remark": "Credit", "point": 4},
            {"grade": "C5", "min_score": 50, "remark": "Credit", "point": 5},
            {"grade": "C6", "min_score": 45, "remark": "Credit", "point": 6},
            {"grade": "D7", "min_score": 40, "remark": "Pass", "point": 7},
            {"grade": "E8", "min_score": 35, "remark": "Pass", "point": 8},
            {"grade": "F9", "min_score": 0, "remark": "Fail", "point": 9}
        ])
    }
    for key, val in defaults.items():
        if not db.query(Setting).filter(Setting.key == key).first():
            db.add(Setting(key=key, value=val))
    db.commit()
