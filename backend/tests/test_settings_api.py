from app.api.settings import settings_bp
from app.models.setting import SettingModel
from tests.auth_helpers import add_user, auth_headers, make_auth_app


def test_llm_settings_are_scoped_per_user():
    app = make_auth_app((settings_bp, "/api/settings"))
    user1 = add_user(app.db, "user1@example.com", role="admin")
    user2 = add_user(app.db, "user2@example.com", role="admin")
    client = app.test_client()

    save = client.put(
        "/api/settings/llm",
        json={
            "active_index": 0,
            "configs": [{
                "name": "User1 LLM",
                "base_url": "https://api.example.com/v1",
                "api_key": "sk-test-abcdefghijklmnop",
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
    assert own.get_json()["configs"][0]["api_key"] != "sk-test-abcdefghijklmnop"
    assert "..." in own.get_json()["configs"][0]["api_key"]
    assert own.get_json()["configs"][0]["has_api_key"] is True
    assert other.status_code == 200
    # 全局配置语义：user2 看到同一份（Key 掩码）
    assert other.get_json()["configs"][0]["name"] == "User1 LLM"


def test_default_llm_config_uses_modelscope_without_committing_api_key(monkeypatch):
    for key in [
        "LLM_DEFAULT_ID",
        "LLM_DEFAULT_NAME",
        "LLM_PROVIDER",
        "LLM_API_FORMAT",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_SUPPORTS_STREAMING",
        "LLM_ENABLED",
    ]:
        monkeypatch.delenv(key, raising=False)
    config = SettingModel.get_default_llm_config()

    assert config["id"] == "modelscope-default"
    assert config["provider"] == "modelscope"
    assert config["api_format"] == "openai_compatible"
    assert config["name"] == "ModelScope"
    assert config["base_url"] == "https://api-inference.modelscope.cn/v1"
    assert config["model"] == "deepseek-ai/DeepSeek-V4-Flash"
    assert config["api_key"] == ""
    assert config["supports_streaming"] is True
    assert config["enabled"] is True


def test_llm_save_adds_ids_and_persists_task_routes_only_for_available_configs():
    app = make_auth_app((settings_bp, "/api/settings"))
    user = add_user(app.db, "user@example.com", role="admin")
    client = app.test_client()

    response = client.put(
        "/api/settings/llm",
        json={
            "active_index": 0,
            "configs": [{
                "name": "ModelScope",
                "provider": "modelscope",
                "api_format": "openai_compatible",
                "base_url": "https://api-inference.modelscope.cn/v1",
                "api_key": "sk-test-abcdefghijklmnop",
                "model": "deepseek-ai/DeepSeek-V4-Flash",
                "enabled": True,
            }],
            "task_routes": {
                "summary": "modelscope",
                "transcript_normalize": "missing-provider",
                "briefing": "default",
            },
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 200

    saved = client.get("/api/settings/llm", headers=auth_headers(user))
    payload = saved.get_json()
    assert payload["configs"][0]["id"] == "modelscope"
    assert payload["configs"][0]["api_key"] != "sk-test-abcdefghijklmnop"
    assert "..." in payload["configs"][0]["api_key"]
    assert payload["configs"][0]["has_api_key"] is True
    assert payload["task_routes"] == {
        "summary": "default",
        "transcript_normalize": "default",
        "briefing": "default",
    }


def test_llm_settings_split_providers_models_and_routes_without_returning_keys():
    app = make_auth_app((settings_bp, "/api/settings"))
    user = add_user(app.db, "user@example.com", role="admin")
    client = app.test_client()

    response = client.put(
        "/api/settings/llm",
        json={
            "providers": [{
                "id": "modelscope",
                "name": "ModelScope",
                "provider": "modelscope",
                "api_format": "openai_compatible",
                "base_url": "https://api-inference.modelscope.cn/v1",
                "api_key": "sk-test-abcdefghijklmnop",
                "enabled": True,
            }],
            "models": [
                {
                    "id": "modelscope-deepseek-v4-flash",
                    "provider_id": "modelscope",
                    "name": "DeepSeek V4 Flash",
                    "model": "deepseek-ai/DeepSeek-V4-Flash",
                    "enabled": True,
                    "supports_streaming": True,
                },
                {
                    "id": "bad-model",
                    "provider_id": "missing",
                    "name": "Bad",
                    "model": "bad",
                    "enabled": True,
                },
            ],
            "default_model_id": "modelscope-deepseek-v4-flash",
            "task_routes": {
                "summary": "modelscope-deepseek-v4-flash",
                "transcript_normalize": "bad-model",
                "briefing": "default",
            },
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 200

    payload = client.get("/api/settings/llm", headers=auth_headers(user)).get_json()
    provider_resp = payload["providers"][0]
    assert provider_resp["id"] == "modelscope"
    assert provider_resp["has_api_key"] is True
    assert provider_resp["api_key"] != "sk-test-abcdefghijklmnop"
    assert "..." in provider_resp["api_key"]
    assert payload["models"] == [{
        "id": "modelscope-deepseek-v4-flash",
        "provider_id": "modelscope",
        "name": "DeepSeek V4 Flash",
        "model": "deepseek-ai/DeepSeek-V4-Flash",
        "enabled": True,
        "supports_streaming": True,
    }]
    assert payload["default_model_id"] == "modelscope-deepseek-v4-flash"
    assert payload["task_routes"] == {
        "summary": "modelscope-deepseek-v4-flash",
        "transcript_normalize": "default",
        "briefing": "default",
    }


def test_active_llm_config_is_composed_from_default_provider_and_model():
    app = make_auth_app((settings_bp, "/api/settings"))
    model = SettingModel(app.db, owner_id="owner")
    model.save_llm_settings(
        providers=[{
            "id": "modelscope",
            "name": "ModelScope",
            "provider": "modelscope",
            "api_format": "openai_compatible",
            "base_url": "https://api-inference.modelscope.cn/v1",
            "api_key": "secret",
            "enabled": True,
        }],
        models=[{
            "id": "flash",
            "provider_id": "modelscope",
            "name": "Flash",
            "model": "deepseek-ai/DeepSeek-V4-Flash",
            "enabled": True,
            "supports_streaming": True,
        }],
        default_model_id="flash",
        task_routes={},
    )

    active = model.get_active_llm_config()

    assert active["id"] == "flash"
    assert active["provider_id"] == "modelscope"
    assert active["base_url"] == "https://api-inference.modelscope.cn/v1"
    assert active["api_key"] == "secret"
    assert active["model"] == "deepseek-ai/DeepSeek-V4-Flash"
    assert active["api_format"] == "openai_compatible"


def test_llm_settings_preserve_disabled_provider_models_but_exclude_from_routes():
    app = make_auth_app((settings_bp, "/api/settings"))
    user = add_user(app.db, "user@example.com", role="admin")
    client = app.test_client()

    response = client.put(
        "/api/settings/llm",
        json={
            "providers": [
                {
                    "id": "modelscope",
                    "name": "ModelScope",
                    "provider": "modelscope",
                    "api_format": "openai_compatible",
                    "base_url": "https://api-inference.modelscope.cn/v1",
                    "api_key": "sk-test-abcdefghijklmnop",
                    "enabled": True,
                },
                {
                    "id": "deepseek",
                    "name": "DeepSeek",
                    "provider": "deepseek",
                    "api_format": "openai_compatible",
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "sk-test-deepseek-key-xyz",
                    "enabled": False,
                },
            ],
            "models": [
                {
                    "id": "flash",
                    "provider_id": "modelscope",
                    "name": "Flash",
                    "model": "deepseek-ai/DeepSeek-V4-Flash",
                    "enabled": True,
                    "supports_streaming": True,
                },
                {
                    "id": "deepseek-chat",
                    "provider_id": "deepseek",
                    "name": "DeepSeek Chat",
                    "model": "deepseek-chat",
                    "enabled": True,
                    "supports_streaming": True,
                },
            ],
            "default_model_id": "deepseek-chat",
            "task_routes": {
                "summary": "deepseek-chat",
                "transcript_normalize": "flash",
                "briefing": "default",
            },
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 200

    payload = client.get("/api/settings/llm", headers=auth_headers(user)).get_json()
    assert [model["id"] for model in payload["models"]] == ["flash", "deepseek-chat"]
    assert payload["default_model_id"] == "flash"
    assert payload["task_routes"] == {
        "summary": "default",
        "transcript_normalize": "flash",
        "briefing": "default",
    }


def test_llm_test_uses_stored_provider_key_when_model_id_is_sent(monkeypatch):
    app = make_auth_app((settings_bp, "/api/settings"))
    user = add_user(app.db, "user@example.com", role="admin")
    client = app.test_client()
    created = {}

    class FakeMessage:
        content = "OK"

    class FakeChoice:
        message = FakeMessage()

    class FakeCompletions:
        def create(self, **kwargs):
            created["request"] = kwargs
            return type("Response", (), {"choices": [FakeChoice()]})()

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, api_key, base_url):
            created["api_key"] = api_key
            created["base_url"] = base_url
            self.chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)
    client.put(
        "/api/settings/llm",
        json={
            "providers": [{
                "id": "modelscope",
                "name": "ModelScope",
                "provider": "modelscope",
                "api_format": "openai_compatible",
                "base_url": "https://api-inference.modelscope.cn/v1",
                "api_key": "stored-secret",
                "enabled": True,
            }],
            "models": [{
                "id": "flash",
                "provider_id": "modelscope",
                "name": "Flash",
                "model": "deepseek-ai/DeepSeek-V4-Flash",
                "enabled": True,
                "supports_streaming": True,
            }],
            "default_model_id": "flash",
            "task_routes": {},
        },
        headers=auth_headers(user),
    )

    response = client.post(
        "/api/settings/llm/test",
        json={
            "model_id": "flash",
            "provider_id": "modelscope",
            "api_key": "",
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert created["api_key"] == "stored-secret"
    assert created["base_url"] == "https://api-inference.modelscope.cn/v1"
    assert created["request"]["model"] == "deepseek-ai/DeepSeek-V4-Flash"


def test_bilibili_status_endpoint(monkeypatch):
    monkeypatch.setattr("app.config.Config", type("C", (), {"BILI_SESSDATA": ""}))
    """B站登录态端点：返回 configured 标记（无 SESSDATA 时 configured=False）"""
    app = make_auth_app((settings_bp, "/api/settings"))
    user = add_user(app.db, "u9@example.com", role="admin")
    client = app.test_client()
    resp = client.get("/api/settings/bilibili-status", headers=auth_headers(user))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["configured"] is False
    assert body["valid"] is False


def test_update_bilibili_sessdata_validates_and_persists(monkeypatch, tmp_path):
    from app.api import settings as settings_module
    from app.services.bilibili_service import BilibiliService
    from app.config import Config

    app = make_auth_app((settings_bp, "/api/settings"))
    admin = add_user(app.db, "u@example.com", role="admin")
    viewer = add_user(app.db, "v@example.com", role="viewer")
    client = app.test_client()

    # viewer 不可用（admin 专属）
    denied = client.put(
        "/api/settings/bilibili-sessdata",
        json={"sessdata": "x"},
        headers=auth_headers(viewer),
    )
    assert denied.status_code == 403

    # 空值 400
    assert client.put(
        "/api/settings/bilibili-sessdata", json={}, headers=auth_headers(admin)
    ).status_code == 400

    # 正常更新：运行时生效 + 写入 .env + 回传验证结果
    monkeypatch.setattr(
        BilibiliService, "_get",
        classmethod(lambda cls, path: ({"isLogin": True, "uname": "zz", "mid": 42}, None)),
    )
    env_file = tmp_path / ".env"
    env_file.write_text("JWT_SECRET=old\nBILI_SESSDATA=stale\n", encoding="utf-8")
    # 经 ENV_FILE 注入临时路径，测试绝不碰真实 backend/.env
    app.config["ENV_FILE"] = str(env_file)

    resp = client.put(
        "/api/settings/bilibili-sessdata",
        json={"sessdata": "NEW%2CVALUE"},
        headers=auth_headers(admin),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["valid"] is True
    assert body["nickname"] == "zz"
    assert Config.BILI_SESSDATA == "NEW%2CVALUE"  # 运行时立即生效

    written = env_file.read_text(encoding="utf-8")
    assert "BILI_SESSDATA=NEW%2CVALUE" in written
    assert "JWT_SECRET=old" in written


def test_feed_check_error_is_humanized_in_response():
    from bson import ObjectId

    from app.models.feed import Feed

    doc = {
        "_id": ObjectId(),
        "title": "硅谷101",
        "rss_url": "https://space.bilibili.com/1",
        "type": "bilibili",
        "check_error": "Bilibili login required (check BILI_SESSDATA)",
    }
    resp = Feed.to_response(doc)
    assert resp["check_error"].startswith("B站登录已失效")
    assert "SESSDATA" in resp["check_error"]
