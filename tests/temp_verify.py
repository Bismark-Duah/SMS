import json
import urllib.request

body = json.dumps({"name": "Probe", "level": "Test"}).encode()
req = urllib.request.Request('http://127.0.0.1:8000/api/classes/', data=body, headers={'Content-Type': 'application/json'}, method='POST')
try:
    with urllib.request.urlopen(req) as response:
        print('STATUS', response.status)
        print('BODY', response.read().decode())
except Exception as exc:
    print('ERROR', type(exc).__name__)
    print('CODE', getattr(exc, 'code', None))
    if hasattr(exc, 'read'):
        try:
            print('ERRBODY', exc.read().decode())
        except Exception:
            pass
