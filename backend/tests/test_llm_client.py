from app.services import llm_client as llm_module
from app.services.llm_client import LLMClient
from types import SimpleNamespace
import pytest


def test_reading_effort_is_light_only_for_supported_flash(monkeypatch):
    from app.services.llm_client import reading_request_options
    assert reading_request_options("DeepSeek-V4.1-Flash") == {"reasoning_effort": "low"}
    assert reading_request_options("test-model") == {}
    client = LLMClient(base_url="https://example.com/v1", api_key="k", model="DeepSeek-V4.1-Flash")
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'), finish_reason="stop")], usage=None)
    monkeypatch.setattr(client.client.chat.completions, "create", create)
    client.chat(messages=[{"role": "user", "content": "Read"}], **reading_request_options(client.model))
    assert captured["reasoning_effort"] == "low"


def _chat_result(content, completion):
    return {
        "content": content,
        "usage": {"prompt": 10, "completion": completion, "total": 10 + completion},
        "model": "test-model",
        "elapsed_seconds": 1,
    }


def test_chat_json_retries_once_when_output_truncated(monkeypatch):
    client = LLMClient(base_url="https://example.com/v1", api_key="k", model="test-model")
    caps = []

    def fake_chat(**kwargs):
        caps.append(kwargs["max_tokens"])
        if len(caps) == 1:
            # 输出顶到 max_tokens 上限，JSON 字符串被截断
            return _chat_result('{"summary": "半截', 100)
        return _chat_result('{"summary": "完整输出"}', 6)

    monkeypatch.setattr(client, "chat", fake_chat)

    result = client.chat_json(messages=[{"role": "user", "content": "hi"}], max_tokens=100)

    assert result["data"] == {"summary": "完整输出"}
    assert caps == [100, 200]


def test_chat_json_salvages_trailing_extra_data(monkeypatch):
    client = LLMClient(base_url="https://example.com/v1", api_key="k", model="test-model")
    calls = []

    def fake_chat(**kwargs):
        calls.append(1)
        # 完整 JSON 后模型又输出了收尾碎语（实测 transcript 策略出现过）
        return _chat_result('{"summary": {"totalEpisodes": 2}} 以上就是全部内容。', 3000)

    monkeypatch.setattr(client, "chat", fake_chat)

    result = client.chat_json(messages=[{"role": "user", "content": "hi"}], max_tokens=4096)

    assert result["data"] == {"summary": {"totalEpisodes": 2}}
    assert len(calls) == 1  # 截取成功，无需重试


def test_chat_json_does_not_retry_on_malformed_json(monkeypatch):
    import pytest

    client = LLMClient(base_url="https://example.com/v1", api_key="k", model="test-model")
    calls = []

    def fake_chat(**kwargs):
        calls.append(1)
        return _chat_result("这不是 JSON", 3)

    monkeypatch.setattr(client, "chat", fake_chat)

    with pytest.raises(ValueError):
        client.chat_json(messages=[{"role": "user", "content": "hi"}], max_tokens=100)

    assert len(calls) == 1


def test_openai_compatible_client_uses_openai_sdk(monkeypatch):
    created = {}

    class FakeOpenAI:
        def __init__(self, api_key, base_url, http_client=None):
            created["api_key"] = api_key
            created["base_url"] = base_url
            created["http_client"] = http_client

    monkeypatch.setattr(llm_module.openai, "OpenAI", FakeOpenAI)

    client = LLMClient(
        base_url="https://api-inference.modelscope.cn/v1",
        api_key="secret",
        model="deepseek-ai/DeepSeek-V4-Flash",
        api_format="openai_compatible",
    )

    assert client.api_format == "openai_compatible"
    assert created["api_key"] == "secret"
    assert created["base_url"] == "https://api-inference.modelscope.cn/v1"
    # 专用 http 客户端：LLM 流量不受环境/系统代理影响
    assert created["http_client"] is not None
    assert created["http_client"]._trust_env is False


