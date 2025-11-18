"""Utility script to create a test user and call /api/data/delete_request/<user_id>
Uses the Flask test client so it runs without starting the server and will attempt to send email
using SMTP settings in the repository `.env`.
"""
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from datetime import datetime
import sys

HERE = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(HERE, '..'))
DOTENV_PATH = os.path.join(REPO_ROOT, '.env')
load_dotenv(DOTENV_PATH)

MONGO_URI = os.getenv('MONGO_URI')
client = MongoClient(MONGO_URI)
db = client['citizen_portal']
users_col = db['users']
deletion_confirmations_col = db['deletion_confirmations']

import werkzeug
if not hasattr(werkzeug, '__version__'):
    werkzeug.__version__ = '2.0.0'

from importlib import import_module
sys.path.insert(0, REPO_ROOT)
app = import_module('app').app

def run():
    # create test user
    u = {'email': 'kishojeyapragash@gmail.com', 'profile': {'name': 'Live Test'}, 'created': datetime.utcnow()}
    res = users_col.insert_one(u)
    user_id = str(res.inserted_id)
    print('Inserted test user id:', user_id)

    try:
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['admin_logged_in'] = True
                sess['admin_user'] = 'admin'

            r = c.post(f'/api/data/delete_request/{user_id}', json={})
            print('Response status:', r.status_code)
            print('Response json:', r.get_json())

            rec = deletion_confirmations_col.find_one({'user_id': user_id})
            print('DB token record present:', bool(rec))

    finally:
        # cleanup: remove test user and any confirmation records
        users_col.delete_one({'_id': res.inserted_id})
        deletion_confirmations_col.delete_many({'user_id': user_id})

if __name__ == '__main__':
    run()
