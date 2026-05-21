# AI API Config Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the AI API settings area around provider-first configuration, safe API key handling, ModelScope defaults, API format metadata, and task-to-model routing.

**Architecture:** Keep the existing `/api/settings/llm` endpoint and MongoDB `settings` storage, but extend each config with `id`, `provider`, `api_format`, `supports_streaming`, and `enabled`. Add a separate `llm_task_routes` setting so tasks can only choose configured models. The frontend becomes a provider-first settings panel with a routing section sourced from available configs.

**Tech Stack:** Flask, MongoDB settings model, OpenAI SDK for OpenAI-compatible providers, optional Anthropic Messages adapter via HTTP, React + Vite + TailwindCSS, pytest, `npm run build`.

---

### Task 1: Ignore Visual Companion Scratch Files

**Files:**
- Modify: `.gitignore`

- [ ] Add `.superpowers/` to `.gitignore`.
- [ ] Run `git status --short --untracked-files=all`.
- [ ] Commit with `chore: 忽略 superpowers 临时草图`.

### Task 2: Backend LLM Config Schema

**Files:**
- Modify: `backend/app/models/setting.py`
- Modify: `backend/app/api/settings.py`
- Test: `backend/tests/test_settings_api.py`
- Modify: `backend/.env.example`

- [ ] Add failing tests that default LLM config is ModelScope, API keys are masked, configs receive stable IDs, and task routes reject unavailable config IDs.
- [ ] Run `uv run pytest tests/test_settings_api.py` and confirm failure.
- [ ] Extend `SettingModel` with `KEY_LLM_TASK_ROUTES`, config normalization, ModelScope default values, and task route validation.
- [ ] Extend settings API response with `task_routes` and accept `task_routes` on save.
- [ ] Update `.env.example` with ModelScope default comments and no real API key.
- [ ] Run target tests and commit `feat: 扩展 AI API 配置模型和任务路由`.

### Task 3: LLM Client Adapter Metadata

**Files:**
- Modify: `backend/app/services/llm_client.py`
- Test: `backend/tests/test_llm_client.py` or extend existing AI tests

- [ ] Add failing tests for creating OpenAI-compatible client from `api_format=openai_compatible`.
- [ ] Add failing test that `api_format=anthropic_messages` is accepted by the config object and surfaces a clear unsupported/missing dependency error only when called if not fully configured.
- [ ] Implement minimal adapter branching without changing existing call sites.
- [ ] Run target tests and backend full tests.
- [ ] Commit `feat: 支持 AI API 格式元数据`.

### Task 4: Provider-First Frontend Panel

**Files:**
- Rewrite: `frontend/src/components/views/settings/LlmConfigPanel.jsx`
- Modify: `frontend/src/locales/zh.json`
- Modify: `frontend/src/locales/en.json`

- [ ] Rebuild panel layout around provider presets, with ModelScope first.
- [ ] Add API key visible/hidden toggle.
- [ ] Move max tokens into an advanced section.
- [ ] Add task routing section where dropdown options come only from enabled configured providers.
- [ ] Keep existing `settingsApi.getLlmConfigs/saveLlmConfigs/testLlmConnection` service names.
- [ ] Run `npm run build`.
- [ ] Commit `feat: 重塑 AI API 配置界面`.

### Task 5: Secret Handling Documentation

**Files:**
- Modify: `README_CN.md`
- Modify: `README.md` if needed

- [ ] Document that real API keys belong in `backend/.env` or MongoDB settings, not Git.
- [ ] Document the ModelScope default provider and model.
- [ ] Run `git status`.
- [ ] Commit `docs: 说明 AI API 密钥和默认模型配置`.
