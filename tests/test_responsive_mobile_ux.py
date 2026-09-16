"""
Automated Test Suite for Responsive and Mobile UX Subsystem (Prompt 24).
Verifies:
1. 100% viewport meta tag coverage across all frontend HTML pages.
2. Cross-device responsive media query definitions in styles.css.
3. Mobile touch-target and input zoom-prevention safeguards.
4. Table containment and horizontal scrolling across high-use workflow templates.
5. Mobile off-canvas navigation and hamburger button styling.
"""

import os
import re
import unittest

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
CSS_PATH = os.path.join(FRONTEND_DIR, "css", "styles.css")
DOCS_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "RESPONSIVE_AND_MOBILE_UX.md")


class TestResponsiveMobileUX(unittest.TestCase):

    def test_01_responsive_documentation_exists(self):
        """Verify that comprehensive Responsive and Mobile UX documentation is present."""
        self.assertTrue(os.path.isfile(DOCS_PATH), "docs/RESPONSIVE_AND_MOBILE_UX.md must exist.")
        with open(DOCS_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Responsive & Mobile UX Architecture", content)
        self.assertIn("auth.html", content)
        self.assertIn("dashboard.html", content)
        self.assertIn("table-responsive", content)
        self.assertIn("640px", content)
        self.assertIn("1024px", content)

    def test_02_all_html_files_have_viewport_meta_tag(self):
        """Verify all HTML files in frontend contain the responsive viewport meta tag."""
        html_files = [f for f in os.listdir(FRONTEND_DIR) if f.endswith(".html")]
        self.assertGreaterEqual(len(html_files), 30, f"Expected at least 30 HTML files, found {len(html_files)}")

        missing_viewport = []
        for h in html_files:
            full_path = os.path.join(FRONTEND_DIR, h)
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            if not re.search(r'<meta\s+name=["\']viewport["\']\s+content=["\'][^"\']*width=device-width', content, re.IGNORECASE):
                missing_viewport.append(h)

        self.assertEqual(missing_viewport, [], f"The following HTML files lack a viewport meta tag: {missing_viewport}")

    def test_03_styles_css_contains_responsive_media_queries(self):
        """Verify that styles.css defines standard mobile and tablet breakpoints."""
        self.assertTrue(os.path.isfile(CSS_PATH), "frontend/css/styles.css must exist.")
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            css = f.read()

        has_1024 = "@media screen and (max-width: 1024px)" in css or "@media (max-width: 1024px)" in css
        has_768 = "@media screen and (max-width: 768px)" in css or "@media (max-width: 768px)" in css
        has_640 = "@media screen and (max-width: 640px)" in css or "@media (max-width: 640px)" in css

        self.assertTrue(has_1024, "Missing tablet breakpoint (max-width: 1024px) in styles.css")
        self.assertTrue(has_768, "Missing mobile breakpoint (max-width: 768px) in styles.css")
        self.assertTrue(has_640, "Missing small mobile breakpoint (max-width: 640px) in styles.css")

    def test_04_touch_target_and_zoom_safeguards_in_css(self):
        """Verify touch targets enforce min-height and inputs enforce 16px to prevent iOS auto-zoom."""
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertTrue("min-height: 42px" in css or "min-height: 44px" in css)
        self.assertIn("font-size: 16px !important", css)
        self.assertIn(".mobile-hamburger-btn", css)
        self.assertIn("min-width: 44px", css)
        self.assertIn("min-height: 44px", css)

    def test_05_table_responsive_and_containment_classes(self):
        """Verify table-responsive and table-container support horizontal touch scrolling."""
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn(".table-responsive", css)
        self.assertIn("overflow-x: auto", css)
        self.assertIn("-webkit-overflow-scrolling: touch", css)

    def test_06_auth_login_screen_has_mobile_safeguards(self):
        """Verify auth.html supports vertical scrolling on small screens and 16px inputs."""
        auth_path = os.path.join(FRONTEND_DIR, "auth.html")
        with open(auth_path, "r", encoding="utf-8") as f:
            content = f.read()

        has_mobile_mq = "@media (max-width: 600px)" in content or "@media screen and (max-width: 640px)" in content
        self.assertTrue(has_mobile_mq, "auth.html must contain mobile media query")
        self.assertIn("overflow-y: auto", content)
        self.assertIn("16px", content)

    def test_07_high_use_workflow_tables_wrapped(self):
        """Verify high-use workflow pages contain responsive table wrappers."""
        critical_pages = [
            "students.html",
            "attendance.html",
            "results.html",
            "fees.html",
            "messaging.html",
            "report-card.html",
            "data-tools.html",
        ]

        for page in critical_pages:
            page_path = os.path.join(FRONTEND_DIR, page)
            self.assertTrue(os.path.isfile(page_path), f"Page {page} must exist.")
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("table", content.lower(), f"{page} is expected to have tables")
            has_responsive_wrapper = (
                "table-responsive" in content
                or "table-container" in content
                or bool(re.search(r'overflow-x:\s*auto', content))
                or bool(re.search(r'overflow:\s*auto', content))
            )
            self.assertTrue(has_responsive_wrapper, f"{page} must have table wrapped in responsive scroll container")


if __name__ == "__main__":
    unittest.main()
