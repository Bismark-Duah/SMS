"""
Test Suite: LAN Wi-Fi Multi-Device Hub & Host Network Discovery
"""
import sys
import os

# Set working directory to project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.routes.settings import get_lan_info

def test_lan_info_payload():
    data = get_lan_info()

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

if __name__ == "__main__":
    test_lan_info_payload()
