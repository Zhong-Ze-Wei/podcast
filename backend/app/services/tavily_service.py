# -*- coding: utf-8 -*-
"""
Tavily搜索服务 - 支持多API密钥轮换与失败切换
"""

import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from tavily import TavilyClient

logger = logging.getLogger(__name__)


class TavilyService:
    """Tavily搜索服务"""

    def __init__(self, setting_model):
        self.setting_model = setting_model
        self._last_key_usage = {}
        self._failed_keys = {}  # key -> 失败时间戳，用于临时跳过

    def _get_config(self) -> Dict[str, Any]:
        return self.setting_model.get_tavily_config()

    def _get_active_keys(self) -> List[str]:
        config = self._get_config()
        if not config.get("enabled", False):
            return []
        return config.get("api_keys", [])

    def _select_key(self, exclude: Optional[str] = None) -> Optional[str]:
        """选择可用的API密钥（轮换 + 跳过近期失败的）"""
        keys = self._get_active_keys()
        if not keys:
            return None

        now = time.time()

        # 过滤掉 exclude 和 60秒内失败过的 key
        candidates = []
        for key in keys:
            if key == exclude:
                continue
            failed_at = self._failed_keys.get(key, 0)
            if now - failed_at < 60:
                continue
            last_used = self._last_key_usage.get(key, 0)
            candidates.append((key, last_used))

        # 如果全被过滤了，放宽条件（只排除 exclude）
        if not candidates:
            candidates = [
                (key, self._last_key_usage.get(key, 0))
                for key in keys
                if key != exclude
            ]

        # 还是空的，说明只有一个 key 且被 exclude 了，那就用它
        if not candidates:
            candidates = [(keys[0], 0)]

        # 选最久没用的
        candidates.sort(key=lambda x: x[1])
        selected = candidates[0][0]
        self._last_key_usage[selected] = now
        return selected

    def _mark_failed(self, key: str):
        self._failed_keys[key] = time.time()

    def _make_client(self, api_key: str) -> TavilyClient:
        return TavilyClient(api_key=api_key)

    def search(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        执行Tavily搜索，失败时自动切换key重试一次

        Returns:
            Tavily API 原始响应
        """
        config = self._get_config()
        key = self._select_key()
        if not key:
            raise ValueError("没有可用的 Tavily API 密钥")

        search_kwargs = self._build_search_params(query, config, **kwargs)

        # 第一次尝试
        try:
            return self._do_search(key, **search_kwargs)
        except Exception as e:
            logger.warning(f"Tavily search failed with key ...{key[-4:]}: {e}")
            self._mark_failed(key)

        # 切换 key 重试
        fallback_key = self._select_key(exclude=key)
        if not fallback_key or fallback_key == key:
            raise ValueError(f"Tavily 搜索失败且无可用备用密钥: {e}")

        logger.info(f"Tavily fallback to key ...{fallback_key[-4:]}")
        return self._do_search(fallback_key, **search_kwargs)

    def extract_content(self, urls: List[str], **kwargs) -> Dict[str, Any]:
        """
        从URL列表提取内容，失败时自动切换key重试一次

        Returns:
            Tavily extract API 原始响应
        """
        key = self._select_key()
        if not key:
            raise ValueError("没有可用的 Tavily API 密钥")

        extract_kwargs = {
            "urls": urls,
            "extract_depth": kwargs.get("extract_depth", "basic"),
        }

        try:
            return self._do_extract(key, **extract_kwargs)
        except Exception as e:
            logger.warning(f"Tavily extract failed with key ...{key[-4:]}: {e}")
            self._mark_failed(key)

        fallback_key = self._select_key(exclude=key)
        if not fallback_key or fallback_key == key:
            raise ValueError(f"Tavily 提取失败且无可用备用密钥: {e}")

        logger.info(f"Tavily extract fallback to key ...{fallback_key[-4:]}")
        return self._do_extract(fallback_key, **extract_kwargs)

    def _build_search_params(self, query: str, config: Dict, **kwargs) -> Dict:
        params = {
            "query": query,
            "search_depth": kwargs.get("search_depth", config.get("search_depth", "basic")),
            "max_results": kwargs.get("max_results", config.get("max_results", 5)),
        }

        include_domains = kwargs.get("include_domains", config.get("include_domains", []))
        if include_domains:
            params["include_domains"] = include_domains

        exclude_domains = kwargs.get("exclude_domains", config.get("exclude_domains", []))
        if exclude_domains:
            params["exclude_domains"] = exclude_domains

        days_back = kwargs.get("days_back", config.get("days_back", 30))
        if days_back > 0:
            params["end_date"] = datetime.now().strftime("%Y-%m-%d")
            params["start_date"] = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        return params

    def _do_search(self, api_key: str, **kwargs) -> Dict[str, Any]:
        client = self._make_client(api_key)
        logger.info(f"Tavily search: query={kwargs.get('query', '')!r}")
        return client.search(**kwargs)

    def _do_extract(self, api_key: str, **kwargs) -> Dict[str, Any]:
        client = self._make_client(api_key)
        logger.info(f"Tavily extract: urls={kwargs.get('urls', [])}")
        return client.extract(**kwargs)
