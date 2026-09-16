import os
import sys
import re
import json
import logging
import logging.handlers
from datetime import datetime, timezone
from typing import Optional, Dict, Any

# Base logs directory at project root
LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logs"))

# Sensitive patterns for log sanitization & PII/Secret redaction
SENSITIVE_PATTERNS = [
    # Passwords in JSON, query strings, headers, and log messages
    (re.compile(r'("?password"?\s*[:=]\s*"?)([^"\'\s,}]+)("?)', re.IGNORECASE), r'\1***REDACTED***\3'),
    (re.compile(r'("?admin_password"?\s*[:=]\s*"?)([^"\'\s,}]+)("?)', re.IGNORECASE), r'\1***REDACTED***\3'),
    (re.compile(r'("?new_password"?\s*[:=]\s*"?)([^"\'\s,}]+)("?)', re.IGNORECASE), r'\1***REDACTED***\3'),
    # Bearer tokens & JWTs
    (re.compile(r'(Bearer\s+)[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*', re.IGNORECASE), r'\1***REDACTED_JWT***'),
    (re.compile(r'("?access_token"?\s*[:=]\s*"?)([^"\'\s,}]+)("?)', re.IGNORECASE), r'\1***REDACTED***\3'),
    (re.compile(r'("?token"?\s*[:=]\s*"?)([^"\'\s,}]+)("?)', re.IGNORECASE), r'\1***REDACTED***\3'),
    # API Secret Keys (Paystack, Hubtel, etc.)
    (re.compile(r'(sk_live_[a-zA-Z0-9_\-]+)', re.IGNORECASE), r'***REDACTED_KEY***'),
    (re.compile(r'(sk_test_[a-zA-Z0-9_\-]+)', re.IGNORECASE), r'***REDACTED_KEY***'),
    (re.compile(r'(pk_live_[a-zA-Z0-9_\-]+)', re.IGNORECASE), r'***REDACTED_KEY***'),
    (re.compile(r'("?secret_key"?\s*[:=]\s*"?)([^"\'\s,}]+)("?)', re.IGNORECASE), r'\1***REDACTED***\3'),
    (re.compile(r'("?client_secret"?\s*[:=]\s*"?)([^"\'\s,}]+)("?)', re.IGNORECASE), r'\1***REDACTED***\3'),
    # Database connection strings with embedded passwords
    (re.compile(r'(postgres(?:ql)?:\/\/[^:]+:)([^@]+)(@)', re.IGNORECASE), r'\1***REDACTED***\3'),
]


def sanitize_log_text(text: str) -> str:
    """
    Sanitizes log messages, removing passwords, JWTs, secret keys, and credentials.
    """
    if not text:
        return ""
    sanitized = str(text)
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def is_sensitive_dict_key(key: str) -> bool:
    """
    Determines if a dictionary key represents a sensitive credential or secret.
    Avoids false positives on plural collection keys like 'tokens'.
    """
    k = key.lower().strip()
    if k in ("password", "admin_password", "new_password", "secret", "secret_key",
             "client_secret", "access_token", "refresh_token", "token", "jwt",
             "authorization", "api_key", "db_password"):
        return True
    if any(k.startswith(prefix) or k.endswith(suffix)
           for prefix in ("password_", "secret_")
           for suffix in ("_password", "_secret", "_token", "_jwt", "_key")):
        return True
    return False


def sanitize_dict_payload(data: Any) -> Any:
    """
    Recursively scrubs sensitive keys from dictionary payloads before logging.
    """
    if isinstance(data, dict):
        scrubbed = {}
        for k, v in data.items():
            if is_sensitive_dict_key(k):
                scrubbed[k] = "***REDACTED***"
            else:
                scrubbed[k] = sanitize_dict_payload(v)
        return scrubbed
    elif isinstance(data, list):
        return [sanitize_dict_payload(item) for item in data]
    elif isinstance(data, str):
        return sanitize_log_text(data)
    return data


