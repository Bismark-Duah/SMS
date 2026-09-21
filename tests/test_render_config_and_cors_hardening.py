"""
tests/test_render_config_and_cors_hardening.py

Regression test suite for Fix 8: Production Render Deployment Configuration & Zero-Data-Loss PostgreSQL Hardening (P1).
Verifies:
1. render.yaml declares a persistent managed PostgreSQL database service.
2. Web service in render.yaml does NOT use ephemeral SQLite for production deployment.
3. Web service in render.yaml does NOT allow wildcard '*' in CORS_ORIGINS.
4. Web service in render.yaml runs automated Alembic schema migrations on build.
5. Production CORS resolution strictly rejects wildcard '*' and insecure HTTP origins.
6. Development CORS resolution permits local development smoothly.
"""

import unittest
import os
import sys
import yaml

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("backend"))

from backend.app.cors_config import resolve_cors_origins, get_cors_configuration, DEFAULT_PROD_ORIGINS


class TestRenderConfigAndCorsHardening(unittest.TestCase):
    def setUp(self):
        self.render_yaml_path = os.path.abspath("render.yaml")
        self.assertTrue(os.path.exists(self.render_yaml_path), "render.yaml must exist at project root")
        with open(self.render_yaml_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

    def test_01_render_yaml_defines_persistent_database(self):
        """render.yaml must declare a managed PostgreSQL database service."""
        databases = self.config.get("databases", [])
        self.assertIsInstance(databases, list)
        self.assertGreater(len(databases), 0, "render.yaml must declare at least one managed database service")
        db_names = [db.get("name") for db in databases]
        self.assertIn("edumanage-db", db_names)

    def test_02_web_service_prohibits_ephemeral_sqlite(self):
        """render.yaml web service must not use ephemeral sqlite:/// which wipes on restart."""
        services = self.config.get("services", [])
        web_service = next((s for s in services if s.get("type") == "web"), None)
        self.assertIsNotNone(web_service, "render.yaml must define a web service")

        env_vars = {ev.get("key"): ev for ev in web_service.get("envVars", [])}
        db_url_cfg = env_vars.get("DATABASE_URL")
        self.assertIsNotNone(db_url_cfg, "DATABASE_URL must be configured")

        # Must not be hardcoded to sqlite
        if "value" in db_url_cfg:
            self.assertFalse(
                str(db_url_cfg["value"]).startswith("sqlite:///"),
                "Production render.yaml must not use ephemeral sqlite:///"
            )

        # Must reference persistent database service
        self.assertIn("fromDatabase", db_url_cfg, "DATABASE_URL should reference managed database")
        self.assertEqual(db_url_cfg["fromDatabase"].get("name"), "edumanage-db")

    def test_03_web_service_prohibits_wildcard_cors(self):
        """render.yaml must not use wildcard '*' for CORS_ORIGINS."""
        services = self.config.get("services", [])
        web_service = next((s for s in services if s.get("type") == "web"), None)
        env_vars = {ev.get("key"): ev for ev in web_service.get("envVars", [])}

        cors_cfg = env_vars.get("CORS_ORIGINS")
        self.assertIsNotNone(cors_cfg, "CORS_ORIGINS must be configured in render.yaml")
        cors_val = cors_cfg.get("value", "")
        self.assertNotEqual(cors_val, "*", "CORS_ORIGINS must not be wildcard '*' in production render.yaml")
        self.assertNotIn("*", cors_val.split(","))

    def test_04_web_service_executes_automated_migrations(self):
        """buildCommand in render.yaml must run alembic upgrade head to prevent schema desync."""
        services = self.config.get("services", [])
        web_service = next((s for s in services if s.get("type") == "web"), None)
        build_cmd = web_service.get("buildCommand", "")
        self.assertIn("alembic upgrade head", build_cmd, "render.yaml buildCommand must execute alembic migrations")

    def test_05_cors_production_rejects_wildcard_and_insecure_origins(self):
        """resolve_cors_origins in production mode rejects '*' and insecure http:// origins."""
        # Wildcard alone
        with self.assertRaises(ValueError) as ctx:
            resolve_cors_origins(environment="production", cors_env_str="*")
        self.assertIn("forbidden in production", str(ctx.exception).lower())

        # Wildcard within list
        with self.assertRaises(ValueError) as ctx:
            resolve_cors_origins(environment="production", cors_env_str="https://sms-nald.onrender.com,*")
        self.assertIn("cannot be included in production", str(ctx.exception).lower())

        # Insecure HTTP origin
        with self.assertRaises(ValueError) as ctx:
            resolve_cors_origins(environment="production", cors_env_str="http://insecure-school.com")
        self.assertIn("must use secure https protocol", str(ctx.exception).lower())

    def test_06_cors_production_and_development_happy_paths(self):
        """Validates legitimate origins in production and development."""
        # Production with valid HTTPS
        prod_origins, prod_creds = resolve_cors_origins(
            environment="production",
            cors_env_str="https://sms-nald.onrender.com,https://smsghana.onrender.com"
        )
        self.assertEqual(prod_origins, ["https://sms-nald.onrender.com", "https://smsghana.onrender.com"])
        self.assertTrue(prod_creds)

        # Development default
        dev_origins, dev_creds = resolve_cors_origins(environment="development")
        self.assertIn("http://localhost:8000", dev_origins)
        self.assertTrue(dev_creds)


if __name__ == "__main__":
    unittest.main()
