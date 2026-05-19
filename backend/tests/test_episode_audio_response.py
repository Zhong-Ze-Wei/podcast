from datetime import datetime

from bson import ObjectId
from flask import Flask

from app.config import Config
from app.models.episode import Episode
from app.api import episodes
from tests.conftest import MockDB


def make_app(**config):
    app = Flask(__name__)
    app.config.update(MEDIA_ROOT=".")
    app.config.update(config)
    return app


def base_episode(local_path=None):
    return {
        "_id": ObjectId(),
        "feed_id": ObjectId(),
        "guid": "episode-1",
        "title": "Episode 1",
        "audio_url": "https://example.com/episode.mp3",
        "local_path": local_path,
        "published": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


def test_to_response_includes_local_audio_url_when_file_exists(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    audio_file = media_root / "audio" / "feed-1" / "episode.mp3"
    audio_file.parent.mkdir(parents=True)
    audio_file.write_bytes(b"audio")
    monkeypatch.setattr(Config, "MEDIA_ROOT", str(media_root))

    response = Episode.to_response(base_episode("audio/feed-1/episode.mp3"))

    assert response["local_audio_url"] == "/api/media/audio/feed-1/episode.mp3"


def test_to_response_omits_local_audio_url_when_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "MEDIA_ROOT", str(tmp_path / "media"))

    response = Episode.to_response(base_episode("audio/feed-1/missing.mp3"))

    assert response["local_audio_url"] is None


def test_download_allows_redownload_when_status_downloaded_but_file_missing(monkeypatch, tmp_path):
    app = make_app(MEDIA_ROOT=str(tmp_path))
    db = MockDB()
    episode_id = ObjectId()
    db.episodes._data.append({
        "_id": episode_id,
        "feed_id": ObjectId(),
        "title": "Downloaded But Missing",
        "status": Episode.STATUS_DOWNLOADED,
        "audio_url": "https://example.com/audio.mp3",
        "local_path": "audio/missing.mp3",
    })
    submitted = {}
    monkeypatch.setattr(episodes, "get_db", lambda: db)
    monkeypatch.setattr(episodes.task_queue, "submit", lambda **kwargs: submitted.update(kwargs) or "task-1")

    with app.test_request_context(f"/api/episodes/{episode_id}/download", method="POST"):
        response, status_code = episodes.download_episode(str(episode_id))

    assert status_code == 200
    assert response.get_json()["data"]["task_id"] == "task-1"
    assert submitted["task_type"] == "download"
