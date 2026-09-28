# -*- coding: utf-8 -*-
"""
设置API路由
"""

from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from ..models.setting import SettingModel
from .decorators import current_owner_id, require_auth

settings_bp = Blueprint("settings", __name__)


def mask_api_key(key):
    """部分掩码 API Key：保留前6后4，中间用 ... 替代。"""
    if not key or len(key) < 12:
        return key or ""
    return key[:6] + "..." + key[-4:]


def get_setting_model():
    """获取设置模型实例"""
    from .. import get_db

    return SettingModel(get_db(), owner_id=current_owner_id())


@settings_bp.route("/llm", methods=["GET"])
@require_auth
def get_llm_configs():
    """获取LLM配置列表"""
    try:
        model = get_setting_model()
        data = model.get_llm_configs()

        configs = []
        for config in data["configs"]:
            safe_config = config.copy()
            raw_key = safe_config.get("api_key", "")
            safe_config["api_key"] = mask_api_key(raw_key)
            safe_config["has_api_key"] = bool(raw_key)
            configs.append(safe_config)

        providers = []
        for provider in data.get("providers", []):
            safe_provider = provider.copy()
            raw_key = safe_provider.get("api_key", "")
            safe_provider["api_key"] = mask_api_key(raw_key)
            safe_provider["has_api_key"] = bool(raw_key)
            providers.append(safe_provider)

        return jsonify({
            "configs": configs,
            "active_index": data["active_index"],
            "providers": providers,
            "models": data.get("models", []),
            "default_model_id": data.get("default_model_id", "default"),
            "task_routes": data.get("task_routes", {}),
        })
    except Exception as e:
        current_app.logger.error(f"Failed to get LLM configs: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/llm", methods=["PUT"])
@require_auth
def save_llm_configs():
    """保存LLM配置列表"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        configs = data.get("configs", [])
        providers = data.get("providers")
        models = data.get("models")
        active_index = data.get("active_index")
        default_model_id = data.get("default_model_id")
        task_routes = data.get("task_routes")

        if providers is None and not configs:
            return jsonify({"error": "At least one config is required"}), 400

        if configs and len(configs) > 5:
            return jsonify({"error": "Maximum 5 configs allowed"}), 400

        model = get_setting_model()
        existing_data = model.get_llm_configs()

        if providers is not None:
            if not providers:
                return jsonify({"error": "At least one provider is required"}), 400
            if not models:
                return jsonify({"error": "At least one model is required"}), 400

            existing_providers = existing_data.get("providers", [])
            existing_provider_by_id = {
                provider.get("id"): provider
                for provider in existing_providers
                if provider.get("id")
            }
            for provider in providers:
                api_key = provider.get("api_key", "")
                if not api_key or "..." in api_key:
                    existing = existing_provider_by_id.get(provider.get("id"))
                    if existing:
                        provider["api_key"] = existing.get("api_key", "")
                provider.pop("has_api_key", None)

            model.save_llm_settings(providers, models, default_model_id, task_routes)
            return jsonify({"success": True, "message": "LLM configs saved"})

        # 获取现有配置，用于保留未更改的 API key
        existing_configs = existing_data.get("configs", [])

        existing_by_id = {
            config.get("id"): config
            for config in existing_configs
            if config.get("id")
        }

        for i, config in enumerate(configs):
            api_key = config.get("api_key", "")
            if not api_key or "..." in api_key:
                existing = existing_by_id.get(config.get("id"))
                if existing is None and i < len(existing_configs):
                    existing = existing_configs[i]
                if existing:
                    config["api_key"] = existing.get("api_key", "")
            # 清理临时标记
            config.pop("has_api_key", None)

        model.save_llm_configs(configs, active_index)
        normalized = model.get_llm_configs()["configs"]
        if task_routes is not None:
            model.save_llm_task_routes(task_routes, normalized)

        return jsonify({"success": True, "message": "LLM configs saved"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Failed to save LLM configs: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/llm/active", methods=["PUT"])
@require_auth
def set_active_llm():
    """设置激活的LLM配置"""
    try:
        data = request.get_json()
        if data is None or "index" not in data:
            return jsonify({"error": "index is required"}), 400

        index = data["index"]
        model = get_setting_model()
        model.set_active_llm_index(index)

        return jsonify({"success": True, "message": f"Active LLM set to index {index}"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Failed to set active LLM: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/llm/test", methods=["POST"])
@require_auth
def test_llm_connection():
    """测试LLM连接"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No config provided"}), 400

        base_url = data.get("base_url", "").rstrip("/")
        api_key = data.get("api_key", "")
        llm_model = data.get("model")
        model_id = data.get("model_id")
        provider_id = data.get("provider_id")

        if model_id or provider_id:
            settings = get_setting_model().get_llm_settings()
            configured_model = next(
                (item for item in settings.get("models", []) if item.get("id") == model_id),
                None,
            )
            configured_provider_id = provider_id or (configured_model or {}).get("provider_id")
            configured_provider = next(
                (item for item in settings.get("providers", []) if item.get("id") == configured_provider_id),
                None,
            )
            if configured_model:
                llm_model = llm_model or configured_model.get("model")
            if configured_provider:
                base_url = base_url or configured_provider.get("base_url", "").rstrip("/")
                api_key = api_key or configured_provider.get("api_key", "")

        if not base_url or not llm_model:
            return jsonify({"error": "base_url and model are required"}), 400

        from openai import OpenAI

        client = OpenAI(base_url=base_url, api_key=api_key or "sk-placeholder")

        # 发送简单测试请求
        response = client.chat.completions.create(
            model=llm_model,
            messages=[{"role": "user", "content": "Say 'OK' if you can hear me."}],
            max_tokens=10,
            timeout=15,
        )

        return jsonify({
            "success": True,
            "message": "Connection successful",
            "base_url": base_url,
            "model": llm_model,
            "response": response.choices[0].message.content if response.choices else "",
        })

    except Exception as e:
        error_str = str(e)
        current_app.logger.error(f"LLM test failed: {e}")

        # 解析常见错误类型，给出可操作的提示
        hint = ""
        if "401" in error_str or "unauthorized" in error_str.lower() or "authentication" in error_str.lower():
            hint = "认证失败：API Key 不正确或已过期。请检查 Key 是否完整复制（注意前后空格）。"
        elif "404" in error_str or "not found" in error_str.lower():
            hint = "模型不存在或 Base URL 路径不正确。请检查：1) Model 名称拼写 2) Base URL 是否需要包含 /v1"
        elif "Connection" in error_str or "connect" in error_str.lower() or "timeout" in error_str.lower():
            hint = "网络连接失败：无法连接到服务器。请检查 Base URL 是否正确，服务是否可达。"
        elif "403" in error_str or "forbidden" in error_str.lower():
            hint = "权限不足：该 API Key 没有访问此模型的权限。"
        elif "429" in error_str or "rate" in error_str.lower():
            hint = "请求频率过高，请稍后重试。"

        return jsonify({
            "success": False,
            "error": error_str,
            "hint": hint,
            "base_url": base_url if 'base_url' in dir() else "",
            "model": llm_model if 'llm_model' in dir() else "",
        }), 200


