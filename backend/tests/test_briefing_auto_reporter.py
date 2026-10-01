"""自动报告的周期边界、持久去重、重启与账户开关。"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import Lock

import pytest
from flask import Flask

from app.services.briefing_auto_reporter import BriefingAutoReporter, closed_period
from tests.auth_helpers import add_user
from tests.conftest import MockCollection, MockDB


class Runs(MockCollection):
    def __init__(self):
        super().__init__("briefing_auto_runs")
        self.lock = Lock()

    def update_one(self, query, update, **options):
        with self.lock:
            index = next((i for i, item in enumerate(self._data) if self._match(item, query)), None)
            if index is None:
                if not options.get("upsert"):
                    return
                self._data.append({**query, **deepcopy(update.get("$setOnInsert", {}))})
                index = len(self._data) - 1
            self._data[index].update(deepcopy(update.get("$set", {})))
            for key, value in update.get("$inc", {}).items():
                self._data[index][key] = self._data[index].get(key, 0) + value

    def find_one_and_update(self, query, update, **options):
        with self.lock:
            for item in self._data:
                if self._match(item, query):
                    item.update(deepcopy(update.get("$set", {})))
                    for key, value in update.get("$inc", {}).items():
                        item[key] = item.get(key, 0) + value
                    return deepcopy(item)


class Queue:
    def __init__(self):
        self.tasks = {}

    def submit(self, **options):
        identifier = "task-" + str(len(self.tasks) + 1)
        self.tasks[identifier] = {**options, "status": "pending"}
        return identifier

    def get_status(self, identifier):
        return self.tasks.get(identifier)

    def run(self, identifier):
        options = self.tasks[identifier]
        options["status"] = "processing"
        result = options["func"](run_id=options["run_id"], user_id=options["user_id"], period=options["period"])
        options.update(status="completed", result=result)
        return result


@pytest.fixture
def setup():
    db = MockDB()
    db.briefing_auto_runs = Runs()
    app = Flask(__name__)
    app.db = db
    app.config["AI_ANALYSIS_ENABLED"] = True
    user = add_user(db, "automatic@example.com")
    db.users.update_one({"_id": user["_id"]}, {"$set": {
        "briefing_auto_period": "week", "briefing_auto_enabled_at": datetime(2026, 10, 1),
        "briefing_interests": [{"label": "AI", "enabled": True}],
    }})
    queue = Queue()
    reporter = BriefingAutoReporter(db, queue)
    generated = []

    class Scope:
        def collect(self, kind, start):
            prefs = db.users.find_one({"_id": user["_id"]})["briefing_interests"]
            return {"corpus": {"sources": [{"full_text": "真实正文"}]}, "selection_key": "body-key",
                    "interests": [item["label"] for item in prefs if item["enabled"]], "period": {"type": kind, "start": start}}

    class Modes:
        reports = {key: None for key in ("core", "quotes", "connections", "concepts", "resources")}

        def snapshot(self, scope):
            return {"reports": self.reports}

        def generate(self, **options):
            generated.append(options)
            return {"reports": {key: {"id": key} for key in self.reports}}

    scope, modes = Scope(), Modes()
    reporter._services = lambda owner: (scope, modes)
    with app.app_context():
        yield db, user, reporter, queue, generated, modes


def test_natural_periods_wait_five_minutes_in_hong_kong():
    assert closed_period("week", datetime(2026, 10, 4, 16, 4, tzinfo=timezone.utc)) is None
    assert closed_period("week", datetime(2026, 10, 4, 16, 5, tzinfo=timezone.utc))["start"] == "2026-09-28"
    assert closed_period("month", datetime(2026, 10, 31, 16, 5, tzinfo=timezone.utc))["start"] == "2026-10-01"
    assert closed_period("month", datetime(2026, 12, 31, 16, 5, tzinfo=timezone.utc))["start"] == "2026-12-01"


def test_enabling_does_not_generate_period_ended_before_opt_in(setup):
    db, user, reporter, queue, generated, modes = setup
    assert reporter.check_due(datetime(2026, 10, 1, 10, tzinfo=timezone.utc)) == []
    assert queue.tasks == {}


def test_closed_week_submits_once_and_reads_latest_interests(setup):
    db, user, reporter, queue, generated, modes = setup
    now = datetime(2026, 10, 4, 16, 5, tzinfo=timezone.utc)
    identifier, = reporter.check_due(now)
    assert reporter.check_due(now + timedelta(minutes=5)) == []
    db.users.update_one({"_id": user["_id"]}, {"$set": {"briefing_interests": [{"label": "机器人", "enabled": True}]}})
    queue.run(identifier)
    assert generated[0]["mode"] == "all"
    assert generated[0]["scope"]["interests"] == ["机器人"]
    assert generated[0]["scope"]["period"]["start"] == "2026-09-28"
    assert reporter.check_due(now + timedelta(days=1)) == []
    assert db.briefing_auto_runs.find_one({"owner_id": str(user["_id"])})["status"] == "completed"


def test_account_and_global_switches_prevent_new_work(setup):
    db, user, reporter, queue, generated, modes = setup
    now = datetime(2026, 10, 4, 16, 5, tzinfo=timezone.utc)
    db.settings.insert_one({"_id": "ai_analysis", "enabled": False})
    # MockCollection生成自己的_id，按此mock的实际文档更新。
    db.settings._data[0]["_id"] = "ai_analysis"
    assert reporter.check_due(now) == []
    db.settings.update_one({"_id": "ai_analysis"}, {"$set": {"enabled": True}})
    db.users.update_one({"_id": user["_id"]}, {"$set": {"briefing_auto_period": None}})
    assert reporter.check_due(now) == []
    assert generated == []


def test_queued_report_is_cancelled_if_account_turns_it_off(setup):
    db, user, reporter, queue, generated, modes = setup
    identifier, = reporter.check_due(datetime(2026, 10, 4, 16, 5, tzinfo=timezone.utc))
    db.users.update_one({"_id": user["_id"]}, {"$set": {"briefing_auto_period": None}})
    assert queue.run(identifier) == {"cancelled": True}
    assert generated == []


def test_reenabling_after_period_end_does_not_revive_an_old_queued_report(setup):
    db, user, reporter, queue, generated, modes = setup
    now = datetime(2026, 10, 4, 16, 5, tzinfo=timezone.utc)
    identifier, = reporter.check_due(now)
    db.users.update_one({"_id": user["_id"]}, {"$set": {"briefing_auto_enabled_at": now.replace(tzinfo=None)}})
    assert queue.run(identifier) == {"cancelled": True}
    assert generated == []


def test_manual_report_task_blocks_automatic_duplicate(setup):
    db, user, reporter, queue, generated, modes = setup
    db.tasks.insert_one({"owner_id": str(user["_id"]), "task_type": "briefing-report", "status": "processing"})
    assert reporter.check_due(datetime(2026, 10, 4, 16, 5, tzinfo=timezone.utc)) == []


def test_saved_complete_report_does_not_call_model(setup):
    db, user, reporter, queue, generated, modes = setup
    modes.reports = {key: {"id": key} for key in modes.reports}
    now = datetime(2026, 10, 4, 16, 5, tzinfo=timezone.utc)
    assert reporter.check_due(now) == []
    assert reporter.check_due(now) == []
    assert generated == []


def test_restart_recovers_stale_claim_and_caps_attempts(setup):
    db, user, reporter, queue, generated, modes = setup
    now = datetime(2026, 10, 4, 16, 5, tzinfo=timezone.utc)
    reporter.check_due(now)
    queue.tasks.clear()
    assert reporter.check_due(now + timedelta(minutes=50)) == []
    assert len(reporter.check_due(now + timedelta(hours=1))) == 1
    queue.tasks.clear()
    assert len(reporter.check_due(now + timedelta(hours=2))) == 1
    queue.tasks.clear()
    assert reporter.check_due(now + timedelta(hours=3)) == []
    assert db.briefing_auto_runs._data[0]["attempts"] == 3


def test_month_and_week_have_distinct_durable_runs(setup):
    db, user, reporter, queue, generated, modes = setup
    now = datetime(2026, 11, 1, 9, tzinfo=timezone.utc)
    identifier, = reporter.check_due(now)
    queue.run(identifier)
    db.users.update_one({"_id": user["_id"]}, {"$set": {"briefing_auto_period": "month"}})
    month_id, = reporter.check_due(now)
    queue.run(month_id)
    assert generated[1]["scope"]["period"] == {"type": "month", "start": "2026-10-01"}
    assert db.briefing_auto_runs.count_documents({}) == 2
