# -*- coding: utf-8 -*-
"""
Backfill existing single-user data with a default owner_id.

Run from backend:
    uv run python scripts/backfill_default_owner.py
"""
import os
import sys
from datetime import datetime

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()


def main():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db = os.getenv("MONGO_DB", "podcast")
    owner_email = os.getenv("DEFAULT_ADMIN_EMAIL", "zz").strip().lower()
    owner_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "123456")

    client = MongoClient(mongo_uri)
    db = client[mongo_db]

    user = db.users.find_one({"email": owner_email})
    if not user:
        now = datetime.utcnow()
        result = db.users.insert_one({
            "email": owner_email,
            "password_hash": generate_password_hash(owner_password),
            "role": "admin",
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "last_login_at": None,
        })
        owner_id = str(result.inserted_id)
        print(f"Created default admin: {owner_email}")
    else:
        owner_id = str(user["_id"])
        print(f"Using existing default admin: {owner_email}")

    collections = ["feeds", "episodes", "transcripts", "summaries", "tasks", "settings"]
    for name in collections:
        result = db[name].update_many(
            {"owner_id": {"$exists": False}},
            {"$set": {"owner_id": owner_id, "updated_at": datetime.utcnow()}},
        )
        print(f"{name}: backfilled {result.modified_count}")

    print("\nDone.")
    print(f"DEFAULT_ADMIN_EMAIL={owner_email}")
    print("Change DEFAULT_ADMIN_PASSWORD after first login if this is not local development.")


if __name__ == "__main__":
    main()
