# -*- coding: utf-8 -*-
"""
Summary Service

Facade for summarization functionality.
Wraps the new SummarizationEngine while maintaining backward compatibility.
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId

from app.core.summarization import SummarizationEngine, get_summarization_engine
from app.services.llm_client import get_llm_client
from app.services.prompts import PromptRouter

logger = logging.getLogger(__name__)


class SummaryService:
    """
    Summary generation service.

    This is a facade that:
    - Uses the new SummarizationEngine for template-based summaries
    - Falls back to legacy prompts for backward compatibility
    - Handles translation separately
    """

    def __init__(self, db):
        self.db = db
        self.llm = get_llm_client()
        self._engine = None

    @property
    def engine(self) -> SummarizationEngine:
        """Lazy-load the summarization engine"""
        if self._engine is None:
            self._engine = get_summarization_engine(self.db, self.llm)
        return self._engine

    def generate_summary(
        self,
        episode_id: ObjectId,
        template_name: str = None,
        summary_type: str = None,
        enabled_blocks: List[str] = None,
        params: Dict = None,
        user_focus: str = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Generate summary for an episode.

        New API (template-based):
            - template_name: Name of template to use
            - enabled_blocks: List of block IDs to enable
            - params: Parameter values (e.g., {"length": "long"})
            - user_focus: User's specific focus to prioritize (max 50 chars)

        Legacy API (backward compatible):
            - summary_type: "general" or "investment"

        Args:
            episode_id: Episode ObjectId
            template_name: Template name (new API)
            summary_type: Summary type (legacy API, mapped to template)
            enabled_blocks: Block IDs to enable (new API)
            params: Parameters (new API)
            user_focus: User's specific focus (new API)
            force: Force regenerate

        Returns:
            Summary document
        """
        # Resolve template name from legacy summary_type
        if template_name is None and summary_type is not None:
            template_name = self._map_legacy_type(summary_type)
        elif template_name is None:
            template_name = "investment"  # Default template

        # Check if template exists in database
        template = self.db.prompt_templates.find_one({
            "name": template_name,
            "is_active": True
        })

        if template:
            # Use new engine
            logger.info(f"Using template-based engine: {template_name}")
            return self._generate_with_engine(
                episode_id=episode_id,
                template_name=template_name,
                enabled_blocks=enabled_blocks,
                params=params,
                user_focus=user_focus,
                force=force
            )
        else:
            # Fall back to legacy prompts
            logger.warning(f"Template '{template_name}' not found, using legacy prompts")
            return self._generate_legacy(
                episode_id=episode_id,
                summary_type=summary_type or "general",
                force=force
            )

    def _generate_with_engine(
        self,
        episode_id: ObjectId,
        template_name: str,
        enabled_blocks: List[str] = None,
        params: Dict = None,
        user_focus: str = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """Generate summary using new engine"""
        return self.engine.summarize_episode(
            episode_id=episode_id,
            template_name=template_name,
            enabled_blocks=enabled_blocks,
            params=params,
            user_focus=user_focus,
            force=force
        )

    def _generate_legacy(
        self,
        episode_id: ObjectId,
        summary_type: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Generate summary using legacy prompts.

        This maintains backward compatibility with existing code.
        """
        # Check existing
        if not force:
            existing = self.db.summaries.find_one({
                "episode_id": episode_id,
                "summary_type": summary_type
            })
            if existing:
                logger.info(f"Summary already exists for episode {episode_id}")
                return existing

        # Load episode and transcript
        episode = self.db.episodes.find_one({"_id": episode_id})
        if not episode:
            raise ValueError(f"Episode not found: {episode_id}")

        transcript = self.db.transcripts.find_one({"episode_id": episode_id})
        if not transcript or not transcript.get("text"):
            raise ValueError(f"Transcript not found for episode: {episode_id}")

        transcript_text = transcript["text"]
        title = episode.get("title", "Unknown")
        guest = self._extract_guest(episode)

        logger.info(f"Generating legacy {summary_type} summary for: {title}")

        # Use legacy prompt router
        prompt = PromptRouter.get_prompt(summary_type)
        messages = prompt.build_messages(
            transcript=transcript_text,
            title=title,
            guest=guest
        )

        result = self.llm.chat_json(
            messages=messages,
            temperature=0.2
        )

        # Save to database
        summary_doc = self._create_legacy_summary_document(
            episode_id=episode_id,
            summary_type=summary_type,
            content=result["data"],
            usage=result["usage"],
            model=result["model"],
            elapsed=result["elapsed_seconds"]
        )

        self.db.summaries.update_one(
            {"episode_id": episode_id, "summary_type": summary_type},
            {"$set": summary_doc},
            upsert=True
        )

        saved_doc = self.db.summaries.find_one({
            "episode_id": episode_id,
            "summary_type": summary_type
        })

        # Update episode status
        self.db.episodes.update_one(
            {"_id": episode_id},
            {"$set": {
                "has_summary": True,
                "status": "summarized",
                "updated_at": datetime.utcnow()
            }}
        )

        return saved_doc

    def translate_summary(
        self,
        episode_id: ObjectId,
        summary_type: str = None,
        template_name: str = None
    ) -> Dict[str, Any]:
        """
        Translate summary to Chinese.

        Args:
            episode_id: Episode ObjectId
            summary_type: Legacy summary type
            template_name: Template name (new API)

        Returns:
            Updated summary document
        """
        # Find existing summary
        query = {"episode_id": episode_id}
        if template_name:
            query["template_name"] = template_name
        elif summary_type:
            query["summary_type"] = summary_type

        summary = self.db.summaries.find_one(query, sort=[("created_at", -1)])

        if not summary:
            raise ValueError(f"Summary not found for episode: {episode_id}")

        # Check if already translated
        if summary.get("content_zh"):
            logger.info(f"Chinese translation already exists for episode {episode_id}")
            return summary

        content = summary.get("content", {})
        if not content:
            raise ValueError("Summary content is empty")

        logger.info(f"Translating summary for episode {episode_id}")

        # Use translate prompt
        translate_prompt = PromptRouter.get_translate_prompt()
        messages = translate_prompt.build_messages(content=content)

        result = self.llm.chat_json(
            messages=messages,
            temperature=0.2
        )

        translated = result["data"]

        # Update database
        update_data = {
            "content_zh": translated,
            "translation_model": result["model"],
            "translation_tokens": result["usage"],
            "translated_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        self.db.summaries.update_one(
            {"_id": summary["_id"]},
            {"$set": update_data}
        )

        return self.db.summaries.find_one({"_id": summary["_id"]})

    def _map_legacy_type(self, summary_type: str) -> str:
        """Map legacy summary type to template name"""
        mapping = {
            "general": "investment",  # Default to investment for general
            "investment": "investment",
            "stakeholder": "stakeholder",
            "data_evidence": "data_evidence"
        }
        return mapping.get(summary_type, "investment")

    def _create_legacy_summary_document(
        self,
        episode_id: ObjectId,
        summary_type: str,
        content: Dict,
        usage: Dict,
        model: str,
        elapsed: float
    ) -> Dict:
        """Create legacy summary document"""
        now = datetime.utcnow()

        return {
            "episode_id": episode_id,
            "summary_type": summary_type,
            "version": "v2",  # Legacy version

            "tldr": content.get("tldr", ""),
            "tags": content.get("tags", []),
            "content": content,

            "model": model,
            "tokens_used": usage,
            "generation_time_seconds": elapsed,

            "created_at": now,
            "updated_at": now
        }

    def _extract_guest(self, episode: Dict) -> str:
        """Extract guest name from episode info"""
        title = episode.get("title", "")

        if " - " in title:
            parts = title.split(" - ", 1)
            if len(parts) > 1:
                guest_part = parts[1].split(":")[0].strip()
                return guest_part

        if " | " in title:
            parts = title.split(" | ")
            return parts[0].strip()

        return "Unknown"

    def get_available_templates(self) -> List[Dict]:
        """Get available templates for UI"""
        return self.engine.get_available_templates()


def get_summary_service(db) -> SummaryService:
    """Get summary service instance"""
    return SummaryService(db)
