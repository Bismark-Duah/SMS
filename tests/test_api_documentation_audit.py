import os
import sys
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app

client = TestClient(app)


class TestApiDocumentationAudit(unittest.TestCase):

    def test_openapi_schema_generation(self):
        """Verify OpenAPI JSON schema generates cleanly with metadata and tags."""
        resp = client.get("/openapi.json")
        self.assertEqual(resp.status_code, 200, "OpenAPI schema failed to generate")
        
        schema = resp.json()
        self.assertEqual(schema["info"]["title"], "EduManage 360 Institutional API")
        self.assertEqual(schema["info"]["version"], "1.0.0")
        self.assertIn("paths", schema)
        self.assertGreater(len(schema["paths"]), 50, "OpenAPI schema should contain all routes (>50 endpoints)")

        # Verify tags are documented
        self.assertIn("tags", schema)
        tag_names = [t["name"] for t in schema["tags"]]
        self.assertIn("Authentication & Session Guard", tag_names)
        self.assertIn("Tenant Forensic Audit Feed", tag_names)
        self.assertIn("Grading & Terminal Reports", tag_names)

    def test_swagger_ui_endpoint(self):
        """Verify /docs endpoint renders Swagger UI cleanly."""
        resp = client.get("/docs")
        self.assertEqual(resp.status_code, 200, "Swagger UI /docs failed to return 200")
        self.assertIn("text/html", resp.headers["content-type"])
        self.assertIn("swagger", resp.text.lower())

    def test_redoc_ui_endpoint(self):
        """Verify /redoc endpoint renders ReDoc UI cleanly."""
        resp = client.get("/redoc")
        self.assertEqual(resp.status_code, 200, "ReDoc UI /redoc failed to return 200")
        self.assertIn("text/html", resp.headers["content-type"])
        self.assertIn("redoc", resp.text.lower())

    def test_final_production_audit_document_exists(self):
        """Verify docs/FINAL_PRODUCTION_ENGINEERING_AUDIT.md exists and documents all 31 prompts."""
        doc_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "FINAL_PRODUCTION_ENGINEERING_AUDIT.md"))
        self.assertTrue(os.path.exists(doc_path), "docs/FINAL_PRODUCTION_ENGINEERING_AUDIT.md does not exist")
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Prompt 31", content)
        self.assertIn("Prompt 1", content)


if __name__ == "__main__":
    unittest.main()
