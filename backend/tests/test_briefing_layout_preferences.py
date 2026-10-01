"""阅读版式属于账号偏好，不写全局设置，也不改变其他简报选项。"""
from copy import deepcopy

import pytest

from tests.auth_helpers import add_user, auth_headers
from tests.test_briefing_scope import client


def test_layout_default_is_read_only_and_saved_per_account(client):
    app, http, headers, service = client
    before = deepcopy(app.db.users._data)
    initial = http.get("/api/briefing-reports/preferences", headers=headers)
    assert initial.get_json()["data"]["layout"] == "paper"
    assert app.db.users._data == before
    for layout in ("space", "large", "list", "columns", "paper", "newspaper", "notes"):
        changed = http.put("/api/briefing-reports/preferences", headers=headers, json={"layout": layout})
        assert changed.status_code == 200
        assert changed.get_json()["data"]["layout"] == layout
    assert app.db.users.find_one({"_id": app.db.users._data[0]["_id"]})["briefing_layout"] == "notes"
    other = add_user(app.db, "other-layout@example.com")
    assert http.get("/api/briefing-reports/preferences", headers=auth_headers(other)).get_json()["data"]["layout"] == "paper"
    assert app.db.settings.count_documents({}) == 0


def test_layout_interests_and_automatic_period_updates_preserve_each_other(client):
    app, http, headers, service = client
    tags = [{"label": "科学", "enabled": True}]
    changed = http.put("/api/briefing-reports/preferences", headers=headers, json={"layout": "newspaper", "interests": tags, "auto_period": "month"})
    assert changed.status_code == 200
    enabled_at = changed.get_json()["data"]["auto_enabled_at"]
    layout_only = http.put("/api/briefing-reports/preferences", headers=headers, json={"layout": "large"}).get_json()["data"]
    assert layout_only["interests"] == tags and layout_only["auto_period"] == "month"
    assert layout_only["auto_enabled_at"] == enabled_at
    other_tags = [{"label": "历史", "enabled": True}]
    edited = http.put("/api/briefing-reports/preferences", headers=headers, json={"interests": other_tags}).get_json()["data"]
    assert edited["layout"] == "large" and edited["auto_period"] == "month"


@pytest.mark.parametrize("layout", ["compact", None, [], {}, 1])
def test_invalid_layout_does_not_write_preferences(client, layout):
    app, http, headers, service = client
    before = deepcopy(app.db.users._data)
    response = http.put("/api/briefing-reports/preferences", headers=headers, json={"layout": layout})
    assert response.status_code == 400
    assert app.db.users._data == before


def test_viewer_retains_existing_personal_preferences_access(client):
    app, http, headers, service = client
    viewer = add_user(app.db, "viewer-layout@example.com", role="viewer")
    response = http.put("/api/briefing-reports/preferences", headers=auth_headers(viewer), json={"layout": "list"})
    assert response.status_code == 200 and response.get_json()["data"]["layout"] == "list"
