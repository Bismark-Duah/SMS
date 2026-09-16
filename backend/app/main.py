from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
import os

from sqlalchemy import text
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .routes import auth, students, attendance, results, reports, classes, subjects, programs, academic, notifications, settings, assignments, promotions, fees, timetable, discipline, departments, houses, messaging, exeat, academic_hierarchy, backup, rollover, cssps_enrollment, cumulative_records, super_admin, vouchers, assets, clearance, audit, sync



from .routes import assets, clearance, cssps_enrollment, cumulative_records
from .ncca_seed import seed_ncca_curriculum
import time
import uuid
from datetime import datetime, timezone
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from .logger import setup_logging, get_logger
from .database import run_migrations, get_database_telemetry

# Initialize structured logging engine
setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger("main")

# Run schema migrations once at startup
run_migrations()

# Seed default settings & NaCCA curriculum
with next(get_db()) as db:
    settings.seed_default_settings(db)
    classes.seed_default_stages(db)
    auth._seed_db(db)
    try:
        seed_ncca_curriculum(db)
    except Exception as e:
        logger.info(f"NaCCA curriculum auto-seed notice: {e}")

# Verify Environment Configuration & Fail-Secure Production Guard
from .env_audit import validate_production_environment_or_exit, get_sanitized_env_summary
validate_production_environment_or_exit()

secret_key = os.getenv("SECRET_KEY", "").strip()
env_mode = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
if env_mode not in ("production", "prod") and (not secret_key or secret_key == "your-secret-key-change-in-production"):
    import warnings
    warnings.warn(
        "SECURITY WARNING: SECRET_KEY is unset or using a default placeholder. Set a strong SECRET_KEY before deploying to production.",
        UserWarning
    )

# DevOps Concurrency Guard for SQLite
db_url = os.getenv("DATABASE_URL", "sqlite")
web_concurrency = os.getenv("WEB_CONCURRENCY") or os.getenv("WORKERS")
if ("sqlite" in db_url.lower()) and web_concurrency and int(web_concurrency) > 1:
    logger.warning(
        f"DEVOPS CONCURRENCY WARNING: WEB_CONCURRENCY={web_concurrency} detected with SQLite database. "
        "Multiple worker processes can cause SQLite database locked errors. Pin workers to 1 or switch to PostgreSQL."
    )

