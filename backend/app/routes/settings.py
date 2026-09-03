from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Header, Request
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
from ..dependencies import get_current_user, get_current_user_optional, get_school_id

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
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                buffered = io.BytesIO()
                img.save(buffered, format="PNG", optimize=True)
                encoded = base64.b64encode(buffered.getvalue()).decode("utf-8")
                return f"data:image/png;base64,{encoded}"
            else:
                img = img.convert("RGB")
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG", quality=quality, optimize=True)
                encoded = base64.b64encode(buffered.getvalue()).decode("utf-8")
                return f"data:image/jpeg;base64,{encoded}"
        except Exception as e:
            print(f"[LogoProcessor] Image compression error: {e}")
            pass

    # Fallback to direct raw Base64 Data URI
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"

@router.get("/public-branding")
def get_public_branding(
    db: Session = Depends(get_db),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id"),
    school_id: Optional[int] = Depends(get_school_id),
    mode: Optional[str] = None
):
    """
    Public lightweight endpoint returning school name, logo, and mode
    for public-facing portals (Candidate Admission, Result Checking, Parent Portal).
    """
    target_school_id = int(school_id) if isinstance(school_id, (int, float)) else None
    if not target_school_id and isinstance(x_school_id, str) and x_school_id.strip():
        try:
            target_school_id = int(x_school_id.strip())
        except ValueError:
            pass

    if target_school_id:
        settings_list = db.query(Setting).filter(
            (Setting.school_id == target_school_id) | (Setting.school_id == None)
        ).all()
    else:
        settings_list = db.query(Setting).all()

    res = {s.key: s.value for s in settings_list}

    school = None
    if target_school_id:
        school = db.query(School).filter(School.id == target_school_id).first()

    if not school and mode and mode.upper() in ["SHS", "SHS_ONLY", "CSSPS"]:
        # Prioritize Senior High / STEM / Technical School for CSSPS admission portal
        school = db.query(School).filter(School.school_mode.in_(["SHS_ONLY", "COMBINED"])).first()

    if not school:
        school = db.query(School).first()

    name = school.name if school else (res.get("school_name") or "GHANA SENIOR HIGH SCHOOL")
    logo = school.logo_url if school and school.logo_url else res.get("school_logo")
    smode = school.school_mode if school and school.school_mode else (res.get("school_mode") or "COMBINED")

    try:
        voucher_price = float(res.get("admission_voucher_price", "0.10"))
    except (ValueError, TypeError):
        voucher_price = 0.10

    momo_recipient_number = res.get("admission_momo_recipient_number", "0508929456")
    momo_recipient_name = res.get("admission_momo_recipient_name", "Duah Bismark")
    momo_recipient_network = res.get("admission_momo_recipient_network", "Telecel")

    return {
        "school_id": school.id if school else None,
        "school_name": name,
        "school_logo": logo,
        "school_mode": smode,
        "voucher_price": voucher_price,
        "momo_recipient_number": momo_recipient_number,
        "momo_recipient_name": momo_recipient_name,
        "momo_recipient_network": momo_recipient_network,
        "school_code": school.code if school else res.get("school_code", "")
    }

