from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os

from sqlalchemy import text
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
app.mount("/assets", StaticFiles(directory=frontend_dir, html=True), name="assets")
app.mount("/frontend", StaticFiles(directory=frontend_dir, html=True), name="frontend")



@app.get("/")
def root_redirect():
    return RedirectResponse(url="/assets/index.html")


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "School management API is running"}
