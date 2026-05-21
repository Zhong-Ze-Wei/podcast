from flask import Flask

from app.api.admin import admin_bp
from app.api.auth import auth_bp
from tests.conftest import MockDB


def make_app():
    app = Flask(__name__)
    app.config.update(
        AUTH_REQUIRED=True,
        JWT_SECRET="test-secret",
        JWT_EXPIRES_HOURS=1,
        DEFAULT_OWNER_ID="local-default-user",
        DEFAULT_OWNER_EMAIL="local@podcast.local",
    )
    app.db = MockDB()
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    return app


def test_register_first_user_as_admin_and_me_returns_user():
    app = make_app()
    client = app.test_client()

    response = client.post("/api/auth/register", json={
        "email": "Admin@Example.com",
        "password": "password123",
    })

    assert response.status_code == 201
    body = response.get_json()["data"]
    assert body["user"]["email"] == "admin@example.com"
    assert body["user"]["role"] == "admin"
    assert body["token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200
    assert me.get_json()["data"]["user"]["email"] == "admin@example.com"


def test_login_rejects_wrong_password_and_disabled_user():
    app = make_app()
    client = app.test_client()
    client.post("/api/auth/register", json={
        "email": "admin@example.com",
        "password": "password123",
    })

    bad = client.post("/api/auth/login", json={
        "email": "admin@example.com",
        "password": "wrong-password",
    })
    assert bad.status_code == 401

    user = app.db.users.find_one({"email": "admin@example.com"})
    app.db.users.update_one({"_id": user["_id"]}, {"$set": {"status": "disabled"}})
    disabled = client.post("/api/auth/login", json={
        "email": "admin@example.com",
        "password": "password123",
    })
    assert disabled.status_code == 403


def test_admin_routes_require_admin_role():
    app = make_app()
    client = app.test_client()

    admin = client.post("/api/auth/register", json={
        "email": "admin@example.com",
        "password": "password123",
    }).get_json()["data"]
    user = client.post("/api/auth/register", json={
        "email": "user@example.com",
        "password": "password123",
    }).get_json()["data"]

    forbidden = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {user['token']}"},
    )
    assert forbidden.status_code == 403

    allowed = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert allowed.status_code == 200
    assert len(allowed.get_json()["data"]) == 2