@pytest.mark.parametrize("reasoning_effort", [None, "low"])
def test_anthropic_messages_client_calls_messages_endpoint(monkeypatch, reasoning_effort):
    requests = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "content": [{"type": "text", "text": "{\"ok\": true}"}],
                "usage": {"input_tokens": 3, "output_tokens": 4},
                "model": "claude-test",
            }

    def fake_post(url, headers, json, timeout, proxies=None):
        requests["url"] = url
        requests["headers"] = headers
        requests["json"] = json
        requests["timeout"] = timeout
        requests["proxies"] = proxies
        return FakeResponse()

    monkeypatch.setattr(llm_module.requests, "post", fake_post)

    client = LLMClient(
        base_url="https://api.anthropic.com/v1",
        api_key="anthropic-secret",
        model="claude-test",
        api_format="anthropic_messages",
    )
    result = client.chat(
        messages=[
            {"role": "system", "content": "Return JSON."},
            {"role": "user", "content": "Ping"},
        ],
        max_tokens=32,
        temperature=0.1,
        json_mode=True,
        reasoning_effort=reasoning_effort,
    )

    assert requests["url"] == "https://api.anthropic.com/v1/messages"
    assert requests["headers"]["x-api-key"] == "anthropic-secret"
    assert requests["headers"]["anthropic-version"] == "2023-06-01"
    assert requests["json"]["system"] == "Return JSON."
    assert requests["json"]["messages"] == [{"role": "user", "content": "Ping"}]
    assert requests["json"]["max_tokens"] == 32
    assert requests["json"]["temperature"] == 0.1
    # 不继承环境代理：显式覆盖 http/https（None=直连），环境变量无法再插手
    assert requests["proxies"] == {"http": None, "https": None}
    if reasoning_effort is not None:
        assert requests["json"]["output_config"]["effort"] == "low"
    else:
        assert "output_config" not in requests["json"]
    assert result["content"] == "{\"ok\": true}"
    assert result["usage"] == {"prompt": 3, "completion": 4, "total": 7}


def test_screening_schema_reaches_openai_compatible_api(monkeypatch):
    captured = {}
    client = LLMClient(base_url="https://example.com/v1", api_key="k", model="test-model")
    schema = {"type": "object", "properties": {"matches": {"type": "array"}}, "required": ["matches"]}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"matches":[]}'), finish_reason="stop")], usage=None)

    monkeypatch.setattr(client.client.chat.completions, "create", create)
    result = client.chat(messages=[{"role": "user", "content": "Screen this transcript."}], json_mode=True, response_schema=schema)

    assert captured["response_format"] == {"type": "json_schema", "json_schema": {"name": "structured_result", "strict": True, "schema": schema}}
    assert result["finish_reason"] == "stop"


@pytest.mark.parametrize("choices", [[], [SimpleNamespace(message=SimpleNamespace(content=None), finish_reason="length")]])
def test_empty_openai_response_preserves_usage_and_finish_reason(monkeypatch, choices):
    client = LLMClient(base_url="https://example.com/v1", api_key="k", model="test-model")
    response = SimpleNamespace(choices=choices, usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=30))
    monkeypatch.setattr(client.client.chat.completions, "create", lambda **kwargs: response)
    with pytest.raises(llm_module.EmptyLLMResponse) as error:
        client.chat(messages=[{"role": "user", "content": "hi"}])
    assert error.value.response["content"] == ""
    assert error.value.response["usage"]["total"] == 30
    assert error.value.response["finish_reason"] == ("length" if choices else None)


def test_empty_anthropic_response_preserves_usage_and_finish_reason(monkeypatch):
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
        "content": [], "stop_reason": "max_tokens", "usage": {"input_tokens": 10, "output_tokens": 20},
    })
    monkeypatch.setattr(llm_module.requests, "post", lambda *args, **kwargs: response)
    client = LLMClient(base_url="https://example.com/v1", api_key="k", model="test-model", api_format="anthropic_messages")
    with pytest.raises(llm_module.EmptyLLMResponse) as error:
        client.chat(messages=[{"role": "user", "content": "hi"}])
    assert error.value.response["content"] == ""
    assert error.value.response["usage"]["total"] == 30
    assert error.value.response["finish_reason"] == "max_tokens"


