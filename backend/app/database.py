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
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA busy_timeout=30000;")
            cursor.execute("PRAGMA wal_autocheckpoint=1000;")
        except Exception:
            pass
        finally:
            cursor.close()
    return sqlite_engine

engine = _init_resilient_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def checkpoint_database(mode: str = "TRUNCATE") -> dict:
    """
    Executes a WAL checkpoint operation to flush WAL log frames back to the main DB file.
    Modes: PASSIVE, FULL, RESTART, TRUNCATE.
    """
    if not is_sqlite:
        return {"status": "skipped", "message": "WAL checkpoint only applicable to SQLite database."}
    valid_modes = {"PASSIVE", "FULL", "RESTART", "TRUNCATE"}
    selected_mode = mode.upper() if mode.upper() in valid_modes else "TRUNCATE"
    with engine.connect() as conn:
        from sqlalchemy import text
        res = conn.execute(text(f"PRAGMA wal_checkpoint({selected_mode});")).fetchone()
        return {
            "status": "success",
            "mode": selected_mode,
            "busy": res[0] if res else 0,
            "log": res[1] if res else 0,
            "checkpointed": res[2] if res else 0
        }


def vacuum_database() -> dict:
    """
    Reclaims unused disk space and defragments SQLite database file.
    """
    if not is_sqlite:
        return {"status": "skipped", "message": "VACUUM only applicable to SQLite database."}
    with engine.connect() as conn:
        from sqlalchemy import text
        # Set isolation level to autocommit for VACUUM
        conn.execution_options(isolation_level="AUTOCOMMIT").execute(text("VACUUM;"))
        return {"status": "success", "message": "Database successfully vacuumed and compacted."}


