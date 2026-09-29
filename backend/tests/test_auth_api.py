from flask import Flask

from app.api.admin import admin_bp
from app.api.auth import auth_bp
from app.models.user import User
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


def test_login_accepts_username_alias_for_local_admin():
    app = make_app()
    client = app.test_client()
    app.db.users.insert_one(User.create("zz", "123456", role="admin"))

    response = client.post("/api/auth/login", json={
        "username": "zz",
        "password": "123456",
    })

    assert response.status_code == 200
    body = response.get_json()["data"]
    assert body["user"]["email"] == "zz"
    assert body["user"]["role"] == "admin"
    assert body["token"]


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

    # 注册审批制：第二个注册用户为 pending，token 无法通过 admin 校验
    forbidden = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {user['token']}"},
    )
    # pending 用户 token 视同未认证
    assert forbidden.status_code == 401

    allowed = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert allowed.status_code == 200
    assert len(allowed.get_json()["data"]) == 2


def test_registration_requires_admin_approval():
    app = make_app()
    client = app.test_client()

    # 首个用户 = admin（直接可用）
    admin = client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"}).get_json()["data"]
    # 第二个用户 = pending
    client.post("/api/auth/register", json={"email": "newbie@example.com", "password": "password123"})

    pending = client.post("/api/auth/login", json={"email": "newbie@example.com", "password": "password123"})
    assert pending.status_code == 403
    assert pending.get_json()["error_code"] == "ACCOUNT_PENDING"

    # admin 审批
    headers = {"Authorization": f"Bearer {admin['token']}"}
    users = client.get("/api/admin/users", headers=headers).get_json()["data"]
    newbie = next(u for u in users if u["email"] == "newbie@example.com")
    assert newbie["status"] == "pending"

    approved = client.patch(f"/api/admin/users/{newbie['id']}", json={"status": "active"}, headers=headers)
    assert approved.status_code == 200

    ok = client.post("/api/auth/login", json={"email": "newbie@example.com", "password": "password123"})
    assert ok.status_code == 200
