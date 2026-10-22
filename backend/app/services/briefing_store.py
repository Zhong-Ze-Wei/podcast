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
                *sorted(self.root.glob("reading-v*/editions"))]

    def _visible(self, report):
        """被新版本取代的报告不再出现在列表里，但文件保留便于追溯。"""
        if report.get("superseded_by"):
            return False
        return report.get("owner_id") in (None, self.owner_id)

    def supersede(self, directory, *, keep_id, owner_id, period_type, period_start, modes=None):
        """把同一周期（可选限定模式）的旧报告标记为已被 keep_id 取代。

        重新生成一期简报时，旧版本不该继续出现在页面和历史列表里，否则同一个
        周期会堆出十几份看起来一样的报告；文件本身保留，能追溯到当时的材料。
        """
        marked = []
        with _PUBLICATION_LOCK:
            for path in (self.root / directory).glob("*.json"):
                report = self._load(path)
                if not report or report.get("id") == keep_id:
                    continue
                if report.get("superseded_by"):
                    continue
                if (report.get("owner_id") or None) != (owner_id or None):
                    continue
                saved_period = report.get("period") or {}
                if (saved_period.get("type"), saved_period.get("start")) != (period_type, period_start):
                    continue
                if modes is not None and report.get("mode") not in modes:
                    continue
                report["superseded_by"] = keep_id
                write_json(path, report)
                if self.db is not None:
                    self.db.briefing_reports.update_one(
                        {"report_id": report["id"]}, {"$set": {"superseded_by": keep_id}})
                marked.append(report["id"])
        return marked

    def _index(self, path, report):
        metadata = {key: deepcopy(report[key]) for key in REPORT_FIELDS if key in report}
        metadata.update(report_id=report["id"], owner_id=report.get("owner_id"), path=path.relative_to(self.root).as_posix())
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
                if self.db is not None and path.parent.name != "sources":
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
            # 清理未发布记录及早期误登记的单篇缓存；不删除原始文件。
            directories = set(self._directories())
            for indexed in self.db.briefing_reports.find({}):
                path = self.root / indexed["path"].replace("\\", "/")
                if path.parent not in directories or not path.is_file():
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
