# -*- coding: utf-8 -*-
"""Clash 节点轮换：组推导、轮换选择、不可用时静默跳过"""
from app.services import clash_service


class FakeResp:
    def __init__(self, payload=None, status=200):
        self._payload = payload or {}
        self.status_code = status

    def json(self):
        return self._payload


PROXIES = {
    "proxies": {
        "Port-7891-Node": {"type": "Selector", "now": "US - A", "all": ["US - A", "US - B", "HK - C", "🔰 节点选择"]},
        "🔰 节点选择": {"type": "Selector", "now": "x", "all": ["US - A"]},
        "US - A": {"type": "Vmess"},
        "US - B": {"type": "Trojan"},
        "HK - C": {"type": "Ss"},
    }
}


def test_rotate_picks_next_real_node(monkeypatch):
    puts = []

    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/proxies"):
            return FakeResp(PROXIES)
        if "/proxies/Port-7891-Node" in url:
            return FakeResp(PROXIES["proxies"]["Port-7891-Node"])
        return FakeResp({"meta": True})

    def fake_put(url, headers=None, json=None, timeout=None):
        puts.append(json["name"])
        return FakeResp(None, 204)

    monkeypatch.setattr(clash_service.requests, "get", fake_get)
    monkeypatch.setattr(clash_service.requests, "put", fake_put)
    monkeypatch.setattr(clash_service, "_group_name", lambda: "Port-7891-Node")

    switched = clash_service.rotate_next()
    # 当前 US - A → 下一个真实节点 US - B（跳过嵌套组）
    assert switched == "US - B"
    assert puts == ["US - B"]


def test_rotate_returns_empty_when_api_down(monkeypatch):
    def boom(*args, **kwargs):
        raise ConnectionError("down")

    monkeypatch.setattr(clash_service.requests, "get", boom)
    monkeypatch.setattr(clash_service, "_group_name", lambda: "Port-7891-Node")
    assert clash_service.rotate_next() == ""


def test_available_false_without_secret(monkeypatch):
    monkeypatch.setattr(clash_service, "Config", type("C", (), {"CLASH_API_SECRET": ""}))
    assert clash_service.available() is False
