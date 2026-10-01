"""不可变报告文件及可补建的历史索引；与任务 TTL 分开保存。"""
from copy import deepcopy
import json
import logging
from pathlib import Path
import re
from threading import RLock

from .briefing_lab_service import read_json, write_json


logger = logging.getLogger(__name__)
_PUBLICATION_LOCK = RLock()
REPORT_FIELDS = ("id", "owner_id", "generated_at", "title", "mode", "variant", "topic", "period", "corpus_id", "selection_key", "coverage")


class BriefingStore:
    def __init__(self, root, db=None, owner_id=None):
        self.root = Path(root)
        self.db = db
        self.owner_id = owner_id

    def _directories(self):
        return [self.root / "reports", self.root / "content-modes-v1" / "reports",
                *sorted(self.root.glob("reading-v*/editions")), *sorted(self.root.glob("reading-v*/sources"))]

    def _visible(self, report):
        return report.get("owner_id") in (None, self.owner_id)

    def _index(self, path, report):
        metadata = {key: deepcopy(report[key]) for key in REPORT_FIELDS if key in report}
        metadata.update(report_id=report["id"], owner_id=report.get("owner_id"), path=str(path.relative_to(self.root)))
        self.db.briefing_reports.update_one({"report_id": report["id"]}, {"$set": metadata}, upsert=True)

    def publish(self, report, directory):
        if not re.fullmatch(r"[a-f0-9]{32}", report["id"]):
            raise ValueError("报告编号无效")
        path = self.root / directory / (report["id"] + ".json")
        with _PUBLICATION_LOCK:
            if path.exists():
                raise ValueError("已发布报告不可覆盖")
            try:
                write_json(path, report)
                if self.db is not None:
                    self._index(path, report)
            except Exception:
                # 新版本发布失败不能进入目录扫描，也不能影响旧 UUID 文件。
                path.unlink(missing_ok=True)
                raise
        return report

    def _load(self, path):
        try:
            return read_json(path)
        except (OSError, json.JSONDecodeError):
            logger.warning("跳过无法读取的历史简报：%s", path.name)
            return None

    def reports(self, directory):
        with _PUBLICATION_LOCK:
            return [report for path in (self.root / directory).glob("*.json")
                    if (report := self._load(path)) is not None and self._visible(report)]

    def all_reports(self):
        with _PUBLICATION_LOCK:
            return [report for directory in self._directories() for path in directory.glob("*.json")
                    if re.fullmatch(r"[a-f0-9]{32}", path.stem)
                    and (report := self._load(path)) is not None and self._visible(report)]

    def report(self, report_id):
        if not isinstance(report_id, str) or not re.fullmatch(r"[a-f0-9]{32}", report_id):
            return None
        with _PUBLICATION_LOCK:
            for directory in self._directories():
                path = directory / (report_id + ".json")
                if path.is_file():
                    report = self._load(path)
                    return report if report is not None and self._visible(report) else None
        return None

    def rebuild_index(self):
        with _PUBLICATION_LOCK:
            # Mongo 写入响应丢失时可能留下已登记、文件未发布的记录。
            for indexed in self.db.briefing_reports.find({}):
                if not (self.root / indexed["path"]).is_file():
                    self.db.briefing_reports.delete_one({"report_id": indexed["report_id"]})
            for directory in self._directories():
                for path in directory.glob("*.json"):
                    if not re.fullmatch(r"[a-f0-9]{32}", path.stem):
                        continue
                    if self.db.briefing_reports.find_one({"report_id": path.stem}) is not None:
                        continue
                    report = self._load(path)
                    if report is not None and report.get("id") == path.stem:
                        self._index(path, report)

    def history(self, page, per_page, period_type=None, period_start=None, mode=None):
        self.rebuild_index()
        query = {"owner_id": {"$in": [self.owner_id, None]}}
        if period_type is not None:
            query["period.type"] = period_type
        if period_start is not None:
            query["period.start"] = period_start
        if mode is not None:
            query["mode"] = mode
        total = self.db.briefing_reports.count_documents(query)
        rows = self.db.briefing_reports.find(query).sort([("generated_at", -1), ("report_id", -1)]).skip((page - 1) * per_page).limit(per_page)
        return [{key: row[key] for key in REPORT_FIELDS if key in row} for row in rows], total
