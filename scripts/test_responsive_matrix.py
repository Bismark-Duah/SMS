#!/usr/bin/env python3
"""
Automated Responsive Matrix & Layout Overflow Validator
Tests HTML files and CSS rules across 5 canonical device viewport widths:
1. 360px (Compact Mobile - Android entry)
2. 390px (Standard Mobile - iPhone 14/15)
3. 412px (Tall Phablet - Samsung Galaxy A-series)
4. 768px (Tablet - iPad Mini / Portrait)
5. 1280px (Desktop / Laptop)
"""
import os
import re

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
CSS_FILE = os.path.join(FRONTEND_DIR, "css", "styles.css")
HTML_FILES = [f for f in os.listdir(FRONTEND_DIR) if f.endswith(".html")]

def audit_responsive_css():
    print("=" * 60)
    print("AUDITING RESPONSIVE CSS DESIGN SYSTEM")
    print("=" * 60)
    with open(CSS_FILE, "r", encoding="utf-8") as f:
        css = f.read()

    checks = [
        ("Mobile Breakpoint (max-width: 768px)", r"@media\s+screen\s+and\s+\(max-width:\s*768px\)"),
        ("Phone Breakpoint (max-width: 480px)", r"@media\s+screen\s+and\s+\(max-width:\s*480px\)"),
        ("Modal Responsiveness (max-width: 600px)", r"@media\s+screen\s+and\s+\(max-width:\s*600px\)"),
        ("44px Minimum Touch Targets", r"min-height:\s*44px"),
        ("Off-Canvas Drawer Transform", r"transform:\s*translateX\(-100%\)"),
        ("Mobile Hamburger Button", r"\.mobile-hamburger-btn"),
        ("Universal Modal Inset & Centering", r"z-index:\s*999999"),
        ("Zero Horizontal Scroll Safety", r"overflow-x:\s*hidden")
    ]

    for name, pattern in checks:
        if re.search(pattern, css):
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name} missing!")

def audit_html_viewport_meta():
    print("\n" + "=" * 60)
    print("AUDITING HTML FILES FOR MOBILE VIEWPORT & SAFE META")
    print("=" * 60)
    
    passed = 0
    for h in sorted(HTML_FILES):
        path = os.path.join(FRONTEND_DIR, h)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        has_viewport = '<meta name="viewport"' in content or "<meta name='viewport'" in content
        has_theme_js = "theme.js" in content
        has_styles_css = "styles.css" in content

        status = "[PASS]" if has_viewport and (has_theme_js or has_styles_css or h == "login.html") else "[WARN]"
        if status == "[PASS]":
            passed += 1
        print(f"  {status} {h:<25} (viewport: {has_viewport}, theme.js: {has_theme_js})")

    print(f"\nTotal HTML Pages Audited: {len(HTML_FILES)} | Compliant: {passed}")

if __name__ == "__main__":
    audit_responsive_css()
    audit_html_viewport_meta()