@router.get("/")
def get_settings(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
    school_id: Optional[int] = Depends(get_school_id),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id")
):
    user = current_user if isinstance(current_user, User) else None
    target_school_id = int(school_id) if isinstance(school_id, (int, float)) else None
    if target_school_id is None and isinstance(x_school_id, str) and x_school_id.strip():
        try:
            target_school_id = int(x_school_id.strip())
        except ValueError:
            pass
    elif target_school_id is None and user and user.school_id:
        target_school_id = user.school_id

    res = {}
    # 1. Global settings (fallback defaults)
    global_settings = db.query(Setting).filter(Setting.school_id == None).all()
    for s in global_settings:
        res[s.key] = s.value

    # 2. Tenant-specific settings override global defaults
    if target_school_id:
        tenant_settings = db.query(Setting).filter(Setting.school_id == target_school_id).all()
        for s in tenant_settings:
            res[s.key] = s.value
        school = db.query(School).filter(School.id == target_school_id).first()
        if school:
            res["school_name"] = school.name
            res["school_code"] = school.code
            res["school_abbreviation"] = school.code
            res["school_logo"] = school.logo_url or ""
            res["school_mode"] = school.school_mode or res.get("school_mode", "COMBINED")
            res["ownership_type"] = school.ownership_type or res.get("ownership_type", "PRIVATE")
            res["boarding_status"] = school.boarding_type or res.get("boarding_status", "BOARDING_AND_DAY")
    elif user and user.school:
        res["school_name"] = user.school.name
        res["school_code"] = user.school.code
        res["school_abbreviation"] = user.school.code
        res["school_logo"] = user.school.logo_url or ""
        res["school_mode"] = user.school.school_mode or res.get("school_mode", "COMBINED")
        res["ownership_type"] = user.school.ownership_type or res.get("ownership_type", "PRIVATE")
        res["boarding_status"] = user.school.boarding_type or res.get("boarding_status", "BOARDING_AND_DAY")
    else:
        school = db.query(School).first()
        if school:
            tenant_settings = db.query(Setting).filter(Setting.school_id == school.id).all()
            for s in tenant_settings:
                res[s.key] = s.value
            res["school_name"] = school.name
            res["school_code"] = school.code
            res["school_abbreviation"] = school.code
            res["school_logo"] = school.logo_url or ""
            res["school_mode"] = school.school_mode or res.get("school_mode", "COMBINED")
            res["ownership_type"] = school.ownership_type or res.get("ownership_type", "PRIVATE")
            res["boarding_status"] = school.boarding_type or res.get("boarding_status", "BOARDING_AND_DAY")

    curr_year = db.query(AcademicYear).filter(AcademicYear.is_current == True).first()
    curr_sem = db.query(Semester).filter(Semester.is_current == True).first()

    res["active_year_label"] = curr_year.label if curr_year else res.get("active_year_label", "")
    res["active_term_name"] = curr_sem.name if curr_sem else res.get("active_term_name", "")
    res["active_academic_year_id"] = str(curr_year.id) if curr_year else res.get("active_academic_year_id", "")
    res["active_semester_id"] = str(curr_sem.id) if curr_sem else res.get("active_semester_id", "")
    res["system_theme"] = res.get("system_theme", "midnight")
    res["school_mode"] = res.get("school_mode", "COMBINED")
    res["ownership_type"] = res.get("ownership_type", "PRIVATE")
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
def update_settings(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    school_id: Optional[int] = Depends(get_school_id),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id")
):
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
    # If not a platform super-admin, strictly strip governance-level parameters so school admins cannot override them
    if not is_super_admin:
        for locked_key in ["school_name", "school_code", "school_abbreviation", "school_mode", "boarding_status", "boarding_hierarchy_mode"]:
            if locked_key in payload:
                del payload[locked_key]

    target_sch_id = int(school_id) if isinstance(school_id, (int, float)) else None
    if target_sch_id is None and isinstance(x_school_id, str) and x_school_id.strip():
        try:
            target_sch_id = int(x_school_id.strip())
        except ValueError:
            pass
    elif target_sch_id is None and isinstance(current_user, User) and current_user.school_id:
        target_sch_id = current_user.school_id

    if target_sch_id:
        sch = db.query(School).filter(School.id == target_sch_id).first()
        if sch:
            if "school_name" in payload and payload["school_name"]:
                sch.name = str(payload["school_name"]).strip()
            if "school_abbreviation" in payload and payload["school_abbreviation"]:
                new_code = str(payload["school_abbreviation"]).strip()
                existing_code = db.query(School).filter(School.code == new_code, School.id != sch.id).first()
                if not existing_code:
                    sch.code = new_code
            elif "school_code" in payload and payload["school_code"]:
                new_code = str(payload["school_code"]).strip()
                existing_code = db.query(School).filter(School.code == new_code, School.id != sch.id).first()
                if not existing_code:
                    sch.code = new_code
            if "school_logo" in payload and payload["school_logo"]:
                sch.logo_url = str(payload["school_logo"]).strip()
            if "school_mode" in payload and payload["school_mode"]:
                new_mode = str(payload["school_mode"]).upper()
                sch.school_mode = new_mode
                # Auto-derive and persist boarding_hierarchy_mode whenever school_mode changes
                auto_hierarchy = "BASIC_TWO_TIER" if new_mode == "BASIC_ONLY" else "SHS_THREE_TIER"
                hierarchy_setting = db.query(Setting).filter(
                    Setting.key == "boarding_hierarchy_mode",
                    Setting.school_id == target_sch_id
                ).first()
                if hierarchy_setting:
                    hierarchy_setting.value = auto_hierarchy
                else:
                    db.add(Setting(school_id=target_sch_id, key="boarding_hierarchy_mode", value=auto_hierarchy))
            if "boarding_status" in payload and payload["boarding_status"]:
                sch.boarding_type = str(payload["boarding_status"]).upper()

    for key, value in payload.items():
        if isinstance(value, (list, dict)):
            val_str = json.dumps(value)
        else:
            val_str = str(value)
            
        if target_sch_id:
            setting = db.query(Setting).filter(
                Setting.key == key,
                Setting.school_id == target_sch_id
            ).first()
            if setting:
                setting.value = val_str
            else:
                new_setting = Setting(school_id=target_sch_id, key=key, value=val_str)
                db.add(new_setting)
        else:
            setting = db.query(Setting).filter(Setting.key == key).first()
            if setting:
                setting.value = val_str
    db.commit()
    return {"status": "success"}


MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_DOC_SIZE = 10 * 1024 * 1024   # 10 MB

def _validate_image_bytes(file_bytes: bytes, filename: str) -> str:
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds maximum size limit of 5MB.")
    
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
        raise HTTPException(status_code=400, detail="Invalid image format. Allowed formats: PNG, JPG, JPEG, WEBP.")
    
    # Check Magic Bytes
    if ext == ".png" and not file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=400, detail="Corrupted or invalid PNG file header.")
    elif ext in [".jpg", ".jpeg"] and not file_bytes.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=400, detail="Corrupted or invalid JPEG file header.")
    elif ext == ".webp" and not (file_bytes.startswith(b"RIFF") and b"WEBP" in file_bytes[:16]):
        raise HTTPException(status_code=400, detail="Corrupted or invalid WEBP file header.")
    
    return ext

def _validate_doc_bytes(file_bytes: bytes, filename: str) -> str:
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_DOC_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds maximum size limit of 10MB.")
    
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".pdf", ".png", ".jpg", ".jpeg", ".webp"]:
        raise HTTPException(status_code=400, detail="Invalid document format. Allowed formats: PDF, PNG, JPG, JPEG, WEBP.")
    
    if ext == ".pdf" and not file_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Corrupted or invalid PDF file header.")
    elif ext in [".png", ".jpg", ".jpeg", ".webp"]:
        _validate_image_bytes(file_bytes, filename)
    
    return ext

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

    file_bytes = await file.read()
    ext = _validate_image_bytes(file_bytes, file.filename or "logo.png")

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

    target_sch_id = getattr(current_user, 'school_id', None)
    # Save/update setting with persistent Data URI
    setting_q = db.query(Setting).filter(Setting.key == "school_logo")
    if target_sch_id:
        setting_q = setting_q.filter(Setting.school_id == target_sch_id)
    setting = setting_q.first()
    if setting:
        setting.value = data_uri
    else:
        new_setting = Setting(school_id=target_sch_id, key="school_logo", value=data_uri)
        db.add(new_setting)

    # Sync with associated School model if available
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

    target_sch_id = getattr(current_user, 'school_id', None)
    setting_q = db.query(Setting).filter(Setting.key == "school_logo")
    if target_sch_id:
        setting_q = setting_q.filter(Setting.school_id == target_sch_id)
    setting = setting_q.first()
    if setting:
        setting.value = ""

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

    file_bytes = await file.read()
    ext = _validate_image_bytes(file_bytes, file.filename or "signature.png")

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

    target_sch_id = getattr(current_user, 'school_id', None)
    # Save/update setting
    setting_q = db.query(Setting).filter(Setting.key == "headmaster_signature")
    if target_sch_id:
        setting_q = setting_q.filter(Setting.school_id == target_sch_id)
    setting = setting_q.first()
    if setting:
        setting.value = data_uri
    else:
        new_setting = Setting(school_id=target_sch_id, key="headmaster_signature", value=data_uri)
        db.add(new_setting)
    db.commit()

    return {"signature_url": data_uri, "web_path": web_path}


