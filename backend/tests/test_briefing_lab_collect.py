"""Scope and data-preservation checks for the explicitly authorized flag repair."""
from copy import deepcopy
import json

from bson import ObjectId
import pytest

from scripts.briefing_lab_collect import (
    fetch_linked_transcript,
    persist_transcript,
    reconcile_selected_sources,
)
from tests.conftest import MockDB


def frozen_corpus(tmp_path):
    db = MockDB()
    statuses = ["new", "downloaded", "error", "transcribed", "summarized", "summarizing", "downloading", "transcribing", "new", None]
    sources = []
    for index, status in enumerate(statuses, 1):
        episode_id = ObjectId()
        text = f"Complete real transcript {index} with an explicit source claim."
        db.episodes._data.append({"_id": episode_id, "guid": f"youtube:episode-{index}", "title": f"Episode {index}", "status": status, "has_transcript": False})
        db.transcripts._data.append({"_id": ObjectId(), "episode_id": episode_id, "source": "youtube", "text": text, "segments": [{"start": 0, "end": 5, "text": text}]})
        sources.append({"id": f"S{index:02d}", "episode_id": str(episode_id), "title": f"Episode {index}", "full_text": text})
    outside_id = ObjectId()
    db.episodes._data.append({"_id": outside_id, "status": "new", "has_transcript": False, "title": "Outside authorized batch"})
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps({"sources": sources, "diagnostics": {"input_batch_frozen": True}}), encoding="utf-8")
    return db, path, outside_id, statuses


def test_reconciliation_repairs_only_the_frozen_ten_without_downgrading_active_or_summarized_work(tmp_path):
    db, path, outside_id, statuses = frozen_corpus(tmp_path)
    original_sources = json.loads(path.read_text(encoding="utf-8"))["sources"]
    original_transcripts = deepcopy(db.transcripts._data)
    outside = db.episodes.find_one({"_id": outside_id})

    records = reconcile_selected_sources(db, path)

    assert len(records) == 10
    assert all(record["has_transcript"] is True and record["transcript_source"] == "youtube" for record in records)
    assert [record["status"] for record in records] == ["transcribed", "transcribed", "transcribed", "transcribed", "summarized", "summarizing", "downloading", "transcribing", "transcribed", "transcribed"]
    assert [record["previous_status"] for record in records] == statuses
    assert db.episodes.find_one({"_id": outside_id}) == outside
    assert db.transcripts._data == original_transcripts
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["sources"] == original_sources
    assert manifest["diagnostics"]["input_batch_frozen"] is True


def test_reconciliation_verifies_all_ten_before_writing_any_episode(tmp_path):
    db, path, _, _ = frozen_corpus(tmp_path)
    db.transcripts._data[-1]["text"] = "A revised transcript no longer matches the frozen model input."
    original_episodes = deepcopy(db.episodes._data)
    original_manifest = path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="S10"):
        reconcile_selected_sources(db, path)

    assert db.episodes._data == original_episodes
    assert path.read_text(encoding="utf-8") == original_manifest


def test_reconciliation_cannot_expand_to_an_unfrozen_or_larger_batch(tmp_path):
    db, path, _, _ = frozen_corpus(tmp_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["sources"].append(dict(manifest["sources"][0], id="S11"))
    path.write_text(json.dumps(manifest), encoding="utf-8")
    original = deepcopy(db.episodes._data)

    with pytest.raises(ValueError, match="unique ten-source"):
        reconcile_selected_sources(db, path)

    assert db.episodes._data == original


def test_existing_transcript_is_never_overwritten_by_capture(tmp_path):
    db, _, _, _ = frozen_corpus(tmp_path)
    episode = db.episodes._data[0]
    original = deepcopy(db.transcripts._data)

    persisted = persist_transcript(db, episode, {"text": "Replacement model output must not replace the existing transcript."}, "external")

    assert persisted is False
    assert db.transcripts._data == original


def test_new_capture_sets_real_transcript_flags_and_preserves_summarized_state():
    db = MockDB()
    episode = {"_id": ObjectId(), "guid": "youtube:new-capture", "status": "summarized", "owner_id": "member-1"}
    db.episodes._data.append(dict(episode))

    assert persist_transcript(db, episode, {"text": "Complete captured speech, retained without rewriting.", "segments": [{"start": 0, "end": 8, "text": "Complete captured speech, retained without rewriting."}]}, "youtube") is True

    updated = db.episodes.find_one({"_id": episode["_id"]})
    assert updated["status"] == "summarized"
    assert updated["has_transcript"] is True
    assert updated["transcript_source"] == "youtube"
    assert db.transcripts.find_one({"episode_id": episode["_id"]})["text"] == "Complete captured speech, retained without rewriting."


def test_show_notes_without_explicit_transcript_link_are_excluded(monkeypatch):
    class ShowNotesPage:
        url = "https://example.com/episode"
        text = "<article>A very detailed episode introduction and promotional overview.</article><a href='/about'>About us</a>"

        def raise_for_status(self):
            return None

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: ShowNotesPage())

    with pytest.raises(ValueError, match="show notes were excluded"):
        fetch_linked_transcript({"link": "https://example.com/episode"})
