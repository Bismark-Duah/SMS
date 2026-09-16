import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class TestDeveloperSetupAndEnv(unittest.TestCase):

    def test_env_example_file_exists_and_has_variables(self):
        """Verify .env.example exists and contains all required environment variables."""
        env_example_path = os.path.join(REPO_ROOT, ".env.example")
        self.assertTrue(os.path.exists(env_example_path), ".env.example does not exist at repository root")

        with open(env_example_path, "r", encoding="utf-8") as f:
            content = f.read()

        expected_vars = [
            "ENVIRONMENT",
            "LOG_LEVEL",
            "DATABASE_URL",
            "SECRET_KEY",
            "JWT_SECRET_KEY",
            "JWT_ALGORITHM",
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "CORS_ORIGINS",
            "ALLOWED_HOSTS",
            "UPLOAD_DIR",
            "MAX_UPLOAD_SIZE_MB",
            "PAYSTACK_ENABLED",
            "HUBTEL_ENABLED",
            "BACKUP_DIR"
        ]

        for var_name in expected_vars:
            self.assertIn(f"{var_name}=", content, f".env.example is missing variable: {var_name}")

    def test_env_example_contains_no_real_secrets(self):
        """Verify .env.example contains only placeholders, not real credentials."""
        env_example_path = os.path.join(REPO_ROOT, ".env.example")
        with open(env_example_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            if "=" in line_str:
                key, val = line_str.split("=", 1)
                val_lower = val.lower()
                # Ensure secret keys do not contain real credentials
                if "secret" in key.lower() or "key" in key.lower() or "password" in key.lower():
                    is_placeholder = any(p in val_lower for p in [
                        "placeholder", "change", "your-", "example", "secret-key", "strong_password", ""
                    ])
                    self.assertTrue(
                        is_placeholder,
                        f"Potentially exposed credential in .env.example for {key}: {val}"
                    )

    def test_developer_setup_documentation_exists(self):
        """Verify docs/DEVELOPER_SETUP.md exists and covers critical onboarding steps."""
        guide_path = os.path.join(REPO_ROOT, "docs", "DEVELOPER_SETUP.md")
        self.assertTrue(os.path.exists(guide_path), "docs/DEVELOPER_SETUP.md does not exist")

        with open(guide_path, "r", encoding="utf-8") as f:
            guide_content = f.read().lower()

        critical_sections = [
            "prerequisites",
            "virtual environment",
            "alembic upgrade head",
            "verify_all.py",
            "postgresql",
            "run.py"
        ]

        for section in critical_sections:
            self.assertIn(section, guide_content, f"DEVELOPER_SETUP.md missing section: {section}")


if __name__ == "__main__":
    unittest.main()
