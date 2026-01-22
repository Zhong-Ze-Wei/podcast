# -*- coding: utf-8 -*-
"""
Summarization Engine

Core engine for podcast summarization.
Orchestrates template loading, prompt building, LLM calling, and validation.
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from bson import ObjectId

from .prompt_builder import PromptBuilder
from .schema_validator import SchemaValidator, ValidationError

logger = logging.getLogger(__name__)


class SummarizationEngine:
    """
    Core summarization engine.

    Responsibilities:
    - Load templates from database
    - Build prompts dynamically
    - Call LLM and parse response
    - Validate output against schema
    - Handle retries on validation failure
    """

    MAX_RETRIES = 2

    def __init__(self, db, llm_client):
        """
        Initialize engine.

        Args:
            db: MongoDB database instance
            llm_client: LLM client instance
        """
        self.db = db
        self.llm = llm_client
        self.prompt_builder = PromptBuilder()
        self.validator = SchemaValidator(strictness="normal")

    def summarize(
        self,
        transcript: str,
        template_name: str,
        enabled_blocks: List[str] = None,
        params: Dict = None,
        title: str = "Unknown",
        guest: str = "Unknown",
        retry_on_failure: bool = True
    ) -> Dict[str, Any]:
        """
        Generate summary from transcript using specified template.

        Args:
            transcript: Podcast transcript text
            template_name: Name of template to use
            enabled_blocks: List of block IDs to enable (None = use defaults)
            params: Parameter values (e.g., {"length": "long"})
            title: Podcast episode title
            guest: Guest name
            retry_on_failure: Whether to retry on validation failure

        Returns:
            {
                "data": parsed summary data,
                "usage": token usage info,
                "model": model used,
                "elapsed_seconds": time taken,
                "template_name": template used,
                "enabled_blocks": list of enabled block IDs
            }
        """
        params = params or {}

        # 1. Load template
        template = self._load_template(template_name)
        if not template:
            raise ValueError(f"Template not found: {template_name}")

        logger.info(f"Using template: {template_name}")

        # 2. Resolve enabled blocks
        actual_blocks = self.prompt_builder.get_enabled_block_ids(template, enabled_blocks)
        logger.info(f"Enabled blocks: {actual_blocks}")

        # 3. Build messages
        messages = self.prompt_builder.build(
            template=template,
            transcript=transcript,
            enabled_blocks=enabled_blocks,
            params=params,
            title=title,
            guest=guest
        )

        # 4. Get max_tokens
        max_tokens = self.prompt_builder.get_max_tokens(template, params)
        logger.info(f"Max tokens: {max_tokens}")

        # 5. Call LLM with retry logic
        result = self._call_with_retry(
            messages=messages,
            template=template,
            enabled_blocks=actual_blocks,
            max_tokens=max_tokens,
            retry_on_failure=retry_on_failure
        )

        # 6. Add metadata
        result["template_name"] = template_name
        result["enabled_blocks"] = actual_blocks

        return result

    def summarize_episode(
        self,
        episode_id: ObjectId,
        template_name: str,
        enabled_blocks: List[str] = None,
        params: Dict = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Summarize an episode by ID.

        This is a higher-level method that handles:
        - Loading episode and transcript from database
        - Checking for existing summary
        - Saving result to database

        Args:
            episode_id: Episode ObjectId
            template_name: Template name to use
            enabled_blocks: Block IDs to enable
            params: Parameter values
            force: Force regenerate even if exists

        Returns:
            Summary document
        """
        # 1. Check existing
        if not force:
            existing = self.db.summaries.find_one({
                "episode_id": episode_id,
                "template_name": template_name
            })
            if existing:
                logger.info(f"Summary already exists for episode {episode_id}")
                return existing

        # 2. Load episode
        episode = self.db.episodes.find_one({"_id": episode_id})
        if not episode:
            raise ValueError(f"Episode not found: {episode_id}")

        # 3. Load transcript
        transcript = self.db.transcripts.find_one({"episode_id": episode_id})
        if not transcript or not transcript.get("text"):
            raise ValueError(f"Transcript not found for episode: {episode_id}")

        transcript_text = transcript["text"]
        title = episode.get("title", "Unknown")
        guest = self._extract_guest(episode)

        logger.info(f"Summarizing episode: {title}, transcript length: {len(transcript_text)}")

        # 4. Generate summary
        result = self.summarize(
            transcript=transcript_text,
            template_name=template_name,
            enabled_blocks=enabled_blocks,
            params=params,
            title=title,
            guest=guest
        )

        # 5. Create and save document
        summary_doc = self._create_summary_document(
            episode_id=episode_id,
            template_name=template_name,
            enabled_blocks=result["enabled_blocks"],
            params=params or {},
            content=result["data"],
            usage=result["usage"],
            model=result["model"],
            elapsed=result["elapsed_seconds"]
        )

        # Upsert to database
        self.db.summaries.update_one(
            {"episode_id": episode_id, "template_name": template_name},
            {"$set": summary_doc},
            upsert=True
        )

        # Get saved document
        saved_doc = self.db.summaries.find_one({
            "episode_id": episode_id,
            "template_name": template_name
        })

        # 6. Update episode status
        self.db.episodes.update_one(
            {"_id": episode_id},
            {"$set": {
                "has_summary": True,
                "status": "summarized",
                "updated_at": datetime.utcnow()
            }}
        )

        logger.info(f"Summary saved for episode {episode_id}")
        return saved_doc

    def _load_template(self, name: str) -> Optional[Dict]:
        """Load template from database"""
        return self.db.prompt_templates.find_one({
            "name": name,
            "is_active": True
        })

    def _call_with_retry(
        self,
        messages: List[Dict],
        template: Dict,
        enabled_blocks: List[str],
        max_tokens: int,
        retry_on_failure: bool
    ) -> Dict:
        """Call LLM with retry on validation failure"""
        last_error = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                # Call LLM
                result = self.llm.chat_json(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.2
                )

                data = result.get("data", {})

                # Validate
                is_valid, errors = self.validator.validate(
                    data=data,
                    template=template,
                    enabled_blocks=enabled_blocks
                )

                if is_valid:
                    return result
                else:
                    logger.warning(f"Validation errors (attempt {attempt + 1}): {errors}")
                    if not retry_on_failure or attempt >= self.MAX_RETRIES:
                        # Use lenient mode to fill defaults
                        result["data"] = self.validator.ensure_required_fields(data, template)
                        logger.warning("Using lenient validation with defaults")
                        return result

                    # Add correction hint for retry
                    messages = self._add_correction_hint(messages, errors)

            except Exception as e:
                last_error = e
                logger.error(f"LLM call failed (attempt {attempt + 1}): {e}")
                if attempt >= self.MAX_RETRIES:
                    raise

        raise last_error or Exception("Max retries exceeded")

    def _add_correction_hint(self, messages: List[Dict], errors: List[str]) -> List[Dict]:
        """Add correction hint to messages for retry"""
        hint = (
            "\n\nIMPORTANT: Your previous response had validation issues:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\n\nPlease ensure your response includes all required fields with correct types."
        )

        new_messages = list(messages)
        if new_messages and new_messages[-1]["role"] == "user":
            new_messages[-1] = {
                "role": "user",
                "content": new_messages[-1]["content"] + hint
            }

        return new_messages

    def _create_summary_document(
        self,
        episode_id: ObjectId,
        template_name: str,
        enabled_blocks: List[str],
        params: Dict,
        content: Dict,
        usage: Dict,
        model: str,
        elapsed: float
    ) -> Dict:
        """Create summary document for database"""
        now = datetime.utcnow()

        return {
            "episode_id": episode_id,
            "template_name": template_name,
            "enabled_blocks": enabled_blocks,
            "params": params,
            "version": "v3",  # New version for structured templates

            # Extract top-level fields
            "tldr": content.get("tldr", ""),
            "tags": content.get("tags", []),

            # Full content
            "content": content,

            # Meta
            "model": model,
            "tokens_used": usage,
            "generation_time_seconds": elapsed,

            "created_at": now,
            "updated_at": now
        }

    def _extract_guest(self, episode: Dict) -> str:
        """Extract guest name from episode info"""
        title = episode.get("title", "")

        # Pattern: "#123 - Guest Name: Topic"
        if " - " in title:
            parts = title.split(" - ", 1)
            if len(parts) > 1:
                guest_part = parts[1].split(":")[0].strip()
                return guest_part

        # Pattern: "Guest Name | Topic"
        if " | " in title:
            parts = title.split(" | ")
            return parts[0].strip()

        return "Unknown"

    def get_available_templates(self) -> List[Dict]:
        """Get list of available templates"""
        templates = self.db.prompt_templates.find({"is_active": True})
        return [
            {
                "name": t["name"],
                "display_name": t.get("display_name"),
                "description": t.get("description"),
                "is_system": t.get("is_system", False),
                "blocks_count": len(t.get("optional_blocks", []))
            }
            for t in templates
        ]


def get_summarization_engine(db, llm_client=None) -> SummarizationEngine:
    """
    Get summarization engine instance.

    Args:
        db: MongoDB database instance
        llm_client: Optional LLM client (will create default if not provided)
    """
    if llm_client is None:
        from app.services.llm_client import get_llm_client
        llm_client = get_llm_client()

    return SummarizationEngine(db, llm_client)
