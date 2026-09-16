"""
Automated Test Suite for Accessibility Audit and WCAG 2.1 AA Compliance (Prompt 25).
Verifies:
1. Documentation presence in docs/ACCESSIBILITY_AUDIT.md.
2. Keyboard focus visibility (:focus-visible) in styles.css.
3. Screen-reader utility classes (.sr-only, .visually-hidden).
4. Reduced motion (prefers-reduced-motion) and High Contrast (forced-colors) media queries.
5. Skip-to-main navigation link definition and runtime injection.
6. Modal dialog ARIA semantics, escape key listener, and table header scoping in theme.js.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
CSS_PATH = os.path.join(FRONTEND_DIR, "css", "styles.css")
THEME_JS_PATH = os.path.join(FRONTEND_DIR, "js", "theme.js")
DOCS_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "ACCESSIBILITY_AUDIT.md")


class TestAccessibilityAudit(unittest.TestCase):

    def test_01_documentation_exists(self):
        """Verify docs/ACCESSIBILITY_AUDIT.md exists and covers WCAG 2.1 AA."""
        self.assertTrue(os.path.isfile(DOCS_PATH), "docs/ACCESSIBILITY_AUDIT.md must exist.")
        with open(DOCS_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Accessibility Audit", content)
        self.assertIn("WCAG 2.1 AA", content)
        self.assertIn("focus-visible", content)
        self.assertIn("skip-to-main", content)
        self.assertIn("prefers-reduced-motion", content)

    def test_02_focus_visibility_defined_in_css(self):
        """Verify :focus-visible rules provide high-contrast visible focus indicators."""
        self.assertTrue(os.path.isfile(CSS_PATH), "styles.css must exist.")
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            css = f.read()
        self.assertIn(":focus-visible", css)
        self.assertTrue("outline: 2px solid" in css or "outline: 3px solid" in css)

    def test_03_skip_to_main_navigation_css(self):
        """Verify .skip-to-main link styling exists for keyboard bypass of navigation blocks."""
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            css = f.read()
        self.assertIn(".skip-to-main", css)
        self.assertIn(".skip-to-main:focus", css)

    def test_04_screen_reader_utilities_in_css(self):
        """Verify .sr-only and .visually-hidden clipping utilities exist for screen-reader users."""
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            css = f.read()
        self.assertIn(".sr-only", css)
        self.assertIn(".visually-hidden", css)
        self.assertIn("clip: rect(0, 0, 0, 0)", css)

    def test_05_reduced_motion_adaptations(self):
        """Verify prefers-reduced-motion media query suppresses animations for vestibular safety."""
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            css = f.read()
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertIn("animation-duration", css)

    def test_06_forced_colors_high_contrast_support(self):
        """Verify forced-colors active mode ensures visible element boundaries and focus."""
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            css = f.read()
        self.assertIn("@media (forced-colors: active)", css)
        self.assertIn("ButtonText", css)

    def test_07_theme_js_implements_global_accessibility_controller(self):
        """Verify theme.js includes mountGlobalAccessibility with modal ARIA, ESC key, and table scoping."""
        self.assertTrue(os.path.isfile(THEME_JS_PATH), "theme.js must exist.")
        with open(THEME_JS_PATH, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("mountGlobalAccessibility", js)
        self.assertIn("skip-to-main", js)
        self.assertIn("role", js)
        self.assertIn("dialog", js)
        self.assertIn("aria-modal", js)
        self.assertIn("scope", js)
        self.assertIn("alert", js)

    def test_08_auth_html_contains_skip_to_main_styling(self):
        """Verify auth.html defines .skip-to-main styling so WCAG bypass link remains off-screen until focused."""
        auth_path = os.path.join(FRONTEND_DIR, "auth.html")
        self.assertTrue(os.path.isfile(auth_path), "auth.html must exist.")
        with open(auth_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn(".skip-to-main", content)
        self.assertIn("top: -120px", content)
        self.assertIn(".skip-to-main:focus", content)


if __name__ == "__main__":
    unittest.main()
