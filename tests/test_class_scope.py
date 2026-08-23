import urllib.request, json

req = urllib.request.Request('http://127.0.0.1:8000/api/auth/login',
    data=json.dumps({'username':'Samuel Osei','password':'Welcome123'}).encode(),
    headers={'Content-Type':'application/json'})
data = json.loads(urllib.request.urlopen(req).read().decode())
token = data['access_token']
H = {'Authorization': 'Bearer ' + token}
print("Roles:", data.get('roles'))

endpoints = [
    '/api/subjects/',
    '/api/departments/',
    '/api/houses/',
    '/api/discipline/',
]

for ep in endpoints:
    req2 = urllib.request.Request('http://127.0.0.1:8000' + ep, headers=H)
    try:
        d = json.loads(urllib.request.urlopen(req2).read().decode())
        count = len(d) if isinstance(d, list) else '?'
        print(f"\n{ep} → {count} item(s)")
        if isinstance(d, list):
            for item in d[:3]:
                print("  -", item.get('name', item.get('student_name', item.get('id', item))))
    except Exception as e:
        print(f"\n{ep} → ERROR: {e}")