@settings_bp.route("/tavily", methods=["GET"])
@require_auth
def get_tavily_config():
    """获取Tavily配置"""
    try:
        model = get_setting_model()
        config = model.get_tavily_config()

        # 安全处理API密钥 - 不返回完整值
        safe_config = config.copy()
        if safe_config.get("api_keys"):
            # 返回占位符数组，表示有密钥
            safe_config["api_keys"] = ["***"] * len(safe_config["api_keys"])
            safe_config["has_api_keys"] = True
        else:
            safe_config["has_api_keys"] = False

        return jsonify(safe_config)
    except Exception as e:
        current_app.logger.error(f"Failed to get Tavily config: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/tavily", methods=["PUT"])
@require_auth
def save_tavily_config():
    """保存Tavily配置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # 验证必需字段
        if "enabled" not in data:
            return jsonify({"error": "enabled field is required"}), 400

        # 处理API密钥 - 如果标记有密钥但未提供，则保留现有值
        model = get_setting_model()
        existing_config = model.get_tavily_config()

        api_keys = data.get("api_keys", [])
        has_api_keys = data.get("has_api_keys", False)

        # 如果没有提供API密钥但标记有密钥，则保留现有的
        if not api_keys and has_api_keys and existing_config.get("api_keys"):
            api_keys = existing_config["api_keys"]

        # 构建新的配置
        new_config = {
            "enabled": bool(data["enabled"]),
            "api_keys": api_keys,
            "search_depth": data.get("search_depth", "basic"),
            "max_results": int(data.get("max_results", 5)),
            "include_domains": data.get("include_domains", []),
            "exclude_domains": data.get("exclude_domains", []),
            "days_back": int(data.get("days_back", 30)),
        }

        # 验证配置
        if new_config["enabled"] and not new_config["api_keys"]:
            return jsonify(
                {"error": "At least one API key is required when Tavily is enabled"}
            ), 400

        if new_config["max_results"] < 1 or new_config["max_results"] > 20:
            return jsonify({"error": "max_results must be between 1 and 20"}), 400

        if new_config["days_back"] < 1 or new_config["days_back"] > 365:
            return jsonify({"error": "days_back must be between 1 and 365"}), 400

        model.save_tavily_config(new_config)

        return jsonify({"success": True, "message": "Tavily config saved"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Failed to save Tavily config: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/tavily/test", methods=["POST"])
@require_auth
def test_tavily_connection():
    """测试Tavily API连接"""
    data = request.get_json()
    api_key = (data or {}).get("api_key", "")
    if not api_key:
        return jsonify({"error": "api_key is required"}), 400

    from tavily import TavilyClient

    try:
        client = TavilyClient(api_key=api_key)
        response = client.search("test", max_results=1)
        return jsonify({
            "success": True,
            "message": "连接成功",
            "results_count": len(response.get("results", [])),
        })
    except Exception as e:
        current_app.logger.error(f"Tavily test failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 200


@settings_bp.route("/prompts/search-query", methods=["GET"])
@require_auth
def get_search_query_fragment():
    """获取搜索查询片段"""
    try:
        model = get_setting_model()
        custom_fragments = model.get("search_query_fragments", {})
        fragment = custom_fragments.get("daily_insight", "")

        return jsonify({"fragment": fragment, "has_custom_fragment": bool(fragment)})
    except Exception as e:
        current_app.logger.error(f"Failed to get search query fragment: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/prompts/search-query", methods=["PUT"])
@require_auth
def save_search_query_fragment():
    """保存搜索查询片段"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        fragment = data.get("fragment", "")

        # 验证片段
        if not isinstance(fragment, str):
            return jsonify({"error": "Fragment must be a string"}), 400

        model = get_setting_model()
        custom_fragments = model.get("search_query_fragments", {})
        custom_fragments["daily_insight"] = fragment
        model.set("search_query_fragments", custom_fragments)

        return jsonify({"success": True, "message": "Search query fragment saved"})
    except Exception as e:
        current_app.logger.error(f"Failed to save search query fragment: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/llm/fetch-models", methods=["POST"])
