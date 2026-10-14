"""viewer 可读简报与自己的收藏，但不可写个人收藏状态。"""
import pytest

from tests.auth_helpers import add_user, auth_headers
from tests.test_briefing_persistence import client, compound_sort_mock


@pytest.mark.parametrize("method,path,body", [
    ("put", "/favorites/viewer-item", {"report_id": "a" * 32}),
    ("delete", "/favorites/viewer-item", None),
    ("post", "/favorites/import", {"ids": ["viewer-item"]}),
])
def test_viewer_can_read_but_cannot_modify_favorites(client, method, path, body):
    app, http, headers, store = client
    viewer = add_user(app.db, "readonly-favorites@example.com", role="viewer")
    viewer_headers = auth_headers(viewer)
    stored = {"owner_id": str(viewer["_id"]), "item_id": "viewer-item", "report_id": "a" * 32,
              "item": {"id": "viewer-item", "text": "已有收藏"}, "report": {}, "created_at": "2026-10-01T00:00:00+00:00"}
    app.db.briefing_favorites.insert_one(stored)
    readable = http.get("/api/briefing-reports/favorites", headers=viewer_headers)
    assert readable.status_code == 200
    assert readable.get_json()["pagination"]["total"] == 1
    response = getattr(http, method)("/api/briefing-reports" + path, headers=viewer_headers, json=body)
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "ROLE_DENIED"
    assert app.db.briefing_favorites.find_one({"item_id": "viewer-item"}) == stored
