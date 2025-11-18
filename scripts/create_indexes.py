from pymongo import MongoClient, ASCENDING, DESCENDING
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client['citizen_portal']

print("Creating recommended indexes...")

index_ops = [
    ("engagements", [("user_id", ASCENDING), ("timestamp", DESCENDING)]),
    ("users", [("created", DESCENDING), ("last_active", DESCENDING)]),
    ("products", [("category", ASCENDING), ("tags", ASCENDING), ("id", ASCENDING)]),
    ("orders", [("order_id", ASCENDING), ("user_id", ASCENDING)]),
    ("payments", [("payment_id", ASCENDING), ("order_id", ASCENDING)]),
    ("index_jobs", [("job_id", ASCENDING), ("status", ASCENDING)]),
    ("ads", [("id", ASCENDING), ("active", ASCENDING)]),
    ("services", [("id", ASCENDING)])
]

for coll_name, keys in index_ops:
    coll = db[coll_name]
    print(f"Creating indexes on {coll_name}: {keys}")
    try:
        for key in keys:
            coll.create_index([key])
    except Exception as e:
        print(f"Failed to create index on {coll_name}: {e}")

print("Index creation complete.")
