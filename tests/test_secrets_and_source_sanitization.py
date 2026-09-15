"""
tests/test_secrets_and_source_sanitization.py
Regression tests for Prompt 4: Secrets Rotation, Sanitization & Source Hygiene.

Covers:
1. Verifying that sensitive operational files (.env, *.db, backups/, first_run_credentials.txt)
   are NOT tracked by Git.
2. Verifying that .env.example contains only clean placeholders and no hardcoded machine drive paths
   (e.g., 'd:/documents' or 'C:/') or production secret strings.
3. Verifying that CORS_ORIGINS in .env.example does not default to wildcard '*'.
"""

import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestSecretsAndSourceSanitization(unittest.TestCase):

    def test_sensitive_files_not_tracked_by_git(self):
        """Ensure git ls-files does not track any live .env, database, or credentials files."""
        res = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            check=True
        )
        tracked_files = res.stdout.splitlines()

        for filename in tracked_files:
            lower_name = filename.lower()
            # Must not track live .env files (templates ending in .example are permitted)
            if not lower_name.endswith(".example") and (lower_name.endswith(".env") or lower_name == ".env" or "/.env" in lower_name):
                self.fail(f"Tracked sensitive file detected in git index: {filename}")
            # Must not track SQLite database files
            if lower_name.endswith(".db") or lower_name.endswith(".sqlite") or lower_name.endswith(".sqlite3"):
                self.fail(f"Tracked database file detected in git index: {filename}")
            # Must not track credentials or backup dumps
            if "first_run_credentials" in lower_name or lower_name.startswith("backups/"):
                self.fail(f"Tracked credentials or backup dump detected: {filename}")

    def test_env_example_contains_safe_placeholders_only(self):
        """Ensure .env.example contains safe placeholders and no local machine paths or secrets."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        example_paths = [
            os.path.join(project_root, ".env.example"),
            os.path.join(project_root, "backend", ".env.example")
        ]

        for p in example_paths:
            self.assertTrue(os.path.exists(p), f"Missing configuration template at {p}")
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()

            # Must not contain hardcoded local Windows machine paths
            self.assertNotIn("d:/documents", content.lower(), f"Hardcoded developer path found in {p}")
            self.assertNotIn("c:/users", content.lower(), f"Hardcoded user directory found in {p}")

            # Must not default CORS to open wildcard
            self.assertNotIn("CORS_ORIGINS=*", content, f"Wildcard CORS found in template at {p}")

            # Must contain clean placeholder instructions
            self.assertIn("your-secure-random-256-bit-secret-key-here", content, f"Missing secret placeholder in {p}")


if __name__ == "__main__":
    unittest.main()
