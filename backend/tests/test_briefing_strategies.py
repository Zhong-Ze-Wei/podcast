# -*- coding: utf-8 -*-
"""AI 简报三策略：认证、策略校验、文稿两步压缩、缓存按策略隔离"""
from datetime import datetime, timedelta

from bson import ObjectId

from app.api.insights import insights_bp
from app.services import briefing_service as briefing_module
from tests.auth_helpers import add_user, auth_headers, make_auth_app


class FakeLLM:
    def __init__(self, *args, **kwargs):
        self.chat_calls = 0

    def chat(self, messages, **kwargs):
        self.chat_calls += 1
        return {
            "content": "压缩要点：嘉宾讨论了测试策略与取舍。",
            "usage": {"prompt": 10, "completion": 20, "total": 30},
            "model": "fake",
            "elapsed_seconds": 0,
        }

    def chat_json(self, messages, **kwargs):
        return {
            "data": {
                "summary": {"totalEpisodes": 2, "totalDuration": "1小时", "keyInsights": 1, "newConcepts": 0},
                "hotTopics": [], "newConcepts": [], "trends": {"topics": []},
                "recommended": [], "markdownReport": "# 测试简报",
            },
            "usage": {"prompt": 1, "completion": 2, "total": 3},
            "model": "fake",
            "elapsed_seconds": 0,
        }


def make_briefing_app():
    app = make_auth_app((insights_bp, "/api/insights"))
    app.config.update(AI_ANALYSIS_ENABLED=True)
    return app


def seed_week(db):
    """近 7 天两集：一集有 AI 摘要，一集只有文稿"""
    feed_id = ObjectId()
    db.feeds._data.append({
        "_id": feed_id, "title": "测试播客", "status": "active",
        "created_at": datetime.utcnow(),
    })
    now = datetime.utcnow()

    summarized_id = ObjectId()
    db.episodes._data.append({
        "_id": summarized_id, "feed_id": feed_id, "guid": "ep1", "title": "已摘要单集",
        "status": "new", "published": now - timedelta(days=1), "created_at": now,
        "summary": "RSS简介一", "duration": 3600,
    })
    db.summaries._data.append({
        "_id": ObjectId(), "episode_id": summarized_id,
        "content": {"tldr": "这一集讨论了既定主题的深入分析"},
        "tldr": "这一集讨论了既定主题的深入分析",
        "created_at": now,
    })

    transcript_id = ObjectId()
    db.episodes._data.append({
        "_id": transcript_id, "feed_id": feed_id, "guid": "ep2", "title": "文稿单集",
        "status": "new", "published": now - timedelta(days=2), "created_at": now,
        "summary": "RSS简介二", "duration": 2400,
    })
    db.transcripts._data.append({
        "_id": ObjectId(), "episode_id": transcript_id,
        "text": "这里是完整文稿，主讲者系统阐述了方法的演进。" * 30,
        "created_at": now,
    })
    return feed_id, summarized_id, transcript_id


def test_insights_requires_auth():
    app = make_briefing_app()
    client = app.test_client()
    assert client.get("/api/insights/briefing").status_code == 401
    assert client.post("/api/insights/briefing").status_code == 401


def test_invalid_strategy_rejected():
    app = make_briefing_app()
    user = add_user(app.db, "u@example.com")
    client = app.test_client()

    resp = client.get("/api/insights/briefing?strategy=nonsense", headers=auth_headers(user))
    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "INVALID_STRATEGY"


def test_transcript_strategy_condenses_and_caches_per_strategy(monkeypatch):
    app = make_briefing_app()
    user = add_user(app.db, "u@example.com")
    seed_week(app.db)

    fake = FakeLLM()
    monkeypatch.setattr(briefing_module, "get_llm_client", lambda task=None: fake)

    client = app.test_client()
    resp = client.post("/api/insights/briefing?strategy=transcript", headers=auth_headers(user))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True

    meta = body["briefing"]["briefing"]["_meta"]
    assert meta["strategy"] == "transcript"
    assert fake.chat_calls >= 1  # 无摘要那集走了文稿压缩
    assert meta["source_counts"].get("summary") == 1
    assert meta["source_counts"].get("transcript") == 1

    # 缓存按策略隔离：再生成 summary 策略应是独立文档
    resp2 = client.post("/api/insights/briefing?strategy=summary", headers=auth_headers(user))
    assert resp2.status_code == 200
    docs = list(app.db.briefings.find({}, {"strategy": 1}))
    assert {d.get("strategy") for d in docs} == {"transcript", "summary"}


def test_metadata_strategy_needs_no_condense(monkeypatch):
    app = make_briefing_app()
    user = add_user(app.db, "u@example.com")
    seed_week(app.db)

    fake = FakeLLM()
    monkeypatch.setattr(briefing_module, "get_llm_client", lambda task=None: fake)

    client = app.test_client()
    resp = client.post("/api/insights/briefing?strategy=metadata", headers=auth_headers(user))
    assert resp.status_code == 200

    meta = resp.get_json()["briefing"]["briefing"]["_meta"]
    assert meta["strategy"] == "metadata"
    assert fake.chat_calls == 0  # 元数据策略不做逐集压缩
    assert sum(meta["source_counts"].values()) == 2
