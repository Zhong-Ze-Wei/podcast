"""按账号保存简报条目快照；旧收藏只从可读历史中恢复。"""
from copy import deepcopy
import json
import re

from .briefing_lab_service import now_iso


FAVORITE_FIELDS = ("item_id", "report_id", "item", "report", "created_at")


def valid_item_id(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", value) is not None


def report_items(report):
    def children(items):
        for item in items:
            yield item
            yield from children(item.get("children", []))
    for section in report.get("sections", []):
        yield from children(section.get("items", []))


class BriefingFavorites:
    def __init__(self, db, store, owner_id):
        self.db = db
        self.store = store
        self.owner_id = owner_id

    @staticmethod
    def _response(document):
        return {key: deepcopy(document[key]) for key in FAVORITE_FIELDS}

    def _existing(self, item_id):
        return self.db.briefing_favorites.find_one({"owner_id": self.owner_id, "item_id": item_id})

    def _save(self, item_id, item, report):
        snapshot = {key: deepcopy(report[key]) for key in ("id", "title", "mode", "variant", "generated_at", "period", "topic", "sources") if key in report}
        document = {"owner_id": self.owner_id, "item_id": item_id, "report_id": report["id"],
                    "item": deepcopy(item), "report": snapshot, "created_at": now_iso()}
        self.db.briefing_favorites.update_one({"owner_id": self.owner_id, "item_id": item_id}, {"$setOnInsert": document}, upsert=True)
        return self._response(self._existing(item_id))

    def save(self, item_id, report_id):
        existing = self._existing(item_id)
        if existing is not None:
            return self._response(existing)
        report = self.store.report(report_id)
        item = next((item for item in report_items(report) if item.get("id") == item_id), None) if report else None
        return self._save(item_id, item, report) if item is not None else None

    def delete(self, item_id):
        result = self.db.briefing_favorites.delete_one({"owner_id": self.owner_id, "item_id": item_id})
        return {"item_id": item_id, "deleted": result.deleted_count > 0}

    def list(self, page, per_page, period_type=None, period_start=None, mode=None):
        query = {"owner_id": self.owner_id}
        if period_type is not None:
            query["report.period.type"] = period_type
        if period_start is not None:
            query["report.period.start"] = period_start
        if mode is not None:
            query["report.mode"] = mode
        total = self.db.briefing_favorites.count_documents(query)
        rows = self.db.briefing_favorites.find(query).sort([("created_at", -1), ("item_id", -1)]).skip((page - 1) * per_page).limit(per_page)
        return [self._response(row) for row in rows], total

    @staticmethod
    def _identity(item, report):
        source_ids = {item.get("source_id"), *item.get("source_ids", [])}
        source_ids.update(evidence.get("source_id") for evidence in item.get("evidence", []))
        sources = [source for source in report.get("sources", []) if source.get("id") in source_ids]
        origins = [{key: source.get(key) for key in ("id", "episode_id", "guid", "original_url", "url")} for source in sources]
        identity = {"item": item, "origins": sorted(origins, key=lambda source: source.get("id") or "")}
        if not origins or not any(origin.get("episode_id") or origin.get("guid") or origin.get("original_url") or origin.get("url") for origin in origins):
            identity["corpus_id"] = report.get("corpus_id")
        return json.dumps(identity, ensure_ascii=False, sort_keys=True)

    def import_ids(self, ids):
        if not isinstance(ids, list) or len(ids) > 500 or any(not valid_item_id(item_id) for item_id in ids):
            raise ValueError("旧收藏须为最多500个有效条目编号")
        ids = list(dict.fromkeys(ids))
        reports = self.store.all_reports()
        imported, unresolved = [], []
        for item_id in ids:
            if self._existing(item_id) is not None:
                imported.append(item_id)
                continue
            matches = [(item, report) for report in reports for item in report_items(report) if item.get("id") == item_id]
            if not matches or len({self._identity(item, report) for item, report in matches}) != 1:
                unresolved.append(item_id)
                continue
            item, report = max(matches, key=lambda match: (match[1].get("generated_at", ""), match[1]["id"]))
            self._save(item_id, item, report)
            imported.append(item_id)
        return {"imported": imported, "unresolved": unresolved}
