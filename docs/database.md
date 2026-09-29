# 数据库设计

> 从 `backend/app/models/` + `backend/app/__init__.py` 源码提取。
> 数据库: MongoDB，库名 `podcast`。

---

## 集合总览

| 集合 | 模型文件 | 主要用途 |
|------|---------|---------|
| `users` | `models/user.py` | 用户认证 |
| `feeds` | `models/feed.py` | 订阅源（RSS / YouTube / B站，`type` 分流） |
| `episodes` | `models/episode.py` | 播客单集 |
| `user_episode_states` | `services/user_episode_state.py` | 剧集个人状态（已读/加星/播放进度，按用户隔离） |
| `transcripts` | `models/transcript.py` | 转录文本 |
| `summaries` | `models/summary.py` | AI 摘要 |
| `tasks` | `models/task.py` | 异步任务 |
| `settings` | `models/setting.py` | 应用配置（全局一套，无 owner） |
| `prompt_templates` | `models/prompt_template.py` | 提示词模板 |
| `briefings` | 无独立模型 | AI 简报缓存 |

---

## users

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | |
| `email` | string | 唯一，用于登录 |
| `password_hash` | string | bcrypt 哈希 |
| `role` | string | `"user"` / `"admin"` |
| `status` | string | `"active"` / `"disabled"` |
| `created_at` | datetime | |
| `updated_at` | datetime | |
| `last_login_at` | datetime | nullable |

**索引**: `email` (unique), `role`, `status`

---

## feeds

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | |
| `rss_url` | string | RSS 地址 |
| `owner_id` | string | 用户隔离 |
| `title` | string | 播客标题 |
| `website` | string | |
| `image` | string | 封面图 |
| `description` | string | |
| `author` | string | |
| `language` | string | |
| `status` | string | `active` / `paused` / `error` |
| `last_checked` | datetime | nullable |
| `last_updated` | datetime | nullable |
| `check_error` | string | nullable，刷新错误信息 |
| `is_starred` | bool | 默认 false |
| `is_favorite` | bool | 默认 false |
| `tags` | array | 标签列表 |
| `episode_count` | int | 默认 0 |
| `unread_count` | int | 默认 0 |
| `note` | string | nullable，用户备注 |
| `created_at` | datetime | |
| `updated_at` | datetime | |

**索引**: `(owner_id, rss_url)` unique, `owner_id`, `status`, `is_starred`, `is_favorite`, `created_at`

---

## episodes

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | |
| `feed_id` | ObjectId | 所属 feed |
| `owner_id` | string | 用户隔离 |
| `guid` | string | RSS 全局唯一 ID |
| `title` | string | |
| `summary` | string | RSS summary |
| `content` | string | RSS content:encoded |
| `link` | string | |
| `published` | datetime | 发布时间 |
| `audio_url` | string | 远程音频地址 |
| `audio_type` | string | 默认 `"audio/mpeg"` |
| `audio_size` | int | 字节，默认 0 |
| `duration` | int | 秒，默认 0 |
| `image` | string | nullable |
| `chapters_url` | string | nullable |
| `transcript_url` | string | nullable，外部转录源 |
| `status` | string | 状态机: `new` → `downloading` → `downloaded` → `transcribing` → `transcribed` → `summarizing` → `summarized` (或 `error`) |
| `local_path` | string | nullable，下载后的本地路径 |
| `is_read` | bool | 默认 false |
| `is_starred` | bool | 默认 false |
| `is_favorite` | bool | 默认 false |
| `play_position` | int | 播放进度（秒），默认 0 |
| `popularity_score` | int | 默认 0 |
| `has_transcript` | bool | 转录完成后设为 true |
| `has_summary` | bool | 摘要完成后设为 true |
| `transcript_source` | string | `"official"` / `"local_whisper"` / `"assemblyai"` / `"external"` 等 |
| `last_download_error` | string | nullable |
| `last_transcript_error` | string | nullable |
| `last_summary_error` | string | nullable |
| `created_at` | datetime | |
| `updated_at` | datetime | |

**索引**: `feed_id`, `(owner_id, feed_id, guid)` unique, `owner_id`, `status`, `is_starred`, `published`, `has_transcript`, `has_summary`, `(feed_id, is_read)`

---

## transcripts

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | |
| `episode_id` | ObjectId | |
| `owner_id` | string | 用户隔离 |
| `text` | string | 完整转录文本 |
| `segments` | array | 时间戳分段 |
| `language` | string | 默认 `"en"` |
| `word_count` | int | 从 text 计算 |
| `source` | string | `"whisper"` / `"official"` / `"assemblyai"` / `"external"` 等 |
| `model` | string | 使用的模型，默认 `"base"` |
| `postprocess` | object | nullable，后处理结果 |
| `chapters` | array | nullable，AssemblyAI 章节 |
| `entities` | array | nullable |
| `speakers` | array | nullable |
| `duration` | float | nullable |
| `created_at` | datetime | |
| `updated_at` | datetime | |

**索引**: `(owner_id, episode_id)` unique, `owner_id`

