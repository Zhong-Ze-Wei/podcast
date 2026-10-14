from datetime import datetime

from bson import ObjectId
import pytest

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
    assert [item["id"] for item in payload["data"]] == ["user2-task", "user1-task"]  # 共享库：全部可见


def test_task_detail_is_shared():
    app = make_tasks_app()
    db = app.db
    user1 = add_user(db, "user1@example.com")
    user2 = add_user(db, "user2@example.com")
    add_task(db, str(user2["_id"]), "user2-task")

    response = app.test_client().get("/api/tasks/user2-task", headers=auth_headers(user1))

    # 共享库：他人任务详情可见
    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_task_cancel_is_restricted_to_owner():
    app = make_tasks_app()
    db = app.db
    user1 = add_user(db, "user1@example.com")
    user2 = add_user(db, "user2@example.com")
    add_task(db, str(user2["_id"]), "user2-task")

    response = app.test_client().post(
        "/api/tasks/user2-task/cancel",
        headers=auth_headers(user1),
    )

    # 取消他人任务被拒（共享库中任务取消仍归属操作者）
    assert response.status_code == 404


@pytest.mark.parametrize("status", ["processing", "completed"])
@pytest.mark.parametrize("has_episode_id", [False, True])
def test_single_analysis_tasks_resolve_episode_title_and_target_in_list_and_detail(status, has_episode_id):
    app = make_tasks_app()
    user = add_user(app.db, "reader@example.com")
    feed = {"title": "WhynotTV"}
    app.db.feeds.insert_one(feed)
    episode = {"title": "Danfei Xu：机器人与具身智能", "feed_id": feed["_id"], "status": "transcribed"}
    app.db.episodes.insert_one(episode)
    episode_id = str(episode["_id"])
    doc = add_task(app.db, str(user["_id"]), "reading-task", status)
    app.db.tasks.update_one({"_id": doc["_id"]}, {"$set": {
        "task_type": "briefing-report", "episode_id": episode_id if has_episode_id else None,
        "report_context": {"kind": "reading", "source_id": "ep" + episode_id},
    }})
    http = app.test_client()
    headers = auth_headers(user)
    for task in [http.get("/api/tasks", headers=headers).get_json()["data"][0],
                 http.get("/api/tasks/reading-task", headers=headers).get_json()["data"]]:
        assert task["episode_title"] == episode["title"]
        assert task["feed_title"] == feed["title"]
        assert task["episode_id"] == task["target_id"] == episode_id
        assert task["target_type"] == "episode"
        assert task["target_exists"] is True


def test_deleted_single_analysis_preserves_title_but_does_not_claim_target_exists():
    app = make_tasks_app()
    user = add_user(app.db, "reader@example.com")
    doc = add_task(app.db, str(user["_id"]), "deleted-task")
    app.db.tasks.update_one({"_id": doc["_id"]}, {"$set": {
        "task_type": "briefing-report", "episode_id": str(ObjectId()),
        "report_context": {"kind": "reading", "source_id": "S01", "source_title": "原来的这一期", "feed_title": "原来的播客"},
    }})
    task = app.test_client().get("/api/tasks/deleted-task", headers=auth_headers(user)).get_json()["data"]
    assert task["episode_title"] == "原来的这一期"
    assert task["feed_title"] == "原来的播客"
    assert task["target_exists"] is False


def test_standalone_material_does_not_invent_an_episode_target():
    app = make_tasks_app()
    user = add_user(app.db, "reader@example.com")
    doc = add_task(app.db, str(user["_id"]), "material-task")
    app.db.tasks.update_one({"_id": doc["_id"]}, {"$set": {
        "task_type": "briefing-report",
        "report_context": {"kind": "reading", "source_id": "S01", "source_title": "独立文稿"},
    }})
    task = app.test_client().get("/api/tasks/material-task", headers=auth_headers(user)).get_json()["data"]
    assert task["episode_title"] == "独立文稿"
    assert task["episode_id"] is None
    assert task["target_id"] is None
