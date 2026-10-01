"""Server-side episode queries and processing results are consistent across views."""
from datetime import datetime
from bson import ObjectId
from flask import Flask
import pytest
from app.api.episodes import episodes_bp
from app.api.feeds import feeds_bp
from tests.conftest import MockDB


@pytest.fixture
def app(monkeypatch, tmp_path):
    app = Flask(__name__)
    app.config.update(MEDIA_ROOT=str(tmp_path), AI_ANALYSIS_ENABLED=True, TRANSCRIPTION_CLOUD_ENABLED=False)
    app.db = MockDB()
    app.register_blueprint(episodes_bp, url_prefix="/api/episodes")
    app.register_blueprint(feeds_bp, url_prefix="/api/feeds")
    monkeypatch.setattr("app.config.Config.MEDIA_ROOT", str(tmp_path))
    monkeypatch.setattr("app.services.whisper_service.is_available", lambda: False)
    monkeypatch.setattr("app.services.whisperx_service.is_available", lambda: False)
    return app


def episode(app, title, **fields):
    doc = {"title": title, "published": datetime(2026, 10, 1), "created_at": datetime(2026, 10, 1), "status": "new", "content": "long body" * 1000}
    doc.update(fields)
    return app.db.episodes.insert_one(doc).inserted_id


def test_queries_filter_before_paginating_and_keep_old_favorites(app):
    old = episode(app, "Old Favorite", published=datetime(2020, 1, 1))
    for index in range(501):
        episode(app, f"Episode {index}")
    app.db.user_episode_states.insert_one({"user_id": "local-default-user", "episode_id": old, "is_starred": True})
    client = app.test_client()
    page = client.get("/api/episodes?page=2&per_page=20").get_json()
    assert len(page["data"]) == 20
    assert page["pagination"]["total"] == 502
    favorites = client.get("/api/episodes?is_starred=true").get_json()
    assert [item["id"] for item in favorites["data"]] == [str(old)]
    assert favorites["data"][0]["is_starred"] is True
    assert "content" not in page["data"][0]
    assert client.get(f"/api/episodes/{old}").get_json()["data"]["content"]


def test_search_is_literal_and_identical_in_global_and_feed_lists(app):
    feed = app.db.feeds.insert_one({"title": "Feed", "created_at": datetime(2026, 10, 1)}).inserted_id
    target = episode(app, "C++ [AI]", feed_id=feed)
    episode(app, "AI only", feed_id=feed)
    for url in ("/api/episodes", f"/api/feeds/{feed}/episodes"):
        data = app.test_client().get(url, query_string={"q": "[AI]"}).get_json()
        assert [item["id"] for item in data["data"]] == [str(target)]
        assert data["pagination"]["total"] == 1


def test_workspace_filters_results_instead_of_processing_status(app, tmp_path):
    (tmp_path / "audio.mp3").write_bytes(b"audio")
    audio = episode(app, "Audio", local_path="audio.mp3", has_local_audio=True)
    transcript = episode(app, "Transcript", has_transcript=True, status="summarizing")
    summary = episode(app, "Summary", has_summary=True)
    episode(app, "Pending download", status="downloading")
    client = app.test_client()
    body = client.get("/api/episodes?processed=true").get_json()
    assert {item["id"] for item in body["data"]} == {str(audio), str(transcript), str(summary)}
    assert [item["id"] for item in client.get("/api/episodes?has_local_audio=true").get_json()["data"]] == [str(audio)]
    assert [item["id"] for item in client.get("/api/episodes?has_transcript=true&has_summary=false").get_json()["data"]] == [str(transcript)]


def test_equal_dates_have_stable_order_and_invalid_sort_is_rejected(app):
    first = episode(app, "Beta")
    second = episode(app, "Alpha")
    client = app.test_client()
    assert client.get("/api/episodes?per_page=1").get_json()["data"][0]["id"] == str(second)
    assert client.get("/api/episodes?page=2&per_page=1").get_json()["data"][0]["id"] == str(first)
    assert client.get("/api/episodes?sort=title_asc").get_json()["data"][0]["title"] == "Alpha"
    assert client.get("/api/episodes?sort=unknown").status_code == 400


def test_feed_list_applies_personal_flags_and_paginated_counts(app):
    for index in range(25):
        app.db.feeds.insert_one({"title": f"Feed {index}", "created_at": datetime(2026, 10, 1)})
    feed = app.db.feeds._data[0]["_id"]
    item = episode(app, "Personal favorite", feed_id=feed)
    app.db.user_episode_states.insert_one({"user_id": "local-default-user", "episode_id": item, "is_starred": True})
    client = app.test_client()
    assert client.get("/api/feeds?page=2&per_page=20").get_json()["pagination"]["total"] == 25
    result = client.get(f"/api/feeds/{feed}/episodes?is_starred=true").get_json()["data"]
    assert len(result) == 1 and result[0]["is_starred"] is True


