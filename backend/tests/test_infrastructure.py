# -*- coding: utf-8 -*-
"""
冒烟测试 — 验证测试基础设施正常
"""
from bson import ObjectId
from datetime import datetime, timedelta


def test_mock_db_insert_and_find(mock_db):
    """MockDB 基本插入和查询"""
    mock_db.feeds.insert_one({"title": "Test", "status": "active"})
    result = mock_db.feeds.find_one({"title": "Test"})
    assert result is not None
    assert result["title"] == "Test"


def test_mock_db_count(mock_db, sample_episodes):
    """MockDB 计数"""
    for ep in sample_episodes:
        mock_db.episodes.insert_one(ep)
    assert mock_db.episodes.count_documents({}) == 5
    assert mock_db.episodes.count_documents({"guid": "ep-0"}) == 1


def test_mock_db_sort_and_limit(mock_db, sample_episodes):
    """MockDB 排序和分页"""
    for ep in sample_episodes:
        mock_db.episodes.insert_one(ep)
    results = list(mock_db.episodes.find({}).sort("published", -1).limit(3))
    assert len(results) == 3
    # 最新的排前面
    assert results[0]["guid"] == "ep-0"


def test_mock_db_update(mock_db):
    """MockDB 更新"""
    mock_db.feeds.insert_one({"title": "Old", "status": "active"})
    mock_db.feeds.update_one({"title": "Old"}, {"$set": {"title": "New"}})
    result = mock_db.feeds.find_one({"title": "New"})
    assert result is not None


def test_conftest_fixtures(mock_db, sample_feed, sample_episodes):
    """conftest fixtures 正常工作"""
    assert sample_feed["title"] == "Test Podcast"
    assert len(sample_episodes) == 5
    assert sample_episodes[0]["feed_id"] == sample_feed["_id"]