@pytest.mark.parametrize("top_level", [False, True])
def test_cache_reasoning_and_provider_usage_are_preserved(monkeypatch, top_level):
    client = LLMClient(base_url="https://example.com/v1", api_key="k", model="test-model")
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20, total_tokens=120,
        prompt_tokens_details=SimpleNamespace(cached_tokens=80),
        completion_tokens_details=None if top_level else SimpleNamespace(reasoning_tokens=12))
    if top_level:
        usage.reasoning_tokens = 0
        usage.prompt_cache_hit_tokens = 90
        usage.prompt_cache_miss_tokens = 10
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'), finish_reason="stop")], usage=usage, provider="test-provider")
    monkeypatch.setattr(client.client.chat.completions, "create", lambda **kwargs: response)
    result = client.chat(messages=[{"role": "user", "content": "read"}])
    assert result["usage"]["cached_tokens"] == (90 if top_level else 80)
    assert result["usage"]["reasoning_tokens"] == (0 if top_level else 12)
    assert result["provider"] == "test-provider"
    assert result["visible_output_characters"] == 11


def test_unknown_cache_usage_is_not_reported_as_zero(monkeypatch):
    client = LLMClient(base_url="https://example.com/v1", api_key="k", model="test-model")
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2, total_tokens=12))
    monkeypatch.setattr(client.client.chat.completions, "create", lambda **kwargs: response)
    result = client.chat(messages=[])
    assert "cached_tokens" not in result["usage"] and "reasoning_tokens" not in result["usage"]


def test_normalize_llm_proxy_bare_ipv6_forms():
    from app.services.llm_client import normalize_llm_proxy

    assert normalize_llm_proxy("") == ""
    assert normalize_llm_proxy("   ") == ""
    # 裸 IPv6：按 curl 惯例末段作端口，补方括号和协议
    assert normalize_llm_proxy("::1:7890") == "http://[::1]:7890"
    assert normalize_llm_proxy("::1") == "http://[::1]"
    assert normalize_llm_proxy("[::1]:7890") == "http://[::1]:7890"
    assert normalize_llm_proxy("http://::1:7890") == "http://[::1]:7890"
    assert normalize_llm_proxy("socks5://::1:7890") == "socks5://[::1]:7890"
    # 非 IPv6 写法原样保留，仅补协议
    assert normalize_llm_proxy("http://127.0.0.1:7890") == "http://127.0.0.1:7890"
    assert normalize_llm_proxy("127.0.0.1:7890") == "http://127.0.0.1:7890"
    assert normalize_llm_proxy("http://proxy.internal:8080") == "http://proxy.internal:8080"
    # 修不动的写法原样返回，交给客户端构造阶段报出可读错误
    assert normalize_llm_proxy("http://::1]") == "http://::1]"


def test_llm_client_ignores_environment_proxy(monkeypatch):
    # 回归：畸形系统代理（未加方括号的 IPv6）曾让 AI 简报任务以 Invalid port: ':1]' 失败
    monkeypatch.setenv("ALL_PROXY", "http://::1]")
    monkeypatch.setenv("HTTP_PROXY", "::1")
    monkeypatch.setenv("HTTPS_PROXY", "::1")
    monkeypatch.setenv("http_proxy", "::1")
    monkeypatch.setenv("https_proxy", "::1")
    client = LLMClient(base_url="https://example.com/v1", api_key="k", model="test-model")
    try:
        assert client.client is not None
    finally:
        client.close()


def test_llm_client_rejects_invalid_llm_proxy_with_clear_message(monkeypatch):
    monkeypatch.setattr(llm_module.config, "LLM_PROXY", "http://::1]", raising=False)
    with pytest.raises(ValueError, match="LLM_PROXY"):
        LLMClient(base_url="https://example.com/v1", api_key="k", model="test-model")


def test_llm_client_uses_normalized_llm_proxy(monkeypatch):
    monkeypatch.setattr(llm_module.config, "LLM_PROXY", "::1:7890", raising=False)
    client = LLMClient(base_url="https://example.com/v1", api_key="k", model="test-model")
    try:
        assert client.proxy == "http://[::1]:7890"
        assert client._requests_proxies == {"http": "http://[::1]:7890", "https": "http://[::1]:7890"}
    finally:
        client.close()
