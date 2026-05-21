# -*- coding: utf-8 -*-
"""
Create predictable local test users.

Run from backend:
    uv run python scripts/seed_test_users.py
"""
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

USERS = [
    ("admin@example.com", "admin"),
    ("user1@example.com", "user"),
    ("user2@example.com", "user"),
]


def main():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db = os.getenv("MONGO_DB", "podcast")
    password = os.getenv("TEST_USER_PASSWORD", "password123")
    client = MongoClient(mongo_uri)
    db = client[mongo_db]

    now = datetime.utcnow()
    for email, role in USERS:
        existing = db.users.find_one({"email": email})
        if existing:
            db.users.update_one(
                {"_id": existing["_id"]},
                {"$set": {"role": role, "status": "active", "updated_at": now}},
            )
            print(f"Updated {email} ({role})")
            continue
        db.users.insert_one({
            "email": email,
            "password_hash": generate_password_hash(password),
            "role": role,
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "last_login_at": None,
        })
        print(f"Created {email} ({role})")

    print(f"\nPassword for all test users: {password}")


if __name__ == "__main__":
    main()
