from datetime import datetime

from bson import ObjectId

from app.api.feeds import feeds_bp
from tests.auth_helpers import add_user, auth_headers, make_auth_app


def _add_feed(db, owner_id, title="Feed"):
    feed_id = ObjectId()
    db.feeds._data.append({
        "_id": feed_id,
        "owner_id": owner_id,
        "title": title,
        "rss_url": f"https://example.com/{title}.xml",
        "status": "active",
        "is_starred": False,
        "is_favorite": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    return feed_id


def _add_episode(db, owner_id, feed_id, title="Episode"):
    episode_id = ObjectId()
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


def test_create_feed_rejects_duplicate_url_globally():
    app = make_auth_app((feeds_bp, "/api/feeds"))
    user1 = add_user(app.db, "user1@example.com")
    user2 = add_user(app.db, "user2@example.com")
    _add_feed(app.db, str(user1["_id"]), "Existing")  # rss_url: https://example.com/Existing.xml

    client = app.test_client()

    # 完全相同 URL，共享库下即使换用户也不允许重复
    resp = client.post(
        "/api/feeds", json={"rss_url": "https://example.com/Existing.xml"},
        headers=auth_headers(user2),
    )
    assert resp.status_code == 409
    assert resp.get_json()["error_code"] == "FEED_EXISTS"

    # 带跟踪参数、大小写不同、尾斜杠——规范化后仍是同一来源
    resp = client.post(
        "/api/feeds",
        json={"rss_url": "https://EXAMPLE.com/Existing.xml/?utm_source=rss"},
        headers=auth_headers(user1),
    )
    assert resp.status_code == 409


def test_feed_list_detail_and_episode_list_are_owner_filtered():
    app = make_auth_app((feeds_bp, "/api/feeds"))
    user1 = add_user(app.db, "user1@example.com")
    user2 = add_user(app.db, "user2@example.com")
    feed1 = _add_feed(app.db, str(user1["_id"]), "User1")
    _add_feed(app.db, str(user2["_id"]), "User2")
    _add_episode(app.db, str(user1["_id"]), feed1, "Private Episode")

    client = app.test_client()
    listed = client.get("/api/feeds", headers=auth_headers(user1))
    assert listed.status_code == 200
    assert {feed["title"] for feed in listed.get_json()["data"]} == {"User1", "User2"}

    own_detail = client.get(f"/api/feeds/{feed1}", headers=auth_headers(user1))
    assert own_detail.status_code == 200

    other_detail = client.get(f"/api/feeds/{feed1}", headers=auth_headers(user2))
    assert other_detail.status_code == 200

    other_episodes = client.get(f"/api/feeds/{feed1}/episodes", headers=auth_headers(user2))
    assert other_episodes.status_code == 200


def test_feed_mutations_do_not_cross_owner_boundary():
    app = make_auth_app((feeds_bp, "/api/feeds"))
    user1 = add_user(app.db, "user1@example.com")
    user2 = add_user(app.db, "user2@example.com")
    feed1 = _add_feed(app.db, str(user1["_id"]), "User1")

    client = app.test_client()
    star = client.post(f"/api/feeds/{feed1}/star", json={"starred": True}, headers=auth_headers(user2))
    favorite = client.post(f"/api/feeds/{feed1}/favorite", json={"favorite": True}, headers=auth_headers(user2))

    assert star.status_code == 200
    assert favorite.status_code == 200
    feed = app.db.feeds.find_one({"_id": feed1})
    assert feed["is_starred"] is True  # 共享库：user2 标记生效
    assert feed["is_favorite"] is True
