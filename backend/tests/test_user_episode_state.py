# -*- coding: utf-8 -*-
"""剧集个人状态按用户隔离：进度/已读/加星互不影响"""
from datetime import datetime

from bson import ObjectId

from app.api.episodes import episodes_bp
from app.api.feeds import feeds_bp
from tests.auth_helpers import add_user, auth_headers, make_auth_app


def _add_episode(db, title="Episode"):
    episode_id = ObjectId()
    db.episodes._data.append({
        "_id": episode_id,
        "owner_id": None,
        "feed_id": None,
        "guid": title,
        "title": title,
        "status": "new",
        "is_read": False,
        "is_starred": False,
        "play_position": 0,
        "published": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    return episode_id


def _add_feed(db, title="Feed"):
    feed_id = ObjectId()
    db.feeds._data.append({
        "_id": feed_id,
        "owner_id": None,
        "title": title,
        "rss_url": f"https://example.com/{title}.xml",
        "status": "active",
        "unread_count": 2,
        "created_at": datetime.utcnow(),
    })
    return feed_id


def test_play_position_isolated_per_user():
    app = make_auth_app((episodes_bp, "/api/episodes"))
    user1 = add_user(app.db, "user1@example.com")
    user2 = add_user(app.db, "user2@example.com")
    episode_id = _add_episode(app.db)

    client = app.test_client()
    resp = client.put(
        f"/api/episodes/{episode_id}", json={"play_position": 100},
        headers=auth_headers(user1),
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["play_position"] == 100

    d1 = client.get(f"/api/episodes/{episode_id}", headers=auth_headers(user1)).get_json()["data"]
    d2 = client.get(f"/api/episodes/{episode_id}", headers=auth_headers(user2)).get_json()["data"]
    assert d1["play_position"] == 100
    assert d2["play_position"] == 0  # user2 不受影响

    # 剧集文档本身不被写入
    doc = app.db.episodes.find_one({"_id": episode_id})
    assert doc["play_position"] == 0


def test_read_state_and_filter_per_user():
    app = make_auth_app((episodes_bp, "/api/episodes"))
    user1 = add_user(app.db, "user1@example.com")
    user2 = add_user(app.db, "user2@example.com")
    episode_id = _add_episode(app.db)

    client = app.test_client()
    resp = client.post(f"/api/episodes/{episode_id}/read", json={}, headers=auth_headers(user1))
    assert resp.status_code == 200

    read_list = client.get(
        "/api/episodes?is_read=true", headers=auth_headers(user1)
    ).get_json()["data"]
    unread_list = client.get(
        "/api/episodes?is_read=false", headers=auth_headers(user1)
    ).get_json()["data"]
    assert [e["id"] for e in read_list] == [str(episode_id)]
    assert all(e["id"] != str(episode_id) for e in unread_list)

    # user2 视角该集仍是未读
    user2_list = client.get(
        "/api/episodes?is_read=false", headers=auth_headers(user2)
    ).get_json()["data"]
    assert any(e["id"] == str(episode_id) for e in user2_list)


def test_viewer_cannot_write_state():
    app = make_auth_app((episodes_bp, "/api/episodes"))
    viewer = add_user(app.db, "viewer@example.com", role="viewer")
    episode_id = _add_episode(app.db)

    client = app.test_client()
    resp = client.put(
        f"/api/episodes/{episode_id}", json={"play_position": 50}, headers=auth_headers(viewer)
    )
    assert resp.status_code == 403

    read = client.post(f"/api/episodes/{episode_id}/read", headers=auth_headers(viewer))
    star = client.post(f"/api/episodes/{episode_id}/star", headers=auth_headers(viewer))
    assert read.status_code == 403
    assert star.status_code == 403


def test_feed_list_unread_count_per_user():
    app = make_auth_app((feeds_bp, "/api/feeds"), (episodes_bp, "/api/episodes"))
    user1 = add_user(app.db, "user1@example.com")
    user2 = add_user(app.db, "user2@example.com")
    feed_id = _add_feed(app.db)
    ep1 = _add_episode(app.db, "Ep1")
    ep2 = _add_episode(app.db, "Ep2")
    for eid in (ep1, ep2):
        app.db.episodes._data = [
            {**e, "feed_id": feed_id} if e["_id"] == eid else e for e in app.db.episodes._data
        ]

    client = app.test_client()
    client.post(f"/api/episodes/{ep1}/read", json={}, headers=auth_headers(user1))

    u1_feeds = client.get("/api/feeds", headers=auth_headers(user1)).get_json()["data"]
    u2_feeds = client.get("/api/feeds", headers=auth_headers(user2)).get_json()["data"]
    assert u1_feeds[0]["unread_count"] == 1  # user1 已读一集
    assert u2_feeds[0]["unread_count"] == 2  # user2 视角全未读
