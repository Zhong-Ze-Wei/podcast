"""收藏保持服务器验证的快照，旧 ID 迁移不得猜测报告来源。"""
from copy import deepcopy

import pytest

from tests.auth_helpers import add_user, auth_headers
from tests.conftest import MockCollection
from tests.test_briefing_persistence import client, report, compound_sort_mock


@pytest.fixture(autouse=True)
def set_on_insert_mock(monkeypatch):
    original = MockCollection.update_one
    def update(collection, query, values, **kwargs):
        values = deepcopy(values)
        if "$setOnInsert" in values and collection.find_one(query) is None:
            values["$set"] = {**values["$setOnInsert"], **values.get("$set", {})}
        return original(collection, query, values, **kwargs)
    monkeypatch.setattr(MockCollection, "update_one", update)


def test_favorite_keeps_original_snapshot_after_regeneration_and_file_removal(client):
    app, http, headers, store = client
    previous = report("a", store.owner_id)
    store.publish(previous, "content-modes-v1/reports")
    url = "/api/briefing-reports/favorites/core-stable"
    created = http.put(url, headers=headers, json={"report_id": previous["id"], "item": {"text": "伪造正文"}})
    assert created.status_code == 200
    favorite = created.get_json()["data"]
    assert favorite["item"]["text"] == "原始判断"
    assert favorite["report"]["sources"] == previous["sources"]
    regenerated = report("b", store.owner_id)
    regenerated["sections"][0]["items"][0]["text"] = "重新生成的判断"
    store.publish(regenerated, "content-modes-v1/reports")
    repeated = http.put(url, headers=headers, json={"report_id": regenerated["id"]})
    assert repeated.get_json()["data"] == favorite
    (store.root / "content-modes-v1/reports" / (previous["id"] + ".json")).unlink()
    listed = http.get("/api/briefing-reports/favorites", headers=headers).get_json()
    assert listed["pagination"]["total"] == 1 and listed["data"] == [favorite]
    assert http.delete(url, headers=headers).get_json()["data"]["deleted"] is True
    assert http.delete(url, headers=headers).get_json()["data"]["deleted"] is False


def test_favorites_are_personal_and_cannot_snapshot_another_users_report(client):
    app, http, headers, store = client
    private = report("a", store.owner_id)
    store.publish(private, "content-modes-v1/reports")
    other = add_user(app.db, "other-favorites@example.com")
    other_headers = auth_headers(other)
    url = "/api/briefing-reports/favorites/core-stable"
    assert http.put(url, headers=other_headers, json={"report_id": private["id"]}).status_code == 404
    assert http.put(url, headers=headers, json={"report_id": private["id"]}).status_code == 200
    assert http.get("/api/briefing-reports/favorites", headers=other_headers).get_json()["pagination"]["total"] == 0
    assert http.delete(url, headers=other_headers).get_json()["data"]["deleted"] is False
    assert http.get("/api/briefing-reports/favorites", headers=headers).get_json()["pagination"]["total"] == 1
    migrated = http.post("/api/briefing-reports/favorites/import", headers=other_headers, json={"ids": ["core-stable"]})
    assert migrated.get_json()["data"] == {"imported": [], "unresolved": ["core-stable"]}


def test_import_is_idempotent_preserves_unresolved_and_rejects_client_content(client):
    app, http, headers, store = client
    value = report("a", store.owner_id)
    store.publish(value, "content-modes-v1/reports")
    body = {"ids": ["core-stable", "missing", "core-stable"], "items": [{"id": "missing", "text": "伪造正文"}]}
    url = "/api/briefing-reports/favorites/import"
    for _ in range(2):
        result = http.post(url, headers=headers, json=body)
        assert result.status_code == 200
        assert result.get_json()["data"] == {"imported": ["core-stable"], "unresolved": ["missing"]}
    assert app.db.briefing_favorites.count_documents({}) == 1


def test_import_does_not_guess_when_legacy_id_points_to_different_sources(client):
    app, http, headers, store = client
    for identifier, episode in (("a", "first-episode"), ("b", "second-episode")):
        value = report(identifier, store.owner_id)
        value["sections"][0]["items"][0]["id"] = "S01-C001-quote-01"
        value["sources"][0]["episode_id"] = episode
        store.publish(value, "reading-v1/editions")
    response = http.post("/api/briefing-reports/favorites/import", headers=headers, json={"ids": ["S01-C001-quote-01"]})
    assert response.get_json()["data"] == {"imported": [], "unresolved": ["S01-C001-quote-01"]}
    assert app.db.briefing_favorites.count_documents({}) == 0


def test_import_can_select_newest_identical_content_without_duplicates(client):
    app, http, headers, store = client
    for identifier, timestamp in (("a", "2026-10-01T00:00:00+00:00"), ("b", "2026-10-02T00:00:00+00:00")):
        store.publish(report(identifier, store.owner_id, timestamp), "content-modes-v1/reports")
    result = http.post("/api/briefing-reports/favorites/import", headers=headers, json={"ids": ["core-stable"]})
    assert result.get_json()["data"]["imported"] == ["core-stable"]
    assert http.get("/api/briefing-reports/favorites", headers=headers).get_json()["data"][0]["report_id"] == "b" * 32


def test_favorites_default_to_cross_period_and_filter_before_pagination(client):
    app, http, headers, store = client
    for identifier, start, item_id in (("a", "2026-09-01", "september"), ("b", "2026-10-01", "october")):
        value = report(identifier, store.owner_id)
        value["period"]["start"] = start
        value["sections"][0]["items"][0]["id"] = item_id
        store.publish(value, "content-modes-v1/reports")
        assert http.put("/api/briefing-reports/favorites/" + item_id, headers=headers, json={"report_id": value["id"]}).status_code == 200
    listed = http.get("/api/briefing-reports/favorites?per_page=1", headers=headers).get_json()
    assert listed["pagination"]["total"] == 2 and len(listed["data"]) == 1
    filtered = http.get("/api/briefing-reports/favorites?period_type=month&period_start=2026-09-01&mode=core&per_page=1", headers=headers).get_json()
    assert filtered["pagination"]["total"] == 1 and filtered["data"][0]["item_id"] == "september"


@pytest.mark.parametrize("body", [None, {"ids": "core-stable"}, {"ids": [None]}, {"ids": ["../escape"]}])
def test_invalid_import_never_writes_favorites(client, body):
    app, http, headers, store = client
    assert http.post("/api/briefing-reports/favorites/import", headers=headers, json=body).status_code == 400
    assert app.db.briefing_favorites.count_documents({}) == 0
