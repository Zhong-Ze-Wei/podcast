"""周期结束后生成账号的简报，复用现有队列与正文筛选流程。"""
import logging
import threading
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument

from .ai_control import AI_DISABLED_MESSAGE, is_ai_analysis_enabled
from .briefing_modes_service import BriefingModesService
from .briefing_report_service import BriefingReportService
from .briefing_scope_service import BriefingScopeService, HONG_KONG, calendar_period
from .task_queue import task_queue
from .briefing_task_service import report_task_conflicts


logger = logging.getLogger(__name__)


def closed_period(period_type, now):
    """香港时间零点后五分钟，最近结束的自然周或自然月才到期。"""
    local = now.astimezone(HONG_KONG)
    current = calendar_period(period_type, today=local.date())
    end = datetime.fromisoformat(current["start"]).replace(tzinfo=HONG_KONG)
    if local < end + timedelta(minutes=5):
        return None
    return calendar_period(period_type, (end.date() - timedelta(days=1)).isoformat(), today=local.date())


class BriefingAutoReporter:
    def __init__(self, db, queue=task_queue):
        self.db = db
        self.queue = queue

    def check_due(self, now=None):
        if not is_ai_analysis_enabled():
            return []
        now = now or datetime.now(timezone.utc)
        utc_now = now.astimezone(timezone.utc).replace(tzinfo=None)
        submitted = []
        users = self.db.users.find({"status": "active", "briefing_auto_period": {"$in": ["week", "month"]}})
        for user in users:
            period = closed_period(user["briefing_auto_period"], now)
            if period is None:
                continue
            end = datetime.fromisoformat(period["end"]).replace(tzinfo=HONG_KONG).astimezone(timezone.utc).replace(tzinfo=None)
            enabled_at = user.get("briefing_auto_enabled_at")
            if enabled_at is None or end < enabled_at:
                continue
            owner = str(user["_id"])
            active_tasks = self.db.tasks.find({"owner_id": owner, "task_type": "briefing-report", "status": {"$in": ["pending", "processing"]}})
            if any(report_task_conflicts(task, owner, period) for task in active_tasks):
                continue
            run_id = f"{owner}:{period['type']}:{period['start']}"
            run = self.db.briefing_auto_runs.find_one({"_id": run_id})
            if run and run["status"] in ("queued", "processing"):
                task = self.queue.get_status(run.get("task_id")) if run.get("task_id") else None
                if task and task["status"] == "completed":
                    self.db.briefing_auto_runs.update_one({"_id": run_id}, {"$set": {"status": "completed"}})
                    continue
                if task and task["status"] in ("pending", "processing"):
                    continue
                if run["lease_until"] > utc_now:
                    continue
                self.db.briefing_auto_runs.update_one({"_id": run_id}, {"$set": {"status": "failed", "next_retry_at": utc_now}})
                run = self.db.briefing_auto_runs.find_one({"_id": run_id})
            if run and (run["status"] in ("completed", "cancelled") or run["attempts"] >= 3 or run["next_retry_at"] > utc_now):
                continue
            scope_service, modes = self._services(owner)
            scope = scope_service.collect(period["type"], period["start"])
            if not scope["corpus"]["sources"]:
                continue
            if all(modes.snapshot(scope=scope)["reports"].values()):
                self.db.briefing_auto_runs.update_one({"_id": run_id}, {"$set": {"status": "completed"}}, upsert=True)
                continue
            self.db.briefing_auto_runs.update_one({"_id": run_id}, {"$setOnInsert": {
                "owner_id": owner, "period": period, "status": "ready", "attempts": 0, "next_retry_at": utc_now,
            }}, upsert=True)
            claimed = self.db.briefing_auto_runs.find_one_and_update(
                {"_id": run_id, "status": {"$in": ["ready", "failed"]}, "attempts": {"$lt": 3}, "next_retry_at": {"$lte": utc_now}},
                {"$set": {"status": "queued", "lease_until": utc_now + timedelta(hours=1), "updated_at": utc_now}, "$inc": {"attempts": 1}},
                return_document=ReturnDocument.AFTER,
            )
            if claimed is None:
                continue
            task_id = self.queue.submit(
                task_type="briefing-report", owner_id=owner, func=self._generate,
                report_period=period,
                run_id=run_id, user_id=user["_id"], period=period,
                on_failure=lambda error, identifier=run_id: self._failed(identifier, error),
            )
            self.db.briefing_auto_runs.update_one({"_id": run_id}, {"$set": {"task_id": task_id}})
            submitted.append(task_id)
        return submitted

    def _services(self, owner):
        report = BriefingReportService(owner_id=owner)
        scope_service = BriefingScopeService(self.db, report, owner)
        modes = BriefingModesService(owner_id=owner, report_service=report, scope_service=scope_service)
        return scope_service, modes

    def _generate(self, run_id, user_id, period, progress_callback=None):
        user = self.db.users.find_one({"_id": user_id})
        end = datetime.fromisoformat(period["end"]).replace(tzinfo=HONG_KONG).astimezone(timezone.utc).replace(tzinfo=None)
        if user is None or user.get("status") != "active" or user.get("briefing_auto_period") != period["type"] or not user.get("briefing_auto_enabled_at") or user["briefing_auto_enabled_at"] > end:
            self.db.briefing_auto_runs.update_one({"_id": run_id}, {"$set": {"status": "cancelled"}})
            return {"cancelled": True}
        if not is_ai_analysis_enabled():
            raise RuntimeError(AI_DISABLED_MESSAGE)
        self.db.briefing_auto_runs.update_one({"_id": run_id}, {"$set": {"status": "processing"}})
        scope_service, modes = self._services(str(user_id))
        scope = scope_service.collect(period["type"], period["start"])
        result = modes.generate(mode="all", scope=scope, progress_callback=progress_callback)
        self.db.briefing_auto_runs.update_one({"_id": run_id}, {"$set": {
            "status": "completed", "completed_at": datetime.utcnow(), "selection_key": scope["selection_key"],
        }})
        return result

    def _failed(self, run_id, error):
        self.db.briefing_auto_runs.update_one({"_id": run_id}, {"$set": {
            "status": "failed", "error": str(error), "next_retry_at": datetime.utcnow() + timedelta(hours=1),
        }})


_stop = threading.Event()
_thread = None


def start_auto_reporter(app):
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    reporter = BriefingAutoReporter(app.db)

    def run():
        if _stop.wait(30):
            return
        while not _stop.is_set():
            try:
                with app.app_context():
                    reporter.check_due()
            except Exception:
                logger.exception("自动简报检查失败，下次检查继续")
            _stop.wait(300)

    _thread = threading.Thread(target=run, name="briefing-auto-reporter", daemon=True)
    _thread.start()


def stop_auto_reporter():
    _stop.set()
    if _thread:
        _thread.join(timeout=5)
