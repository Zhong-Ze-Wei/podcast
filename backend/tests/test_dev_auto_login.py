"""本地回环请求按 AUTH_DEV_AUTO_LOGIN 直接以指定管理员进入，其余来源照常验证。"""
from app.api import auth as auth_api
from tests.auth_helpers import add_user, auth_headers, make_auth_app


def make_client(auto_login=None):
    app = make_auth_app((auth_api.auth_bp, "/api/auth"))
    if auto_login is not None:
        app.config["AUTH_DEV_AUTO_LOGIN"] = auto_login
    return app, app.test_client()


def test_loopback_without_token_enters_as_configured_admin():
    app, http = make_client(auto_login="zz")
    admin = add_user(app.db, "zz", role="admin")
    response = http.get("/api/auth/me")
    assert response.status_code == 200
    user = response.get_json()["data"]["user"]
    assert user["email"] == "zz" and user["role"] == "admin"
    assert user["id"] == str(admin["_id"])


def test_non_loopback_source_still_requires_login():
    app, http = make_client(auto_login="zz")
    add_user(app.db, "zz", role="admin")
    response = http.get("/api/auth/me", environ_overrides={"REMOTE_ADDR": "192.168.31.50"})
    assert response.status_code == 401


def test_flag_off_keeps_normal_auth():
    app, http = make_client()
    add_user(app.db, "zz", role="admin")
    assert http.get("/api/auth/me").status_code == 401


def test_flag_only_accepts_active_admin_accounts():
    app, http = make_client(auto_login="zz")
    add_user(app.db, "zz", role="user")
    assert http.get("/api/auth/me").status_code == 401

    app.db.users._data[0]["role"] = "admin"
    app.db.users._data[0]["status"] = "pending"
    assert http.get("/api/auth/me").status_code == 401


def test_flag_refers_to_missing_account():
    app, http = make_client(auto_login="nobody")
    add_user(app.db, "zz", role="admin")
    assert http.get("/api/auth/me").status_code == 401


def test_bearer_token_wins_over_dev_auto_login():
    app, http = make_client(auto_login="zz")
    add_user(app.db, "zz", role="admin")
    other = add_user(app.db, "member@example.com", role="user")
    response = http.get("/api/auth/me", headers=auth_headers(other))
    assert response.status_code == 200
    assert response.get_json()["data"]["user"]["email"] == "member@example.com"
