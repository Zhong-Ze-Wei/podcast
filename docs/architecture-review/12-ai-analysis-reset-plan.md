# AI Analysis Freeze and Reset Plan

Date: 2026-05-17

## Current Status

AI analysis is now soft-frozen by default.

Set `AI_ANALYSIS_ENABLED=1` only when intentionally testing the legacy AI generation path. When the flag is not enabled:

- Existing episode summaries remain readable.
- Existing cached daily briefings remain readable.
- New summary generation is blocked.
- Summary translation is blocked.
- Daily briefing regeneration is blocked.
- `GET /api/insights/briefing` does not auto-generate a new briefing when no cache exists.

This is a reversible freeze. No old v2/v3 summary data, prompt templates, or prompt files were deleted.

## Product Functions That Still Matter

Core non-AI functions:

- RSS subscription management.
- Feed refresh and episode ingestion.
- Episode list/workspace browsing.
- Local audio download.
- Local-first audio playback with remote fallback.
- Official transcript fetching.
- Manual/cloud transcript generation.
- Transcript reading and deletion.
- Task progress tracking.
- Existing summary display.
- Existing cached briefing display/export.
- LLM settings UI, currently retained but not used for new generation while frozen.

AI functions currently frozen:

- New episode summary generation.
- Summary regeneration.
- Summary translation.
- Daily AI briefing generation/regeneration.

## Current AI File Map

Frontend AI entry points:

- `frontend/src/components/views/EpisodeDetailView.jsx`
  - Loads transcripts.
  - Loads existing summaries.
  - Previously submitted summary generation and regeneration.
  - Now disables summary generation when AI is frozen.

- `frontend/src/components/views/AIBriefingView.jsx`
  - Loads cached briefing.
  - Previously regenerated daily briefing.
  - Now disables generation when AI is frozen.

- `frontend/src/services/api.js`
  - Defines `summariesApi`, `promptTemplatesApi`, and `insightsApi`.

Backend API entry points:

- `backend/app/api/summaries.py`
  - `GET /api/summaries/<episode_id>` reads existing summary.
  - `POST /api/summaries/<episode_id>` is frozen by default.
  - `POST /api/summaries/<episode_id>/translate` is frozen by default.
  - `DELETE /api/summaries/<episode_id>` still deletes summaries.
  - `GET /api/summaries/templates` still lists templates.

- `backend/app/api/insights.py`
  - `GET /api/insights/briefing` reads cached briefing only while frozen.
  - `POST /api/insights/briefing` is frozen by default.
  - `GET /api/insights/briefing/export` exports cached briefing only.

- `backend/app/api/prompt_templates.py`
  - CRUD for legacy prompt templates.
  - Retained for inspection and compatibility.

Backend AI generation implementation:

- `backend/app/services/summary_service.py`
  - Legacy summary orchestration wrapper.
  - Calls the v3 summarization engine.
  - Also contains translation prompts.

- `backend/app/core/summarization/engine.py`
  - Loads prompt templates.
  - Builds prompts.
  - Calls LLM.
  - Validates JSON.
  - Saves summary documents.

- `backend/app/core/summarization/prompt_builder.py`
  - Converts template definitions into LLM messages and JSON schema text.

- `backend/app/core/summarization/schema_validator.py`
  - Validates LLM JSON output against selected blocks.

- `backend/app/core/summarization/defaults/templates.py`
  - Legacy/default v3 prompt templates and optional block definitions.

- `backend/app/models/summary.py`
  - Converts summary documents to API response.
  - Still carries compatibility behavior for old frontend fields.

- `backend/app/models/prompt_template.py`
  - Data model for prompt template documents.

- `backend/app/services/briefing_service.py`
  - Collects recent episodes and summaries.
  - Calls LLM to generate daily briefing.

- `backend/app/services/briefing_prompts.py`
  - Daily briefing prompts.

- `backend/app/services/llm_client.py`
  - OpenAI-compatible LLM client.

Freeze control:

- `backend/app/services/ai_control.py`
  - Central `AI_ANALYSIS_ENABLED` gate.
  - Shared disabled message.

## Why The Current AI Design Feels Uncontrolled

The current system mixes several concerns:

- Summary generation and summary translation live in the same service.
- Prompt templates are editable data, but default templates are also hardcoded Python data.
- The API claims to use `template_name`, while historical `summary_type` compatibility still exists elsewhere.
- Summary result data is partly `content`, partly top-level fields, and partly dynamic `blocks`.
- Frontend rendering knows too many summary field names.
- Daily briefing consumes both RSS metadata and AI summaries, then calls another AI prompt.

This makes debugging difficult because one user action can cross API, task queue, transcript, prompt template, LLM, validator, summary model, and frontend rendering code.

## Reset Strategy

Do not delete legacy AI files yet. Use a staged replacement:

1. Keep AI frozen.
2. Define a new `analysis_v1` contract before writing generation code.
3. Build the new analysis pipeline in separate files.
4. Make the frontend render only generic blocks.
5. Add tests for the new contract.
6. Switch one template/use case to the new pipeline.
7. Confirm old v2/v3 generation has no callers.
8. Delete legacy prompts and services only after the replacement path is proven.

## Proposed New Contract

Future generated analysis should look like:

```json
{
  "analysis_id": "...",
  "episode_id": "...",
  "version": "analysis_v1",
  "language": "zh",
  "model": "provider/model",
  "tokens_used": {
    "prompt": 0,
    "completion": 0,
    "total": 0
  },
  "elapsed_ms": 0,
  "transcript_chars": 0,
  "blocks": [
    {
      "id": "key_points",
      "title": "核心要点",
      "type": "list",
      "content": ["..."]
    }
  ],
  "created_at": "..."
}
```

Rules:

- The frontend should not know hardcoded fields like `investment_signals`, `core_content`, or `guest_background`.
- Old summaries may be adapted into blocks for display.
- New generation should save blocks as the primary result.
- Legacy v2/v3 data remains read-only until deletion is explicitly planned.

## Suggested Next Step

Before rebuilding AI generation, implement a small read-only map screen or markdown doc that shows:

- existing feeds count,
- episodes count,
- downloaded count,
- transcribed count,
- summarized count,
- active tasks,
- frozen AI state.

That will help separate the stable podcast pipeline from the frozen AI analysis layer.
