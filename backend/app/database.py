import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backend", ".env"))

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

# Determine absolute path to single authoritative school.db at project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "school.db")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# Normalize postgres:// to postgresql:// for SQLAlchemy 1.4+
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

is_sqlite = DATABASE_URL.startswith("sqlite")
is_postgres = DATABASE_URL.startswith("postgresql")

engine_kwargs = {}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
elif is_postgres:
    engine_kwargs["pool_size"] = 20
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 300

engine = create_engine(DATABASE_URL, **engine_kwargs)

if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            pass
        finally:
            cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def run_migrations():
    from sqlalchemy import text
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
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
                except Exception:
                    pass

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
            ("awards", "TEXT"),
            ("elective_combination", "VARCHAR")
        ]
        try:
            conn.execute(text("SELECT code FROM programs LIMIT 1"))
        except Exception:
            try:
                conn.execute(text("ALTER TABLE programs ADD COLUMN code VARCHAR"))
                conn.commit()
            except Exception:
                pass

        for col_name, col_type in student_columns:
            try:
                conn.execute(text(f"SELECT {col_name} FROM students LIMIT 1"))
            except Exception:
                try:
                    conn.execute(text(f"ALTER TABLE students ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
                except Exception:
                    pass

        score_columns = [
            ("approval_status", "VARCHAR DEFAULT 'DRAFT'")
        ]
        for col_name, col_type in score_columns:
            try:
                conn.execute(text(f"SELECT {col_name} FROM scores LIMIT 1"))
            except Exception:
                try:
                    conn.execute(text(f"ALTER TABLE scores ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
                except Exception:
                    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


