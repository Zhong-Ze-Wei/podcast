# -*- coding: utf-8 -*-
"""本地 AI 转写组件（可选依赖）：未安装守卫与安装器平台检测"""
import os
import sys
from datetime import datetime

from bson import ObjectId

from app.api.transcripts import transcripts_bp
from app.services import whisper_service, whisperx_service
from tests.auth_helpers import add_user, auth_headers, make_auth_app

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import setup_local_ai  # noqa: E402


def _add_episode(db, guid="ep-1"):
    episode_id = ObjectId()
    db.episodes._data.append({
        "_id": episode_id,
        "owner_id": None,
        "feed_id": None,
        "guid": guid,
        "title": "Episode",
        "status": "new",
        "published": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    return episode_id


def test_local_whisper_task_rejected_when_component_missing(monkeypatch):
    app = make_auth_app((transcripts_bp, "/api/transcripts"))
    user = add_user(app.db, "u@example.com")
    episode_id = _add_episode(app.db, guid="rss-ep")

    monkeypatch.setattr(whisper_service, "is_available", lambda: False)
    client = app.test_client()
    resp = client.post(
        f"/api/transcripts/{episode_id}",
        json={"provider": "local_whisper"},
        headers=auth_headers(user),
    )

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error_code"] == "LOCAL_AI_NOT_INSTALLED"
    assert "setup_local_ai" in body["message"]


def test_video_transcribe_rejected_when_whisperx_missing(monkeypatch):
    app = make_auth_app((transcripts_bp, "/api/transcripts"))
    user = add_user(app.db, "u@example.com")
    episode_id = _add_episode(app.db, guid="youtube:abc123")

    monkeypatch.setattr(whisperx_service, "is_available", lambda: False)
    client = app.test_client()
    resp = client.post(
        f"/api/transcripts/{episode_id}/fetch-video-audio",
        headers=auth_headers(user),
    )

    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "LOCAL_AI_NOT_INSTALLED"


def test_detect_variant_matrix(monkeypatch):
    monkeypatch.setattr(setup_local_ai, "is_termux", lambda: False)

    # Windows / Linux + NVIDIA → CUDA
    monkeypatch.setattr(setup_local_ai.platform, "system", lambda: "Windows")
    monkeypatch.setattr(setup_local_ai, "has_nvidia_gpu", lambda: True)
    assert setup_local_ai.detect_variant()[0] == "cuda"

    # macOS（Apple Silicon 标注在说明里）→ CPU 通用
    monkeypatch.setattr(setup_local_ai.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(setup_local_ai.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(setup_local_ai, "has_nvidia_gpu", lambda: False)
    variant, note = setup_local_ai.detect_variant()
    assert variant == "cpu"
    assert "Apple Silicon" in note

    # Linux 无 NVIDIA → CPU 通用
    monkeypatch.setattr(setup_local_ai.platform, "system", lambda: "Linux")
    assert setup_local_ai.detect_variant()[0] == "cpu"

    # Android/Termux → 不安装，给指引
    monkeypatch.setattr(setup_local_ai, "is_termux", lambda: True)
    assert setup_local_ai.detect_variant()[0] == "termux"
