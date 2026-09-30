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
    CONDENSE_SYSTEM_PROMPT,
    CONDENSE_USER_PROMPT,
)

logger = logging.getLogger(__name__)

# 简报策略：同一份订阅数据，三种取材路线（前端以 tab 并列供用户对比选择）
STRATEGY_SUMMARY = "summary"      # 摘要聚合：AI 摘要优先，RSS 元数据兜底（原有逻辑）
STRATEGY_TRANSCRIPT = "transcript"  # 文稿直析：无摘要的单集从 transcript 两步提取要点
STRATEGY_METADATA = "metadata"    # 元数据雷达：标题 + RSS 简介，零依赖最快

STRATEGIES = (STRATEGY_SUMMARY, STRATEGY_TRANSCRIPT, STRATEGY_METADATA)

# 时间窗口（天）允许范围；缓存键含 days，同一天同策略不同窗口各一份
MIN_WINDOW_DAYS = 1
MAX_WINDOW_DAYS = 30
DEFAULT_WINDOW_DAYS = 7

# 文稿直析策略中，允许逐集调 LLM 压缩的最大单集数（超出部分退回 RSS 元数据）
MAX_CONDENSE_CALLS = 10


class BriefingService:
    """AI 简报生成服务"""

    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def get_or_generate(
        self,
        force: bool = False,
        strategy: str = STRATEGY_SUMMARY,
        days: int = DEFAULT_WINDOW_DAYS,
    ) -> Dict[str, Any]:
        """
        获取今日简报；如无缓存则自动生成。缓存键 = date + strategy + days。
        """
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cache_query = {"date": today, "strategy": strategy, "days": days}

        # 1. 检查缓存
        if not force:
            cached = self.db.briefings.find_one(cache_query)
            if cached:
                cached["_id"] = str(cached["_id"])
                logger.info("返回缓存简报 %s/%s/%dd", today, strategy, days)
                return {"success": True, "briefing": cached, "cached": True}

        # 2. 按策略取材
        if strategy == STRATEGY_TRANSCRIPT:
            episodes = self._collect_transcript_material(days=days)
        elif strategy == STRATEGY_METADATA:
            episodes = self._collect_metadata_material(days=days)
        else:
            episodes = self._collect_recent_episodes(days=days)

        if len(episodes) < 1:
            return {
                "success": True,
                "briefing": None,
                "message": f"近 {days} 天没有可分析的剧集，请先订阅或刷新",
            }

        # 3. 生成简报
        briefing_data = self._generate(episodes, strategy=strategy)

        # 4. 存入 MongoDB（按策略与窗口隔离）
        doc = {
            "date": today,
            "strategy": strategy,
            "days": days,
            "briefing": briefing_data,
            "episode_count": len(episodes),
            "created_at": datetime.utcnow(),
        }
        self.db.briefings.update_one(cache_query, {"$set": doc}, upsert=True)

        saved = self.db.briefings.find_one(cache_query)
        saved["_id"] = str(saved["_id"])

        return {"success": True, "briefing": saved, "cached": False}

    def get_cached(
        self,
        strategy: str = STRATEGY_SUMMARY,
        days: int = DEFAULT_WINDOW_DAYS,
    ) -> Optional[Dict[str, Any]]:
        """仅获取缓存，不触发生成"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cached = self.db.briefings.find_one({"date": today, "strategy": strategy, "days": days})
        if cached:
            cached["_id"] = str(cached["_id"])
        return cached

    def window_counts(self, days: int = DEFAULT_WINDOW_DAYS) -> Dict[str, int]:
        """时间窗口内剧集统计（滑块预览用，零 LLM 成本）"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        feed_ids = [f["_id"] for f in self.db.feeds.find({"status": "active"}, {"_id": 1})]
        if not feed_ids:
            return {"days": days, "total": 0, "with_transcript": 0, "with_summary": 0}
        base = {"feed_id": {"$in": feed_ids}, "published": {"$gte": cutoff}}
        return {
            "days": days,
            "total": self.db.episodes.count_documents(base),
            "with_transcript": self.db.episodes.count_documents({**base, "has_transcript": True}),
            "with_summary": self.db.episodes.count_documents({**base, "has_summary": True}),
        }

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
                "source": "summary" if ai_summary else "metadata",
                "published": ep.get("published"),
            })

        return results

    def _window_episodes(self, days: int, extra_query: Optional[dict] = None, limit: int = 30) -> List[Dict[str, Any]]:
        """近 N 天窗口内的剧集（活跃订阅），按发布时间倒序"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        feed_ids = [f["_id"] for f in self.db.feeds.find({"status": "active"}, {"_id": 1})]
        if not feed_ids:
            return []
        query = {"feed_id": {"$in": feed_ids}, "published": {"$gte": cutoff}}
        if extra_query:
            query.update(extra_query)
        return list(self.db.episodes.find(query).sort("published", -1).limit(limit))

    def _entry_common(self, ep: Dict[str, Any], feed_map: Dict[str, str]) -> Dict[str, Any]:
        duration = ep.get("duration", 0)
        if isinstance(duration, (int, float)) and duration > 300:
            duration = int(duration / 60)
        elif isinstance(duration, (int, float)):
            duration = int(duration)
        else:
            duration = 0
        return {
            "episode_id": str(ep["_id"]),
            "episode_title": ep.get("title", "未知标题"),
            "feed_title": feed_map.get(ep.get("feed_id"), "未知播客"),
            "duration": duration,
            "published": ep.get("published"),
        }

    def _build_feed_map(self, episodes: List[Dict[str, Any]]) -> Dict[str, str]:
        feed_ids = list({ep.get("feed_id") for ep in episodes if ep.get("feed_id")})
        if not feed_ids:
            return {}
        return {
            f["_id"]: f.get("title", "未知播客")
            for f in self.db.feeds.find({"_id": {"$in": feed_ids}}, {"title": 1})
        }

    def _collect_transcript_material(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        文稿直析策略取材：有 AI 摘要的用摘要，无摘要但有文稿的
        逐集调 LLM 现场压缩要点（两步法的第一步），都没有的退回 RSS 元数据。
        """
        episodes = self._window_episodes(days, limit=30)
        if not episodes:
            return []

        feed_map = self._build_feed_map(episodes)
        episode_ids = [ep["_id"] for ep in episodes]

        summaries_map = {}
        for s in self.db.summaries.find({"episode_id": {"$in": episode_ids}}, {"episode_id": 1, "content": 1, "tldr": 1}):
            if s.get("episode_id"):
                summaries_map[s["episode_id"]] = s

        transcripts_map = {}
        for tr in self.db.transcripts.find({"episode_id": {"$in": episode_ids}}, {"episode_id": 1, "text": 1}):
            if tr.get("episode_id") and tr.get("text"):
                transcripts_map[tr["episode_id"]] = tr["text"]

        results = []
        condense_queue = []  # [(entry, transcript_text)]
        for ep in episodes:
            entry = self._entry_common(ep, feed_map)
            ai_summary = summaries_map.get(ep["_id"])
            transcript_text = transcripts_map.get(ep["_id"])

            if ai_summary:
                content = ai_summary.get("content", {})
                if isinstance(content, dict):
                    entry["summary_content"] = (
                        content.get("tldr", "") or content.get("summary", "")
                        or ai_summary.get("tldr", "") or str(content)[:2000]
                    ).strip()
                else:
                    entry["summary_content"] = str(content)[:2000]
                entry["source"] = "summary"
                entry["has_ai_summary"] = True
            elif transcript_text:
                entry["summary_content"] = ""  # 待压缩填充
                entry["source"] = "transcript"
                entry["has_ai_summary"] = False
                condense_queue.append((entry, transcript_text))
            else:
                entry["summary_content"] = self._rss_fallback_text(ep)
                entry["source"] = "metadata"
                entry["has_ai_summary"] = False
            results.append(entry)

        self._condense_missing(condense_queue, feed_map)
        return [e for e in results if e.get("summary_content")]

    @staticmethod
    def _rss_fallback_text(ep: Dict[str, Any]) -> str:
        rss_summary = ep.get("summary", "") or ep.get("description", "")
        rss_content = ep.get("content", "")
        if rss_content and len(rss_content) > len(rss_summary):
            return rss_content[:1500].strip()
        if rss_summary:
            return rss_summary[:1200].strip()
        return ep.get("title", "无描述")

    def _condense_missing(self, queue: List[tuple], feed_map: Dict[str, str]) -> None:
        """两步法第一步：无摘要单集从 transcript 压缩要点。压缩失败退回 RSS 元数据。"""
        if not queue:
            return
        llm = get_llm_client(task="briefing")
        budget = MAX_CONDENSE_CALLS
        for entry, transcript_text in queue:
            if budget <= 0:
                entry["summary_content"] = self._rss_fallback_text_by_title(entry)
                entry["source"] = "metadata"
                continue
            budget -= 1
            # 长文稿取头尾：核心内容通常在开头，结论在结尾
            excerpt = transcript_text[:6000]
            if len(transcript_text) > 8000:
                excerpt += "\n...(中间省略)...\n" + transcript_text[-1500:]
            try:
                result = llm.chat(
                    messages=[
                        {"role": "system", "content": CONDENSE_SYSTEM_PROMPT},
                        {"role": "user", "content": CONDENSE_USER_PROMPT.format(
                            feed_title=entry["feed_title"],
                            episode_title=entry["episode_title"],
                            transcript_excerpt=excerpt,
                        )},
                    ],
                    temperature=0.2,
                    max_tokens=600,
                )
                condensed = (result.get("content") or "").strip()
            except Exception as e:
                logger.warning("文稿压缩失败（%s）：%s", entry["episode_title"], e)
                condensed = ""
            if condensed:
                entry["summary_content"] = condensed
            else:
                entry["summary_content"] = self._rss_fallback_text_by_title(entry)
                entry["source"] = "metadata"

    def _rss_fallback_text_by_title(self, entry: Dict[str, Any]) -> str:
        ep = self.db.episodes.find_one({"_id": ObjectId(entry["episode_id"])})
        return self._rss_fallback_text(ep) if ep else entry["episode_title"]

    def _collect_metadata_material(self, days: int = 7) -> List[Dict[str, Any]]:
        """元数据雷达取材：不依赖摘要和文稿，标题 + RSS 简介直出"""
        episodes = self._window_episodes(days, limit=40)
        if not episodes:
            return []
        feed_map = self._build_feed_map(episodes)
        results = []
        for ep in episodes:
            entry = self._entry_common(ep, feed_map)
            entry["summary_content"] = self._rss_fallback_text(ep)
            entry["source"] = "metadata"
            entry["has_ai_summary"] = False
            results.append(entry)
        return results

    def _generate(self, episodes: List[Dict[str, Any]], strategy: str = STRATEGY_SUMMARY) -> Dict[str, Any]:
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

        source_counts = {}
        for ep in episodes:
            key = ep.get("source", "summary")
            source_counts[key] = source_counts.get(key, 0) + 1
        source_labels = {"summary": "已有摘要", "transcript": "文稿压缩", "metadata": "元数据"}
        material_note = " + ".join(
            f"{count} 集{source_labels.get(source, source)}"
            for source, count in source_counts.items()
        )

        briefing_data["_meta"] = {
            "model": result.get("model", ""),
            "tokens": result.get("usage", {}),
            "elapsed_seconds": result.get("elapsed_seconds", 0),
            "strategy": strategy,
            "episode_count": len(episodes),
            "ai_summarized_count": sum(1 for ep in episodes if ep.get("has_ai_summary")),
            "source_counts": source_counts,
            "material_note": f"取材：{material_note}",
        }

        logger.info(
            "AI 简报生成完成：model=%s, tokens=%s, elapsed=%.1fs",
            result.get("model"),
            result.get("usage", {}).get("total", 0),
            result.get("elapsed_seconds", 0),
        )

        return briefing_data
