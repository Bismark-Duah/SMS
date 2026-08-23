from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
import os

from sqlalchemy import text
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .routes import auth, students, attendance, results, reports, classes, subjects, programs, academic, notifications, settings, assignments, promotions, fees, timetable, discipline, departments, houses, messaging, exeat, academic_hierarchy, backup, rollover, cssps_enrollment, cumulative_records, super_admin, vouchers, assets, clearance


# Check/create message_logs table dynamically for SQLite
with engine.connect() as conn:
    try:
        conn.execute(text("SELECT id FROM message_logs LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS message_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER REFERENCES users(id),
                    student_id INTEGER REFERENCES students(id),
                    recipient_name VARCHAR,
                    recipient_phone VARCHAR,
                    channel VARCHAR DEFAULT 'SMS',
                    message_type VARCHAR DEFAULT 'GENERAL',
                    message_body TEXT,
                    overall_grade VARCHAR,
                    status VARCHAR DEFAULT 'SENT',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        except Exception as create_err:
            print("Failed to create message_logs table:", create_err)

Base.metadata.create_all(bind=engine)

# Check/add status column to students table dynamically for SQLite compatibility
with engine.connect() as conn:
    try:
        conn.execute(text("SELECT status FROM students LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("ALTER TABLE students ADD COLUMN status VARCHAR DEFAULT 'ACTIVE'"))
            conn.commit()
        except Exception as alter_err:
            print("Failed to alter students table:", alter_err)

    # Check/add program_id column to class_sections table dynamically for SQLite compatibility
    try:
        conn.execute(text("SELECT program_id FROM class_sections LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("ALTER TABLE class_sections ADD COLUMN program_id INTEGER REFERENCES programs(id)"))
            conn.commit()
        except Exception as alter_err:
            print("Failed to alter class_sections table:", alter_err)

    # Check/add gender column to users table dynamically for SQLite compatibility
    try:
        conn.execute(text("SELECT gender FROM users LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN gender VARCHAR"))
            conn.commit()
        except Exception as alter_err:
            print("Failed to alter users table for gender:", alter_err)

    # Check/add subject columns dynamically for SQLite compatibility
    subject_columns = [
        ("category", "VARCHAR DEFAULT 'Core'"),
        ("group_code", "VARCHAR"),
        ("assessment_type", "VARCHAR DEFAULT 'External_WASSCE'"),
        ("school_level", "VARCHAR DEFAULT 'SHS'")
    ]
    for col_name, col_type in subject_columns:
        try:
            conn.execute(text(f"SELECT {col_name} FROM subjects LIMIT 1"))
        except Exception:
            try:
                conn.execute(text(f"ALTER TABLE subjects ADD COLUMN {col_name} {col_type}"))
                conn.commit()
            except Exception as e:
                print(f"Failed to add column {col_name} to subjects:", e)

    # Check/add student columns dynamically for SQLite compatibility
    student_columns = [
        ("first_name", "VARCHAR"),
        ("middle_name", "VARCHAR"),
        ("last_name", "VARCHAR"),
        ("bece_index_number", "VARCHAR(12)"),
        ("enrolment_code", "VARCHAR(15)"),
        ("bece_raw_score", "INTEGER"),
        ("bece_aggregate", "INTEGER"),
        ("jhs_attended", "VARCHAR"),
        ("residential_status", "VARCHAR DEFAULT 'B'"),
        ("enrollment_status", "VARCHAR DEFAULT 'Fully Registered'"),
        ("family_background_notes", "TEXT"),
        ("socio_economic_notes", "TEXT"),
        ("personality_traits", "TEXT"),
        ("leadership_notes", "TEXT"),
        ("teacher_observations", "TEXT"),
        ("co_curricular_activities", "TEXT"),
        ("hobbies_talents", "TEXT"),
        ("awards", "TEXT")
    ]
    for col_name, col_type in student_columns:
        try:
            conn.execute(text(f"SELECT {col_name} FROM students LIMIT 1"))
        except Exception:
            try:
                conn.execute(text(f"ALTER TABLE students ADD COLUMN {col_name} {col_type}"))
                conn.commit()
            except Exception as e:
                print(f"Failed to add column {col_name} to students:", e)
    try:
        conn.execute(text("SELECT form_master_id FROM class_sections LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("ALTER TABLE class_sections ADD COLUMN form_master_id INTEGER REFERENCES users(id)"))
            conn.commit()
        except Exception as alter_err:
            print("Failed to alter class_sections table for form_master_id:", alter_err)

    # Check/add house_id column to students table dynamically for SQLite compatibility
    try:
        conn.execute(text("SELECT house_id FROM students LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("ALTER TABLE students ADD COLUMN house_id INTEGER REFERENCES houses(id)"))
            conn.commit()
        except Exception as alter_err:
            print("Failed to alter students table for house_id:", alter_err)

    # Check/add dormitory_id column to students table dynamically for SQLite compatibility
    try:
        conn.execute(text("SELECT dormitory_id FROM students LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("ALTER TABLE students ADD COLUMN dormitory_id INTEGER REFERENCES dormitories(id)"))
            conn.commit()
        except Exception as alter_err:
            print("Failed to alter students table for dormitory_id:", alter_err)

    # Check/add house_master_id column to houses table dynamically for SQLite compatibility
    try:
        conn.execute(text("SELECT house_master_id FROM houses LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("ALTER TABLE houses ADD COLUMN house_master_id INTEGER REFERENCES users(id)"))
            conn.commit()
        except Exception as alter_err:
            print("Failed to alter houses table for house_master_id:", alter_err)

    # Check/add assistant_house_master_id column to houses table dynamically for SQLite compatibility
    try:
        conn.execute(text("SELECT assistant_house_master_id FROM houses LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("ALTER TABLE houses ADD COLUMN assistant_house_master_id INTEGER REFERENCES users(id)"))
            conn.commit()
        except Exception as alter_err:
            print("Failed to alter houses table for assistant_house_master_id:", alter_err)

    # Check/add senior_in_charge_girls_id column to houses table dynamically for SQLite compatibility
    try:
        conn.execute(text("SELECT senior_in_charge_girls_id FROM houses LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("ALTER TABLE houses ADD COLUMN senior_in_charge_girls_id INTEGER REFERENCES users(id)"))
            conn.commit()
        except Exception as alter_err:
            print("Failed to alter houses table for senior_in_charge_girls_id:", alter_err)

    # Check/add house_master_girls_id column to houses table dynamically for SQLite compatibility
    try:
        conn.execute(text("SELECT house_master_girls_id FROM houses LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("ALTER TABLE houses ADD COLUMN house_master_girls_id INTEGER REFERENCES users(id)"))
            conn.commit()
        except Exception as alter_err:
            print("Failed to alter houses table for house_master_girls_id:", alter_err)

    # Check/add assistant_house_master_girls_id column to houses table dynamically for SQLite compatibility
    try:
        conn.execute(text("SELECT assistant_house_master_girls_id FROM houses LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("ALTER TABLE houses ADD COLUMN assistant_house_master_girls_id INTEGER REFERENCES users(id)"))
            conn.commit()
        except Exception as alter_err:
            print("Failed to alter houses table for assistant_house_master_girls_id:", alter_err)

    # Check/create program_subjects table if needed
    try:
        conn.execute(text("SELECT 1 FROM program_subjects LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS program_subjects (
                    program_id INTEGER NOT NULL,
                    subject_id INTEGER NOT NULL,
                    PRIMARY KEY (program_id, subject_id),
                    FOREIGN KEY(program_id) REFERENCES programs (id) ON DELETE CASCADE,
                    FOREIGN KEY(subject_id) REFERENCES subjects (id) ON DELETE CASCADE
                )
            """))
            conn.commit()
        except Exception as create_err:
            print("Failed to create program_subjects table:", create_err)    # Check/add start_date column to semesters table dynamically for SQLite compatibility
    try:
        conn.execute(text("SELECT start_date FROM semesters LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("ALTER TABLE semesters ADD COLUMN start_date DATETIME"))
            conn.commit()
        except Exception as alter_err:
            print("Failed to alter semesters table for start_date:", alter_err)

    # Check/add end_date column to semesters table dynamically for SQLite compatibility
    try:
        conn.execute(text("SELECT end_date FROM semesters LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("ALTER TABLE semesters ADD COLUMN end_date DATETIME"))
            conn.commit()
        except Exception as alter_err:
            print("Failed to alter semesters table for end_date:", alter_err)

    # Check/create student_semester_summaries table dynamically for SQLite compatibility
    try:
        conn.execute(text("SELECT 1 FROM student_semester_summaries LIMIT 1"))
    except Exception:
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS student_semester_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    semester_id INTEGER NOT NULL,
                    attitude TEXT,
                    conduct TEXT,
                    interest TEXT,
                    form_teacher_remarks TEXT,
                    headteacher_remarks TEXT,
                    promoted_to TEXT,
                    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
                    FOREIGN KEY(semester_id) REFERENCES semesters(id) ON DELETE CASCADE,
                    UNIQUE(student_id, semester_id)
                )
            """))
            conn.commit()
        except Exception as create_err:
            print("Failed to create student_semester_summaries table:", create_err)


from .routes import assets, clearance, cssps_enrollment, cumulative_records
from .ncca_seed import seed_ncca_curriculum
from .database import run_migrations

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
        print("NaCCA curriculum auto-seed notice:", e)

# Verify SECRET_KEY configuration
secret_key = os.getenv("SECRET_KEY", "")
if not secret_key or secret_key == "your-secret-key-change-in-production":
    import warnings
    warnings.warn(
        "SECURITY WARNING: SECRET_KEY is set to default or empty. "
        "Please specify a strong random SECRET_KEY in backend/.env for production deployment.",
        UserWarning
    )

app = FastAPI(title="School Management System", version="0.1.0")

cors_origins_env = os.getenv("CORS_ORIGINS", "*")
allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()] if cors_origins_env != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["system"])
@app.get("/api/health", tags=["system"])
def get_system_health(db: Session = Depends(get_db)):
    """
    Enterprise health & telemetry endpoint for container orchestrators (Render / Azure / AWS).
    Checks database connection responsiveness and reports engine status.
    """
    import time
    start_time = time.time()
    try:
        from sqlalchemy import text
        from .models import School, User
        db.execute(text("SELECT 1"))
        latency_ms = round((time.time() - start_time) * 1000, 2)
        
        db_url = os.getenv("DATABASE_URL", "sqlite")
        engine_type = "PostgreSQL" if "postgres" in db_url.lower() else "SQLite (Offline-First)"
        
        schools_count = db.query(School).count()
        users_count = db.query(User).count()

        return {
            "status": "healthy",
            "environment": "cloud_production" if "postgres" in db_url.lower() else "offline_local",
            "database": {
                "engine": engine_type,
                "latency_ms": latency_ms,
                "status": "connected"
            },
            "metrics": {
                "registered_schools": schools_count,
                "total_users": users_count
            },
            "version": "4.2.0"
        }
    except Exception as err:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": {
                    "status": "error",
                    "error": str(err)
                }
            }
        )

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
