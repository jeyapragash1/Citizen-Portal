import urllib.request
import json
import sys

def fetch(path):
    url = f"http://127.0.0.1:5000{path}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode('utf-8')
            try:
                j = json.loads(body)
                return (r.status, j)
            except Exception:
                return (r.status, body[:500])
    except Exception as e:
        return (None, str(e))

endpoints = [
    '/api/services',
    '/api/ads',
    '/api/store/products',
    '/api/store/categories',
    '/api/recommendations/000000000000000000000000'
]

if __name__ == '__main__':
    print('Running smoke tests against http://127.0.0.1:5000')
    for ep in endpoints:
        status, body = fetch(ep)
        print('='*60)
        print(f'Endpoint: {ep}')
        print('Status:', status)
        if isinstance(body, dict):
            sample = json.dumps(body, indent=2)
            print('JSON Response (truncated to 1000 chars):')
            print(sample[:1000])
        else:
            print('Response (truncated):')
            print(str(body)[:1000])
    print('\nSmoke tests finished.')
