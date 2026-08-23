import urllib.request
import json
import sys

BASE_URL = "http://127.0.0.1:8000/api"

def get_token(username, password):
    url = f"{BASE_URL}/auth/login"
    payload = {"username": username, "password": password}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data["access_token"]
    except Exception as e:
        print(f"Login failed: {e}")
        sys.exit(1)

def test_attendance_analytics(token):
    print("Testing /api/attendance/analytics...")
    req = urllib.request.Request(
        f"{BASE_URL}/attendance/analytics",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as res:
        assert res.status == 200, f"Expected 200, got {res.status}"
        data = json.loads(res.read().decode("utf-8"))
        print(f"  Attendance analytics returned {len(data)} items: {data}")

def test_class_averages_authenticated(token, class_id):
    print(f"Testing /api/results/analytics/class-averages/{class_id} (authenticated)...")
    req = urllib.request.Request(
        f"{BASE_URL}/results/analytics/class-averages/{class_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as res:
        assert res.status == 200, f"Expected 200, got {res.status}"
        data = json.loads(res.read().decode("utf-8"))
        print(f"  Class averages returned {len(data)} items: {data}")

def test_class_averages_unauthenticated(class_id):
    print(f"Testing /api/results/analytics/class-averages/{class_id} (unauthenticated)...")
    req = urllib.request.Request(
        f"{BASE_URL}/results/analytics/class-averages/{class_id}"
    )
    try:
        urllib.request.urlopen(req)
        print("  Error: Managed to access endpoint without token!")
        sys.exit(1)
    except urllib.error.HTTPError as e:
        assert e.code == 401, f"Expected HTTP 401 for unauthenticated request, got {e.code}"
        print(f"  Passed: Correctly blocked with HTTP 401.")

if __name__ == "__main__":
    print("--- Starting Analytics Endpoints Verification Tests ---")
    try:
        token = get_token("admin", "admin123!")
    except SystemExit:
        token = get_token("superadmin", "superadmin123!")
    
    test_attendance_analytics(token)
    test_class_averages_authenticated(token, 1)
    test_class_averages_unauthenticated(1)
    
    print("\n--- All tests completed successfully! ---")
