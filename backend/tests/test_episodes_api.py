from datetime import datetime

from bson import ObjectId

from app.api.episodes import episodes_bp
from tests.auth_helpers import add_user, auth_headers, make_auth_app


def make_episodes_app():
    return make_auth_app((episodes_bp, "/api/episodes"))


def add_feed(db, owner_id, title="Feed"):
    feed_id = ObjectId()
    db.feeds._data.append({
        "_id": feed_id,
        "owner_id": owner_id,
        "title": title,
        "rss_url": f"https://example.com/{title}.xml",
        "unread_count": 1,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    return feed_id


def add_episode(db, owner_id, feed_id, title="Episode", status="new"):
    episode_id = ObjectId()
    db.episodes._data.append({
        "_id": episode_id,
        "owner_id": owner_id,
        "feed_id": feed_id,
        "guid": title,
        "title": title,
        "status": status,
        "is_read": False,
        "is_starred": False,
        "published": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "audio_url": "https://example.com/audio.mp3",
    })
    return episode_id


def test_episode_list_ignores_empty_status_filter_segments():
    app = make_episodes_app()
    user = add_user(app.db, "user@example.com")
    feed_id = add_feed(app.db, str(user["_id"]))
    add_episode(app.db, str(user["_id"]), feed_id, "Visible Episode")

    response = app.test_client().get(
        "/api/episodes?status=,%20,",
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    assert [item["title"] for item in response.get_json()["data"]] == ["Visible Episode"]


def test_episode_mutations_do_not_cross_owner_boundary():
    app = make_episodes_app()
    user1 = add_user(app.db, "user1@example.com")
    user2 = add_user(app.db, "user2@example.com")
    feed_id = add_feed(app.db, str(user2["_id"]))
    episode_id = add_episode(app.db, str(user2["_id"]), feed_id, "Private Episode")
    client = app.test_client()
    headers = auth_headers(user1)

    update = client.put(f"/api/episodes/{episode_id}", json={"is_read": True}, headers=headers)
    star = client.post(f"/api/episodes/{episode_id}/star", json={"starred": True}, headers=headers)
    read = client.post(f"/api/episodes/{episode_id}/read", json={"is_read": True}, headers=headers)
    download = client.post(f"/api/episodes/{episode_id}/download", headers=headers)

    assert update.status_code == 200  # 共享库
    assert star.status_code == 200
    assert read.status_code == 200  # 共享库
    assert download.status_code == 200  # 共享库：member 可下载
    # 个人状态按用户隔离：写入 user_episode_states，剧集文档不动
    state = app.db.user_episode_states.find_one(
        {"user_id": str(user1["_id"]), "episode_id": episode_id}
    )
    assert state is not None
    assert state["is_read"] is True
    assert state["is_starred"] is True
    episode = app.db.episodes.find_one({"_id": episode_id})
    assert episode["is_read"] is False  # 文档保留默认值，不影响其他用户
    assert episode["status"] == "downloading"  # 共享库：下载已排队