class StructuredJsonFormatter(logging.Formatter):
    """
    Formats log records into structured JSON objects suitable for ingestion
    by centralized log aggregators (Elasticsearch, Datadog, CloudWatch, Loki)
    and offline audit trails.
    Automatically scrubs sensitive credentials from output.
    """
    def format(self, record: logging.LogRecord) -> str:
        raw_message = record.getMessage()
        sanitized_message = sanitize_log_text(raw_message)

        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitized_message,
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
            log_obj["path"] = sanitize_log_text(record.path)
        if hasattr(record, "status_code") and record.status_code is not None:
            log_obj["status_code"] = record.status_code
        if hasattr(record, "duration_ms") and record.duration_ms is not None:
            log_obj["duration_ms"] = record.duration_ms
        if hasattr(record, "school_id") and record.school_id is not None:
            log_obj["school_id"] = record.school_id

        # Include security/audit specific fields
        if hasattr(record, "security_event"):
            log_obj["security_event"] = record.security_event
        if hasattr(record, "audit_action"):
            log_obj["audit_action"] = record.audit_action

        # Include exception trace if present, scrubbed of secrets
        if record.exc_info:
            raw_exc = self.formatException(record.exc_info)
            log_obj["exception"] = sanitize_log_text(raw_exc)

        return json.dumps(log_obj)


class ColoredConsoleFormatter(logging.Formatter):
    """
    Human-readable colored formatter for terminal output during local development.
    Scrubs sensitive credentials to prevent accidental terminal exposure.
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
        sanitized_msg = sanitize_log_text(record.getMessage())
        msg = f"{color}[{record.levelname:<7}]{self.RESET} {timestamp} {record.name}{req_id}: {sanitized_msg}"
        if record.exc_info:
            sanitized_exc = sanitize_log_text(self.formatException(record.exc_info))
            msg += f"\n{sanitized_exc}"
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


# =============================================================================
# Security & Operational Event Observability Functions
# =============================================================================

def log_security_event(
    event_type: str,
    severity: str,
    details: Dict[str, Any],
    request_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    school_id: Optional[int] = None
):
    """
    Emits an audited, structured security event to the 'edumanage.security' logger.
    Automatically scrubs secrets before recording.
    """
    sec_logger = get_logger("security")
    level = getattr(logging, severity.upper(), logging.WARNING)

    clean_details = sanitize_dict_payload(details)
    msg = f"SECURITY EVENT [{event_type}]: {json.dumps(clean_details)}"

    record = logging.LogRecord(
        name="edumanage.security",
        level=level,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None
    )
    record.security_event = event_type
    record.request_id = request_id
    record.client_ip = client_ip
    record.school_id = school_id
    sec_logger.handle(record)


def log_admin_audit_event(
    action: str,
    target_type: str,
    target_id: Any,
    actor_user_id: int,
    school_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None
):
    """
    Emits an administrative audit event for tracking configuration and system state changes.
    """
    audit_logger = get_logger("audit")
    clean_details = sanitize_dict_payload(details or {})

    payload = {
        "action": action,
        "target_type": target_type,
        "target_id": str(target_id),
        "actor_user_id": actor_user_id,
        "school_id": school_id,
        "details": clean_details
    }

    record = logging.LogRecord(
        name="edumanage.audit",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=f"ADMIN AUDIT [{action}] on {target_type} ID {target_id} by User {actor_user_id}: {json.dumps(clean_details)}",
        args=(),
        exc_info=None
    )
    record.audit_action = action
    record.school_id = school_id
    audit_logger.handle(record)


def log_startup_diagnostics(
    environment: str,
    db_engine: str,
    version: str = "4.2.0",
    extra_info: Optional[Dict[str, Any]] = None
):
    """
    Emits safe startup diagnostics at application boot, verifying operational parameters
    without logging any sensitive credentials or database passwords.
    """
    diag_logger = get_logger("startup")
    info = {
        "app": "EduManage 360",
        "version": version,
        "environment": environment,
        "database_engine": db_engine,
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if extra_info:
        info.update(sanitize_dict_payload(extra_info))

    msg = f"STARTUP DIAGNOSTICS: Environment={environment} | DB={db_engine} | Version={version}"
    record = logging.LogRecord(
        name="edumanage.startup",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None
    )
    diag_logger.handle(record)
