import pytest
import werkzeug
import os, sys, pathlib
# Ensure project root is on sys.path so 'app' can be imported when pytest runs from tests folder
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if not hasattr(werkzeug, "__version__"):
    # Some Werkzeug builds don't expose __version__; tests expect it — provide fallback
    werkzeug.__version__ = "3.0.0"

from app import app, users_col, eng_col
from bson import ObjectId
from datetime import datetime


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_extended_profile_and_engagement(client):
    # Insert a temporary user
    uid = users_col.insert_one({"profile": {"basic": {"name": "Test User"}}, "created": datetime.utcnow()}).inserted_id
    profile_id = str(uid)

    # Post extended profile
    resp = client.post('/api/profile/extended', json={
        "profile_id": profile_id,
        "marital_status": "single",
        "children": [],
        "highest_qualification": "degree",
        "current_job": "Engineer",
        "marketing_emails": True
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('status') == 'ok'

    # Verify in DB
    user = users_col.find_one({"_id": ObjectId(profile_id)})
    assert user is not None
    assert 'extended_profile' in user

    # Post enhanced engagement
    resp2 = client.post('/api/engagement/enhanced', json={
        "user_id": profile_id,
        "session_id": "s1",
        "age": 30,
        "job": "Engineer",
        "desires": ["degree_programs"],
        "question_clicked": "How to apply?",
        "service": "civil_servant_info",
        "ad": "ad_courses_01",
        "time_spent": 12,
        "scroll_depth": 50,
        "clicks": [],
        "searches": []
    })
    assert resp2.status_code == 200
    d = resp2.get_json()
    assert d.get('status') == 'ok'

    # Ensure engagement saved
    e = eng_col.find_one({"user_id": profile_id})
    assert e is not None

    # Cleanup
    users_col.delete_one({"_id": ObjectId(profile_id)})
    eng_col.delete_many({"user_id": profile_id})
