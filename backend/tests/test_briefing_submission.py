"""真实线程同时提交时，手动和自动简报只排队一次。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier, Event, Lock

import pytest

from app.api import briefing_reports as api
from app.services.briefing_auto_reporter import BriefingAutoReporter
from app.services.briefing_reading_service import BriefingReadingService
from app.services.task_queue import TaskQueue
from app.services import briefing_task_service as submission
from tests.test_briefing_scope import client, add_episode, TEXT
from tests.test_briefing_auto_reporter import Queue, Runs, setup


class BlockingQueue(Queue):
    def __init__(self, db=None):
        super().__init__()
        self.db = db
        self.lock = Lock()
        self.entered = Event()
        self.release = Event()
        self.second_submit = Event()
        self.submissions = 0

    def submit(self, **options):
        with self.lock:
            self.submissions += 1
            number = self.submissions
        if number == 1:
            self.entered.set()
            assert self.release.wait(5), "test must release the first submit"
        else:
            self.second_submit.set()
        with self.lock:
            identifier = super().submit(**options)
            if self.db is not None:
                self.db.tasks.insert_one({"task_id": identifier, "task_type": options["task_type"],
                    "owner_id": options["owner_id"], "status": "pending",
                    **({"report_period": options["report_period"]} if options.get("report_period") else {})})
            return identifier

    def get_all_tasks(self, **options):
        with self.lock:
            return list(super().get_all_tasks(**options))


@pytest.fixture
def requests(client, monkeypatch):
    app, http, headers, scope = client
    app.config["AI_ANALYSIS_ENABLED"] = True
    episode, _ = add_episode(app.db, datetime(2026, 9, 29), "atomic-source", TEXT)
    sid = "ep" + str(episode["_id"])
    scope.report_service._corpus = {"sources": [scope.source(sid)]}
    app.db.briefing_auto_runs = Runs()
    queue = BlockingQueue(app.db)
    monkeypatch.setattr(api, "task_queue", queue)
    monkeypatch.setattr(api, "is_ai_analysis_enabled", lambda: True)
    monkeypatch.setattr(api, "BriefingReportService", lambda **options: scope.report_service)
    monkeypatch.setattr(api, "BriefingReadingService", lambda **options: BriefingReadingService(
        owner_id=scope.owner_id, report_service=scope.report_service))
    monkeypatch.setattr(scope.report_service.lab, "_model_call", lambda *args, **kwargs: pytest.fail("submit must not generate"))
    return app, headers, scope, sid, queue


@pytest.mark.parametrize("path,body", [
    ("/modes/generate", {"mode": "core", "period_type": "week", "period_start": "2026-09-28"}),
    ("/reading/{sid}/generate", {}), ("/edition/generate", {}), ("/generate", {}),
])
def test_concurrent_manual_requests_enqueue_only_once(requests, path, body):
    app, headers, scope, sid, queue = requests
    barrier = Barrier(3)

    def post():
        barrier.wait(timeout=5)
        return app.test_client().post("/api/briefing-reports" + path.format(sid=sid), headers=headers, json=body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(post), pool.submit(post)]
        barrier.wait(timeout=5)
        try:
            assert queue.entered.wait(5)
            queue.second_submit.wait(0.3)
        finally:
            queue.release.set()
        statuses = sorted(future.result(timeout=5).status_code for future in futures)
    assert statuses == [202, 409]
    assert queue.submissions == 1


@pytest.mark.parametrize("first", ["manual", "automatic"])
def test_manual_and_automatic_requests_share_the_submission_boundary(requests, first):
    app, headers, scope, sid, queue = requests
    app.db.users.update_one({"_id": app.db.users._data[0]["_id"]}, {"$set": {
        "briefing_auto_period": "week", "briefing_auto_enabled_at": datetime(2026, 10, 1)}})
    reporter = BriefingAutoReporter(app.db, queue)

    class Modes:
        def snapshot(self, scope):
            return {"reports": {name: None for name in ("core", "quotes", "connections", "concepts", "resources")}}

    reporter._services = lambda owner: (scope, Modes())
    now = datetime(2026, 10, 4, 16, 5, tzinfo=timezone.utc)

    def automatic():
        with app.app_context():
            return reporter.check_due(now)

    def manual():
        return app.test_client().post("/api/briefing-reports/modes/generate", headers=headers,
            json={"mode": "core", "period_type": "week", "period_start": "2026-09-28"})

    operations = {"manual": manual, "automatic": automatic}
    with ThreadPoolExecutor(max_workers=2) as pool:
        leading = pool.submit(operations[first])
        try:
            assert queue.entered.wait(5)
            following = pool.submit(operations["automatic" if first == "manual" else "manual"])
            queue.second_submit.wait(0.3)
        finally:
            queue.release.set()
        leading_result, following_result = leading.result(timeout=5), following.result(timeout=5)
    manual_result = leading_result if first == "manual" else following_result
    automatic_result = leading_result if first == "automatic" else following_result
    assert queue.submissions == 1
    assert manual_result.status_code == (202 if first == "manual" else 409)
    assert len(automatic_result) == (0 if first == "manual" else 1)
    if first == "manual":
        run = app.db.briefing_auto_runs.find_one({"owner_id": scope.owner_id})
        assert run is None or (run["status"] == "ready" and run["attempts"] == 0)


@pytest.mark.parametrize("active_owner,active_period,expected", [
    ("mine", {"type": "week", "start": "2026-09-28"}, None),
    ("mine", None, None),
    ("other", {"type": "week", "start": "2026-09-28"}, "task-2"),
    ("mine", {"type": "month", "start": "2026-09-01"}, "task-2"),
])
def test_business_submission_keeps_owner_period_and_legacy_conflict_rules(active_owner, active_period, expected):
    queue = BlockingQueue()
    queue.release.set()
    queue.tasks["existing"] = {"owner_id": active_owner, "report_period": active_period,
                               "task_type": "briefing-report", "status": "processing"}
    result = submission.submit_report_task(queue, owner_id="mine", func=lambda: None,
        report_period={"type": "week", "start": "2026-09-28"})
    assert result == expected
    assert queue.submissions == (expected is not None)


def test_automatic_submit_failure_releases_claim_without_consuming_an_attempt(setup, monkeypatch):
    db, user, reporter, queue, generated, modes = setup
    now = datetime(2026, 10, 4, 16, 5, tzinfo=timezone.utc)
    original_submit = queue.submit

    def fail(**options):
        raise RuntimeError("executor closed")

    monkeypatch.setattr(queue, "submit", fail)
    with pytest.raises(RuntimeError, match="executor closed"):
        reporter.check_due(now)
    run = db.briefing_auto_runs.find_one({"owner_id": str(user["_id"])})
    assert run["status"] == "ready"
    assert run["attempts"] == 0
    assert run["next_retry_at"] <= now.replace(tzinfo=None)
    monkeypatch.setattr(queue, "submit", original_submit)
    assert len(reporter.check_due(now)) == 1
    assert db.briefing_auto_runs._data[0]["attempts"] == 1
    assert generated == []


def test_running_report_does_not_hold_the_business_submission_lock():
    queue = TaskQueue(max_workers=1)
    started, finish = Event(), Event()

    def generate(progress_callback=None):
        started.set()
        assert finish.wait(5)
        return {"report": "saved"}

    try:
        first = submission.submit_report_task(queue, owner_id="mine", func=generate,
            report_period={"type": "week", "start": "2026-09-28"})
        assert started.wait(5)
        second = submission.submit_report_task(queue, owner_id="mine", func=generate,
            report_period={"type": "week", "start": "2026-10-05"})
        assert first != second and second is not None
        assert queue.get_status(first)["status"] == "processing"
        assert queue.get_status(second)["status"] == "pending"
    finally:
        finish.set()
        queue.shutdown()
    assert queue.get_status(first)["status"] == "completed"
    assert queue.get_status(second)["status"] == "completed"