def test_artifacts_tasks_and_actions_describe_independent_information(app):
    item = episode(app, "Readable while summarizing", has_transcript=True, transcript_url="https://example.com/transcript.vtt")
    app.db.tasks.insert_one({"task_id": "summary-1", "episode_id": str(item), "task_type": "summarize", "status": "processing", "progress": 40, "owner_id": "another-user", "result": {"secret": "do not expose"}})
    app.db.tasks.insert_one({"task_id": "private-report", "episode_id": str(item), "task_type": "briefing-report", "status": "processing", "owner_id": "another-user"})
    client = app.test_client()
    for body in (client.get(f"/api/episodes/{item}").get_json()["data"], client.get("/api/episodes").get_json()["data"][0]):
        assert body["artifacts"] == {"local_audio": False, "transcript": True, "summary": False}
        assert len(body["active_tasks"]) == 1
        assert body["active_tasks"][0]["task_id"] == "summary-1"
        assert "result" not in body["active_tasks"][0]
        assert body["actions"]["summarize"] == {"allowed": False, "reason_code": "TASK_IN_PROGRESS"}
        assert body["actions"]["transcribe"]["reason_code"] == "ALREADY_TRANSCRIBED"


def test_transcription_capabilities_match_provider_runtime_and_download_need(app, monkeypatch):
    monkeypatch.setattr("app.services.whisper_service.is_available", lambda: True)
    item = episode(app, "Downloadable", audio_url="https://example.com/audio.mp3")
    body = app.test_client().get(f"/api/episodes/{item}").get_json()["data"]
    providers = {item["id"]: item for item in body["transcription_providers"]}
    assert providers["local_whisper"] == {"id": "local_whisper", "available": True, "reason_code": None, "download_required": True}
    assert providers["local_whisperx"]["reason_code"] == "LOCAL_AI_NOT_INSTALLED"
    assert providers["assemblyai"]["reason_code"] == "CLOUD_TRANSCRIPTION_DISABLED"
    assert providers["official"]["reason_code"] == "NO_TRANSCRIPT_URL"
    assert body["actions"]["transcribe"]["allowed"] is True


def test_viewer_capabilities_and_processing_posts_are_consistent(monkeypatch):
    from app.api.transcripts import transcripts_bp
    from app.api.summaries import summaries_bp
    from tests.auth_helpers import make_auth_app, add_user, auth_headers
    app = make_auth_app((episodes_bp, "/api/episodes"), (transcripts_bp, "/api/transcripts"), (summaries_bp, "/api/summaries"))
    viewer = add_user(app.db, "viewer@example.com", role="viewer")
    item = episode(app, "Read only", audio_url="https://example.com/audio.mp3", transcript_url="https://example.com/sub.vtt")
    monkeypatch.setattr("app.services.whisper_service.is_available", lambda: True)
    monkeypatch.setattr("app.services.whisperx_service.is_available", lambda: True)
    client = app.test_client()
    headers = auth_headers(viewer)
    data = client.get(f"/api/episodes/{item}", headers=headers).get_json()["data"]
    assert all(action == {"allowed": False, "reason_code": "ROLE_DENIED"} for action in data["actions"].values())
    assert all(not provider["available"] for provider in data["transcription_providers"])
    for path in (f"/api/episodes/{item}/download", f"/api/transcripts/{item}", f"/api/transcripts/{item}/fetch-video-audio", f"/api/transcripts/{item}/fetch", f"/api/summaries/{item}", f"/api/summaries/{item}/translate"):
        response = client.post(path, json={"provider": "official"}, headers=headers)
        assert response.status_code == 403, path
        assert response.get_json()["error_code"] == "ROLE_DENIED"


def test_processing_post_rechecks_runtime_after_capability_response(app, monkeypatch):
    from app.api.transcripts import transcripts_bp
    app.register_blueprint(transcripts_bp, url_prefix="/api/transcripts")
    app.config["TRANSCRIPTION_CLOUD_ENABLED"] = True
    item = episode(app, "Cloud audio", audio_url="https://example.com/audio.mp3")
    client = app.test_client()
    data = client.get(f"/api/episodes/{item}").get_json()["data"]
    assert next(provider for provider in data["transcription_providers"] if provider["id"] == "assemblyai")["available"] is True
    app.config["TRANSCRIPTION_CLOUD_ENABLED"] = False
    monkeypatch.setattr("app.api.transcripts.task_queue.submit_unique", lambda *a, **kw: pytest.fail("disabled provider must not submit work"))
    response = client.post(f"/api/transcripts/{item}", json={"provider": "assemblyai"})
    assert response.status_code == 423
    assert response.get_json()["error_code"] == "CLOUD_TRANSCRIPTION_DISABLED"


