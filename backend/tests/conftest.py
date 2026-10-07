# -*- coding: utf-8 -*-
"""
测试配置和 fixtures
"""
import sys
import os
import pytest

# 确保项目路径在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


class MockDB:
    """轻量 MongoDB mock，用于单元测试"""

    def __init__(self):
        self._collections = {}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._collections:
            self._collections[name] = MockCollection(name)
        return self._collections[name]

    def __getitem__(self, name):
        return getattr(self, name)


class MockCollection:
    """模拟 MongoDB collection"""

    def __init__(self, name):
        self.name = name
        self._data = []
        self._id_counter = 0

    def insert_one(self, doc):
        from bson import ObjectId
        self._id_counter += 1
        doc["_id"] = ObjectId()
        self._data.append(dict(doc))
        from pymongo.results import InsertOneResult
        return InsertOneResult(doc["_id"], acknowledged=True)

    def insert_many(self, docs):
        for doc in docs:
            self.insert_one(doc)
        from pymongo.results import InsertManyResult
        return InsertManyResult([d["_id"] for d in docs], acknowledged=True)

    def find_one(self, query, *args, **kwargs):
        from bson import ObjectId
        for doc in self._data:
            if self._match(doc, query):
                return dict(doc)
        return None

    def find(self, query=None, *args, **kwargs):
        query = query or {}
        results = [dict(doc) for doc in self._data if self._match(doc, query)]
        return MockCursor(results)

    def update_one(self, query, update, **kwargs):
        from pymongo.results import UpdateResult
        for i, orig_doc in enumerate(self._data):
            if self._match(orig_doc, query):
                if "$set" in update:
                    self._data[i].update(update["$set"])
                for field in update.get("$unset", {}):
                    self._data[i].pop(field, None)
                return UpdateResult({"n": 1, "nModified": 1}, True)
        if kwargs.get("upsert"):
            new_doc = dict(query)
            if "$set" in update:
                new_doc.update(update["$set"])
            self.insert_one(new_doc)
            return UpdateResult({"n": 1, "nModified": 0}, True)
        return UpdateResult({"n": 0, "nModified": 0}, True)

    def delete_one(self, query):
        for i, doc in enumerate(self._data):
            if self._match(doc, query):
                self._data.pop(i)
                from pymongo.results import DeleteResult
                return DeleteResult({"n": 1}, acknowledged=True)
        from pymongo.results import DeleteResult
        return DeleteResult({"n": 0}, acknowledged=True)

    def delete_many(self, query):
        before = len(self._data)
        self._data = [d for d in self._data if not self._match(d, query)]
        count = before - len(self._data)
        from pymongo.results import DeleteResult
        return DeleteResult({"n": count}, acknowledged=True)

    def count_documents(self, query):
        return sum(1 for doc in self._data if self._match(doc, query))

    def create_index(self, *args, **kwargs):
        pass

    def _match(self, doc, query):
        for key, value in query.items():
            if key == "$or":
                if not any(self._match(doc, clause) for clause in value):
                    return False
                continue
            if key == "_id":
                from bson import ObjectId
                doc_val = doc.get("_id")
                if isinstance(value, ObjectId):
                    if doc_val != value:
                        return False
                elif isinstance(value, dict):
                    if not self._match_operator(doc_val, value):
                        return False
                elif isinstance(value, str):
                    if str(doc_val) != value:
                        return False
            elif key == "$in":
                # Not a key, this shouldn't happen at this level
                pass
            elif "." in key:
                # Nested field query (e.g., "feed_id": {"$in": [...]})
                parts = key.split(".")
                val = doc
                for p in parts:
                    val = val.get(p) if isinstance(val, dict) else None
                if isinstance(value, dict):
                    if not self._match_operator(val, value):
                        return False
                elif val != value:
                    return False
            elif isinstance(value, dict):
                doc_val = doc.get(key)
                if not self._match_operator(doc_val, value):
                    return False
            elif doc.get(key) != value:
                return False
        return True

    def _match_operator(self, val, ops):
        from datetime import datetime
        if "$gte" in ops:
            if val is None or val < ops["$gte"]:
                return False
        if "$gt" in ops:
            if val is None or val <= ops["$gt"]:
                return False
        if "$lte" in ops:
            if val is None or val > ops["$lte"]:
                return False
        if "$lt" in ops:
            if val is None or val >= ops["$lt"]:
                return False
        if "$in" in ops:
            if val not in ops["$in"]:
                return False
        if "$nin" in ops:
            if val in ops["$nin"]:
                return False
        if "$ne" in ops:
            if val == ops["$ne"]:
                return False
        return True


class MockCursor:
    """模拟 MongoDB cursor"""

    def __init__(self, data):
        self._data = data
        self._sort = None
        self._skip = 0
        self._limit_val = 0

    def sort(self, key, direction=None):
        if isinstance(key, str):
            reverse = direction == -1 if direction else False
            self._data.sort(key=lambda x: (x.get(key) is not None, x.get(key)), reverse=reverse)
        return self

    def skip(self, n):
        self._skip = n
        return self

    def limit(self, n):
        self._limit_val = n
        return self

    def __iter__(self):
        data = self._data[self._skip:]
        if self._limit_val:
            data = data[:self._limit_val]
        return iter(data)

    def __list__(self):
        data = self._data[self._skip:]
        if self._limit_val:
            data = data[:self._limit_val]
        return data


@pytest.fixture
def mock_db():
    """提供一个干净的 MockDB 实例"""
    return MockDB()


@pytest.fixture
def sample_feed():
    """示例 Feed 数据"""
    from bson import ObjectId
    return {
        "_id": ObjectId(),
        "title": "Test Podcast",
        "rss_url": "https://example.com/feed.xml",
        "status": "active",
        "episode_count": 5,
    }


@pytest.fixture
def sample_episodes(sample_feed):
    """示例 Episode 数据"""
    from bson import ObjectId
    from datetime import datetime, timedelta
    feed_id = sample_feed["_id"]
    now = datetime.utcnow()
    return [
        {
            "_id": ObjectId(),
            "feed_id": feed_id,
            "guid": f"ep-{i}",
            "title": f"Episode {i}: AI and the Future",
            "summary": f"This episode discusses AI topic {i}.",
            "content": "",
            "published": now - timedelta(days=i),
            "duration": 3600,
            "audio_url": f"https://example.com/ep{i}.mp3",
            "status": "new",
            "created_at": now - timedelta(days=i),
        }
        for i in range(5)
    ]
