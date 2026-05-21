from app.services import llm_client as llm_module
from app.services.llm_client import LLMClient


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