def get_database_telemetry(db = None) -> dict:
    """
    Returns enterprise database telemetry, health metrics, and replication lag data
    for PostgreSQL clusters or SQLite WAL storage engines.
    """
    import time
    start_time = time.time()
    
    if is_postgres:
        try:
            with engine.connect() as conn:
                from sqlalchemy import text
                # 1. Check recovery / replica mode
                rec_res = conn.execute(text("SELECT pg_is_in_recovery();")).fetchone()
                is_replica = bool(rec_res[0]) if rec_res else False

                latency_ms = round((time.time() - start_time) * 1000, 2)
                
                if is_replica:
                    # Query replication lag from replica viewpoint
                    lag_res = conn.execute(text("""
                        SELECT 
                            pg_last_wal_receive_lsn()::text AS receive_lsn,
                            pg_last_wal_replay_lsn()::text AS replay_lsn,
                            EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))::float AS lag_seconds
                    """)).fetchone()
                    
                    return {
                        "engine": "PostgreSQL",
                        "role": "Replica (Standby)",
                        "status": "connected",
                        "latency_ms": latency_ms,
                        "replication": {
                            "is_in_recovery": True,
                            "lag_seconds": round(lag_res[2], 2) if (lag_res and lag_res[2] is not None) else 0.0,
                            "last_wal_receive_lsn": lag_res[0] if lag_res else None,
                            "last_wal_replay_lsn": lag_res[1] if lag_res else None,
                            "health": "healthy" if (lag_res and (lag_res[2] is None or lag_res[2] < 30)) else "lagging"
                        }
                    }
                else:
                    # Primary node: query active standby replicas from pg_stat_replication
                    try:
                        rep_res = conn.execute(text("""
                            SELECT 
                                client_addr::text,
                                state,
                                sync_state,
                                replay_lsn::text,
                                pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)::bigint AS lag_bytes
                            FROM pg_stat_replication
                        """)).fetchall()
                        
                        replicas = []
                        max_lag_bytes = 0
                        for r in rep_res:
                            lag_b = r[4] or 0
                            if lag_b > max_lag_bytes: max_lag_bytes = lag_b
                            replicas.append({
                                "client_addr": r[0],
                                "state": r[1],
                                "sync_state": r[2],
                                "replay_lsn": r[3],
                                "lag_bytes": lag_b
                            })
                            
                        return {
                            "engine": "PostgreSQL",
                            "role": "Primary (Writer)",
                            "status": "connected",
                            "latency_ms": latency_ms,
                            "replication": {
                                "active_replicas_count": len(replicas),
                                "max_replication_lag_bytes": max_lag_bytes,
                                "replicas": replicas,
                                "health": "healthy" if max_lag_bytes < (10 * 1024 * 1024) else "lagging"
                            }
                        }
                    except Exception as rep_err:
                        return {
                            "engine": "PostgreSQL",
                            "role": "Primary (Standalone)",
                            "status": "connected",
                            "latency_ms": latency_ms,
                            "replication": {
                                "active_replicas_count": 0,
                                "notice": str(rep_err)
                            }
                        }
        except Exception as e:
            return {
                "engine": "PostgreSQL",
                "status": "degraded",
                "error": str(e)
            }
            
    # SQLite WAL Telemetry
    try:
        db_file = DEFAULT_DB_PATH
        wal_file = f"{db_file}-wal"
        shm_file = f"{db_file}-shm"
        
        db_size_bytes = os.path.getsize(db_file) if os.path.exists(db_file) else 0
        wal_size_bytes = os.path.getsize(wal_file) if os.path.exists(wal_file) else 0
        
        with engine.connect() as conn:
            from sqlalchemy import text
            cp_res = conn.execute(text("PRAGMA wal_checkpoint(PASSIVE);")).fetchone()
            page_res = conn.execute(text("PRAGMA page_count;")).fetchone()
            pagesize_res = conn.execute(text("PRAGMA page_size;")).fetchone()
            
            latency_ms = round((time.time() - start_time) * 1000, 2)
            
            page_count = page_res[0] if page_res else 0
            page_size = pagesize_res[0] if pagesize_res else 4096
            
            return {
                "engine": "SQLite (Offline-First WAL)",
                "role": "Standalone Local Server",
                "status": "connected",
                "latency_ms": latency_ms,
                "storage": {
                    "db_path": os.path.basename(db_file),
                    "db_size_bytes": db_size_bytes,
                    "db_size_mb": round(db_size_bytes / (1024 * 1024), 2),
                    "wal_size_bytes": wal_size_bytes,
                    "wal_size_mb": round(wal_size_bytes / (1024 * 1024), 2),
                    "page_count": page_count,
                    "page_size": page_size
                },
                "wal_checkpoint_status": {
                    "busy": cp_res[0] if cp_res else 0,
                    "log_frames": cp_res[1] if cp_res else 0,
                    "checkpointed_frames": cp_res[2] if cp_res else 0,
                    "health": "optimal" if (cp_res and cp_res[0] == 0) else "busy"
                }
            }
    except Exception as e:
        return {
            "engine": "SQLite",
            "status": "error",
            "error": str(e)
        }


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
            ("ownership_type", "VARCHAR DEFAULT 'PRIVATE'"),
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
            ("school_id", "INTEGER REFERENCES schools(id)"),
            ("phone_number", "VARCHAR"),
            ("is_first_login", "BOOLEAN DEFAULT TRUE"),
            ("contact_verified", "BOOLEAN DEFAULT FALSE")
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
        ],
        "payments": [
            ("receipt_number", "VARCHAR")
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

        # Expand column lengths & make email nullable for PostgreSQL on Render
        if not is_sqlite:
            for col in ["bece_index_number", "enrolment_code", "student_code"]:
                try:
                    conn.execute(text(f"ALTER TABLE students ALTER COLUMN {col} TYPE VARCHAR(64)"))
                    conn.commit()
                except Exception:
                    conn.rollback()
            try:
                conn.execute(text("ALTER TABLE users ALTER COLUMN email DROP NOT NULL"))
                conn.commit()
            except Exception:
                conn.rollback()
        else:
            # Safe SQLite migration to ensure users.email is nullable
            try:
                user_cols = inspector.get_columns("users")
                email_col = next((c for c in user_cols if c["name"].lower() == "email"), None)
                if email_col and not email_col.get("nullable", True):
                    conn.execute(text("PRAGMA foreign_keys=OFF;"))
                    conn.execute(text("CREATE TABLE IF NOT EXISTS users_migration_backup AS SELECT * FROM users;"))
                    conn.execute(text("DROP TABLE users;"))
                    conn.commit()
                    Base.metadata.tables["users"].create(conn)
                    conn.commit()
                    fresh_insp = inspect(conn)
                    b_cols = {c["name"].lower() for c in fresh_insp.get_columns("users_migration_backup")}
                    target_cols = [c["name"] for c in fresh_insp.get_columns("users") if c["name"].lower() in b_cols]
                    cols_str = ", ".join(target_cols)
                    conn.execute(text(f"INSERT INTO users ({cols_str}) SELECT {cols_str} FROM users_migration_backup;"))
                    conn.execute(text("DROP TABLE users_migration_backup;"))
                    conn.execute(text("PRAGMA foreign_keys=ON;"))
                    conn.commit()
            except Exception as sqlite_user_err:
                conn.rollback()
                print("Notice: SQLite users email migration:", sqlite_user_err)

        # Performance & Scalability Indexes Migration
        indexes_to_ensure = [
            "CREATE INDEX IF NOT EXISTS ix_scores_student_subject_sem ON scores (student_id, subject_id, semester_id);",
            "CREATE INDEX IF NOT EXISTS ix_scores_sem_subject ON scores (semester_id, subject_id);",
            "CREATE INDEX IF NOT EXISTS ix_attendance_student_date ON attendance (student_id, date);",
            "CREATE INDEX IF NOT EXISTS ix_fees_student_id ON fees (student_id);",
            "CREATE INDEX IF NOT EXISTS ix_fees_student_status ON fees (student_id, status);",
            "CREATE INDEX IF NOT EXISTS ix_fees_year_term ON fees (academic_year, term);",
            "CREATE INDEX IF NOT EXISTS ix_payments_fee_id ON payments (fee_id);",
            "CREATE INDEX IF NOT EXISTS ix_payments_fee_date ON payments (fee_id, payment_date);",
            "CREATE INDEX IF NOT EXISTS ix_timetable_class_day_period ON timetable (class_section_id, day_of_week, period_number);",
            "CREATE INDEX IF NOT EXISTS ix_timetable_teacher_day_period ON timetable (teacher_id, day_of_week, period_number);",
        ]
        for idx_sql in indexes_to_ensure:
            try:
                conn.execute(text(idx_sql))
                conn.commit()
            except Exception:
                conn.rollback()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



