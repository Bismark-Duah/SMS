"""
Test Suite: LAN Wi-Fi Multi-Device Hub & Host Network Discovery
"""
import sys
import os
import unittest

# Set working directory to project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from starlette.requests import Request
from backend.app.routes.settings import get_lan_info

class TestLanInfo(unittest.TestCase):
    def test_lan_info_payload(self):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/settings/lan-info",
            "headers": [(b"host", b"localhost:8000")],
            "scheme": "http"
        }
        req = Request(scope)
        data = get_lan_info(req)

        self.assertIsNotNone(data.get("hostname"))
        self.assertIsNotNone(data.get("primary_url"))
        self.assertEqual(data.get("port"), 8000)

        interfaces = data.get("interfaces", [])
        self.assertGreater(len(interfaces), 0)

        for iface in interfaces:
            self.assertIn("url", iface)
            self.assertIn("ip", iface)

        self.assertIn("instructions", data)

    def test_cloud_domain_payload(self):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/settings/lan-info",
            "headers": [(b"host", b"sms-nald.onrender.com"), (b"x-forwarded-proto", b"https")],
            "scheme": "https"
        }
        req = Request(scope)
        data = get_lan_info(req)

        self.assertTrue(data.get("is_cloud"))
        self.assertEqual(data.get("primary_url"), "https://sms-nald.onrender.com")

if __name__ == "__main__":
    unittest.main()