@require_auth
def fetch_provider_models():
    """从服务商拉取可用模型列表"""
    data = request.get_json() or {}
    provider_id = data.get("provider_id")
    if not provider_id:
        return jsonify({"error": "provider_id is required"}), 400

    model = get_setting_model()
    settings = model.get_llm_settings()
    provider = next(
        (p for p in settings["providers"] if p["id"] == provider_id), None
    )
    if not provider:
        return jsonify({"error": "Provider not found"}), 404

    if provider.get("api_format") == "anthropic_messages":
        return jsonify({
            "models": [],
            "hint": "Anthropic API 不支持模型列表接口，请手动输入模型名称。",
        })

    base_url = provider["base_url"].rstrip("/")
    api_key = provider.get("api_key", "")

    try:
        import requests as http_requests

        resp = http_requests.get(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        model_list = sorted(
            [{"id": m.get("id", ""), "name": m.get("id", "")} for m in body.get("data", []) if m.get("id")],
            key=lambda x: x["id"],
        )
        return jsonify({"models": model_list})
    except Exception as e:
        current_app.logger.error(f"Failed to fetch models from {base_url}: {e}")
        return jsonify({"models": [], "error": f"拉取模型列表失败: {str(e)}"})


@settings_bp.route("/ai-analysis", methods=["GET"])
@require_auth
def get_ai_analysis_switch():
    """AI 分析总开关状态"""
    from ..services.ai_control import is_ai_analysis_enabled

    return jsonify({"enabled": is_ai_analysis_enabled()})


@settings_bp.route("/ai-analysis", methods=["PUT"])
@require_auth
def save_ai_analysis_switch():
    """更新 AI 分析总开关（写入数据库，运行时生效）"""
    data = request.get_json() or {}
    if "enabled" not in data:
        return jsonify({"error": "enabled is required"}), 400

    db = current_app.db
    db.settings.update_one(
        {"_id": "ai_analysis"},
        {"$set": {"enabled": bool(data["enabled"]), "updated_at": datetime.utcnow()}},
        upsert=True,
    )
    from ..services.ai_control import is_ai_analysis_enabled

    return jsonify({"enabled": is_ai_analysis_enabled()})


@settings_bp.route("/bilibili-status", methods=["GET"])
@require_auth
def get_bilibili_status():
    """B站登录态：验证 SESSDATA 是否配置且有效（调 nav 接口实时校验）"""
    from ..config import Config
    from ..services.bilibili_service import BilibiliService

    if not Config.BILI_SESSDATA:
        return jsonify({"configured": False, "valid": False})

    data, error = BilibiliService._get("/x/web-interface/nav")
    if error:
        return jsonify({"configured": True, "valid": False, "error": error})
    return jsonify({
        "configured": True,
        "valid": bool(data and data.get("isLogin")),
        "nickname": (data or {}).get("uname", ""),
        "mid": (data or {}).get("mid"),
    })
