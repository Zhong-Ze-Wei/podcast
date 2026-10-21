# -*- coding: utf-8 -*-
"""
Clash 外部控制器（代理节点轮换）

YouTube 等抓取走专用本地端口（YOUTUBE_PROXY，默认 7891），对应 Verge 配置里的
"Port-7891-Node" 选择器组。被限流时轮换该组的出口节点 = 换 IP，且不影响
用户主代理组（节点选择/国外媒体等）的任何流量。

配置（backend/.env）：
    CLASH_API_URL     默认 http://127.0.0.1:9090
    CLASH_API_SECRET  外部控制器密钥
    CLASH_YOUTUBE_GROUP  覆盖自动推导的组名（默认按 YOUTUBE_PROXY 端口推导 Port-<port>-Node）
"""

import logging
from urllib.parse import urlparse

import requests

from ..config import Config

logger = logging.getLogger(__name__)


def _api_base() -> str:
    return (getattr(Config, "CLASH_API_URL", "") or "http://127.0.0.1:9090").rstrip("/")


def _headers() -> dict:
    secret = getattr(Config, "CLASH_API_SECRET", "") or ""
    return {"Authorization": f"Bearer {secret}"} if secret else {}


def _group_name() -> str:
    override = getattr(Config, "CLASH_YOUTUBE_GROUP", "") or ""
    if override:
        return override
    proxy = getattr(Config, "YOUTUBE_PROXY", "") or ""
    port = urlparse(proxy).port if proxy else None
    return f"Port-{port}-Node" if port else ""


def _request(path: str, timeout: float = 5.0):
    return requests.get(f"{_api_base()}{path}", headers=_headers(), timeout=timeout)


def available() -> bool:
    """外部控制器是否可达且配置了密钥"""
    if not getattr(Config, "CLASH_API_SECRET", ""):
        return False
    try:
        return _request("/version").status_code == 200
    except Exception:
        return False


def current_node(group: str = None) -> str:
    """该选择器组当前使用的节点名；不可用返回空串"""
    group = group or _group_name()
    try:
        data = _request(f"/proxies/{group}").json()
        return data.get("now", "")
    except Exception:
        return ""


def _node_candidates(group: str = None):
    """组内真实节点列表（排除嵌套组与 DIRECT 等特殊项）"""
    group = group or _group_name()
    try:
        proxies = _request("/proxies", timeout=8).json().get("proxies", {})
        members = proxies.get(group, {}).get("all") or []
        special = {name for name, info in proxies.items() if info.get("type") in ("Selector", "URLTest", "Fallback", "Direct", "Reject")}
        return [name for name in members if name not in special and name != "DIRECT"]
    except Exception:
        return []


def rotate_next(group: str = None) -> str:
    """
    把组切换到下一个节点（按列表顺序轮换）。返回切换后的节点名，失败返回空串。
    """
    group = group or _group_name()
    if not group:
        return ""
    nodes = _node_candidates(group)
    if len(nodes) < 2:
        return ""
    now = current_node(group)
    try:
        index = nodes.index(now) if now in nodes else -1
    except ValueError:
        index = -1
    next_node = nodes[(index + 1) % len(nodes)]
    if next_node == now:
        return ""
    try:
        resp = requests.put(
            f"{_api_base()}/proxies/{group}",
            headers=_headers(), json={"name": next_node}, timeout=5,
        )
        if resp.status_code in (200, 204):
            logger.info("Clash 节点轮换 %s: %s → %s", group, now, next_node)
            return next_node
        logger.warning("Clash 节点轮换失败 %s: HTTP %s", group, resp.status_code)
    except Exception as error:
        logger.warning("Clash 节点轮换异常 %s: %s", group, error)
    return ""


def select_node(name: str, group: str = None) -> bool:
    """把组切换到指定节点（并发通道初始化时分散到不同出口用）"""
    group = group or _group_name()
    if not group or not name:
        return False
    try:
        resp = requests.put(
            f"{_api_base()}/proxies/{group}",
            headers=_headers(), json={"name": name}, timeout=5,
        )
        return resp.status_code in (200, 204)
    except Exception as error:
        logger.warning("Clash 节点切换异常 %s → %s: %s", group, name, error)
        return False


def node_names(group: str = None) -> list:
    """组内真实节点名列表（组名推导失败返回空）"""
    return _node_candidates(group)


def rotate_next_healthy(group: str = None, max_tries: int = 6) -> str:
    """轮换到下一个对 YouTube 可达的节点（跳过死节点）。返回节点名，失败返回空串。

    订阅里常有失效节点，盲切会把出口换到连不上 YouTube 的节点上；
    这里逐个探测直到找到可用的，全部不可用时恢复原节点。
    """
    group = group or _group_name()
    if not group:
        return ""
    nodes = _node_candidates(group)
    if len(nodes) < 2:
        return ""
    now = current_node(group)
    try:
        index = nodes.index(now) if now in nodes else -1
    except ValueError:
        index = -1
    switched = ""
    try:
        for step in range(1, max_tries + 1):
            candidate = nodes[(index + step) % len(nodes)]
            if candidate == now:
                return ""
            if not select_node(candidate, group):
                continue
            import time
            time.sleep(0.4)
            try:
                proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
                resp = requests.get("https://www.youtube.com/robots.txt", proxies=proxies, timeout=(3, 6))
                if resp.status_code == 200:
                    logger.info("Clash 轮换到可用节点 %s: %s → %s", group, now, candidate)
                    switched = candidate
                    return candidate
            except Exception:
                continue
    finally:
        # 一个可用节点都没找到：恢复原节点，避免停在死节点上（成功时不回切）
        if not switched and now and current_node(group) != now:
            select_node(now, group)
    logger.warning("Clash 连续 %d 个节点不可用，保持 %s", max_tries, now)
    return ""
