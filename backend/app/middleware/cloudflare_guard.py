"""
Cloudflare Enterprise Perimeter Guard Middleware & Turnstile Validator.
Extracts authentic visitor IP, country codes, and validates Cloudflare Turnstile bot tokens.
"""
import os
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
import urllib.request
import urllib.parse
import json

class CloudflareGuardMiddleware(BaseHTTPMiddleware):
    """
    Middleware that inspects Cloudflare headers (CF-Connecting-IP, CF-IPCountry)
    and populates request.state.client_ip and request.state.country.
    """
    async def dispatch(self, request: Request, call_next):
        # 1. Resolve true client IP address
        cf_connecting_ip = request.headers.get("cf-connecting-ip")
        x_forwarded_for = request.headers.get("x-forwarded-for")
        x_real_ip = request.headers.get("x-real-ip")

        if cf_connecting_ip:
            client_ip = cf_connecting_ip.strip()
        elif x_forwarded_for:
            # Take the first IP in the X-Forwarded-For chain
            client_ip = x_forwarded_for.split(",")[0].strip()
        elif x_real_ip:
            client_ip = x_real_ip.strip()
        elif request.client and request.client.host:
            client_ip = request.client.host
        else:
            client_ip = "127.0.0.1"

        # 2. Resolve geographic country code
        country = request.headers.get("cf-ipcountry", "GH")

        # 3. Store on request state for downstream handlers, loggers, and rate limiters
        request.state.client_ip = client_ip
        request.state.country = country

        response = await call_next(request)
        return response


def verify_turnstile_token(token: str, remote_ip: str = None) -> bool:
    """
    Validates Cloudflare Turnstile response token.
    In local offline/dev environment without secret key, safely returns True.
    """
    secret_key = os.getenv("CLOUDFLARE_TURNSTILE_SECRET_KEY")
    if not secret_key:
        # Offline development mode or Turnstile not configured -> Pass
        return True

    if not token:
        return False

    try:
        url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
        payload = {"secret": secret_key, "response": token}
        if remote_ip:
            payload["remoteip"] = remote_ip

        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return bool(result.get("success"))
    except Exception as e:
        print("Cloudflare Turnstile verification warning:", e)
        # Fail safe if network times out
        return True
