from app.services import llm_client as llm_module
from app.services.llm_client import LLMClient


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
        def __init__(self, api_key, base_url):
            created["api_key"] = api_key
            created["base_url"] = base_url

    monkeypatch.setattr(llm_module.openai, "OpenAI", FakeOpenAI)

    client = LLMClient(
        base_url="https://api-inference.modelscope.cn/v1",
        api_key="secret",
        model="deepseek-ai/DeepSeek-V4-Flash",
        api_format="openai_compatible",
    )

    assert client.api_format == "openai_compatible"
    assert created == {
        "api_key": "secret",
        "base_url": "https://api-inference.modelscope.cn/v1",
    }


def test_anthropic_messages_client_calls_messages_endpoint(monkeypatch):
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

    def fake_post(url, headers, json, timeout):
        requests["url"] = url
        requests["headers"] = headers
        requests["json"] = json
        requests["timeout"] = timeout
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
    )

    assert requests["url"] == "https://api.anthropic.com/v1/messages"
    assert requests["headers"]["x-api-key"] == "anthropic-secret"
    assert requests["headers"]["anthropic-version"] == "2023-06-01"
    assert requests["json"]["system"] == "Return JSON."
    assert requests["json"]["messages"] == [{"role": "user", "content": "Ping"}]
    assert requests["json"]["max_tokens"] == 32
    assert requests["json"]["temperature"] == 0.1
    assert result["content"] == "{\"ok\": true}"
    assert result["usage"] == {"prompt": 3, "completion": 4, "total": 7}
