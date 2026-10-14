# -*- coding: utf-8 -*-
"""原文依据按需中译：批量翻译 + 引文哈希缓存（第二次不再调 LLM）"""
from app.api.briefing_reports import briefing_reports_bp
from app.services import llm_client as llm_module
from tests.auth_helpers import add_user, auth_headers, make_auth_app


class FakeLLM:
    def __init__(self, *args, **kwargs):
        pass

    def chat_json(self, messages, **kwargs):
        return {
            "data": {"items": [{"i": 0, "zh": "第一句译文"}, {"i": 1, "zh": "第二句译文"}]},
            "usage": {}, "model": "fake", "elapsed_seconds": 0,
        }


def make_evidence_app():
    app = make_auth_app((briefing_reports_bp, "/api/briefing-reports"))
    app.config.update(AI_ANALYSIS_ENABLED=True)
    return app


def test_translate_evidence_translates_then_hits_cache(monkeypatch):
    app = make_evidence_app()
    user = add_user(app.db, "u@example.com")
    calls = []

    class CountingLLM(FakeLLM):
        def chat_json(self, messages, **kwargs):
            calls.append(1)
            return FakeLLM.chat_json(self, messages, **kwargs)

    monkeypatch.setattr(llm_module, "get_llm_client", lambda task=None: CountingLLM())
    client = app.test_client()
    quotes = [{"id": "E1", "quote": "Hello world"}, {"id": "E2", "quote": "Second quote"}]

    first = client.post(
        "/api/briefing-reports/reading/epX/translate-evidence",
        json={"quotes": quotes}, headers=auth_headers(user),
    )
    assert first.status_code == 200
    translations = first.get_json()["data"]["translations"]
    assert translations == {"E1": "第一句译文", "E2": "第二句译文"}

    # 相同引文第二次走缓存，不再触发 LLM
    second = client.post(
        "/api/briefing-reports/reading/epX/translate-evidence",
        json={"quotes": quotes}, headers=auth_headers(user),
    )
    assert second.get_json()["data"]["translations"] == translations
    assert len(calls) == 1


def test_translate_evidence_rejects_empty_quotes():
    app = make_evidence_app()
    user = add_user(app.db, "u@example.com")
    client = app.test_client()
    resp = client.post(
        "/api/briefing-reports/reading/epX/translate-evidence",
        json={"quotes": []}, headers=auth_headers(user),
    )
    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "INVALID_QUOTES"
