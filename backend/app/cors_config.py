"""
EduManage 360 - Production CORS Hardening Configuration
Task 19: Strict CORS isolation, environment-specific origin separation,
and credential safety enforcement.
"""

import os
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("app.cors")

DEFAULT_LOCAL_ORIGINS: List[str] = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://sms-nald.onrender.com",
    "https://smsghana.onrender.com",
    "https://smsgh.onrender.com",
]

DEFAULT_PROD_ORIGINS: List[str] = [
    "https://sms-nald.onrender.com",
    "https://smsghana.onrender.com",
    "https://smsgh.onrender.com",
]


def resolve_cors_origins(
    environment: str = None,
    cors_env_str: str = None
) -> Tuple[List[str], bool]:
    """
    Resolves allowed CORS origins and credentials flag based on the operational environment.

    Rules:
    - Production (ENVIRONMENT=production):
      - Wildcard '*' is strictly prohibited and raises a ValueError.
      - Insecure 'http://' origins are strictly prohibited in production and raise a ValueError.
      - If CORS_ORIGINS is configured, splits and validates that all origins are secure HTTPS.
      - If CORS_ORIGINS is unset, defaults to known secure HTTPS production domains.
      - Credentials (allow_credentials) is True for explicitly listed origins.
    - Development / Testing (ENVIRONMENT!=production):
      - If CORS_ORIGINS='*', allows '*' but forces allow_credentials=False (per W3C CORS spec).
      - If CORS_ORIGINS is set to explicit origins, uses them and sets allow_credentials=True.
      - If CORS_ORIGINS is unset, defaults to DEFAULT_LOCAL_ORIGINS with allow_credentials=True.
    """
    env = (environment if environment is not None else os.getenv("ENVIRONMENT", "development")).strip().lower()
    is_prod = env in ("production", "prod")

    raw_origins = cors_env_str if cors_env_str is not None else os.getenv("CORS_ORIGINS", "")
    raw_origins = raw_origins.strip()

    if is_prod:
        if raw_origins == "*":
            raise ValueError(
                "CORS Security Violation: Wildcard origin ('*') is strictly forbidden in production mode. "
                "Specify explicit trusted HTTPS origins in CORS_ORIGINS."
            )
        if raw_origins:
            parsed = [o.strip() for o in raw_origins.split(",") if o.strip()]
            if "*" in parsed:
                raise ValueError(
                    "CORS Security Violation: Wildcard origin ('*') cannot be included in production CORS_ORIGINS."
                )
            for o in parsed:
                if not o.lower().startswith("https://"):
                    raise ValueError(
                        f"CORS Security Violation: Production origins must use secure HTTPS protocol: '{o}'"
                    )
            allowed = parsed
        else:
            allowed = list(DEFAULT_PROD_ORIGINS)
        
        # Explicit origins with credentials allowed in production
        return allowed, True

    # Non-production (development / test)
    if raw_origins == "*":
        return ["*"], False
    
    if raw_origins:
        parsed = [o.strip() for o in raw_origins.split(",") if o.strip()]
        if "*" in parsed:
            return ["*"], False
        return parsed, True

    return list(DEFAULT_LOCAL_ORIGINS), True


def get_cors_configuration(
    environment: str = None,
    cors_env_str: str = None
) -> Dict[str, Any]:
    """
    Generates the full kwargs dictionary to pass into CORSMiddleware.
    """
    allowed_origins, allow_credentials = resolve_cors_origins(
        environment=environment,
        cors_env_str=cors_env_str
    )

    return {
        "allow_origins": allowed_origins,
        "allow_credentials": allow_credentials,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["*"],
        "expose_headers": ["X-Request-ID", "Content-Disposition"],
        "max_age": 600,
    }
