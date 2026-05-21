from datetime import datetime

from app.api.tasks import _task_status_query, tasks_bp
from tests.auth_helpers import add_user, auth_headers, make_auth_app


def test_task_status_query_supports_comma_separated_statuses():
    assert _task_status_query("pending,processing") == {
        "$in": ["pending", "processing"]
    }


def test_task_status_query_keeps_single_status_as_string():
    assert _task_status_query("failed") == "failed"


def test_task_status_query_ignores_empty_status_segments():
    assert _task_status_query(" , ,, ") is None


def add_task(db, owner_id, task_id, status="pending"):
    doc = {
        "task_id": task_id,
        "task_type": "transcribe",
        "owner_id": owner_id,
        "episode_id": None,
        "feed_id": None,
        "status": status,
        "progress": 0,
        "result": None,
        "error_message": None,
        "created_at": datetime.utcnow(),
        "started_at": None,
        "completed_at": None,
    }
    db.tasks.insert_one(doc)
    return doc


def make_tasks_app():
    return make_auth_app((tasks_bp, "/api/tasks"))


def test_task_list_is_filtered_by_owner():
    app = make_tasks_app()
    db = app.db
    user1 = add_user(db, "user1@example.com")
    user2 = add_user(db, "user2@example.com")
    add_task(db, str(user1["_id"]), "user1-task")
    add_task(db, str(user2["_id"]), "user2-task")

    response = app.test_client().get("/api/tasks", headers=auth_headers(user1))

    assert response.status_code == 200
    payload = response.get_json()
    assert [item["id"] for item in payload["data"]] == ["user1-task"]


def test_task_detail_hides_other_owner_task():
    app = make_tasks_app()
    db = app.db
    user1 = add_user(db, "user1@example.com")
    user2 = add_user(db, "user2@example.com")
    add_task(db, str(user2["_id"]), "user2-task")

    response = app.test_client().get("/api/tasks/user2-task", headers=auth_headers(user1))

    assert response.status_code == 404
    assert response.get_json()["error_code"] == "TASK_NOT_FOUND"


def test_task_cancel_hides_other_owner_task():
    app = make_tasks_app()
    db = app.db
    user1 = add_user(db, "user1@example.com")
    user2 = add_user(db, "user2@example.com")
    add_task(db, str(user2["_id"]), "user2-task")

    response = app.test_client().post(
        "/api/tasks/user2-task/cancel",
        headers=auth_headers(user1),
    )

    assert response.status_code == 404
    assert response.get_json()["error_code"] == "TASK_NOT_FOUND"
