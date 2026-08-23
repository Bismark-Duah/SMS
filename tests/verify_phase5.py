import urllib.request, urllib.error, json

BASE = 'http://localhost:8000/api'

def get(path, label):
    try:
        r = urllib.request.urlopen(f'{BASE}{path}', timeout=6)
        d = json.loads(r.read())
        s = f'list({len(d)})' if isinstance(d, list) else str(dict(list(d.items())[:4]))
        print(f'[OK]   {label}: {s}')
        return d
    except urllib.error.HTTPError as e:
        print(f'[FAIL] {label}: HTTP {e.code} {e.read().decode()[:100]}')
    except Exception as e:
        print(f'[FAIL] {label}: {e}')
    return None

def req(method, path, payload, label):
    try:
        data = json.dumps(payload).encode()
        r = urllib.request.Request(
            f'{BASE}{path}', data=data,
            headers={'Content-Type': 'application/json'}, method=method
        )
        resp = urllib.request.urlopen(r, timeout=6)
        d = json.loads(resp.read())
        s = str(dict(list(d.items())[:4])) if isinstance(d, dict) else str(d)
        print(f'[OK]   {label}: {s}')
        return d
    except urllib.error.HTTPError as e:
        print(f'[FAIL] {label}: HTTP {e.code} {e.read().decode()[:100]}')
    except Exception as e:
        print(f'[FAIL] {label}: {e}')
    return None

print('=== Phase 5 Backend Verification ===\n')

# Students list with enriched fields
students = get('/students/', 'GET /students/')
if students:
    first = students[0]
    print(f'  -> has class_name:    {"class_name" in first}')
    print(f'  -> has gender:        {"gender" in first}')
    print(f'  -> has guardian_name: {"guardian_name" in first}')
    sid = first['id']

    # GET single student
    s = get(f'/students/{sid}', f'GET /students/{sid}')

    # PUT update
    if s:
        payload = {
            'student_code': s['student_code'],
            'full_name': s['full_name'],
            'class_section_id': s['class_section_id'],
            'gender': 'Male',
            'guardian_name': 'Test Guardian',
        }
        updated = req('PUT', f'/students/{sid}', payload, f'PUT /students/{sid}')
        if updated:
            print(f'  -> guardian_name saved: {updated.get("guardian_name")}')

print()

# Academic years (enriched with semesters)
years = get('/academic/years', 'GET /academic/years')
if years:
    print(f'  -> has semesters key: {"semesters" in years[0]}')
    yid = years[0]['id']
    req('PATCH', f'/academic/years/{yid}/set-current', {}, 'PATCH /years/set-current')

# Academic semesters (enriched with academic_year)
semesters = get('/academic/semesters', 'GET /academic/semesters')
if semesters:
    print(f'  -> has academic_year: {"academic_year" in semesters[0]}')
    sid = semesters[0]['id']
    req('PATCH', f'/academic/semesters/{sid}/set-current', {}, 'PATCH /semesters/set-current')

print('\n=== Done ===')
