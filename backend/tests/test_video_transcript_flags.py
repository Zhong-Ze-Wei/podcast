"""视频字幕成功后的可见标记，与已经完成的摘要阶段保持一致。"""
import pytest
from bson import ObjectId

from app.api.feeds import _upsert_video_episode
from app.models.episode import Episode
from tests.conftest import MockDB


@pytest.mark.parametrize("source", ["youtube", "bilibili"])
def test_new_video_with_captions_is_marked_transcribed(source):
    db = MockDB()
    feed = {"_id": ObjectId(), "owner_id": "owner"}
    _upsert_video_episode(db, feed, f"{source}:new", "Video", transcript={"text": "Actual full captions", "segments": []}, transcript_source=source)
    episode = db.episodes.find_one({"guid": f"{source}:new"})
    assert episode["has_transcript"] is True
    assert episode["status"] == Episode.STATUS_TRANSCRIBED
    assert episode["transcript_source"] == source
    assert db.transcripts.find_one({"episode_id": episode["_id"]})["text"] == "Actual full captions"


@pytest.mark.parametrize("status", [Episode.STATUS_NEW, Episode.STATUS_SUMMARIZED, Episode.STATUS_SUMMARIZING])
def test_caption_backfill_preserves_summary_stage(status):
    db = MockDB()
    feed = {"_id": ObjectId(), "owner_id": "owner"}
    episode = Episode.create(feed["_id"], "youtube:old", "Video", owner_id="owner")
    episode["status"] = status
    db.episodes.insert_one(episode)
    outcome = _upsert_video_episode(db, feed, "youtube:old", "Video", transcript={"text": "Backfilled actual captions", "segments": []}, transcript_source="youtube")
    stored = db.episodes.find_one({"_id": episode["_id"]})
    assert outcome == "backfilled"
    assert stored["has_transcript"] is True
    assert stored["transcript_source"] == "youtube"
    assert stored["status"] == (Episode.STATUS_TRANSCRIBED if status == Episode.STATUS_NEW else status)
