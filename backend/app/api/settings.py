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

        return jsonify({
            "configs": configs,
            "active_index": data["active_index"]
        })
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

        client = OpenAI(
            base_url=base_url,
            api_key=api_key or "sk-xxx"
        )

        # 发送简单测试请求
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'OK' if you can hear me."}],
            max_tokens=10,
            timeout=10
        )

        return jsonify({
            "success": True,
            "message": "Connection successful",
            "response": response.choices[0].message.content if response.choices else ""
        })
    except Exception as e:
        current_app.logger.error(f"LLM test failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 200  # 返回200但success=false，便于前端处理
