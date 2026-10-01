"""报告发布、历史索引和用户边界不能依赖任务记录的生命周期。"""
import pytest
from pymongo.errors import PyMongoError

from app.api import briefing_reports as api
from app.services import briefing_store as store_module
from app.services.briefing_lab_service import write_json
from app.services.briefing_store import BriefingStore
from tests.auth_helpers import add_user, auth_headers, make_auth_app
from tests.conftest import MockDB, MockCursor


@pytest.fixture(autouse=True)
def compound_sort_mock(monkeypatch):
    # 生产查询使用 Mongo 复合排序，现有轻量 mock 只实现了单字段排序。
    original = MockCursor.sort
    def sort(cursor, keys, direction=None):
        if isinstance(keys, list):
            for key, order in reversed(keys):
                cursor._data.sort(key=lambda row: row.get(key, ""), reverse=order == -1)
            return cursor
        return original(cursor, keys, direction)
    monkeypatch.setattr(MockCursor, "sort", sort)


def report(identifier="a", owner="owner", generated_at="2026-10-01T00:00:00+00:00"):
    return {"id": identifier * 32, "owner_id": owner, "generated_at": generated_at,
            "mode": "core", "variant": "overview", "title": "核心提要", "corpus_id": "corpus",
            "period": {"type": "month", "start": "2026-09-01", "end": "2026-10-01"},
            "sources": [{"id": "S01", "episode_id": "episode", "title": "节目"}],
            "sections": [{"id": "core", "items": [{"id": "core-stable", "text": "原始判断", "source_id": "S01", "start": 12}]}]}


def test_publish_is_immutable_and_indexes_only_complete_report(tmp_path):
    db = MockDB()
    store = BriefingStore(tmp_path, db, "owner")
    value = report()
    store.publish(value, "content-modes-v1/reports")
    assert store.report(value["id"]) == value
    indexed = db.briefing_reports.find_one({"report_id": value["id"]})
    assert indexed["owner_id"] == "owner"
    assert indexed["period"] == value["period"]
    assert "sections" not in indexed
    changed = {**value, "title": "不得覆盖"}
    with pytest.raises(ValueError, match="不可覆盖"):
        store.publish(changed, "content-modes-v1/reports")
    assert store.report(value["id"]) == value


@pytest.mark.parametrize("failure", ["file", "index"])
def test_failed_publication_preserves_previous_report(tmp_path, monkeypatch, failure):
    db = MockDB()
    store = BriefingStore(tmp_path, db, "owner")
    previous = report()
    store.publish(previous, "content-modes-v1/reports")
    current = report("b", generated_at="2026-10-02T00:00:00+00:00")
    if failure == "file":
        def fail(*args, **kwargs):
            raise OSError("disk full")
        monkeypatch.setattr(store_module, "write_json", fail)
    else:
        def fail(*args, **kwargs):
            raise PyMongoError("index unavailable")
        monkeypatch.setattr(db.briefing_reports, "update_one", fail)
    with pytest.raises((OSError, PyMongoError)):
        store.publish(current, "content-modes-v1/reports")
    assert store.report(previous["id"]) == previous
    assert store.report(current["id"]) is None
    assert list(store.reports("content-modes-v1/reports")) == [previous]


def test_legacy_rebuild_is_idempotent_and_does_not_assign_shared_owner(tmp_path):
    db = MockDB()
    store = BriefingStore(tmp_path, db, "owner")
    for value in (report(), report("b", owner=None), report("c", owner="other")):
        write_json(tmp_path / "content-modes-v1/reports" / (value["id"] + ".json"), value)
    store.rebuild_index()
    store.rebuild_index()
    assert db.briefing_reports.count_documents({}) == 3
    assert db.briefing_reports.find_one({"report_id": "b" * 32})["owner_id"] is None
    assert store.report("b" * 32)["owner_id"] is None
    assert store.report("c" * 32) is None
    assert store.report("../outside") is None


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = make_auth_app((api.briefing_reports_bp, "/api/briefing-reports"))
    user = add_user(app.db, "persistence@example.com")
    owner = str(user["_id"])
    store = BriefingStore(tmp_path, app.db, owner)
    monkeypatch.setattr(api, "_report_store", lambda current_owner: BriefingStore(tmp_path, app.db, current_owner))
    return app, app.test_client(), auth_headers(user), store


def test_history_is_paginated_authorized_and_survives_task_cleanup(client):
    app, http, headers, store = client
    values = [report("a", store.owner_id), report("b", None, "2026-10-02T00:00:00+00:00"), report("c", "other")]
    for value in values:
        store.publish(value, "content-modes-v1/reports")
    app.db.tasks.delete_many({})
    response = http.get("/api/briefing-reports/reports?page=1&per_page=1", headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["pagination"]["total"] == 2 and payload["pagination"]["has_next"]
    assert payload["data"][0]["id"] == values[1]["id"]
    assert "sections" not in payload["data"][0]
    second = http.get("/api/briefing-reports/reports?page=2&per_page=1", headers=headers).get_json()
    assert second["data"][0]["id"] == values[0]["id"]
    own = http.get("/api/briefing-reports/reports/" + values[0]["id"], headers=headers)
    assert own.get_json()["data"] == values[0]
    assert http.get("/api/briefing-reports/reports/" + values[2]["id"], headers=headers).status_code == 404
    assert http.get("/api/briefing-reports/reports", headers={}).status_code == 401
    filtered = http.get("/api/briefing-reports/reports?period_type=week", headers=headers).get_json()
    assert filtered["pagination"]["total"] == 0


def test_uncertain_index_write_is_reconciled_without_publishing_failed_report(tmp_path, monkeypatch):
    db = MockDB()
    store = BriefingStore(tmp_path, db, "owner")
    store.publish(report(), "reports")
    original = db.briefing_reports.update_one
    def uncertain(*args, **kwargs):
        original(*args, **kwargs)
        raise PyMongoError("write acknowledgement unavailable")
    monkeypatch.setattr(db.briefing_reports, "update_one", uncertain)
    with pytest.raises(PyMongoError):
        store.publish(report("b"), "reports")
    monkeypatch.setattr(db.briefing_reports, "update_one", original)
    rows, total = store.history(1, 20)
    assert total == 1 and rows[0]["id"] == "a" * 32
