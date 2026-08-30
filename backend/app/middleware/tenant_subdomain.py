"""
Multi-Tenant Subdomain Routing Middleware for SaaS School Management System.
Resolves school tenant dynamically from incoming Host headers (e.g. sunyani-shs.sms.edu.gh -> School.id)
or custom headers (X-School-Id, X-School-Slug), injecting tenant context into request.state.
"""
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Optional
from ..database import SessionLocal
from ..models import School

_active_tenant_school_id: ContextVar[Optional[int]] = ContextVar("active_tenant_school_id", default=None)

def get_current_request_school_id() -> Optional[int]:
    """Returns the tenant school_id resolved for the current active request thread/task."""
    return _active_tenant_school_id.get()

def extract_subdomain_from_host(host: str, root_domains=None) -> Optional[str]:
    """
    Extracts the tenant subdomain slug from a raw Host header (e.g. 'jak-stem.sms.edu.gh' -> 'jak-stem').
    Returns None for root domains, raw IPs, or reserved prefixes ('www', 'api', 'admin', 'app').
    """
    if not host:
        return None
    clean_host = host.split(":")[0].lower().strip()
    if clean_host.replace(".", "").isdigit():
        return None

    roots = root_domains or [
        "localhost",
        "127.0.0.1",
        "onrender.com",
        "sms.edu.gh",
        "edumanage.gh"
    ]

    parts = clean_host.split(".")
    if len(parts) >= 2:
        potential_sub = parts[0].strip()
        if potential_sub not in ["www", "api", "admin", "app", "localhost", "mail"]:
            is_root = any(clean_host == d or clean_host == f"www.{d}" for d in roots)
            if not is_root:
                return potential_sub
    return None


class TenantSubdomainMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, root_domains=None):
        super().__init__(app)
        self.root_domains = root_domains or [
            "localhost",
            "127.0.0.1",
            "onrender.com",
            "sms.edu.gh",
            "edumanage.gh"
        ]

    async def dispatch(self, request: Request, call_next) -> Response:
        host = request.headers.get("host", "")
        subdomain = extract_subdomain_from_host(host, self.root_domains)

        # 2. Check Fallback Headers (X-School-Slug / X-School-Id)
        x_slug = request.headers.get("x-school-slug", "").strip()
        x_id_str = request.headers.get("x-school-id", "").strip()
        
        target_slug = x_slug or subdomain
        target_id = None
        if x_id_str.isdigit():
            target_id = int(x_id_str)

        # 3. Resolve School Tenant Context
        request.state.school_id = None
        request.state.school_slug = None
        request.state.school_name = None

        if target_slug or target_id:
            db = SessionLocal()
            try:
                school = None
                if target_id:
                    school = db.query(School).filter(School.id == target_id, School.status == "ACTIVE").first()
                elif target_slug:
                    school = db.query(School).filter(
                        (School.slug == target_slug) | (School.code.ilike(target_slug)),
                        School.status == "ACTIVE"
                    ).first()

                if school:
                    request.state.school_id = school.id
                    request.state.school_slug = school.slug
                    request.state.school_name = school.name
            except Exception as e:
                # Log non-fatal error to prevent request abort
                print(f"[TenantMiddleware] Subdomain resolution notice: {e}")
            finally:
                db.close()

        # Set request-scoped ContextVar
        token = _active_tenant_school_id.set(request.state.school_id)
        try:
            response = await call_next(request)
        finally:
            _active_tenant_school_id.reset(token)
        
        # Inject tenant headers into response for client telemetry
        if request.state.school_id:
            response.headers["X-Tenant-School-Id"] = str(request.state.school_id)
            if request.state.school_slug:
                response.headers["X-Tenant-School-Slug"] = str(request.state.school_slug)

        return response