app = FastAPI(title="School Management System", version="0.1.0")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Injects request correlation ID (X-Request-ID) and emits structured JSON access telemetry.
    """
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = req_id
        start_time = time.time()

        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        response = await call_next(request)

        duration_ms = round((time.time() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = req_id
        response.headers["Accept-CH"] = "Sec-CH-UA-Model, Sec-CH-UA-Platform, Sec-CH-UA-Platform-Version, Sec-CH-UA-Mobile, Sec-CH-UA-Full-Version-List"
        response.headers["Permissions-Policy"] = "ch-ua-model=*, ch-ua-platform=*, ch-ua-platform-version=*"
        response.headers["Critical-CH"] = "Sec-CH-UA-Model, Sec-CH-UA-Platform"

        # Skip high-frequency health poll noise unless error
        if path not in ("/health", "/api/health", "/api/system/health") or response.status_code >= 400:
            log_record = logging.LogRecord(
                name="edumanage.access",
                level=logging.INFO if response.status_code < 400 else logging.WARNING,
                pathname="",
                lineno=0,
                msg=f"{method} {path} -> {response.status_code} ({duration_ms}ms)",
                args=(),
                exc_info=None
            )
            log_record.request_id = req_id
            log_record.client_ip = client_ip
            log_record.method = method
            log_record.path = path
            log_record.status_code = response.status_code
            log_record.duration_ms = duration_ms
            log_record.school_id = getattr(request.state, "school_id", None)
            logger.handle(log_record)

        return response

from .cors_config import DEFAULT_LOCAL_ORIGINS, DEFAULT_PROD_ORIGINS, get_cors_configuration

_cors_cfg = get_cors_configuration()
allowed_origins = _cors_cfg["allow_origins"]
allow_creds = _cors_cfg["allow_credentials"]

from .middleware.cloudflare_guard import CloudflareGuardMiddleware
from .middleware.tenant_subdomain import TenantSubdomainMiddleware

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(TenantSubdomainMiddleware)
app.add_middleware(CloudflareGuardMiddleware)

app.add_middleware(
    CORSMiddleware,
    **_cors_cfg
)

# Standardized API Error Handling & Fault Sanitization
from .errors import register_error_handlers
register_error_handlers(app)

@app.on_event("startup")
def sanitize_multi_tenant_state():
    """
    Ensures multi-tenant database state is 100% clean and isolated:
    1. Purges legacy global 'school_name', 'school_logo', 'school_mode', 'school_abbreviation', 'school_code' from Setting table where school_id is NULL.
    2. Ensures School 1 (Atwima Koforidua Basic) has its correct identity and BASIC_ONLY mode.
    3. Ensures School 2 (J.A. Kufuor STEM) has its correct identity and SHS_ONLY mode.
    """
    try:
        from .database import SessionLocal
        from .models import School, Setting
        db = SessionLocal()
        
        # 1. Purge leaking global branding settings that belong to specific tenants
        db.query(Setting).filter(
            Setting.school_id == None,
            Setting.key.in_(["school_name", "school_logo", "school_mode", "school_abbreviation", "school_code", "boarding_status", "system_theme"])
        ).delete(synchronize_session=False)

        # 2. Rectify School 1 if present
        sch1 = db.query(School).filter(School.id == 1).first()
        if sch1:
            if "basic" in sch1.name.lower() or "atwima" in sch1.name.lower() or "islamic" in sch1.name.lower():
                sch1.name = "Atwima Koforidua Islamic Basic School"
                sch1.code = "AKIBS"
                sch1.school_mode = "BASIC_ONLY"
            elif "kufuor" in sch1.name.lower() or "stem" in sch1.name.lower():
                sch1.name = "J.A. Kufuor STEM Technical School"
                sch1.code = "JAK STEM"
                sch1.school_mode = "SHS_ONLY"

        # 3. Rectify School 2 if present
        sch2 = db.query(School).filter(School.id == 2).first()
        if sch2:
            if "kufuor" in sch2.name.lower() or "stem" in sch2.name.lower():
                sch2.name = "J.A. Kufuor STEM Technical School"
                sch2.code = "JAK STEM"
                sch2.school_mode = "SHS_ONLY"
            elif "basic" in sch2.name.lower() or "atwima" in sch2.name.lower() or "islamic" in sch2.name.lower():
                sch2.name = "Atwima Koforidua Islamic Basic School"
                sch2.code = "AKIBS"
                sch2.school_mode = "BASIC_ONLY"

        db.commit()
        db.close()

        # 4. Emit safe startup diagnostics
        from .logger import log_startup_diagnostics
        log_startup_diagnostics(
            environment=env_mode,
            db_engine="PostgreSQL" if is_postgres else "SQLite WAL"
        )
    except Exception as e:
        logger.error(f"[StartupSanitization] Error: {e}")

@app.get("/health", tags=["system"])
@app.get("/api/health", tags=["system"])
@app.get("/api/system/health", tags=["system"])
def get_system_health(db: Session = Depends(get_db)):
    """
    Enterprise health & telemetry endpoint for container orchestrators (Render / Azure / AWS).
    Checks database connection responsiveness, storage engine status, and replication state.
    """
    telemetry = get_database_telemetry(db)
    is_healthy = telemetry.get("status") == "connected"
    
    status_code = 200 if is_healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if is_healthy else "degraded",
            "environment": os.getenv("ENVIRONMENT", "offline_local"),
            "database": telemetry,
            "version": "4.2.0"
        }
    )

@app.get("/api/system/telemetry", tags=["system"])
def get_system_telemetry(db: Session = Depends(get_db)):
    """
    DevOps telemetry and observability endpoint for Prometheus, Grafana, and Super Admin monitors.
    """
    from .models import School, User, Student
    db_telemetry = get_database_telemetry(db)
    return {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": db_telemetry,
        "counts": {
            "schools": db.query(School).count(),
            "users": db.query(User).count(),
            "students": db.query(Student).count()
        }
    }

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(students.router, prefix="/api/students", tags=["students"])
app.include_router(attendance.router, prefix="/api/attendance", tags=["attendance"])
app.include_router(results.router, prefix="/api/results", tags=["results"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(classes.router, prefix="/api/classes", tags=["classes"])
app.include_router(subjects.router, prefix="/api/subjects", tags=["subjects"])
app.include_router(programs.router, prefix="/api/programs", tags=["programs"])
app.include_router(academic.router, prefix="/api/academic", tags=["academic"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(assignments.router, prefix="/api/assignments", tags=["assignments"])
app.include_router(promotions.router, prefix="/api/promotions", tags=["promotions"])
app.include_router(fees.router, prefix="/api/fees", tags=["fees"])
app.include_router(timetable.router, prefix="/api/timetable", tags=["timetable"])
app.include_router(discipline.router, prefix="/api/discipline", tags=["discipline"])
app.include_router(departments.router, prefix="/api/departments", tags=["departments"])
app.include_router(houses.router, prefix="/api/houses", tags=["houses"])
app.include_router(messaging.router, prefix="/api/messaging", tags=["messaging"])
app.include_router(exeat.router, prefix="/api/exeat", tags=["exeat"])
app.include_router(academic_hierarchy.router, prefix="/api/academic-hierarchy", tags=["academic-hierarchy"])
app.include_router(backup.router, prefix="/api/backup", tags=["backup"])
app.include_router(rollover.router, prefix="/api/rollover", tags=["rollover"])
app.include_router(assets.router, prefix="/api/assets", tags=["assets"])
app.include_router(clearance.router, prefix="/api/clearance", tags=["clearance"])
app.include_router(audit.router, prefix="/api/audit")
app.include_router(sync.router, prefix="/api/sync", tags=["sync"])
app.include_router(vouchers.router)
app.include_router(cssps_enrollment.router)
app.include_router(cumulative_records.router)
app.include_router(super_admin.router, prefix="/api")


current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "frontend"))
assets_dir = os.path.join(frontend_dir, "assets")
js_dir = os.path.join(frontend_dir, "js")
css_dir = os.path.join(frontend_dir, "css")
uploads_dir = os.path.join(frontend_dir, "uploads")

os.makedirs(assets_dir, exist_ok=True)
os.makedirs(js_dir, exist_ok=True)
os.makedirs(css_dir, exist_ok=True)
os.makedirs(uploads_dir, exist_ok=True)

app.mount("/assets/uploads", StaticFiles(directory=uploads_dir), name="assets_uploads")
app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
app.mount("/js", StaticFiles(directory=js_dir), name="js")
app.mount("/css", StaticFiles(directory=css_dir), name="css")
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
app.mount("/frontend", StaticFiles(directory=frontend_dir, html=True), name="frontend")


def _serve(filename: str):
    """Helper: serve a frontend HTML file by name."""
    return FileResponse(os.path.join(frontend_dir, filename))


# ── Public pages ──────────────────────────────────────────────────────────────
@app.get("/")
@app.get("/index.html")
def root_index():
    return _serve("index.html")

@app.get("/auth.html")
def serve_auth():
    return _serve("auth.html")

@app.get("/login.html")
def serve_login():
    return _serve("login.html")

@app.get("/manifest.json")
def serve_manifest():
    return FileResponse(os.path.join(frontend_dir, "manifest.json"), media_type="application/manifest+json")

@app.get("/sw.js")
def serve_sw():
    return FileResponse(os.path.join(frontend_dir, "sw.js"), media_type="application/javascript")

@app.get("/enrollment.html")
def serve_enrollment():
    return _serve("enrollment.html")

@app.get("/paystack-callback")
def serve_paystack_callback(reference: str = "", trxref: str = ""):
    ref = reference or trxref
    return RedirectResponse(url=f"/enrollment.html?reference={ref}&status=success")


# ── App pages (authenticated) ─────────────────────────────────────────────────
@app.get("/dashboard.html")
def serve_dashboard():
    return _serve("dashboard.html")

@app.get("/students.html")
def serve_students():
    return _serve("students.html")

@app.get("/attendance.html")
def serve_attendance():
    return _serve("attendance.html")

@app.get("/fees.html")
def serve_fees():
    return _serve("fees.html")

@app.get("/reports.html")
def serve_reports():
    return _serve("reports.html")

@app.get("/report-card.html")
def serve_report_card():
    return _serve("report-card.html")

@app.get("/results.html")
def serve_results():
    return _serve("results.html")

@app.get("/assignments.html")
def serve_assignments():
    return _serve("assignments.html")

@app.get("/timetable.html")
def serve_timetable():
    return _serve("timetable.html")

@app.get("/discipline.html")
def serve_discipline():
    return _serve("discipline.html")

@app.get("/exeat.html")
def serve_exeat():
    return _serve("exeat.html")

@app.get("/messaging.html")
def serve_messaging():
    return _serve("messaging.html")

@app.get("/houses.html")
def serve_houses():
    return _serve("houses.html")

@app.get("/classes.html")
def serve_classes():
    return _serve("classes.html")

@app.get("/subjects.html")
def serve_subjects():
    return _serve("subjects.html")

@app.get("/departments.html")
def serve_departments():
    return _serve("departments.html")

@app.get("/programs.html")
def serve_programs():
    return _serve("programs.html")

@app.get("/academic.html")
def serve_academic():
    return _serve("academic.html")

@app.get("/settings.html")
def serve_settings():
    return _serve("settings.html")

@app.get("/users.html")
def serve_users():
    return _serve("users.html")

@app.get("/promotions.html")
def serve_promotions():
    return _serve("promotions.html")

@app.get("/rollover.html")
def serve_rollover():
    return _serve("rollover.html")

@app.get("/clearance.html")
def serve_clearance():
    return _serve("clearance.html")

@app.get("/assets.html")
def serve_assets_page():
    return _serve("assets.html")

@app.get("/broadsheet.html")
def serve_broadsheet():
    return _serve("broadsheet.html")

@app.get("/cumulative-record.html")
def serve_cumulative():
    return _serve("cumulative-record.html")

@app.get("/announcements.html")
def serve_announcements():
    return _serve("announcements.html")

@app.get("/data-tools.html")
def serve_data_tools():
    return _serve("data-tools.html")

@app.get("/parent-view.html")
def serve_parent_view():
    return _serve("parent-view.html")

@app.get("/super-admin.html")
def serve_super_admin():
    return _serve("super-admin.html")

@app.get("/bulk-entry.html")
def serve_bulk_entry():
    return _serve("bulk-entry.html")


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "School management API is running"}
