"""
EduManage 360 - Production Environment Variable Audit & Fail-Secure Verification
Task 20: Comprehensive catalog, classification, and fail-secure validation of
production environment variables.
"""

import os
import re
import logging
from enum import Enum
from typing import Dict, List, Optional, Any, Set

logger = logging.getLogger("app.env_audit")


class EnvClassification(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    DEVELOPMENT_ONLY = "development-only"
    SECRET = "secret"
    DEPRECATED = "deprecated"


KNOWN_INSECURE_SECRETS: Set[str] = {
    "insecure-default-change-in-production",
    "test_secret",
    "secret",
    "changeme",
    "your-secure-random-256-bit-secret-key-here",
    "placeholder_secret",
    "admin123",
    "edumanage-default-insecure-secret-key-2026",
}

# Master Specification Catalog of Environment Variables
ENV_VARIABLE_CATALOG: Dict[str, Dict[str, Any]] = {
    "ENVIRONMENT": {
        "classifications": [EnvClassification.REQUIRED],
        "description": "Operational deployment mode (development, test, staging, production).",
        "default": "development",
        "is_secret": False,
    },
    "SECRET_KEY": {
        "classifications": [EnvClassification.REQUIRED, EnvClassification.SECRET],
        "description": "Cryptographic key for signing JWTs, session cookies, and authentication tokens.",
        "default": None,
        "is_secret": True,
    },
    "DATABASE_URL": {
        "classifications": [EnvClassification.REQUIRED],
        "description": "Database connection URI. Must be PostgreSQL (postgresql://) in production.",
        "default": "sqlite:///./school.db",
        "is_secret": False,
    },
    "CORS_ORIGINS": {
        "classifications": [EnvClassification.OPTIONAL],
        "description": "Comma-separated list of allowed frontend web origins. Wildcards forbidden in production.",
        "default": None,
        "is_secret": False,
    },
    "LOG_LEVEL": {
        "classifications": [EnvClassification.OPTIONAL],
        "description": "Application logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
        "default": "INFO",
        "is_secret": False,
    },
    "ACCESS_TOKEN_EXPIRE_MINUTES": {
        "classifications": [EnvClassification.OPTIONAL],
        "description": "JWT session token lifespan in minutes.",
        "default": "1440",
        "is_secret": False,
    },
    "INITIAL_SUPERADMIN_PASSWORD": {
        "classifications": [EnvClassification.OPTIONAL, EnvClassification.SECRET],
        "description": "Initial bootstrap password for the root super-admin account on first run.",
        "default": None,
        "is_secret": True,
    },
    "DB_POOL_SIZE": {
        "classifications": [EnvClassification.OPTIONAL],
        "description": "SQLAlchemy connection pool base size.",
        "default": "20",
        "is_secret": False,
    },
    "DB_MAX_OVERFLOW": {
        "classifications": [EnvClassification.OPTIONAL],
        "description": "SQLAlchemy maximum overflow connections.",
        "default": "10",
        "is_secret": False,
    },
    "DB_POOL_TIMEOUT": {
        "classifications": [EnvClassification.OPTIONAL],
        "description": "Timeout in seconds waiting for a pool connection.",
        "default": "30",
        "is_secret": False,
    },
    "DB_POOL_RECYCLE": {
        "classifications": [EnvClassification.OPTIONAL],
        "description": "Connection recycle timeout in seconds to prevent stale pool connections.",
        "default": "1800",
        "is_secret": False,
    },
    "MAX_BACKUPS_RETAINED": {
        "classifications": [EnvClassification.OPTIONAL],
        "description": "Maximum number of historical database backups to retain before rotation.",
        "default": "14",
        "is_secret": False,
    },
    "AUTH_RATE_LIMIT_MAX_REQUESTS": {
        "classifications": [EnvClassification.OPTIONAL],
        "description": "Maximum failed login attempts allowed within the rate limit window.",
        "default": "5",
        "is_secret": False,
    },
    "AUTH_RATE_LIMIT_WINDOW_SECONDS": {
        "classifications": [EnvClassification.OPTIONAL],
        "description": "Rate limiting evaluation window in seconds.",
        "default": "60",
        "is_secret": False,
    },
    "PAYSTACK_ENABLED": {
        "classifications": [EnvClassification.OPTIONAL],
        "description": "Flag enabling Paystack online fee collection (true/false).",
        "default": "false",
        "is_secret": False,
    },
    "PAYSTACK_SECRET_KEY": {
        "classifications": [EnvClassification.OPTIONAL, EnvClassification.SECRET],
        "description": "Paystack private API secret key for payment processing and verification.",
        "default": None,
        "is_secret": True,
    },
    "PAYSTACK_PUBLIC_KEY": {
        "classifications": [EnvClassification.OPTIONAL],
        "description": "Paystack public key for frontend checkout widgets.",
        "default": None,
        "is_secret": False,
    },
    "HUBTEL_ENABLED": {
        "classifications": [EnvClassification.OPTIONAL],
        "description": "Flag enabling Hubtel Ghana SMS notifications (true/false).",
        "default": "false",
        "is_secret": False,
    },
    "HUBTEL_CLIENT_ID": {
        "classifications": [EnvClassification.OPTIONAL],
        "description": "Hubtel API client identifier.",
        "default": None,
        "is_secret": False,
    },
    "HUBTEL_CLIENT_SECRET": {
        "classifications": [EnvClassification.OPTIONAL, EnvClassification.SECRET],
        "description": "Hubtel API client secret authentication key.",
        "default": None,
        "is_secret": True,
    },
    "MNOTIFY_API_KEY": {
        "classifications": [EnvClassification.OPTIONAL, EnvClassification.SECRET],
        "description": "mNotify Ghana SMS API key.",
        "default": None,
        "is_secret": True,
    },
    "CLOUDFLARE_TURNSTILE_SECRET_KEY": {
        "classifications": [EnvClassification.OPTIONAL, EnvClassification.SECRET],
        "description": "Cloudflare Turnstile captcha server validation secret.",
        "default": None,
        "is_secret": True,
    },
    "DB_ALLOW_SQLITE_FALLBACK": {
        "classifications": [EnvClassification.DEVELOPMENT_ONLY],
        "description": "Development toggle allowing SQLite fallback when PostgreSQL is unreachable.",
        "default": "false",
        "is_secret": False,
    },
    "SKIP_DB_INIT": {
        "classifications": [EnvClassification.DEVELOPMENT_ONLY],
        "description": "Development test fixture bypass flag.",
        "default": "false",
        "is_secret": False,
    },
    "ENV": {
        "classifications": [EnvClassification.DEPRECATED],
        "description": "Legacy alias for ENVIRONMENT. Superseded by ENVIRONMENT.",
        "default": None,
        "is_secret": False,
    },
    "PG_DATABASE_URL": {
        "classifications": [EnvClassification.DEPRECATED],
        "description": "Legacy migration alias. Superseded by DATABASE_URL.",
        "default": None,
        "is_secret": False,
    },
}


class EnvironmentAuditResult:
    def __init__(self):
        self.is_valid: bool = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.details: Dict[str, Any] = {}

    def add_error(self, message: str):
        self.is_valid = False
        self.errors.append(message)

    def add_warning(self, message: str):
        self.warnings.append(message)


def audit_environment_configuration(
    env_dict: Optional[Dict[str, str]] = None,
    target_env: Optional[str] = None
) -> EnvironmentAuditResult:
    """
    Audits every environment variable against production security standards.
    Validates strong secrets, PostgreSQL URIs, CORS rules, and payment/SMS bindings.
    """
    envs = os.environ if env_dict is None else env_dict
    result = EnvironmentAuditResult()

    # 1. Resolve operational environment mode
    current_env = (target_env or envs.get("ENVIRONMENT", envs.get("ENV", "development"))).strip().lower()
    is_prod = current_env in ("production", "prod")
    result.details["environment"] = current_env
    result.details["is_production"] = is_prod

    # 2. Check deprecated variables
    for var_name, spec in ENV_VARIABLE_CATALOG.items():
        if EnvClassification.DEPRECATED in spec["classifications"]:
            if var_name in envs and envs[var_name].strip():
                result.add_warning(
                    f"Deprecated environment variable '{var_name}' is set. "
                    f"Use '{spec['description'].split('Superseded by ')[-1]}' instead."
                )

    if not is_prod:
        # Development / Test / Staging: non-blocking advisory
        return result

    # =========================================================================
    # PRODUCTION FAIL-SECURE CHECKS
    # =========================================================================

    # A. ENVIRONMENT must be explicitly 'production'
    if current_env != "production":
        result.add_warning(f"Production environment flag resolved to non-standard: '{current_env}'.")

    # B. SECRET_KEY validation
    secret_key = envs.get("SECRET_KEY", "").strip()
    if not secret_key:
        result.add_error("Production failure: SECRET_KEY is missing or empty. A 256-bit secret is required.")
    elif secret_key in KNOWN_INSECURE_SECRETS or "change-in-production" in secret_key.lower():
        result.add_error("Production failure: Insecure default or placeholder SECRET_KEY detected.")
    elif len(secret_key) < 32:
        result.add_error(f"Production failure: SECRET_KEY length ({len(secret_key)}) is under minimum 32 characters (256-bit entropy).")

    # C. DATABASE_URL validation
    db_url = envs.get("DATABASE_URL", "").strip()
    if not db_url:
        result.add_error("Production failure: DATABASE_URL is missing. PostgreSQL is required in production.")
    elif db_url.startswith("sqlite"):
        result.add_error("Production failure: SQLite DATABASE_URL is forbidden in production. Use PostgreSQL (postgresql://).")
    elif not (db_url.startswith("postgresql://") or db_url.startswith("postgres://")):
        result.add_error(f"Production failure: DATABASE_URL has invalid scheme '{db_url.split('://')[0]}://'. Must be postgresql://")

    # D. CORS_ORIGINS validation
    cors_origins = envs.get("CORS_ORIGINS", "").strip()
    if cors_origins == "*":
        result.add_error("Production failure: CORS_ORIGINS cannot be wildcard '*' in production.")
    elif cors_origins:
        origins_list = [o.strip() for o in cors_origins.split(",") if o.strip()]
        if "*" in origins_list:
            result.add_error("Production failure: CORS_ORIGINS contains wildcard '*' item.")

    # E. Payment configuration consistency
    paystack_enabled = envs.get("PAYSTACK_ENABLED", "false").strip().lower() in ("true", "1", "yes")
    if paystack_enabled:
        paystack_secret = envs.get("PAYSTACK_SECRET_KEY", "").strip()
        paystack_public = envs.get("PAYSTACK_PUBLIC_KEY", "").strip()
        if not paystack_secret:
            result.add_error("Production failure: PAYSTACK_ENABLED=true but PAYSTACK_SECRET_KEY is missing.")
        elif paystack_secret.startswith("pk_") or "placeholder" in paystack_secret:
            result.add_error("Production failure: Insecure or invalid PAYSTACK_SECRET_KEY.")
        if not paystack_public:
            result.add_warning("PAYSTACK_ENABLED=true but PAYSTACK_PUBLIC_KEY is not configured.")

    # F. SMS Gateway configuration consistency
    hubtel_enabled = envs.get("HUBTEL_ENABLED", "false").strip().lower() in ("true", "1", "yes")
    if hubtel_enabled:
        hubtel_id = envs.get("HUBTEL_CLIENT_ID", "").strip()
        hubtel_secret = envs.get("HUBTEL_CLIENT_SECRET", "").strip()
        if not hubtel_id or not hubtel_secret:
            result.add_error("Production failure: HUBTEL_ENABLED=true but HUBTEL_CLIENT_ID or HUBTEL_CLIENT_SECRET is missing.")
        elif "placeholder" in hubtel_secret.lower():
            result.add_error("Production failure: Insecure placeholder HUBTEL_CLIENT_SECRET detected.")

    # G. Development-only variables strictly prohibited in production
    if envs.get("DB_ALLOW_SQLITE_FALLBACK", "").strip().lower() in ("true", "1", "yes"):
        result.add_error("Production failure: DB_ALLOW_SQLITE_FALLBACK cannot be enabled in production.")

    # H. Logging configuration check
    log_level = envs.get("LOG_LEVEL", "INFO").strip().upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if log_level not in valid_levels:
        result.add_error(f"Production failure: Invalid LOG_LEVEL '{log_level}'. Valid options: {valid_levels}")

    return result


def validate_production_environment_or_exit(env_dict: Optional[Dict[str, str]] = None):
    """
    Enforces safe startup. If running in production mode and any critical requirement fails,
    raises RuntimeError with detailed actionable feedback, preventing insecure startup.
    """
    report = audit_environment_configuration(env_dict=env_dict)
    if not report.is_valid:
        error_block = "\n".join(f"  [!] {err}" for err in report.errors)
        raise RuntimeError(
            f"\n{'='*70}\n"
            f"CRITICAL PRODUCTION ENVIRONMENT CONFIGURATION FAILURE\n"
            f"{'='*70}\n"
            f"The application cannot safely start in production mode due to the following\n"
            f"misconfigurations or missing critical environment variables:\n\n"
            f"{error_block}\n\n"
            f"Remediation: Review docs/ENVIRONMENT_AUDIT.md and configure all required variables.\n"
            f"{'='*70}"
        )


def get_sanitized_env_summary(env_dict: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """
    Returns an audited, classified summary of all known environment variables,
    safely masking sensitive secrets to prevent data leakage in audit reports or dashboards.
    """
    envs = os.environ if env_dict is None else env_dict
    summary = []

    for name, spec in ENV_VARIABLE_CATALOG.items():
        is_set = name in envs and bool(envs[name].strip())
        raw_val = envs.get(name, "")

        if spec["is_secret"]:
            if is_set:
                masked_val = raw_val[:4] + "****" if len(raw_val) > 4 else "****"
            else:
                masked_val = "[NOT SET]"
        else:
            masked_val = raw_val if is_set else (spec["default"] or "[NOT SET]")

        summary.append({
            "name": name,
            "classifications": [c.value for c in spec["classifications"]],
            "is_set": is_set,
            "value_preview": masked_val,
            "description": spec["description"],
            "is_secret": spec["is_secret"],
        })

    return summary
