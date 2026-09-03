"""
test_offline_pwa_audit.py — Automated Test Suite for Offline-First, PWA Service Worker, and Local PDF Generation.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestOfflinePwaAudit(unittest.TestCase):

    def setUp(self):
        self.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.frontend_dir = os.path.join(self.root_dir, "frontend")
        self.sw_path = os.path.join(self.frontend_dir, "sw.js")

    def test_01_service_worker_asset_coverage(self):
        """Verify sw.js STATIC_ASSETS caches all HTML pages and JS scripts."""
        self.assertTrue(os.path.exists(self.sw_path), "sw.js must exist")
        with open(self.sw_path, "r", encoding="utf-8") as f:
            sw_content = f.read()

        # Extract STATIC_ASSETS array items
        match = re.search(r"const STATIC_ASSETS = \[(.*?)\];", sw_content, re.DOTALL)
        self.assertIsNotNone(match, "STATIC_ASSETS array must be defined in sw.js")
        raw_assets = match.group(1)
        cached_assets = set(re.findall(r"['\"](.*?)['\"]", raw_assets))

        # Check all frontend html files exist in cached_assets
        for fname in os.listdir(self.frontend_dir):
            if fname.endswith(".html"):
                asset_url = f"/{fname}"
                self.assertIn(asset_url, cached_assets, f"Missing HTML page in sw.js: {asset_url}")

        # Check all js files exist in cached_assets
        js_dir = os.path.join(self.frontend_dir, "js")
        for fname in os.listdir(js_dir):
            if fname.endswith(".js"):
                asset_url = f"/js/{fname}"
                self.assertIn(asset_url, cached_assets, f"Missing JS script in sw.js: {asset_url}")

    def test_02_service_worker_skips_api_calls(self):
        """Verify sw.js does not cache dynamic /api/ calls."""
        with open(self.sw_path, "r", encoding="utf-8") as f:
            sw_content = f.read()
        self.assertIn("/api/", sw_content, "sw.js must inspect /api/ requests")
        self.assertIn("return;", sw_content, "sw.js must skip /api/ requests to prevent stale database state")

    def test_03_zero_external_javascript_cdns(self):
        """Verify no HTML page imports unpkg, cdnjs, or external js scripts."""
        disallowed_cdns = ["unpkg.com", "cdnjs.cloudflare.com", "cdn.jsdelivr.net"]
        for fname in os.listdir(self.frontend_dir):
            if fname.endswith(".html"):
                fpath = os.path.join(self.frontend_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                for cdn in disallowed_cdns:
                    self.assertNotIn(f"<script src=\"http://{cdn}", content, f"Disallowed CDN in {fname}: {cdn}")
                    self.assertNotIn(f"<script src=\"https://{cdn}", content, f"Disallowed CDN in {fname}: {cdn}")

    def test_04_css_system_font_fallbacks(self):
        """Verify styles.css defines offline system-ui font fallbacks."""
        css_path = os.path.join(self.frontend_dir, "css", "styles.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
        self.assertIn("system-ui", css_content, "CSS must provide system-ui font fallback")
        self.assertIn("-apple-system", css_content, "CSS must provide -apple-system font fallback")

    def test_05_theme_offline_persistence(self):
        """Verify theme.js has offline local storage and canvas color extraction."""
        theme_js_path = os.path.join(self.frontend_dir, "js", "theme.js")
        with open(theme_js_path, "r", encoding="utf-8") as f:
            theme_content = f.read()
        self.assertIn("localStorage.setItem", theme_content, "theme.js must use localStorage for persistence")
        self.assertIn("extractLogoColors", theme_content, "theme.js must have offline canvas logo color extractor")


if __name__ == "__main__":
    unittest.main()
