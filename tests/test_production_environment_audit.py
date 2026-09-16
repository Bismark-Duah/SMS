"""
tests/test_production_environment_audit.py
Automated test suite for Prompt 20: Production Environment Audit.
Verifies environment variable classifications, validation rules, fail-secure guards, and secret sanitization.
"""

import unittest
from backend.app.env_audit import (
    EnvClassification,
    ENV_VARIABLE_CATALOG,
    audit_environment_configuration,
    validate_production_environment_or_exit,
    get_sanitized_env_summary
)


class TestProductionEnvironmentAudit(unittest.TestCase):

    def test_01_catalog_classification_coverage(self):
        """Verifies all catalog items have valid categories and proper metadata."""
        valid_cats = set(EnvClassification)
        for name, spec in ENV_VARIABLE_CATALOG.items():
            self.assertIn("classifications", spec)
            for c in spec["classifications"]:
                self.assertIn(c, valid_cats)
            self.assertIn("description", spec)
            self.assertIn("is_secret", spec)

        # Check required production keys
        self.assertIn(EnvClassification.REQUIRED, ENV_VARIABLE_CATALOG["SECRET_KEY"]["classifications"])
        self.assertIn(EnvClassification.REQUIRED, ENV_VARIABLE_CATALOG["DATABASE_URL"]["classifications"])
        self.assertIn(EnvClassification.SECRET, ENV_VARIABLE_CATALOG["SECRET_KEY"]["classifications"])
        self.assertIn(EnvClassification.DEVELOPMENT_ONLY, ENV_VARIABLE_CATALOG["DB_ALLOW_SQLITE_FALLBACK"]["classifications"])
        self.assertIn(EnvClassification.DEPRECATED, ENV_VARIABLE_CATALOG["ENV"]["classifications"])

    def test_02_development_mode_passes_without_errors(self):
        """Development mode should not fail startup even with minimal or default configs."""
        env = {
            "ENVIRONMENT": "development",
            "DATABASE_URL": "sqlite:///./school.db"
        }
        report = audit_environment_configuration(env_dict=env, target_env="development")
        self.assertTrue(report.is_valid)
        self.assertEqual(len(report.errors), 0)

    def test_03_production_fails_on_missing_secret_key(self):
        """Production mode must reject missing or empty SECRET_KEY."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql://usr:pwd@localhost:5432/sms",
            "SECRET_KEY": ""
        }
        report = audit_environment_configuration(env_dict=env, target_env="production")
        self.assertFalse(report.is_valid)
        self.assertTrue(any("SECRET_KEY is missing" in e for e in report.errors))

    def test_04_production_fails_on_short_secret_key(self):
        """Production mode must reject SECRET_KEY with insufficient entropy (< 32 chars)."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql://usr:pwd@localhost:5432/sms",
            "SECRET_KEY": "too-short-secret"
        }
        report = audit_environment_configuration(env_dict=env, target_env="production")
        self.assertFalse(report.is_valid)
        self.assertTrue(any("under minimum 32 characters" in e for e in report.errors))

    def test_05_production_fails_on_insecure_default_secret_key(self):
        """Production mode must reject known placeholder secret keys."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql://usr:pwd@localhost:5432/sms",
            "SECRET_KEY": "your-secure-random-256-bit-secret-key-here"
        }
        report = audit_environment_configuration(env_dict=env, target_env="production")
        self.assertFalse(report.is_valid)
        self.assertTrue(any("Insecure default or placeholder SECRET_KEY" in e for e in report.errors))

    def test_06_production_fails_on_sqlite_database_url(self):
        """Production mode must forbid SQLite as a production database."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "sqlite:///./school.db",
            "SECRET_KEY": "a" * 32
        }
        report = audit_environment_configuration(env_dict=env, target_env="production")
        self.assertFalse(report.is_valid)
        self.assertTrue(any("SQLite DATABASE_URL is forbidden in production" in e for e in report.errors))

    def test_07_production_fails_on_missing_database_url(self):
        """Production mode must reject missing DATABASE_URL."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "",
            "SECRET_KEY": "a" * 32
        }
        report = audit_environment_configuration(env_dict=env, target_env="production")
        self.assertFalse(report.is_valid)
        self.assertTrue(any("DATABASE_URL is missing" in e for e in report.errors))

    def test_08_production_fails_on_wildcard_cors(self):
        """Production mode must reject wildcard CORS configuration."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql://usr:pwd@localhost:5432/sms",
            "SECRET_KEY": "a" * 32,
            "CORS_ORIGINS": "*"
        }
        report = audit_environment_configuration(env_dict=env, target_env="production")
        self.assertFalse(report.is_valid)
        self.assertTrue(any("CORS_ORIGINS cannot be wildcard" in e for e in report.errors))

    def test_09_production_fails_on_enabled_paystack_without_secret(self):
        """If PAYSTACK_ENABLED=true in production, PAYSTACK_SECRET_KEY is required."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql://usr:pwd@localhost:5432/sms",
            "SECRET_KEY": "a" * 32,
            "PAYSTACK_ENABLED": "true",
            "PAYSTACK_SECRET_KEY": ""
        }
        report = audit_environment_configuration(env_dict=env, target_env="production")
        self.assertFalse(report.is_valid)
        self.assertTrue(any("PAYSTACK_SECRET_KEY is missing" in e for e in report.errors))

    def test_10_production_fails_on_enabled_hubtel_without_credentials(self):
        """If HUBTEL_ENABLED=true in production, HUBTEL_CLIENT_SECRET is required."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql://usr:pwd@localhost:5432/sms",
            "SECRET_KEY": "a" * 32,
            "HUBTEL_ENABLED": "true",
            "HUBTEL_CLIENT_ID": "",
            "HUBTEL_CLIENT_SECRET": ""
        }
        report = audit_environment_configuration(env_dict=env, target_env="production")
        self.assertFalse(report.is_valid)
        self.assertTrue(any("HUBTEL_CLIENT_ID or HUBTEL_CLIENT_SECRET is missing" in e for e in report.errors))

    def test_11_production_fails_on_dev_only_sqlite_fallback(self):
        """DB_ALLOW_SQLITE_FALLBACK must not be permitted in production."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql://usr:pwd@localhost:5432/sms",
            "SECRET_KEY": "a" * 32,
            "DB_ALLOW_SQLITE_FALLBACK": "true"
        }
        report = audit_environment_configuration(env_dict=env, target_env="production")
        self.assertFalse(report.is_valid)
        self.assertTrue(any("DB_ALLOW_SQLITE_FALLBACK cannot be enabled in production" in e for e in report.errors))

    def test_12_production_valid_configuration_passes(self):
        """Fully valid production configuration passes audit with 0 errors."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql://db_user:secure_pwd@db.host.internal:5432/sms_prod",
            "SECRET_KEY": "f" * 64,
            "CORS_ORIGINS": "https://smsghana.onrender.com, https://app.edumanage360.com",
            "LOG_LEVEL": "INFO"
        }
        report = audit_environment_configuration(env_dict=env, target_env="production")
        self.assertTrue(report.is_valid)
        self.assertEqual(len(report.errors), 0)

    def test_13_sanitized_env_summary_masks_secrets(self):
        """get_sanitized_env_summary must mask all secret values."""
        env = {
            "SECRET_KEY": "super_confidential_token_key",
            "PAYSTACK_SECRET_KEY": "sk_live_1234567890abcdef",
            "DATABASE_URL": "postgresql://localhost:5432/test"
        }
        summary = get_sanitized_env_summary(env_dict=env)
        for item in summary:
            if item["is_secret"] and item["is_set"]:
                self.assertNotIn("super_confidential_token_key", item["value_preview"])
                self.assertNotIn("1234567890abcdef", item["value_preview"])
                self.assertTrue(item["value_preview"].endswith("****"))

    def test_14_validate_production_environment_or_exit_raises_on_error(self):
        """validate_production_environment_or_exit must raise RuntimeError when invalid in prod."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "sqlite:///./school.db",
            "SECRET_KEY": "weak"
        }
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_environment_or_exit(env_dict=env)
        self.assertIn("CRITICAL PRODUCTION ENVIRONMENT CONFIGURATION FAILURE", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
