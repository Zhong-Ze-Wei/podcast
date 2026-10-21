# -*- coding: utf-8 -*-
"""订阅更新参数：统一间隔、钳制边界、静默任务与每日完成统计。"""
from datetime import datetime, timedelta

from bson import ObjectId

from app.services import refresh_settings
from app.services.auto_refresher import FeedAutoRefresher
from app.services.task_queue import TaskQueue
from tests.conftest import MockDB


def test_defaults_are_twelve_hours_for_every_feed_type():
    values = refresh_settings.defaults()
    assert values["feed_interval_hours"] == 12
    assert values["enabled"] is True


def test_saved_settings_override_defaults_and_are_clamped():
    db = MockDB()
    refresh_settings.save_settings(db, {"feed_interval_hours": 500, "transcript_interval_minutes": 0})
    values = refresh_settings.get_settings(db)
    assert values["feed_interval_hours"] == refresh_settings.LIMITS["feed_interval_hours"][1]
    assert values["transcript_interval_minutes"] == refresh_settings.LIMITS["transcript_interval_minutes"][0]


def test_unknown_keys_are_ignored():
    db = MockDB()
    refresh_settings.save_settings(db, {"not_a_setting": 1})
    assert "not_a_setting" not in refresh_settings.get_settings(db)


def test_feed_due_check_uses_one_shared_interval():
    db = MockDB()
    settings = refresh_settings.get_settings(db)
    now = datetime.utcnow()
    assert refresh_settings.is_due(None, settings, now) is True
    assert refresh_settings.is_due(now - timedelta(hours=11), settings, now) is False
    assert refresh_settings.is_due(now - timedelta(hours=13), settings, now) is True


def test_silent_tasks_stay_out_of_the_task_collection():
    db = MockDB()
    queue = TaskQueue()
    queue.set_db(db)
    try:
        queue.submit_silent("refresh", lambda progress_callback=None: {"ok": True},
                            dedup_key="refresh:silent", feed_id=str(ObjectId()))
        for task in list(queue.tasks.values()):
            task["status"] = "completed"
        assert db.tasks.count_documents({}) == 0
    finally:
        queue.shutdown()


def test_daily_summary_counts_successes_and_failures():
    db = MockDB()
    refresher = FeedAutoRefresher(db)
    feed = {"title": "Feed A"}
    refresher._record(feed, True)
    refresher._record(feed, True)
    refresher._record(feed, False)
    summary = refresher.daily_summary()
    assert (summary["done"], summary["failed"], summary["feeds"]) == (2, 1, 3)
    assert summary["last_feed"] == "Feed A"


def test_daily_summary_resets_on_a_new_day():
    db = MockDB()
    refresher = FeedAutoRefresher(db)
    refresher._record({"title": "Feed A"}, True)
    refresher._daily["date"] = "2000-01-01"
    summary = refresher.daily_summary()
    assert summary["done"] == 0 and summary["feeds"] == 0


# ---- 设置接口 ----

def test_refresh_settings_api_round_trip():
    from app.api.settings import settings_bp
    from tests.auth_helpers import add_user, auth_headers, make_auth_app

    app = make_auth_app((settings_bp, "/api/settings"))
    user = add_user(app.db, "user@example.com")
    http = app.test_client()
    headers = auth_headers(user)

    initial = http.get("/api/settings/refresh", headers=headers).get_json()
    assert initial["settings"]["feed_interval_hours"] == 12
    assert initial["limits"]["feed_interval_hours"] == [1, 168]

    saved = http.put("/api/settings/refresh", json={"feed_interval_hours": 24, "feeds_per_tick": 3},
                     headers=headers).get_json()
    assert saved["settings"]["feed_interval_hours"] == 24
    assert saved["settings"]["feeds_per_tick"] == 3
    assert http.get("/api/settings/refresh", headers=headers).get_json()["settings"]["feed_interval_hours"] == 24


def test_refresh_settings_api_rejects_unknown_and_out_of_range_values():
    from app.api.settings import settings_bp
    from tests.auth_helpers import add_user, auth_headers, make_auth_app

    app = make_auth_app((settings_bp, "/api/settings"))
    user = add_user(app.db, "user@example.com")
    http = app.test_client()
    headers = auth_headers(user)

    assert http.put("/api/settings/refresh", json={"nope": 1}, headers=headers).status_code == 400
    # 越界值被钳到边界而不是报错
    clamped = http.put("/api/settings/refresh", json={"feed_interval_hours": 9999},
                       headers=headers).get_json()
    assert clamped["settings"]["feed_interval_hours"] == 168


def test_task_list_exposes_daily_auto_refresh_summary():
    from app.api.tasks import tasks_bp
    from app.services import auto_refresher
    from tests.auth_helpers import add_user, auth_headers, make_auth_app

    app = make_auth_app((tasks_bp, "/api/tasks"))
    user = add_user(app.db, "user@example.com")
    refresher = auto_refresher.FeedAutoRefresher(app.db)
    refresher._record({"title": "Feed A"}, True)
    refresher._record({"title": "Feed B"}, False)
    auto_refresher._refresher_instance = refresher
    try:
        payload = app.test_client().get("/api/tasks", headers=auth_headers(user)).get_json()
    finally:
        auto_refresher._refresher_instance = None
    assert payload["meta"]["auto_refresh_daily"]["done"] == 1
    assert payload["meta"]["auto_refresh_daily"]["feeds"] == 2
