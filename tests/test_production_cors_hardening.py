"""
tests/test_production_cors_hardening.py
Automated verification for Prompt 19: Production CORS Hardening.
Tests environment separation, wildcard prohibition, credential policy, and preflight behavior.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient


from backend.app.cors_config import (
    DEFAULT_LOCAL_ORIGINS,
    DEFAULT_PROD_ORIGINS,
    resolve_cors_origins,
    get_cors_configuration
)
from backend.app.main import app, allowed_origins


class TestProductionCORSHardening(unittest.TestCase):

    def test_01_production_rejects_wildcard(self):
        """Production mode must raise ValueError when wildcard '*' is supplied."""
        with self.assertRaises(ValueError) as ctx:
            resolve_cors_origins(environment="production", cors_env_str="*")
        self.assertIn("Wildcard origin ('*') is strictly forbidden in production", str(ctx.exception))

    def test_02_production_rejects_wildcard_in_list(self):
        """Production mode must reject wildcard even when part of comma-separated list."""
        with self.assertRaises(ValueError) as ctx:
            resolve_cors_origins(environment="production", cors_env_str="https://valid.com, *")
        self.assertIn("cannot be included in production CORS_ORIGINS", str(ctx.exception))

    def test_03_production_default_origins(self):
        """When CORS_ORIGINS is unset in production, secure HTTPS origins must be provided."""
        origins, allow_creds = resolve_cors_origins(environment="production", cors_env_str="")
        self.assertEqual(origins, DEFAULT_PROD_ORIGINS)
        self.assertTrue(allow_creds)
        for orig in origins:
            self.assertTrue(orig.startswith("https://"))

    def test_04_development_wildcard_disables_credentials(self):
        """In non-production, wildcard origin forces allow_credentials to False per W3C specification."""
        origins, allow_creds = resolve_cors_origins(environment="development", cors_env_str="*")
        self.assertEqual(origins, ["*"])
        self.assertFalse(allow_creds)

    def test_05_development_explicit_origins_allows_credentials(self):
        """In development with explicit origins, allow_credentials is True."""
        origins, allow_creds = resolve_cors_origins(
            environment="development",
            cors_env_str="http://localhost:3000, http://127.0.0.1:5173"
        )
        self.assertEqual(origins, ["http://localhost:3000", "http://127.0.0.1:5173"])
        self.assertTrue(allow_creds)

    def test_06_development_default_origins(self):
        """In development with unset CORS_ORIGINS, defaults to local dev servers."""
        origins, allow_creds = resolve_cors_origins(environment="development", cors_env_str="")
        self.assertEqual(origins, DEFAULT_LOCAL_ORIGINS)
        self.assertTrue(allow_creds)
        self.assertIn("http://localhost:8000", origins)
        self.assertIn("http://localhost:3000", origins)

    def test_07_http_preflight_trusted_origin(self):
        """HTTP preflight OPTIONS from a trusted origin returns CORS headers with credentials."""
        client = TestClient(app)
        origin = allowed_origins[0] if allowed_origins and allowed_origins != ["*"] else "http://localhost:8000"
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,Authorization"
        }
        res = client.options("/api/auth/login", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("access-control-allow-origin"), origin)
        self.assertEqual(res.headers.get("access-control-allow-credentials"), "true")

        # Actual request should expose configured headers
        actual_res = client.get("/api/system/health", headers={"Origin": origin})
        self.assertIn("X-Request-ID", actual_res.headers.get("access-control-expose-headers", ""))

    def test_08_http_preflight_untrusted_origin_rejected(self):
        """HTTP preflight OPTIONS from an unauthorized origin is denied CORS headers."""
        client = TestClient(app)
        headers = {
            "Origin": "https://malicious-hacker-site.org",
            "Access-Control-Request-Method": "GET"
        }
        res = client.options("/api/auth/login", headers=headers)
        # Should not grant allow-origin to untrusted domain
        self.assertNotEqual(res.headers.get("access-control-allow-origin"), "https://malicious-hacker-site.org")


if __name__ == "__main__":
    unittest.main()
