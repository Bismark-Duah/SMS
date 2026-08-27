"""
Test Suite: LAN Wi-Fi Multi-Device Hub & Host Network Discovery
"""
import sys
import os

# Set working directory to project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from starlette.requests import Request
from backend.app.routes.settings import get_lan_info

def test_lan_info_payload():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/settings/lan-info",
        "headers": [(b"host", b"localhost:8000")],
        "scheme": "http"
    }
    req = Request(scope)
    data = get_lan_info(req)

    print("\n==================================================================")
    print("TEST SUITE: LAN Wi-Fi Multi-Device Hub Discovery")
    print("==================================================================")
    print(f"[OK] Host Machine: {data.get('hostname')}")
    print(f"[OK] Primary Server URL: {data.get('primary_url')}")
    print(f"[OK] Port: {data.get('port')}")

    interfaces = data.get("interfaces", [])
    print(f"[OK] Detected Network Interfaces: {len(interfaces)}")
    assert len(interfaces) > 0, "Should detect at least 1 network interface"

    for iface in interfaces:
        print(f"     -> [{iface.get('label')}] {iface.get('url')} (IP: {iface.get('ip')})")
        assert "url" in iface, "Interface should have URL"
        assert "ip" in iface, "Interface should have IP"

    assert "instructions" in data, "Should provide connection instructions"
    print("\n==================================================================")
    print("SUCCESS: LAN WI-FI MULTI-DEVICE HUB DISCOVERY VERIFIED 100%!")
    print("==================================================================")

def test_cloud_domain_payload():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/settings/lan-info",
        "headers": [(b"host", b"sms-nald.onrender.com"), (b"x-forwarded-proto", b"https")],
        "scheme": "https"
    }
    req = Request(scope)
    data = get_lan_info(req)

    print("\n==================================================================")
    print("TEST SUITE: Cloud Production Mobile Connect Discovery")
    print("==================================================================")
    print(f"[OK] Cloud Hostname: {data.get('hostname')}")
    print(f"[OK] Cloud URL: {data.get('primary_url')}")
    assert data.get("is_cloud") == True, "Should identify as cloud host"
    assert data.get("primary_url") == "https://sms-nald.onrender.com", "Should resolve to public Render HTTPS domain"
    print("SUCCESS: CLOUD PRODUCTION MOBILE CONNECT VERIFIED 100%!")
    print("==================================================================")

if __name__ == "__main__":
    test_lan_info_payload()
    test_cloud_domain_payload()
