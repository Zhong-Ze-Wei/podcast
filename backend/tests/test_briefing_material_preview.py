import hashlib

from app.services.briefing_lab_service import write_json
from app.services.briefing_material_preview import saved_analysis_previews


def test_saved_preview_matches_text_and_reuses_the_newest_overview(tmp_path):
    text = "节目正文，不能仅凭标题复用另一期的分析。"
    source = {"id": "ep-first", "episode_id": "first", "full_text": text}
    identity = {"text_hash": hashlib.sha256(text.encode()).hexdigest()}
    cache = tmp_path / "episode-analysis"
    write_json(cache / "first.json", {"identity": identity, "takeaway": "旧导读", "generated_at": "2026-10-01"})
    write_json(cache / "latest.json", {"identity": identity, "takeaway": "新导读", "generated_at": "2026-10-07"})
    write_json(cache / "wrong-text.json", {"identity": {"text_hash": "other"}, "takeaway": "不属于本期", "generated_at": "2026-10-08"})
    assert saved_analysis_previews(tmp_path, [source, {**source, "id": "ep-copy"}]) == {"ep-first": "新导读", "ep-copy": "新导读"}


def test_no_saved_overview_does_not_generate_one_and_can_use_saved_topic_summaries(tmp_path):
    source = {"id": "ep-one", "episode_id": "one", "full_text": "正文"}
    assert saved_analysis_previews(tmp_path, [source]) == {}
    write_json(tmp_path / "episode-analysis" / "saved.json", {
        "identity": {"text_hash": hashlib.sha256(source["full_text"].encode()).hexdigest()},
        "points": [{"meaning": "第一个议题"}, {"meaning": "第二个议题"}],
    })
    assert saved_analysis_previews(tmp_path, [source]) == {"ep-one": "第一个议题；第二个议题"}


def test_legacy_source_numbers_are_matched_by_episode_and_private_readings_are_not_exposed(tmp_path):
    source = {"id": "ep-one", "episode_id": "one", "full_text": "正文"}
    saved = {"source_id": "S04", "source": {"episode_id": "one"}, "takeaway": "本人的旧版导读", "owner_id": "current", "generated_at": "2026-10-01"}
    write_json(tmp_path / "reading-v1" / "sources" / "own.json", saved)
    write_json(tmp_path / "reading-v1" / "sources" / "other.json", {**saved, "owner_id": "other", "takeaway": "另一用户的导读", "generated_at": "2026-10-07"})
    assert saved_analysis_previews(tmp_path, [source], "current") == {"ep-one": "本人的旧版导读"}
    assert saved_analysis_previews(tmp_path, [source], "unrelated") == {}
