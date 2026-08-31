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

def _init_resilient_engine():
    global DATABASE_URL, is_sqlite, is_postgres
    if is_postgres:
        try:
            pg_engine = create_engine(
                DATABASE_URL,
                pool_size=25,
                max_overflow=15,
                pool_pre_ping=True,
                pool_recycle=300
            )
            # Test connectivity immediately
            with pg_engine.connect() as conn:
                pass
            return pg_engine
        except Exception as e:
            print(f"[DATABASE WARNING] PostgreSQL connection failed ({e}). Falling back gracefully to local SQLite ({DEFAULT_DB_PATH}).")
            DATABASE_URL = f"sqlite:///{DEFAULT_DB_PATH}"
            is_sqlite = True
            is_postgres = False

    sqlite_engine = create_engine(
        f"sqlite:///{DEFAULT_DB_PATH}",
        connect_args={"check_same_thread": False, "timeout": 30}
    )
    @event.listens_for(sqlite_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            pass
        finally:
            cursor.close()
    return sqlite_engine

engine = _init_resilient_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def run_migrations():
    from sqlalchemy import text, inspect
    Base.metadata.create_all(bind=engine)

    try:
        inspector = inspect(engine)
    except Exception as e:
        print("Migration inspector error:", e)
        return

    table_columns_map = {
        "houses": [
            ("house_type", "VARCHAR DEFAULT 'BOARDING'"),
            ("school_id", "INTEGER REFERENCES schools(id)"),
            ("senior_in_charge_id", "INTEGER REFERENCES users(id)"),
            ("house_master_id", "INTEGER REFERENCES users(id)"),
            ("assistant_house_master_id", "INTEGER REFERENCES users(id)"),
            ("senior_in_charge_girls_id", "INTEGER REFERENCES users(id)"),
            ("house_master_girls_id", "INTEGER REFERENCES users(id)"),
            ("assistant_house_master_girls_id", "INTEGER REFERENCES users(id)")
        ],
        "schools": [
            ("slug", "VARCHAR(100)"),
            ("school_mode", "VARCHAR DEFAULT 'COMBINED'"),
            ("boarding_type", "VARCHAR DEFAULT 'BOARDING_AND_DAY'"),
            ("status", "VARCHAR DEFAULT 'ACTIVE'"),
            ("address", "VARCHAR"),
            ("phone", "VARCHAR"),
            ("email", "VARCHAR"),
            ("logo_url", "VARCHAR"),
            ("sms_balance", "INTEGER DEFAULT 500"),
            ("sms_low_threshold", "INTEGER DEFAULT 200"),
            ("platform_commission_percent", "FLOAT DEFAULT 5.0"),
            ("subscription_plan", "VARCHAR(50) DEFAULT 'STANDARD'"),
            ("subscription_status", "VARCHAR(50) DEFAULT 'ACTIVE'")
        ],
        "message_logs": [
            ("school_id", "INTEGER REFERENCES schools(id)"),
            ("hubtel_message_id", "VARCHAR(100)"),
            ("cost", "FLOAT DEFAULT 1.0")
        ],
        "subjects": [
            ("category", "VARCHAR DEFAULT 'Core'"),
            ("group_code", "VARCHAR"),
            ("assessment_type", "VARCHAR DEFAULT 'External_WASSCE'"),
            ("school_level", "VARCHAR DEFAULT 'SHS'"),
            ("is_active", "BOOLEAN DEFAULT TRUE"),
            ("school_id", "INTEGER REFERENCES schools(id)")
        ],
        "students": [
            ("first_name", "VARCHAR"),
            ("middle_name", "VARCHAR"),
            ("last_name", "VARCHAR"),
            ("bece_index_number", "VARCHAR(64)"),
            ("enrolment_code", "VARCHAR(64)"),
            ("bece_raw_score", "INTEGER"),
            ("bece_aggregate", "INTEGER"),
            ("jhs_attended", "VARCHAR"),
            ("residential_status", "VARCHAR DEFAULT 'B'"),
            ("enrollment_status", "VARCHAR DEFAULT 'Fully Registered'"),
            ("house_id", "INTEGER REFERENCES houses(id)"),
            ("dormitory_id", "INTEGER REFERENCES dormitories(id)"),
            ("school_id", "INTEGER REFERENCES schools(id)"),
            ("family_background_notes", "TEXT"),
            ("socio_economic_notes", "TEXT"),
            ("personality_traits", "TEXT"),
            ("leadership_notes", "TEXT"),
            ("teacher_observations", "TEXT"),
            ("co_curricular_activities", "TEXT"),
            ("hobbies_talents", "TEXT"),
            ("awards", "TEXT"),
            ("elective_combination", "VARCHAR"),
            ("elective_combination_id", "INTEGER REFERENCES elective_combinations(id) ON DELETE SET NULL")
        ],
        "programs": [
            ("code", "VARCHAR"),
            ("school_id", "INTEGER REFERENCES schools(id)")
        ],
        "departments": [
            ("school_id", "INTEGER REFERENCES schools(id)")
        ],
        "school_stages": [
            ("school_id", "INTEGER REFERENCES schools(id)")
        ],
        "class_sections": [
            ("program_id", "INTEGER REFERENCES programs(id)"),
            ("form_master_id", "INTEGER REFERENCES users(id)"),
            ("school_id", "INTEGER REFERENCES schools(id)")
        ],
        "users": [
            ("gender", "VARCHAR"),
            ("department_id", "INTEGER REFERENCES departments(id)"),
            ("school_id", "INTEGER REFERENCES schools(id)")
        ],
        "scores": [
            ("approval_status", "VARCHAR DEFAULT 'DRAFT'")
        ],
        "semesters": [
            ("start_date", "TIMESTAMP" if not is_sqlite else "DATETIME"),
            ("end_date", "TIMESTAMP" if not is_sqlite else "DATETIME")
        ],
        "admission_vouchers": [
            ("purchased_by_phone", "VARCHAR(20)"),
            ("amount_paid", "FLOAT DEFAULT 50.0")
        ]
    }

    with engine.connect() as conn:
        for table_name, columns in table_columns_map.items():
            try:
                if not inspector.has_table(table_name):
                    continue
                existing_cols = {c["name"].lower() for c in inspector.get_columns(table_name)}
                for col_name, col_type in columns:
                    if col_name.lower() not in existing_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                        except Exception as add_err:
                            conn.rollback()
                            print(f"Notice: Could not add column {col_name} to {table_name}: {add_err}")
            except Exception as table_err:
                print(f"Notice: Migration inspection for table {table_name}: {table_err}")

        # Expand column lengths for PostgreSQL on Render
        if not is_sqlite:
            for col in ["bece_index_number", "enrolment_code", "student_code"]:
                try:
                    conn.execute(text(f"ALTER TABLE students ALTER COLUMN {col} TYPE VARCHAR(64)"))
                    conn.commit()
                except Exception:
                    conn.rollback()

        # Auto-populate missing slugs for existing schools
        try:
            conn.execute(text("""
                UPDATE schools 
                SET slug = LOWER(REPLACE(REPLACE(TRIM(code), ' ', '-'), '_', '-'))
                WHERE slug IS NULL OR slug = ''
            """))
            conn.commit()
        except Exception as slug_err:
            conn.rollback()
            print("Notice: Auto-populating school slugs:", slug_err)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



