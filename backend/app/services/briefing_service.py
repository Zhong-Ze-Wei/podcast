# -*- coding: utf-8 -*-
"""
AI 简报生成服务

从用户订阅的播客中聚合最新单集信息，调用 LLM 生成每日简报。
数据来源优先级：AI 摘要 > RSS 元数据（title + summary + content）
结果缓存到 MongoDB `briefings` 集合，同一天内不重复生成。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from bson import ObjectId

from app.services.llm_client import get_llm_client
from app.services.briefing_prompts import (
    BRIEFING_SYSTEM_PROMPT,
    BRIEFING_USER_PROMPT,
    SUMMARY_ENTRY_TEMPLATE,
)

logger = logging.getLogger(__name__)


class BriefingService:
    """AI 简报生成服务"""

    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def get_or_generate(self, force: bool = False) -> Dict[str, Any]:
        """
        获取今日简报；如无缓存则自动生成。
        """
        today = datetime.utcnow().strftime("%Y-%m-%d")

        # 1. 检查缓存
        if not force:
            cached = self.db.briefings.find_one({"date": today})
            if cached:
                cached["_id"] = str(cached["_id"])
                logger.info("返回缓存简报 %s", today)
                return {"success": True, "briefing": cached, "cached": True}

        # 2. 收集最近单集数据
        episodes = self._collect_recent_episodes(days=7)

        if len(episodes) < 1:
            return {
                "success": True,
                "briefing": None,
                "message": "暂无播客数据，请先订阅播客",
            }

        # 3. 生成简报
        briefing_data = self._generate(episodes)

        # 4. 存入 MongoDB
        doc = {
            "date": today,
            "briefing": briefing_data,
            "episode_count": len(episodes),
            "created_at": datetime.utcnow(),
        }
        self.db.briefings.update_one(
            {"date": today}, {"$set": doc}, upsert=True
        )

        saved = self.db.briefings.find_one({"date": today})
        saved["_id"] = str(saved["_id"])

        return {"success": True, "briefing": saved, "cached": False}

    def get_cached(self) -> Optional[Dict[str, Any]]:
        """仅获取缓存，不触发生成"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cached = self.db.briefings.find_one({"date": today})
        if cached:
            cached["_id"] = str(cached["_id"])
        return cached

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _collect_recent_episodes(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        收集用户订阅播客中最近 N 天的单集。
        优先使用 AI 摘要，否则使用 RSS 自带的 summary/content。
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # 获取用户所有订阅的 feed
        feed_ids = [
            f["_id"] for f in self.db.feeds.find({"status": "active"}, {"_id": 1})
        ]

        if not feed_ids:
            return []

        # 查询最近的单集，优先选有 AI 摘要的
        base_query = {
            "feed_id": {"$in": feed_ids},
            "published": {"$gte": cutoff},  # 严格时间窗：窗口外内容不进入简报
        }

        # 先取有 AI 摘要的单集（质量高）
        summarized_episodes = list(
            self.db.episodes.find({**base_query, "has_summary": True})
            .sort("published", -1)
            .limit(30)
        )

        if len(summarized_episodes) >= 5:
            # 有足够的高质量单集，只用这些
            recent_episodes = summarized_episodes
        else:
            # 高质量单集不足，补充未摘要的单集
            summarized_ids = {ep["_id"] for ep in summarized_episodes}
            extra_episodes = list(
                self.db.episodes.find({"$and": [base_query, {"_id": {"$nin": list(summarized_ids)}}]})
                .sort("published", -1)
                .limit(20 - len(summarized_episodes))
            )
            recent_episodes = summarized_episodes + extra_episodes

        if not recent_episodes:
            # 都没有，取数据库中最新添加的
            recent_episodes = list(
                self.db.episodes.find(base_query)
                .sort("created_at", -1)
                .limit(20)
            )

        # 批量获取已有摘要
        episode_ids = [ep["_id"] for ep in recent_episodes]
        summaries_map = {}
        for s in self.db.summaries.find(
            {"episode_id": {"$in": episode_ids}},
            {"episode_id": 1, "content": 1, "tldr": 1},
        ):
            eid = s.get("episode_id")
            if eid:
                summaries_map[eid] = s

        # 批量获取 feed 信息
        feed_map = {}
        for f in self.db.feeds.find({"_id": {"$in": feed_ids}}, {"title": 1}):
            feed_map[f["_id"]] = f.get("title", "未知播客")

        results = []
        for ep in recent_episodes:
            feed_id = ep.get("feed_id")
            feed_title = feed_map.get(feed_id, "未知播客")

            # 优先用 AI 摘要
            ai_summary = summaries_map.get(ep["_id"])
            if ai_summary:
                content = ai_summary.get("content", {})
                if isinstance(content, dict):
                    summary_text = (
                        content.get("tldr", "")
                        or content.get("summary", "")
                        or ai_summary.get("tldr", "")
                        or str(content)[:2000]
                    )
                    # 拼接详细 blocks
                    blocks = content.get("blocks", [])
                    if blocks:
                        block_texts = []
                        for b in blocks:
                            if isinstance(b, dict):
                                block_texts.append(
                                    f"**{b.get('title', '')}**\n{b.get('content', '')}"
                                )
                        if block_texts:
                            summary_text += "\n\n" + "\n\n".join(block_texts)
                else:
                    summary_text = str(content)[:2000]
            else:
                # 用 RSS 自带数据：summary + content
                rss_summary = ep.get("summary", "") or ep.get("description", "")
                rss_content = ep.get("content", "")

                if rss_content and len(rss_content) > len(rss_summary):
                    # content 通常比 summary 更详细
                    summary_text = rss_content[:3000]
                elif rss_summary:
                    summary_text = rss_summary[:2000]
                else:
                    summary_text = ep.get("title", "无描述")

            duration = ep.get("duration", 0)
            if isinstance(duration, (int, float)) and duration > 300:
                duration = int(duration / 60)
            elif isinstance(duration, (int, float)):
                duration = int(duration)
            else:
                duration = 0

            results.append({
                "episode_id": str(ep["_id"]),
                "episode_title": ep.get("title", "未知标题"),
                "feed_title": feed_title,
                "duration": duration,
                "summary_content": summary_text.strip(),
                "has_ai_summary": ai_summary is not None,
                "published": ep.get("published"),
            })

        return results

    def _generate(self, episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """调用 LLM 生成简报。"""
        # 拼接摘要文本
        entries = []
        for i, ep in enumerate(episodes, 1):
            entries.append(SUMMARY_ENTRY_TEMPLATE.format(
                index=i,
                episode_title=ep["episode_title"],
                feed_title=ep["feed_title"],
                duration=ep["duration"],
                episode_id=ep["episode_id"],
                summary_content=ep["summary_content"],
            ))
        summaries_text = "\n".join(entries)

        user_prompt = BRIEFING_USER_PROMPT.format(
            episode_count=len(episodes),
            summaries_text=summaries_text,
        )

        messages = [
            {"role": "system", "content": BRIEFING_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        logger.info("开始生成 AI 简报，输入 %d 条单集", len(episodes))

        llm = get_llm_client(task="briefing")
        result = llm.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=8192,
        )

        briefing_data = result["data"]

        briefing_data["_meta"] = {
            "model": result.get("model", ""),
            "tokens": result.get("usage", {}),
            "elapsed_seconds": result.get("elapsed_seconds", 0),
            "episode_count": len(episodes),
            "ai_summarized_count": sum(1 for ep in episodes if ep.get("has_ai_summary")),
        }

        logger.info(
            "AI 简报生成完成：model=%s, tokens=%s, elapsed=%.1fs",
            result.get("model"),
            result.get("usage", {}).get("total", 0),
            result.get("elapsed_seconds", 0),
        )

        return briefing_data
