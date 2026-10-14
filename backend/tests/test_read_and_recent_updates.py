from datetime import datetime, timedelta, timezone

import pytest

from app.api.episodes import episodes_bp
from app.api.feeds import feeds_bp
from app.services.user_episode_state import user_filter_condition
from tests.auth_helpers import add_user, auth_headers, make_auth_app
from tests.test_episode_queries import app, episode


def test_recent_updates_filter_dates_before_pagination(app, monkeypatch):
    now = datetime(2026, 10, 3, 12)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.replace(tzinfo=timezone.utc) if tz else now

    monkeypatch.setattr("app.services.episode_query_service.datetime", FixedDateTime)
    recent = episode(app, "Recent", published=now - timedelta(days=2))
    boundary = episode(app, "Boundary", published=now - timedelta(days=7))
    episode(app, "Older", published=now - timedelta(days=7, seconds=1))
    episode(app, "No date", published=None)
    episode(app, "Future", published=now + timedelta(days=1))
    client = app.test_client()
    first = client.get("/api/episodes?days=7&per_page=1").get_json()
    assert first["pagination"]["total"] == 2
    assert [item["id"] for item in first["data"]] == [str(recent)]
    second = client.get("/api/episodes?days=7&per_page=1&page=2").get_json()
    assert [item["id"] for item in second["data"]] == [str(boundary)]
    oldest = client.get("/api/episodes?days=7&sort=published_asc").get_json()
    assert [item["id"] for item in oldest["data"]] == [str(boundary), str(recent)]
    searched = client.get("/api/episodes?days=7&q=Recent").get_json()
    assert [item["id"] for item in searched["data"]] == [str(recent)]


@pytest.mark.parametrize("days", ["0", "-1", "3651", "1.5", "abc", "true", ""])
def test_recent_updates_reject_invalid_days(app, days):
    response = app.test_client().get(f"/api/episodes?days={days}")
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "INVALID_QUERY"


def test_workspace_transcript_category_includes_summary_only_episodes(app):
    transcript = episode(app, "Transcript", has_transcript=True)
    summary = episode(app, "Summary without retained transcript", has_summary=True)
    episode(app, "Audio only", has_local_audio=True)
    episode(app, "Unprocessed")
    result = app.test_client().get("/api/episodes?processed=true&has_transcript_or_summary=true").get_json()
    assert result["pagination"]["total"] == 2
    assert {item["id"] for item in result["data"]} == {str(transcript), str(summary)}


def test_personal_read_status_does_not_inherit_shared_legacy_fields():
    app = make_auth_app((episodes_bp, "/api/episodes"))
    user = add_user(app.db, "reader@example.com")
    item = episode(app, "Legacy flags", is_read=True, is_starred=True, play_position=80)
    response = app.test_client().get(f"/api/episodes/{item}", headers=auth_headers(user)).get_json()["data"]
    assert response["is_read"] is False
    assert response["is_starred"] is False
    assert response["play_position"] == 0


def test_viewing_feed_clears_updates_for_only_current_user_without_reading_every_episode():
    app = make_auth_app((episodes_bp, "/api/episodes"), (feeds_bp, "/api/feeds"))
    user = add_user(app.db, "reader@example.com")
    other_user = add_user(app.db, "other-reader@example.com")
    feed = app.db.feeds.insert_one({"title": "Feed"}).inserted_id
    first = episode(app, "First", feed_id=feed)
    second = episode(app, "Second", feed_id=feed)
    app.db.user_episode_states.insert_one({"user_id": str(user["_id"]), "episode_id": first, "is_starred": True, "play_position": 88})
    client = app.test_client()
    headers = auth_headers(user)
    assert client.get("/api/feeds", headers=headers).get_json()["data"][0]["has_unseen_updates"] is True
    loaded = client.get(f"/api/feeds/{feed}/episodes", headers=headers).get_json()
    assert loaded["meta"]["latest_episode_id"] == str(second)
    # 后台 GET /feeds、节目列表查询都不能代替用户进入页面后的确认。
    assert app.db.user_feed_states.count_documents({}) == 0
    result = client.post(f"/api/feeds/{feed}/view", json=loaded["meta"], headers=headers).get_json()["data"]
    assert result == {"feed_id": str(feed), "has_unseen_updates": False}
    personal = client.get(f"/api/episodes/{first}", headers=headers).get_json()["data"]
    assert personal["is_read"] is False and personal["is_starred"] and personal["play_position"] == 88
    assert client.get(f"/api/feeds/{feed}", headers=headers).get_json()["data"]["has_unseen_updates"] is False
    assert client.get("/api/feeds", headers=auth_headers(other_user)).get_json()["data"][0]["has_unseen_updates"] is True
    assert app.db.user_episode_states.count_documents({"user_id": str(user["_id"])}) == 1
    assert not app.db.episodes.find_one({"_id": first}).get("is_read")


