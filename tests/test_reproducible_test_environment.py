"""
Tests for Prompt 16: Reproducible Test Environment.
Verifies dependency declarations, inventory integrity of all verification scripts,
in-memory test isolation, and test runner configurations.
"""
import os
import sys
import py_compile
import unittest
import importlib


class TestReproducibleTestEnvironment(unittest.TestCase):
    def setUp(self):
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def test_required_runtime_and_test_dependencies_importable(self):
        """All critical dependencies required for application runtime and testing must be importable."""
        required_packages = [
            "fastapi",
            "uvicorn",
            "sqlalchemy",
            "pydantic",
            "alembic",
            "requests",
            "httpx",
            "pytest",
            "pypdf",
            "xhtml2pdf",
            "bcrypt"
        ]
        for package_name in required_packages:
            with self.subTest(package=package_name):
                try:
                    mod = importlib.import_module(package_name)
                    self.assertIsNotNone(mod)
                except ImportError as e:
                    self.fail(f"Required test/runtime dependency '{package_name}' could not be imported: {e}")

    def test_requirements_files_exist_and_consistent(self):
        """requirements.txt, backend/requirements.txt, and requirements-test.txt must exist."""
        root_req = os.path.join(self.project_root, "requirements.txt")
        backend_req = os.path.join(self.project_root, "backend", "requirements.txt")
        test_req = os.path.join(self.project_root, "requirements-test.txt")

        self.assertTrue(os.path.exists(root_req), "Root requirements.txt missing")
        self.assertTrue(os.path.exists(backend_req), "backend/requirements.txt missing")
        self.assertTrue(os.path.exists(test_req), "requirements-test.txt missing")

        with open(test_req, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("httpx", content)
            self.assertIn("pytest", content)

    def test_pytest_ini_configuration_valid(self):
        """pytest.ini must exist and specify testpaths."""
        pytest_ini = os.path.join(self.project_root, "pytest.ini")
        self.assertTrue(os.path.exists(pytest_ini), "pytest.ini configuration missing")
        with open(pytest_ini, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("[pytest]", content)
            self.assertIn("testpaths", content)

    def test_verify_all_script_inventory_integrity(self):
        """Every test script referenced in verify_all.py must physically exist and compile without syntax errors."""
        import verify_all
        # Extract test_scripts list from run_all or read AST
        from verify_all import run_all
        import inspect

        source = inspect.getsource(run_all)
        # Parse test_scripts strings
        import re
        script_matches = re.findall(r'"((?:tests|scripts|backend/tests)/[^"]+\.py)"', source)
        self.assertGreater(len(script_matches), 60, "Should have 60+ registered test scripts")

        for rel_path in script_matches:
            abs_path = os.path.join(self.project_root, rel_path.replace("/", os.sep))
            with self.subTest(script=rel_path):
                self.assertTrue(os.path.exists(abs_path), f"Registered test script {rel_path} does not exist at {abs_path}")
                # Verify syntax correctness
                try:
                    py_compile.compile(abs_path, doraise=True)
                except py_compile.PyCompileError as e:
                    self.fail(f"Syntax error in registered test script {rel_path}: {e}")

    def test_in_memory_database_bootstrap_isolation(self):
        """Creating an in-memory SQLite database and loading all ORM models must succeed with 0 errors."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from backend.app.models import Base, School, User, Role

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Seed minimal fixtures
        school = School(name="Isolation Academy", code="ISO_01")
        role = Role(name="admin")
        session.add_all([school, role])
        session.commit()

        user = User(username="iso_admin", password_hash="hash", school_id=school.id)
        user.roles.append(role)
        session.add(user)
        session.commit()

        fetched_user = session.query(User).filter(User.username == "iso_admin").first()
        self.assertIsNotNone(fetched_user)
        self.assertEqual(fetched_user.school_id, school.id)
        session.close()
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
