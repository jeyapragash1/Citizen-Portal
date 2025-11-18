# Quick test script to call protected /api/admin/profiles endpoint using Flask test client
import json
import sys

try:
    from app import app
except Exception as e:
    print('IMPORT_ERROR', e)
    sys.exit(2)

with app.test_client() as c:
    # set admin session flag
    try:
        with c.session_transaction() as sess:
            sess['admin_logged_in'] = True
    except Exception as e:
        print('SESSION_ERROR', e)
    res = c.get('/api/admin/profiles')
    print('STATUS', res.status_code)
    text = res.get_data(as_text=True)
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get('error'):
            print('ERROR_PAYLOAD:', data.get('error'))
        else:
            print('LEN', len(data) if hasattr(data, '__len__') else 'N/A')
            print(json.dumps(data[:5], indent=2))
    except Exception as e:
        print('RESPONSE_TEXT_SNIPPET')
        print(text[:2000])
        print('JSON_LOAD_ERROR', e)
