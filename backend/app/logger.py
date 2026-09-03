import os
import sys
import json
import logging
import logging.handlers
from datetime import datetime, timezone
from typing import Optional

# Base logs directory at project root
LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logs"))


class StructuredJsonFormatter(logging.Formatter):
    """
    Formats log records into structured JSON objects suitable for ingestion
    by centralized log aggregators (Elasticsearch, Datadog, CloudWatch, Loki)
    and offline audit trails.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func_name": record.funcName,
            "line_no": record.lineno,
            "process_id": record.process,
            "thread_id": record.thread,
        }

        # Include contextual request metadata if present
        if hasattr(record, "request_id") and record.request_id:
            log_obj["request_id"] = record.request_id
        if hasattr(record, "client_ip") and record.client_ip:
            log_obj["client_ip"] = record.client_ip
        if hasattr(record, "method") and record.method:
            log_obj["method"] = record.method
        if hasattr(record, "path") and record.path:
            log_obj["path"] = record.path
        if hasattr(record, "status_code") and record.status_code is not None:
            log_obj["status_code"] = record.status_code
        if hasattr(record, "duration_ms") and record.duration_ms is not None:
            log_obj["duration_ms"] = record.duration_ms
        if hasattr(record, "school_id") and record.school_id is not None:
            log_obj["school_id"] = record.school_id

        # Include exception trace if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


class ColoredConsoleFormatter(logging.Formatter):
    """
    Human-readable colored formatter for terminal output during local development.
    """
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        req_id = f" [{getattr(record, 'request_id', '')}]" if hasattr(record, 'request_id') and record.request_id else ""
        msg = f"{color}[{record.levelname:<7}]{self.RESET} {timestamp} {record.name}{req_id}: {record.getMessage()}"
        if record.exc_info:
            msg += f"\n{self.formatException(record.exc_info)}"
        return msg


def setup_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_file_name: str = "sms_app.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB per file
    backup_count: int = 5
) -> logging.Logger:
    """
    Initializes root application logger with both structured JSON file rotation
    and formatted terminal output.
    """
    os.makedirs(LOGS_DIR, exist_ok=True)
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger("edumanage")
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()
    root_logger.propagate = False

    # 1. Console Stream Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(ColoredConsoleFormatter())
    root_logger.addHandler(console_handler)

    # 2. Structured JSON Rotating File Handler
    if log_to_file:
        log_file_path = os.path.join(LOGS_DIR, log_file_name)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(StructuredJsonFormatter())
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Returns child logger namespaced under 'edumanage'."""
    if name:
        return logging.getLogger(f"edumanage.{name}")
    return logging.getLogger("edumanage")
