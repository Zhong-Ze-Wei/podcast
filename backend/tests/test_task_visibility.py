from datetime import datetime
from threading import Event

import pytest

from app.api import tasks as api
from app.services.task_queue import TaskQueue
from tests.auth_helpers import add_user, auth_headers, make_auth_app


def setup_app():
    app = make_auth_app((api.tasks_bp, "/api/tasks"))
    user = add_user(app.db, "reader@example.com")
    other = add_user(app.db, "other@example.com")
    return app, user, other


def insert_task(db, task_id, owner, task_type="briefing-report", **fields):
    db.tasks.insert_one({"task_id": task_id, "owner_id": str(owner["_id"]),
                         "task_type": task_type, "status": "pending",
                         "created_at": datetime.utcnow(), **fields})


@pytest.mark.parametrize("task_type", ["briefing-report", "briefing-lab"])
def test_personal_briefing_tasks_are_hidden_in_list_and_database_fallback(task_type):
    app, user, other = setup_app()
    insert_task(app.db, "mine", user, task_type)
    insert_task(app.db, "private", other, task_type, result={"private_text": "secret"})
    insert_task(app.db, "shared", other, "download")
    client = app.test_client()
    response = client.get("/api/tasks?per_page=1", headers=auth_headers(user)).get_json()
    assert response["pagination"]["total"] == 2
    assert response["data"][0]["id"] == "shared"
    assert client.get("/api/tasks/private", headers=auth_headers(user)).status_code == 404
    assert client.get("/api/tasks/shared", headers=auth_headers(user)).status_code == 200


def test_period_filter_and_metadata_restore_only_the_selected_briefing_task():
    app, user, other = setup_app()
    period = {"type": "month", "start": "2026-10-01"}
    insert_task(app.db, "selected", user, report_period=period)
    insert_task(app.db, "old", user, report_period={"type": "month", "start": "2026-09-01"})
    insert_task(app.db, "private", other, report_period=period)
    payload = app.test_client().get(
        "/api/tasks?type=briefing-report&period_type=month&period_start=2026-10-01",
        headers=auth_headers(user),
    ).get_json()
    assert [task["id"] for task in payload["data"]] == ["selected"]
    assert payload["data"][0]["report_period"] == period


def test_foreign_persisted_task_cannot_be_cancelled():
    app, user, other = setup_app()
    insert_task(app.db, "foreign", other, "transcribe")
    response = app.test_client().post("/api/tasks/foreign/cancel", headers=auth_headers(user))
    assert response.status_code == 404


def test_cancel_capability_matches_the_live_queue_and_requester(monkeypatch):
    app, user, other = setup_app()
    queue = TaskQueue(max_workers=1)
    queue.set_db(app.db)
    monkeypatch.setattr(api, "task_queue", queue)
    started, release = Event(), Event()

    def blocker(progress_callback=None):
        started.set()
        assert release.wait(10)

    try:
        running = queue.submit("refresh", blocker, owner_id=str(user["_id"]))
        assert started.wait(5)
        pending = queue.submit("refresh", lambda progress_callback=None: None, owner_id=str(user["_id"]))
        insert_task(app.db, "orphan", user, "refresh")
        client = app.test_client()
        own = auth_headers(user)
        assert client.get(f"/api/tasks/{pending}", headers=own).get_json()["data"]["can_cancel"] is True
        assert client.get(f"/api/tasks/{pending}", headers=auth_headers(other)).get_json()["data"]["can_cancel"] is False
        assert client.get(f"/api/tasks/{running}", headers=own).get_json()["data"]["can_cancel"] is False
        assert client.get("/api/tasks/orphan", headers=own).get_json()["data"]["can_cancel"] is False
        assert client.post(f"/api/tasks/{pending}/cancel", headers=own).status_code == 200
        assert client.get(f"/api/tasks/{pending}", headers=own).get_json()["data"]["status"] == "cancelled"
    finally:
        release.set()
        queue.shutdown()
