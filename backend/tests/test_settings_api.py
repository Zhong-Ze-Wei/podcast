from app.api.settings import settings_bp
from tests.auth_helpers import add_user, auth_headers, make_auth_app


def test_llm_settings_are_scoped_per_user():
    app = make_auth_app((settings_bp, "/api/settings"))
    user1 = add_user(app.db, "user1@example.com")
    user2 = add_user(app.db, "user2@example.com")
    client = app.test_client()

    save = client.put(
        "/api/settings/llm",
        json={
            "active_index": 0,
            "configs": [{
                "name": "User1 LLM",
                "base_url": "https://api.example.com/v1",
                "api_key": "secret",
                "model": "model-a",
            }],
        },
        headers=auth_headers(user1),
    )
    assert save.status_code == 200

    own = client.get("/api/settings/llm", headers=auth_headers(user1))
    other = client.get("/api/settings/llm", headers=auth_headers(user2))

    assert own.status_code == 200
    assert own.get_json()["configs"][0]["name"] == "User1 LLM"
    assert own.get_json()["configs"][0]["api_key"] == ""
    assert own.get_json()["configs"][0]["has_api_key"] is True
    assert other.status_code == 200
    assert other.get_json()["configs"][0]["name"] != "User1 LLM"
