import importlib.util
from datetime import datetime
import os

APP_PATH = os.path.join(os.path.dirname(__file__), '..', 'app.py')

spec = importlib.util.spec_from_file_location('app', os.path.abspath(APP_PATH))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

doc = {
    "_id": "000000000000000000000000",
    "email": "user@example.com",
    "password": b"hashedpw",
    "profile": {"name":"Alice","password":"plain"},
    "blob": b"\xff\x00\x01",
    "created": datetime.utcnow()
}

print(app.serialize_doc(doc))
