"""单篇解读保留来源缓存职责，不能被当作可导出的整份简报。"""
import pytest
from pymongo.errors import PyMongoError

from app.services.briefing_store import BriefingStore
from app.services.briefing_reading_service import BriefingReadingService
from app.services.briefing_report_service import BriefingReportService
from tests.conftest import MockDB


def single_reading():
    return {"id": "b" * 32, "owner_id": "owner", "source_id": "S01", "corpus_id": "corpus",
            "generated_at": "2026-10-01T00:00:00+00:00", "points": [], "takeaway": "单篇解读"}


def test_single_reading_remains_readable_but_is_not_a_report(tmp_path):
    db = MockDB()
    service = BriefingReportService(tmp_path, owner_id="owner", db=db)
    value = single_reading()
    service.store.publish(value, "reading-v1/sources")
    reading = BriefingReadingService(owner_id="owner", report_service=service)
    assert reading._latest("sources", "corpus", source_id="S01") == value
    assert service.report(value["id"]) is None
    assert service.store.history(1, 20) == ([], 0)


def test_rebuild_removes_previous_source_cache_index_without_removing_file(tmp_path):
    db = MockDB()
    store = BriefingStore(tmp_path, db, "owner")
    value = single_reading()
    store.publish(value, "reading-v1/sources")
    db.briefing_reports.update_one({"report_id": value["id"]}, {"$set": {
        "id": value["id"], "owner_id": "owner", "generated_at": value["generated_at"],
        "path": "reading-v1/sources/" + value["id"] + ".json",
    }}, upsert=True)
    store.rebuild_index()
    assert db.briefing_reports.count_documents({}) == 0
    assert store.reports("reading-v1/sources") == [value]


def test_source_cache_does_not_depend_on_report_index_availability(tmp_path, monkeypatch):
    db = MockDB()
    store = BriefingStore(tmp_path, db, "owner")
    def fail(*args, **kwargs):
        raise PyMongoError("report index unavailable")
    monkeypatch.setattr(db.briefing_reports, "update_one", fail)
    value = single_reading()
    store.publish(value, "reading-v1/sources")
    assert store.reports("reading-v1/sources") == [value]
