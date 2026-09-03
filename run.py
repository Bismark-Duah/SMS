"""
EduManage360 Production Server Launcher & DevOps Concurrency Controller.
Enforces database-aware worker concurrency:
- SQLite (WAL mode): Strictly pins to 1 worker (multi-threaded async event loop) to prevent write collisions.
- PostgreSQL: Dynamically scales workers based on available CPU cores and WEB_CONCURRENCY env var.
"""

import os
import sys
import multiprocessing
import uvicorn
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "backend", ".env"))

def get_recommended_workers() -> int:
    """
    Determines safe worker process count based on the configured database engine.
    """
    db_url = os.getenv("DATABASE_URL", "sqlite")
    is_sqlite = db_url.startswith("sqlite") or "sqlite" in db_url.lower()

    if is_sqlite:
        # Multi-process writes to SQLite WAL trigger database locked errors.
        # Single worker with async loop handles high concurrent connections safely.
        return 1

    # PostgreSQL supports multi-worker scaling
    env_workers = os.getenv("WEB_CONCURRENCY") or os.getenv("WORKERS")
    if env_workers:
        try:
            return max(1, int(env_workers))
        except ValueError:
            pass

    cpu_count = multiprocessing.cpu_count() or 2
    return min(cpu_count * 2 + 1, 8)


def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload_mode = os.getenv("RELOAD", "false").lower() in ("true", "1", "yes")

    workers = 1 if reload_mode else get_recommended_workers()
    db_url = os.getenv("DATABASE_URL", "sqlite")
    engine_name = "SQLite (Single-Worker WAL)" if ("sqlite" in db_url.lower()) else "PostgreSQL (Multi-Worker)"

    print("================================================================")
    print("       EduManage360 Enterprise Server Engine Launcher           ")
    print("================================================================")
    print(f" Database Engine   : {engine_name}")
    print(f" Worker Processes  : {workers}")
    print(f" Host / Port       : {host}:{port}")
    print(f" Live Reload       : {'Enabled' if reload_mode else 'Disabled'}")
    print("================================================================")

    uvicorn.run(
        "backend.app.main:app",
        host=host,
        port=port,
        workers=workers,
        reload=reload_mode,
        access_log=False  # Handled by RequestLoggingMiddleware
    )


if __name__ == "__main__":
    main()