def test_backdated_new_arrival_and_stale_confirmation_do_not_hide_updates():
    app = make_auth_app((feeds_bp, "/api/feeds"))
    user = add_user(app.db, "reader@example.com")
    feed = app.db.feeds.insert_one({"title": "Feed"}).inserted_id
    first = episode(app, "First", feed_id=feed)
    client = app.test_client()
    headers = auth_headers(user)
    loaded = client.get(f"/api/feeds/{feed}/episodes", headers=headers).get_json()
    client.post(f"/api/feeds/{feed}/view", json=loaded["meta"], headers=headers)
    # 删除旧条目再补录旧节目：总数量不变、发布时间更早，也必须算新更新。
    old = episode(app, "Second", feed_id=feed)
    newest = client.get(f"/api/feeds/{feed}/episodes", headers=headers).get_json()["meta"]
    client.post(f"/api/feeds/{feed}/view", json=newest, headers=headers)
    app.db.episodes.delete_one({"_id": first})
    arrival = episode(app, "Backfilled old episode", feed_id=feed, published=datetime(2020, 1, 1))
    stale = client.post(f"/api/feeds/{feed}/view", json=newest, headers=headers).get_json()["data"]
    assert stale["has_unseen_updates"] is True
    latest = client.get(f"/api/feeds/{feed}/episodes", headers=headers).get_json()["meta"]
    assert latest["latest_episode_id"] == str(arrival)
    assert client.post(f"/api/feeds/{feed}/view", json=latest, headers=headers).get_json()["data"]["has_unseen_updates"] is False
    client.post(f"/api/feeds/{feed}/view", json={"latest_episode_id": str(old)}, headers=headers)
    state = app.db.user_feed_states.find_one({"user_id": str(user["_id"]), "feed_id": feed})
    assert state["last_seen_episode_id"] == arrival
    assert app.db.user_feed_states.count_documents({}) == 1


def test_episode_read_filter_is_personal_and_does_not_clear_subscription_updates():
    app = make_auth_app((episodes_bp, "/api/episodes"), (feeds_bp, "/api/feeds"))
    user = add_user(app.db, "reader@example.com")
    feed = app.db.feeds.insert_one({"title": "Feed"}).inserted_id
    item = episode(app, "Recent", feed_id=feed, published=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2))
    client = app.test_client()
    headers = auth_headers(user)
    read = client.post(f"/api/episodes/{item}/read", json={"is_read": True}, headers=headers).get_json()["data"]
    assert read["is_read"] is True and read["unread_count"] == 0
    assert client.get(f"/api/feeds/{feed}", headers=headers).get_json()["data"]["has_unseen_updates"] is True
    assert client.get("/api/episodes?days=7&is_read=false", headers=headers).get_json()["data"] == []
    unread = client.post(f"/api/episodes/{item}/read", json={"is_read": False}, headers=headers).get_json()["data"]
    assert unread["is_read"] is False and unread["unread_count"] == 1
    assert len(client.get("/api/episodes?days=7&is_read=false", headers=headers).get_json()["data"]) == 1
    assert client.post(f"/api/episodes/{item}/read", json={"is_read": "false"}, headers=headers).status_code == 400


def test_view_record_accepts_viewers_but_checks_auth_feed_and_snapshot():
    app = make_auth_app((feeds_bp, "/api/feeds"))
    viewer = add_user(app.db, "viewer@example.com", role="viewer")
    user = add_user(app.db, "reader@example.com")
    feed = app.db.feeds.insert_one({"title": "Feed"}).inserted_id
    item = episode(app, "First", feed_id=feed)
    other_feed = app.db.feeds.insert_one({"title": "Other"}).inserted_id
    other_item = episode(app, "Other feed", feed_id=other_feed)
    client = app.test_client()
    assert client.post(f"/api/feeds/{feed}/view", json={"latest_episode_id": str(item)}, headers=auth_headers(viewer)).status_code == 200
    assert client.post(f"/api/feeds/{feed}/view", json={"latest_episode_id": str(item)}).status_code == 401
    assert client.post("/api/feeds/not-an-id/view", headers=auth_headers(user)).status_code == 400
    assert client.post("/api/feeds/000000000000000000000000/view", headers=auth_headers(user)).status_code == 404
    for snapshot in (None, "not-an-id", 123):
        assert client.post(f"/api/feeds/{feed}/view", json={"latest_episode_id": snapshot}, headers=auth_headers(user)).status_code == 400
    assert client.post(f"/api/feeds/{feed}/view", json={"latest_episode_id": str(other_item)}, headers=auth_headers(user)).status_code == 404
    assert app.db.user_feed_states.count_documents({"user_id": str(user["_id"])}) == 0


def test_empty_feed_has_no_update_dot_and_loading_failure_records_no_view():
    app = make_auth_app((feeds_bp, "/api/feeds"))
    user = add_user(app.db, "reader@example.com")
    feed = app.db.feeds.insert_one({"title": "Empty feed"}).inserted_id
    client = app.test_client()
    headers = auth_headers(user)
    assert client.get("/api/feeds", headers=headers).get_json()["data"][0]["has_unseen_updates"] is False
    assert client.get(f"/api/feeds/{feed}/episodes", headers=headers).get_json()["meta"]["latest_episode_id"] is None
    assert client.get(f"/api/feeds/{feed}/episodes?sort=invalid", headers=headers).status_code == 400
    assert app.db.user_feed_states.count_documents({}) == 0


def test_unread_filter_does_not_fetch_the_shared_episode_library(app, monkeypatch):
    monkeypatch.setattr(app.db.episodes, "find", lambda *args, **kwargs: pytest.fail("unread filtering must not load the full library"))
    assert user_filter_condition(app.db, "reader", is_read=False) == {"_id": {"$nin": []}}
