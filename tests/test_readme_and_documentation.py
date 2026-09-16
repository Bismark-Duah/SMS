import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class TestReadmeAndDocumentation(unittest.TestCase):

    def test_readme_file_exists_and_has_substance(self):
        """Verify README.md exists and contains comprehensive documentation."""
        readme_path = os.path.join(REPO_ROOT, "README.md")
        self.assertTrue(os.path.exists(readme_path), "README.md does not exist at repository root")
        
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertGreater(len(content), 4000, "README.md should be comprehensive (>4000 characters)")

    def test_readme_contains_core_architectural_concepts(self):
        """Verify README.md documents all key architectural and domain concepts."""
        readme_path = os.path.join(REPO_ROOT, "README.md")
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_terms = [
            "Offline-First",
            "FastAPI",
            "SQLite",
            "PostgreSQL",
            "Write-Ahead Log",
            "NaCCA",
            "WAEC",
            "CSSPS",
            "verify_all.py",
            "81",
            "audit-logs.html",
            "PWA"
        ]

        for term in required_terms:
            self.assertIn(term.lower(), content.lower(), f"README.md is missing expected term: {term}")

    def test_readme_referenced_repository_files_exist(self):
        """Verify that all core operational and script files referenced in README exist."""
        referenced_files = [
            "run.py",
            "verify_all.py",
            "Start_EduManage360.bat",
            "Stop_EduManage360.bat",
            "Restart_EduManage360.bat",
            "backend/requirements.txt",
            "backend/app/main.py",
            "frontend/sw.js",
            "frontend/audit-logs.html",
            "scripts/prepare_client_handoff.py"
        ]

        for rel_path in referenced_files:
            full_path = os.path.join(REPO_ROOT, rel_path)
            self.assertTrue(os.path.exists(full_path), f"Referenced file does not exist: {rel_path}")


if __name__ == "__main__":
    unittest.main()