def test_legacy_audio_paths_and_negative_result_filters_are_supported(app, tmp_path):
    (tmp_path / "old.mp3").write_bytes(b"audio")
    old = episode(app, "Legacy downloaded", audio_path="old.mp3")
    raw = episode(app, "Unprocessed")
    client = app.test_client()
    assert [item["id"] for item in client.get("/api/episodes?has_local_audio=true").get_json()["data"]] == [str(old)]
    assert [item["id"] for item in client.get("/api/episodes?processed=false").get_json()["data"]] == [str(raw)]


def test_audio_metadata_migration_is_dry_run_by_default_and_idempotent(app, tmp_path):
    from app.services.audio_metadata_service import reconcile_local_audio
    (tmp_path / "exists.mp3").write_bytes(b"audio")
    valid = episode(app, "Existing audio", local_path="exists.mp3")
    missing = episode(app, "Removed audio", local_path="missing.mp3", has_local_audio=True)
    report = reconcile_local_audio(app.db, str(tmp_path))
    assert report["updated"] == 0 and report["changed"] == 2
    assert "has_local_audio" not in app.db.episodes.find_one({"_id": valid})
    report = reconcile_local_audio(app.db, str(tmp_path), dry_run=False)
    assert report["updated"] == 2
    assert app.db.episodes.find_one({"_id": valid})["has_local_audio"] is True
    assert app.db.episodes.find_one({"_id": missing})["has_local_audio"] is False
    assert reconcile_local_audio(app.db, str(tmp_path), dry_run=False)["updated"] == 0
    assert [item["id"] for item in app.test_client().get("/api/episodes?has_local_audio=true").get_json()["data"]] == [str(valid)]


def test_download_post_rechecks_actual_audio_and_source(app, monkeypatch, tmp_path):
    raw = episode(app, "No source")
    (tmp_path / "exists.mp3").write_bytes(b"audio")
    existing = episode(app, "Existing", local_path="exists.mp3", audio_url="https://example.com/audio.mp3")
    monkeypatch.setattr("app.api.episodes.task_queue.submit_unique", lambda **kwargs: pytest.fail("unavailable action must not submit"))
    client = app.test_client()
    assert client.get(f"/api/episodes/{raw}").get_json()["data"]["actions"]["download"]["reason_code"] == "NO_AUDIO_URL"
    result = client.post(f"/api/episodes/{raw}/download")
    assert result.status_code == 400 and result.get_json()["error_code"] == "NO_AUDIO_URL"
    result = client.post(f"/api/episodes/{existing}/download")
    assert result.status_code == 400 and result.get_json()["error_code"] == "ALREADY_DOWNLOADED"


@pytest.mark.parametrize("operation", ["download", "transcribe", "summarize"])
def test_processing_posts_reject_shared_conflicting_tasks(app, monkeypatch, operation):
    from app.api.transcripts import transcripts_bp
    from app.api.summaries import summaries_bp
    app.register_blueprint(transcripts_bp, url_prefix="/api/transcripts")
    app.register_blueprint(summaries_bp, url_prefix="/api/summaries")
    item = episode(app, "Busy", audio_url="https://example.com/audio.mp3", transcript_url="https://example.com/sub.vtt", has_transcript=operation == "summarize")
    app.db.transcripts.insert_one({"episode_id": item, "text": "Existing text"})
    conflict = "transcribe" if operation == "download" else "download"
    app.db.tasks.insert_one({"task_id": "other-user-task", "episode_id": str(item), "task_type": conflict, "owner_id": "another-user", "status": "pending"})
    monkeypatch.setattr("app.api.episodes.task_queue.submit_unique", lambda *a, **kw: pytest.fail("conflicting operation must not submit"))
    monkeypatch.setattr("app.api.summaries.task_queue.submit", lambda *a, **kw: pytest.fail("conflicting operation must not submit"))
    path = {"download": f"/api/episodes/{item}/download", "transcribe": f"/api/transcripts/{item}", "summarize": f"/api/summaries/{item}"}[operation]
    result = app.test_client().post(path, json={"provider": "official"})
    assert result.status_code == 409 and result.get_json()["error_code"] == "TASK_IN_PROGRESS"


def test_download_reuses_same_active_task_and_error_state_can_retry(app, monkeypatch):
    item = episode(app, "Queued", status="downloading", audio_url="https://example.com/audio.mp3")
    app.db.tasks.insert_one({"task_id": "download-existing", "episode_id": str(item), "task_type": "download", "dedup_key": f"download:{item}", "status": "pending", "owner_id": "another-user"})
    client = app.test_client()
    result = client.post(f"/api/episodes/{item}/download")
    assert result.status_code == 200 and result.get_json()["data"]["task_id"] == "download-existing"
    retry = episode(app, "Retry", status="error", audio_url="https://example.com/audio.mp3")
    monkeypatch.setattr("app.api.episodes.task_queue.submit_unique", lambda **kwargs: "retry-task")
    assert client.get(f"/api/episodes/{retry}").get_json()["data"]["actions"]["download"]["allowed"] is True
    result = client.post(f"/api/episodes/{retry}/download")
    assert result.status_code == 200 and result.get_json()["data"]["task_id"] == "retry-task"