@router.post("/upload-code-of-conduct")
async def upload_code_of_conduct(
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

    file_bytes = await file.read()
    ext = _validate_doc_bytes(file_bytes, file.filename or "conduct.pdf")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "frontend"))
    upload_dir = os.path.join(frontend_dir, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    timestamp = int(time.time())
    new_filename = f"code_of_conduct_{timestamp}{ext}"
    file_path = os.path.join(upload_dir, new_filename)

    with open(file_path, "wb") as buffer:
        buffer.write(file_bytes)

    web_path = f"/assets/uploads/{new_filename}"
    
    target_sch_id = getattr(current_user, 'school_id', None)
    setting_q = db.query(Setting).filter(Setting.key == "code_of_conduct_pdf_url")
    if target_sch_id:
        setting_q = setting_q.filter(Setting.school_id == target_sch_id)
    setting = setting_q.first()
    if setting:
        setting.value = web_path
    else:
        new_setting = Setting(school_id=target_sch_id, key="code_of_conduct_pdf_url", value=web_path)
        db.add(new_setting)
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
        "admission_voucher_price": "0.10",
        "admission_momo_recipient_number": "0508929456",
        "admission_momo_recipient_name": "Duah Bismark",
        "admission_momo_recipient_network": "Telecel",
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


@router.get("/lan-info")
def get_lan_info(request: Request):
    """
    Returns the host machine's local IPv4 addresses or Cloud Host URL
    for offline Wi-Fi / LAN multi-device access across teachers' tablets & phones.
    """
    import socket

    # 1. Detect Cloud / Production Domain Request (Render, Railway, Custom Domain)
    host_header = ""
    proto_header = "http"
    if request is not None:
        host_header = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        proto_header = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
    
    hostname_clean = host_header.split(":")[0].lower() if host_header else ""

    is_cloud = (
        bool(hostname_clean)
        and hostname_clean not in ["localhost", "127.0.0.1"]
        and not hostname_clean.startswith("192.168.")
        and not hostname_clean.startswith("10.")
        and not hostname_clean.startswith("172.")
    )

    if is_cloud:
        cloud_url = f"{proto_header}://{host_header}"
        return {
            "hostname": hostname_clean,
            "port": 443 if proto_header == "https" else 80,
            "primary_url": cloud_url,
            "is_cloud": True,
            "interfaces": [
                {
                    "ip": hostname_clean,
                    "label": "Cloud Web Application",
                    "url": cloud_url,
                    "is_primary": True
                }
            ],
            "instructions": {
                "step1": "Open this URL or scan the QR code on any smartphone, tablet, or PC worldwide.",
                "step2": "No local Wi-Fi pairing required when accessing the Cloud Production Portal.",
                "step3": "Log in with your assigned institutional credentials."
            }
        }

    # 2. Local Offline-First LAN Probing (School Computer / Wi-Fi Hotspot)
    interfaces = []
    seen_ips = set()

    # Probe primary network interface
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("10.255.255.255", 1))
        primary_ip = s.getsockname()[0]
        s.close()
        if primary_ip and not primary_ip.startswith("127.") and primary_ip not in seen_ips:
            seen_ips.add(primary_ip)
            interfaces.append({
                "ip": primary_ip,
                "label": "Primary Wi-Fi / School LAN",
                "url": f"http://{primary_ip}:8000",
                "is_primary": True
            })
    except Exception:
        pass

    # Probe hostname interfaces (including Mobile Hotspots)
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip not in seen_ips and not ip.startswith("127."):
                seen_ips.add(ip)
                is_hotspot = ip.startswith("192.168.43.") or ip.startswith("192.168.137.")
                label = "Mobile Phone Hotspot" if is_hotspot else "Local Wi-Fi Network"
                interfaces.append({
                    "ip": ip,
                    "label": label,
                    "url": f"http://{ip}:8000",
                    "is_primary": False if interfaces else True
                })
    except Exception:
        pass

    # Fallback to localhost if offline standalone
    if not interfaces:
        interfaces.append({
            "ip": "127.0.0.1",
            "label": "Host Machine (Localhost)",
            "url": "http://127.0.0.1:8000",
            "is_primary": True
        })

    hostname = socket.gethostname() if hasattr(socket, "gethostname") else "Localhost"
    primary_url = interfaces[0]["url"]

    return {
        "hostname": hostname,
        "port": 8000,
        "primary_url": primary_url,
        "is_cloud": False,
        "interfaces": interfaces,
        "instructions": {
            "step1": "Ensure the teacher's phone, tablet, or laptop is connected to the same school Wi-Fi or mobile hotspot.",
            "step2": "Scan the QR code or open the displayed URL in any web browser (Chrome, Safari, Edge).",
            "step3": "Log in with the teacher's assigned username and password."
        }
    }


# ── Multi-Tenant Subaccounts, Hubtel SMS Config & Session Controls ───────────

from ..models import SchoolSubaccount, TenantSmsConfig, UserDeviceSession
from ..services.payment_orchestrator import create_or_update_paystack_subaccount
from ..middleware.device_session_guard import revoke_all_other_sessions, hash_token


