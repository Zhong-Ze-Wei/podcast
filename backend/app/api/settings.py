# -*- coding: utf-8 -*-
"""
设置API路由
"""

from flask import Blueprint, request, jsonify, current_app
from ..models.setting import SettingModel

settings_bp = Blueprint("settings", __name__)


def get_setting_model():
    """获取设置模型实例"""
    from .. import get_db

    return SettingModel(get_db())


@settings_bp.route("/llm", methods=["GET"])
def get_llm_configs():
    """获取LLM配置列表"""
    try:
        model = get_setting_model()
        data = model.get_llm_configs()

        # 标记有API密钥但不返回完整值
        configs = []
        for config in data["configs"]:
            safe_config = config.copy()
            if safe_config.get("api_key"):
                # 返回占位符，表示有密钥
                safe_config["api_key"] = ""
                safe_config["has_api_key"] = True
            else:
                safe_config["has_api_key"] = False
            configs.append(safe_config)

        return jsonify({"configs": configs, "active_index": data["active_index"]})
    except Exception as e:
        current_app.logger.error(f"Failed to get LLM configs: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/llm", methods=["PUT"])
def save_llm_configs():
    """保存LLM配置列表"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        configs = data.get("configs", [])
        active_index = data.get("active_index")

        if not configs:
            return jsonify({"error": "At least one config is required"}), 400

        if len(configs) > 5:
            return jsonify({"error": "Maximum 5 configs allowed"}), 400

        model = get_setting_model()

        # 获取现有配置，用于保留未更改的 API key
        existing_data = model.get_llm_configs()
        existing_configs = existing_data.get("configs", [])

        # 如果新配置的 api_key 为空但标记有 has_api_key，保留原来的值
        for i, config in enumerate(configs):
            if not config.get("api_key") and config.get("has_api_key"):
                # 尝试从现有配置中恢复 API key
                if i < len(existing_configs):
                    config["api_key"] = existing_configs[i].get("api_key", "")
            # 清理临时标记
            config.pop("has_api_key", None)

        model.save_llm_configs(configs, active_index)

        return jsonify({"success": True, "message": "LLM configs saved"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Failed to save LLM configs: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/llm/active", methods=["PUT"])
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
def test_llm_connection():
    """测试LLM连接"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No config provided"}), 400

        base_url = data.get("base_url")
        api_key = data.get("api_key", "")
        model = data.get("model")

        if not base_url or not model:
            return jsonify({"error": "base_url and model are required"}), 400

        # 使用 OpenAI 兼容的客户端测试连接
        from openai import OpenAI

        client = OpenAI(base_url=base_url, api_key=api_key or "sk-xxx")

        # 发送简单测试请求
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'OK' if you can hear me."}],
            max_tokens=10,
            timeout=10,
        )

        return jsonify(
            {
                "success": True,
                "message": "Connection successful",
                "response": response.choices[0].message.content
                if response.choices
                else "",
            }
        )
    except Exception as e:
        current_app.logger.error(f"LLM test failed: {e}")
        return jsonify(
            {"success": False, "error": str(e)}
        ), 200  # 返回200但success=false，便于前端处理


@settings_bp.route("/tavily", methods=["GET"])
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
