import pytest
import werkzeug
import os, sys, pathlib
# Ensure project root is on sys.path so 'app' can be imported when pytest runs from tests folder
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

from app import app, users_col, orders_col, payments_col, products_col
from datetime import datetime
from bson import ObjectId


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_store_flow(client):
    # Ensure there's at least one product
    prod = products_col.find_one({})
    assert prod is not None

    # Create a test user
    uid = users_col.insert_one({"profile": {"basic": {"name": "StoreUser"}}, "created": datetime.utcnow()}).inserted_id
    profile_id = str(uid)

    # Login as user to set session
    login_resp = client.post('/api/user/login', json={"profile_id": profile_id})
    assert login_resp.status_code == 200

    # Create an order
    items = [{"id": prod.get('id'), "price": prod.get('price'), "quantity": 1}]
    order_resp = client.post('/api/store/order', json={"user_id": profile_id, "items": items, "total_amount": prod.get('price')})
    assert order_resp.status_code == 200
    order_data = order_resp.get_json()
    assert order_data.get('status') == 'ok'
    order_id = order_data.get('order_id')

    # Process payment (verified) to mark order as paid
    pay_resp = client.post('/api/store/payment', json={"order_id": order_id, "user_id": profile_id, "amount": prod.get('price'), "method": "card", "verified": True, "items": items})
    assert pay_resp.status_code == 200
    pay_data = pay_resp.get_json()
    assert pay_data.get('status') == 'ok'

    # Check order status updated
    o = orders_col.find_one({"order_id": order_id})
    assert o is not None
    assert o.get('status') in ('paid','pending')

    # Cleanup
    orders_col.delete_one({"order_id": order_id})
    payments_col.delete_many({"order_id": order_id})
    users_col.delete_one({"_id": ObjectId(profile_id)})