@router.get("/subaccount")
def get_school_subaccount(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns current school's Paystack settlement subaccount details."""
    school_id = current_user.school_id or 1
    sub = db.query(SchoolSubaccount).filter(SchoolSubaccount.school_id == school_id).first()
    if not sub:
        return {
            "school_id": school_id,
            "has_subaccount": False,
            "paystack_subaccount_code": None,
            "settlement_bank": "MTN Mobile Money",
            "account_number": "",
            "account_name": "",
            "percentage_split": 98.0,
            "is_verified": False
        }

    return {
        "school_id": school_id,
        "has_subaccount": True,
        "paystack_subaccount_code": sub.paystack_subaccount_code,
        "settlement_bank": sub.settlement_bank,
        "account_number": sub.account_number,
        "account_name": sub.account_name,
        "percentage_split": sub.percentage_split,
        "is_verified": sub.is_verified,
        "updated_at": str(sub.updated_at)[:16] if sub.updated_at else ""
    }


@router.post("/subaccount")
def save_school_subaccount(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Saves and provisions a Paystack settlement subaccount for this school."""
    school_id = current_user.school_id or 1
    school = db.query(School).filter(School.id == school_id).first()
    business_name = data.get("account_name") or (school.name if school else f"School #{school_id}")
    settlement_bank = data.get("settlement_bank", "MTN")
    account_number = data.get("account_number", "").strip()
    percentage_charge = float(data.get("percentage_split", 98.0))

    if not account_number:
        raise HTTPException(status_code=400, detail="Account or MoMo number is required.")

    result = create_or_update_paystack_subaccount(
        school_id=school_id,
        business_name=business_name,
        settlement_bank=settlement_bank,
        account_number=account_number,
        percentage_charge=percentage_charge,
        db=db
    )
    return result


@router.get("/sms-config")
def get_school_sms_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns school's Hubtel Dynamic Sender ID configuration."""
    school_id = current_user.school_id or 1
    cfg = db.query(TenantSmsConfig).filter(TenantSmsConfig.school_id == school_id).first()
    if not cfg:
        school = db.query(School).filter(School.id == school_id).first()
        default_sender = (school.code if school and school.code else "EDUMANAGE")[:11]
        return {
            "school_id": school_id,
            "sender_id": default_sender,
            "provider": "HUBTEL",
            "status": "FALLBACK"
        }

    return {
        "school_id": school_id,
        "sender_id": cfg.sender_id,
        "provider": cfg.provider or "HUBTEL",
        "status": cfg.status
    }


@router.post("/sms-config")
def save_school_sms_config(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submits or updates school's 11-character Hubtel Sender ID.
    Super-Admins activate directly; institutional admins submit for regulatory approval.
    """
    school_id = current_user.school_id or 1
    sender_id = data.get("sender_id", "").strip().upper()[:11]
    if not sender_id:
        raise HTTPException(status_code=400, detail="Sender ID cannot be empty.")

    is_super = any(r.name == "super_admin" for r in getattr(current_user, "roles", [])) or current_user.username.lower() == "superadmin"
    status_target = "ACTIVE" if is_super else "PENDING_APPROVAL"

    cfg = db.query(TenantSmsConfig).filter(TenantSmsConfig.school_id == school_id).first()
    if not cfg:
        cfg = TenantSmsConfig(
            school_id=school_id,
            sender_id=sender_id,
            provider="HUBTEL",
            status=status_target
        )
        db.add(cfg)
    else:
        cfg.sender_id = sender_id
        cfg.status = status_target

    db.commit()
    db.refresh(cfg)
    msg = "Sender ID updated and active." if status_target == "ACTIVE" else "Sender ID submitted for Super-Admin & Telco verification."
    return {"status": "success", "sender_id": cfg.sender_id, "approval_status": cfg.status, "message": msg}


@router.get("/sessions")
def get_my_active_sessions(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns list of active device sessions for current user."""
    sessions = db.query(UserDeviceSession).filter(
        UserDeviceSession.user_id == current_user.id,
        UserDeviceSession.is_active == True
    ).order_by(UserDeviceSession.last_active.desc()).all()

    curr_token = authorization.split(" ")[1] if authorization and " " in authorization else ""
    curr_token_hash = hash_token(curr_token) if curr_token else ""

    return [
        {
            "id": s.id,
            "device_name": s.device_name or "Unknown Device",
            "ip_address": s.ip_address or "127.0.0.1",
            "last_active": str(s.last_active)[:16] if s.last_active else "",
            "is_current": s.session_token_hash == curr_token_hash
        }
        for s in sessions
    ]


@router.post("/sessions/revoke-others")
def revoke_other_device_sessions(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Terminates all other logged-in device sessions for current user."""
    if not authorization or " " not in authorization:
        raise HTTPException(status_code=400, detail="Missing auth token.")
    token = authorization.split(" ")[1]
    revoked_count = revoke_all_other_sessions(current_user.id, token, db)
    return {"status": "success", "revoked_sessions": revoked_count}


