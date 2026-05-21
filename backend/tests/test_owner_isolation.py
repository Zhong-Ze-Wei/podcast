from datetime import datetime

from bson import ObjectId
from flask import Flask

from app.api.episodes import episodes_bp
from app.models.user import User
from app.services.jwt_auth import create_token
from tests.conftest import MockDB


def make_app():
    app = Flask(__name__)
    app.config.update(AUTH_REQUIRED=True, JWT_SECRET="test-secret", JWT_EXPIRES_HOURS=1)
    app.db = MockDB()
    app.register_blueprint(episodes_bp, url_prefix="/api/episodes")
    return app


def add_user(db, email):
    doc = User.create(email, "password123")
    result = db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def token_for(user):
    return create_token(
        {"sub": str(user["_id"]), "email": user["email"], "role": user["role"]},
        "test-secret",
        1,
    )


def add_episode(db, owner_id, title):
    episode_id = ObjectId()
    feed_id = ObjectId()
    db.feeds._data.append({
        "_id": feed_id,
        "owner_id": owner_id,
        "title": f"{title} Feed",
        "rss_url": f"https://example.com/{title}.xml",
        "created_at": datetime.utcnow(),
    })
    db.episodes._data.append({
        "_id": episode_id,
        "owner_id": owner_id,
        "feed_id": feed_id,
        "guid": title,
        "title": title,
        "status": "new",
        "published": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    return episode_id


def test_episode_list_and_detail_are_filtered_by_owner():
    app = make_app()
    db = app.db
    user1 = add_user(db, "user1@example.com")
    user2 = add_user(db, "user2@example.com")
    user1_episode = add_episode(db, str(user1["_id"]), "User 1 Episode")
    user2_episode = add_episode(db, str(user2["_id"]), "User 2 Episode")

    client = app.test_client()
    headers = {"Authorization": f"Bearer {token_for(user1)}"}

    listed = client.get("/api/episodes", headers=headers)
    assert listed.status_code == 200
    titles = [item["title"] for item in listed.get_json()["data"]]
    assert titles == ["User 1 Episode"]

    own_detail = client.get(f"/api/episodes/{user1_episode}", headers=headers)
    assert own_detail.status_code == 200

    other_detail = client.get(f"/api/episodes/{user2_episode}", headers=headers)
    assert other_detail.status_code == 404
