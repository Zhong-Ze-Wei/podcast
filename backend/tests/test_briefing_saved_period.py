"""缓存指纹变化不能让已发布的自然周期报告消失，也不能混入其他账号或周期。"""
from copy import deepcopy
from datetime import datetime
import uuid

from app.services.briefing_modes_service import BriefingModesService
from tests.test_briefing_scope import scope_service, add_episode, TEXT


def publish(modes, scope, mode="connections", generated_at="2026-10-01T15:30:00+00:00", **changes):
    report = {"id": uuid.uuid4().hex, "owner_id": modes.owner_id, "mode": mode,
              "corpus_id": "previous-material", "selection_key": "previous-analysis-policy",
              "period": deepcopy(scope["period"]), "generated_at": generated_at,
              "sections": [{"items": [{"id": "saved-view", "text": "已付费生成的原报告", "evidence": []}]}],
              "sources": [], **changes}
    modes.report_service.store.publish(report, "content-modes-v1/reports")
    return report


def test_saved_month_survives_configuration_material_and_interest_changes_without_model_call(tmp_path, monkeypatch):
    collector = scope_service(tmp_path)
    episode, _ = add_episode(collector.db, datetime(2026, 9, 29), "september", TEXT)
    modes = BriefingModesService(owner_id=collector.owner_id, report_service=collector.report_service, scope_service=collector)
    before = collector.collect("month", "2026-09-01")
    saved = publish(modes, before)
    path = modes.root / "reports" / (saved["id"] + ".json")
    original = path.read_bytes()
    collector.db.transcripts.update_one({"episode_id": episode["_id"]}, {"$set": {"text": TEXT + "已补全字幕。"}})
    current = collector.collect("month", "2026-09-01", ["机器人"])
    monkeypatch.setattr(collector.report_service.lab, "_model_call", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Reading saved reports must not call a model")))
    displayed = modes.snapshot(scope=current)["reports"]["connections"]
    assert displayed["id"] == saved["id"]
    assert displayed["sections"] == saved["sections"]
    assert displayed["period"] == saved["period"]
    assert displayed["matches_current_selection"] is False
    assert path.read_bytes() == original


def test_saved_report_lookup_does_not_cross_account_period_type_or_month(tmp_path):
    collector = scope_service(tmp_path)
    modes = BriefingModesService(owner_id=collector.owner_id, report_service=collector.report_service)
    scope = collector.collect("month", "2026-09-01")
    publish(modes, scope, owner_id="another-owner")
    publish(modes, scope, owner_id=None)
    publish(modes, scope, period={**scope["period"], "type": "week"})
    publish(modes, scope, period={**scope["period"], "start": "2026-08-01"})
    assert modes.snapshot(scope=scope)["reports"]["connections"] is None


def test_exact_selection_is_preferred_and_otherwise_the_latest_saved_version_is_used(tmp_path):
    collector = scope_service(tmp_path)
    modes = BriefingModesService(owner_id=collector.owner_id, report_service=collector.report_service)
    scope = collector.collect("month", "2026-09-01")
    matching = publish(modes, scope, selection_key=scope["selection_key"])
    newest = publish(modes, scope, generated_at="2026-10-02T15:30:00+00:00")
    assert modes.snapshot(scope=scope)["reports"]["connections"]["id"] == matching["id"]
    scope["selection_key"] = "changed-again"
    assert modes.snapshot(scope=scope)["reports"]["connections"]["id"] == newest["id"]