---

## summaries

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | |
| `episode_id` | ObjectId | |
| `owner_id` | string | 用户隔离 |
| `template_name` | string | 使用的模板名 |
| `enabled_blocks` | array | 启用的输出块 |
| `params` | object | 模板参数 |
| `version` | string | 当前 `"v3"` |
| `tldr` | string | 一句话总结 |
| `tags` | array | 关键词标签 |
| `content` | object | LLM 完整输出 |
| `content_zh` | object | 中文翻译 |
| `model` | string | 使用的 LLM 模型 |
| `tokens_used` | object | `{ prompt, completion, total }` |
| `generation_time_seconds` | float | |
| `translation_model` | string | nullable |
| `translation_tokens` | object | nullable |
| `translated_at` | datetime | nullable |
| `created_at` | datetime | |
| `updated_at` | datetime | |

**索引**: `episode_id`, `(episode_id, template_name)`, `owner_id`

---

## tasks

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | |
| `task_id` | string | UUID |
| `task_type` | string | `download` / `transcribe` / `summarize` / `translate` / `refresh` |
| `episode_id` | string | |
| `feed_id` | ObjectId | nullable |
| `owner_id` | string | nullable |
| `status` | string | `pending` → `processing` → `completed` / `failed` |
| `progress` | int | 0-100 |
| `result` | object | nullable |
| `error_message` | string | nullable |
| `created_at` | datetime | |
| `started_at` | datetime | nullable |
| `completed_at` | datetime | nullable |

**索引**: `task_id` unique, `owner_id`, `status`, `episode_id`, `created_at`, `completed_at` (TTL 7 天)

---

## settings

KV 存储，按 `owner_id` 隔离。

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | |
| `key` | string | 配置键 |
| `value` | any | 配置值 |
| `owner_id` | string | nullable，用户隔离 |
| `created_at` | datetime | |
| `updated_at` | datetime | |

**预定义键**:

| 键 | 内容 |
|----|------|
| `llm_providers` | 服务商列表 [{ id, name, api_format, base_url, api_key, enabled }] |
| `llm_models` | 模型列表 [{ id, provider_id, model, enabled, supports_streaming }] |
| `llm_default_model_id` | 默认模型 ID |
| `llm_task_routes` | 任务路由 { summary, briefing, transcript_normalize } → model_id |
| `tavily_config` | Tavily 搜索配置 |

---

## prompt_templates

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | |
| `name` | string | 唯一标识 |
| `display_name` | string | 显示名 |
| `description` | string | |
| `locked` | object | 不可修改的部分: { system_prompt, output_format_instruction, required_fields } |
| `optional_blocks` | array | 可选输出块 [{ id, name, name_zh, prompt_fragment, output_field, enabled_by_default, order }] |
| `parameters` | object | 模板参数 (enum/range/boolean) |
| `user_prompt_template` | string | 用户提示词模板 |
| `is_system` | bool | 系统模板不可修改 |
| `is_active` | bool | |
| `parent_id` | ObjectId | nullable，复制来源 |
| `version` | int | |
| `created_at` | datetime | |
| `updated_at` | datetime | |

**索引**: `name` unique, `is_active`, `is_system`

---

## briefings

无独立模型，由 `services/briefing_service.py` 直接操作。

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | |
| `date` | string | `"YYYY-MM-DD"` (UTC) |
| `briefing` | object | LLM 生成的简报内容 |
| `episode_count` | int | |
| `created_at` | datetime | |

**索引**: `date` unique

---

## user_episode_states

共享库模式下剧集全员可见，个人状态按用户隔离存储（`services/user_episode_state.py`）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | string | 用户 id（users._id 字符串） |
| `episode_id` | ObjectId | 剧集 id |
| `is_read` | bool | 已读 |
| `is_starred` | bool | 加星 |
| `play_position` | int | 播放进度（秒） |
| `updated_at` | datetime | |

**索引**: `(user_id, episode_id)` unique, `episode_id`

---

## 数据治理决策（2026-09-30）

演进过程中确立的原则，改动相关逻辑前先读这里：

1. **订阅全局唯一**：按规范化 URL（去 `utm_*`/`spm*` 参数、去尾斜杠、小写）去重，共享库下不允许同一来源重复订阅（入口校验在 `api/feeds.py` `_normalize_feed_url`）。
2. **个人状态不入剧集文档**：`episodes.is_read / is_starred / play_position` 已弃用（仅历史数据保留），读写走 `user_episode_states`；feeds 列表的未读数按请求用户实时计算，`feeds.unread_count` 不再落库维护。
3. **settings 只存全局键**：LLM 配置全员共用一套（管理员维护），不允许 per-user 键；`_id: "ai_analysis"` 的文档是 AI 总开关，按 `_id` 字符串存取。
4. **弃用字段**：`episodes.transcript_source`（文稿来源唯一真源是 `transcripts.source`）；上一条中的三个个人状态字段。
5. **viewer 只读**：个人状态写入接口要求 user/admin 角色。
