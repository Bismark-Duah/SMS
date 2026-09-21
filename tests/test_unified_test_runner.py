"""
tests/test_unified_test_runner.py

Regression test suite for Fix 9: Unified Test Runner & Reproducible Test Environment (P1).
Verifies:
1. run_tests.py exists, compiles cleanly, and exposes standard CLI flags (--security, --tenant, --fast, --all).
2. Automated test discovery finds all test suites in tests/ directory.
3. TESTING.md exists and documents essential commands and testing taxonomy.
4. run_test_files executes cleanly in a sterile test environment.
"""

import unittest
import os
import sys
import py_compile
import subprocess

sys.path.insert(0, os.path.abspath("."))

from run_tests import discover_all_tests, run_test_files, SECURITY_SUITES, FAST_SUITES


class TestUnifiedTestRunner(unittest.TestCase):
    def setUp(self):
        self.project_root = os.path.abspath(".")
        self.runner_script = os.path.join(self.project_root, "run_tests.py")
        self.testing_doc = os.path.join(self.project_root, "TESTING.md")

    def test_01_run_tests_script_exists_and_compiles(self):
        """run_tests.py must exist at project root and compile without syntax errors."""
        self.assertTrue(os.path.exists(self.runner_script), "run_tests.py must exist at root")
        compiled = py_compile.compile(self.runner_script, doraise=True)
        self.assertIsNotNone(compiled)

    def test_02_cli_help_flag_succeeds(self):
        """Executing python run_tests.py --help must exit with code 0 and describe flags."""
        result = subprocess.run(
            [sys.executable, self.runner_script, "--help"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0, f"run_tests.py --help failed: {result.stderr}")
        stdout = result.stdout
        self.assertIn("--security", stdout)
        self.assertIn("--tenant", stdout)
        self.assertIn("--fast", stdout)
        self.assertIn("--all", stdout)

    def test_03_test_discovery_finds_all_suites(self):
        """discover_all_tests must discover all test suites in tests/."""
        all_tests = discover_all_tests()
        self.assertIsInstance(all_tests, list)
        self.assertGreaterEqual(len(all_tests), 70, "Should discover at least 70 test suites")
        for tf in all_tests:
            self.assertTrue(tf.startswith("tests/test_") and tf.endswith(".py"))

    def test_04_testing_documentation_integrity(self):
        """TESTING.md must exist and describe test categories and quickstart commands."""
        self.assertTrue(os.path.exists(self.testing_doc), "TESTING.md must exist at project root")
        with open(self.testing_doc, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("python run_tests.py --security", content)
        self.assertIn("python run_tests.py --all", content)
        self.assertIn("100% Offline Execution", content)
        self.assertIn("Test Suites Taxonomy", content)

    def test_05_curated_suites_files_exist(self):
        """All test files listed in SECURITY_SUITES and FAST_SUITES must exist on disk."""
        for suite_path in SECURITY_SUITES:
            full_p = os.path.join(self.project_root, suite_path)
            self.assertTrue(os.path.exists(full_p), f"Security suite {suite_path} does not exist")

        for suite_path in FAST_SUITES:
            full_p = os.path.join(self.project_root, suite_path)
            self.assertTrue(os.path.exists(full_p), f"Fast suite {suite_path} does not exist")

    def test_06_in_process_execution_runs_cleanly(self):
        """Executing a fast suite via run_test_files must complete with success=True."""
        success, total, failures, errors, elapsed = run_test_files(
            ["tests/test_render_config_and_cors_hardening.py"],
            verbosity=0
        )
        self.assertTrue(success)
        self.assertGreater(total, 0)
        self.assertEqual(failures, 0)
        self.assertEqual(errors, 0)
        self.assertGreaterEqual(elapsed, 0.0)


if __name__ == "__main__":
    unittest.main()
