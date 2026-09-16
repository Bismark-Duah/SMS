"""
errors.py — Enterprise Standardized API Error Handling & Fault Sanitization
Provides centralized exception handling across the EduManage 360 platform.

Guarantees:
1. Standardized JSON response envelope across validation, auth, database, and unexpected errors.
2. Complete sanitization: NEVER exposes stack traces, secrets, SQL details, or internal schemas to users.
3. High-fidelity server-side structured logging with correlation IDs (X-Request-ID).
4. 100% frontend and test backward compatibility (preserves standard detail & message semantics).
"""
import os
import logging
from typing import Any, Optional, Dict, List
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException as FastAPIHTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from pydantic import ValidationError

from .logger import get_logger

logger = get_logger("api_errors")


def _get_request_id(request: Request) -> str:
    """Extract correlation request_id from request state or header."""
    return getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")


def _status_to_error_code(status_code: int) -> str:
    """Map standard HTTP status codes to enterprise error codes."""
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        408: "REQUEST_TIMEOUT",
        409: "CONFLICT",
        410: "GONE",
        413: "PAYLOAD_TOO_LARGE",
        415: "UNSUPPORTED_MEDIA_TYPE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }
    return mapping.get(status_code, "API_ERROR")


def build_error_envelope(
    status_code: int,
    error_code: str,
    detail: Any,
    message: Optional[str] = None,
    errors: Optional[List[Any]] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """Constructs the canonical EduManage 360 standardized error payload."""
    msg = message
    if not msg:
        if isinstance(detail, str):
            msg = detail
        elif isinstance(detail, list) and detail and isinstance(detail[0], dict) and "msg" in detail[0]:
            msg = "; ".join(str(d.get("msg", "")) for d in detail[:3])
        else:
            msg = "An error occurred while processing your request."

    payload: Dict[str, Any] = {
        "status_code": status_code,
        "error_code": error_code,
        "detail": detail,
        "message": msg,
    }
    if errors is not None:
        payload["errors"] = errors
    if request_id:
        payload["request_id"] = request_id

    return payload


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Standardized handler for HTTPExceptions (both Starlette and FastAPI).
    Preserves exact detail string for existing client/test contracts.
    """
    req_id = _get_request_id(request)
    error_code = _status_to_error_code(exc.status_code)
    
    # Do not log 404s/401s as critical errors, but log warnings for audit trails
    if exc.status_code >= 500:
        logger.error(
            f"HTTP {exc.status_code} [{req_id}] on {request.method} {request.url.path}: {exc.detail}"
        )
    elif exc.status_code in (401, 403):
        logger.warning(
            f"Security rejection HTTP {exc.status_code} [{req_id}] on {request.method} {request.url.path}: {exc.detail}"
        )

    envelope = build_error_envelope(
        status_code=exc.status_code,
        error_code=error_code,
        detail=exc.detail,
        request_id=req_id
    )
    headers = getattr(exc, "headers", None) or {}
    headers["X-Request-ID"] = req_id
    return JSONResponse(status_code=exc.status_code, content=envelope, headers=headers)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Standardized handler for FastAPI Pydantic schema validation failures.
    Returns 422 with structured errors array and a readable summary message.
    """
    req_id = _get_request_id(request)
    raw_errors = exc.errors()
    
    # Build human-readable summary
    summary_parts = []
    for err in raw_errors[:3]:
        loc = ".".join(str(part) for part in err.get("loc", []) if part not in ("body",))
        loc_str = f"'{loc}': " if loc else ""
        summary_parts.append(f"{loc_str}{err.get('msg', 'invalid value')}")
    summary = "; ".join(summary_parts) or "Request validation failed"

    logger.warning(
        f"Validation failure [{req_id}] on {request.method} {request.url.path}: {summary}"
    )

    envelope = build_error_envelope(
        status_code=422,
        error_code="VALIDATION_ERROR",
        detail=raw_errors,
        message=f"Validation failed: {summary}",
        errors=raw_errors,
        request_id=req_id
    )
    return JSONResponse(
        status_code=422,
        content=envelope,
        headers={"X-Request-ID": req_id}
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """
    Standardized handler for database constraint violations.
    Sanitizes raw SQL, table names, and column internals while providing
    meaningful conflict/bad-request messages.
    """
    req_id = _get_request_id(request)
    orig_msg = str(exc.orig).lower() if hasattr(exc, "orig") and exc.orig else str(exc).lower()

    # Log full unredacted SQL error to secure server log only
    logger.error(
        f"Database Integrity Violation [{req_id}] on {request.method} {request.url.path}: {exc}",
        exc_info=True
    )

    if "unique" in orig_msg or "duplicate" in orig_msg:
        status_code = status.HTTP_409_CONFLICT
        error_code = "RESOURCE_CONFLICT"
        detail_msg = "A record with the specified unique values already exists in the system."
    elif "foreign key" in orig_msg or "foreignkey" in orig_msg:
        status_code = status.HTTP_400_BAD_REQUEST
        error_code = "INVALID_REFERENCE"
        detail_msg = "The operation refers to a referenced record that does not exist or cannot be modified."
    elif "check constraint" in orig_msg or "check" in orig_msg:
        status_code = status.HTTP_400_BAD_REQUEST
        error_code = "CHECK_CONSTRAINT_FAILED"
        detail_msg = "One or more input values violate permitted domain constraints or allowed ranges."
    elif "not null" in orig_msg:
        status_code = status.HTTP_400_BAD_REQUEST
        error_code = "REQUIRED_FIELD_MISSING"
        detail_msg = "One or more required fields were omitted or null."
    else:
        status_code = status.HTTP_409_CONFLICT
        error_code = "DATABASE_INTEGRITY_ERROR"
        detail_msg = "The requested database change violates system integrity constraints."

    envelope = build_error_envelope(
        status_code=status_code,
        error_code=error_code,
        detail=detail_msg,
        message=detail_msg,
        request_id=req_id
    )
    return JSONResponse(status_code=status_code, content=envelope, headers={"X-Request-ID": req_id})


async def operational_error_handler(request: Request, exc: OperationalError) -> JSONResponse:
    """
    Standardized handler for operational database errors (e.g. SQLite busy, DB down).
    Returns 503 Service Unavailable with a friendly retry message.
    """
    req_id = _get_request_id(request)
    orig_msg = str(exc.orig).lower() if hasattr(exc, "orig") and exc.orig else str(exc).lower()

    logger.error(
        f"Database Operational Failure [{req_id}] on {request.method} {request.url.path}: {exc}",
        exc_info=True
    )

    if "locked" in orig_msg or "busy" in orig_msg:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        error_code = "DATABASE_BUSY"
        detail_msg = "Database is currently busy processing concurrent operations. Please retry shortly."
    else:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        error_code = "DATABASE_UNAVAILABLE"
        detail_msg = "The database service is temporarily unavailable. Please try again shortly."

    envelope = build_error_envelope(
        status_code=status_code,
        error_code=error_code,
        detail=detail_msg,
        message=detail_msg,
        request_id=req_id
    )
    return JSONResponse(status_code=status_code, content=envelope, headers={"X-Request-ID": req_id})


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """
    Catch-all handler for all other SQLAlchemy errors.
    Prevents raw DDL/DML leakage to the client.
    """
    req_id = _get_request_id(request)
    logger.error(
        f"SQLAlchemy Failure [{req_id}] on {request.method} {request.url.path}: {exc}",
        exc_info=True
    )
    detail_msg = "A database operational error occurred. The technical details have been logged."
    envelope = build_error_envelope(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="DATABASE_ERROR",
        detail=detail_msg,
        message=detail_msg,
        request_id=req_id
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=envelope,
        headers={"X-Request-ID": req_id}
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Top-level fail-secure catch-all for any unhandled exceptions.
    Guarantees no stack traces or internal secrets leak to the client.
    """
    req_id = _get_request_id(request)
    logger.critical(
        f"Unhandled System Exception [{req_id}] on {request.method} {request.url.path}: {exc}",
        exc_info=True
    )
    detail_msg = "An unexpected internal server error occurred. Please contact the administrator."
    envelope = build_error_envelope(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_SERVER_ERROR",
        detail=detail_msg,
        message=detail_msg,
        request_id=req_id
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=envelope,
        headers={"X-Request-ID": req_id}
    )


def register_error_handlers(app: FastAPI) -> None:
    """
    Registers all standardized enterprise error handlers onto the FastAPI application.
    """
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(FastAPIHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(OperationalError, operational_error_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
