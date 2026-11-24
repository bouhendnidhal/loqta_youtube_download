"""Manual smoke test for a running packaged desktop window."""
import re
import sys
import time
import requests

base = f'http://127.0.0.1:{sys.argv[1]}'
session = requests.Session()
home = session.get(base, timeout=10)
home.raise_for_status()
token = re.search(r'<meta name="app-token" content="([^"]+)"', home.text).group(1)
headers = {'X-App-Token': token, 'Origin': base}
health = session.get(base + '/api/health', timeout=10).json()
assert health['ready'], health
info_response = session.post(base + '/api/inspect', json={'url': 'https://www.youtube.com/watch?v=jNQXAC9IVRw'}, headers=headers, timeout=120)
info_response.raise_for_status()
info = info_response.json()
job_response = session.post(base + '/api/jobs', json={'inspection_id': info['inspection_id'], 'kind': 'mp3', 'start': '1', 'end': '3'}, headers=headers, timeout=10)
job_response.raise_for_status()
job_id = job_response.json()['id']
for _ in range(120):
    job = next(x for x in session.get(base + '/api/jobs', timeout=10).json() if x['id'] == job_id)
    if job['status'] in ('done', 'error'):
        break
    time.sleep(1)
assert job['status'] == 'done', job
file = session.get(base + f'/api/jobs/{job_id}/file', timeout=30)
file.raise_for_status()
assert file.content.startswith(b'ID3') and len(file.content) > 1000
print('Desktop smoke passed:', info['title'], len(file.content), 'bytes')
session.delete(base + f'/api/jobs/{job_id}', headers=headers, timeout=10).raise_for_status()
