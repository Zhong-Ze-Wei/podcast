# 数据库报告

> MongoDB 数据库：`podcast`
> 文档日期：2026-05-16

---

## 1. 概览

| 集合 | 说明 | 唯一约束 |
|------|------|----------|
| `feeds` | RSS 订阅源 | `rss_url` |
| `episodes` | 单集 | `(feed_id, guid)` 复合唯一 |
| `transcripts` | 转录文本 | `episode_id` |
| `summaries` | AI 摘要 | 无（支持一集多摘要）|
| `tasks` | 异步任务 | `task_id` |
| `settings` | 应用配置（LLM / Tavily）| 无 |
| `prompt_templates` | 摘要 Prompt 模板 | `name` |
| `briefings` | AI 日报缓存 | `date` |

---

## 2. 集合字段详情

### 2.1 feeds

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | MongoDB 主键 |
| `rss_url` | string | RSS 订阅地址（唯一索引）|
| `title` | string | 播客名称 |
| `website` | string | 播客网站 |
| `image` | string | 封面图 URL |
| `description` | string | 播客描述 |
| `author` | string | 作者 |
| `language` | string | 语言代码（如 en-US）|
| `status` | string | `active` / `paused` / `error` |
| `last_checked` | datetime | 最后检查时间 |
| `last_updated` | datetime | 最后有新单集时间 |
| `check_error` | string\|null | 最近一次错误信息 |
| `is_starred` | boolean | 是否标星 |
| `is_favorite` | boolean | 是否收藏 |
| `note` | string | 用户备注 |
| `tags` | array\<string\> | 标签列表 |
| `episode_count` | int | 单集总数 |
| `unread_count` | int | 未读单集数 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

**索引**：`rss_url (unique)`, `status`, `is_starred`, `created_at`

---

### 2.2 episodes

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | MongoDB 主键 |
| `feed_id` | ObjectId | 关联订阅源 |
| `guid` | string | RSS Entry 的唯一标识 |
| `title` | string | 单集标题 |
| `summary` | string | 单集简介（来自 RSS，已清理广告链接）|
| `content` | string | 单集完整内容（HTML 已清理）|
| `link` | string | 单集网页链接 |
| `published` | datetime | 发布时间 |
| `audio_url` | string | 远程音频地址 |
| `audio_type` | string | 音频 MIME 类型（如 audio/mpeg）|
| `audio_size` | int | 音频文件大小（字节）|
| `duration` | int | 时长（秒）|
| `image` | string | 单集封面图 URL |
| `chapters_url` | string\|null | 章节 JSON 地址（Podcasting 2.0）|
| `transcript_url` | string\|null | 官方字幕地址（Podcasting 2.0）|
| `status` | string | 见状态流转表 |
| `audio_path` | string\|null | 本地下载路径（相对 MEDIA_ROOT）|
| `is_read` | boolean | 是否已读 |
| `is_starred` | boolean | 是否标星 |
| `is_favorite` | boolean | 是否收藏 |
| `play_position` | int | 播放进度（秒）|
| `has_transcript` | boolean | 是否有转录 |
| `has_summary` | boolean | 是否有摘要 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

**Episode 状态枚举**：

| 状态 | 说明 |
|------|------|
| `new` | 新建，未处理 |
| `downloading` | 正在下载音频 |
| `downloaded` | 音频下载完成 |
| `transcribing` | 正在转录 |
| `transcribed` | 转录完成 |
| `summarizing` | 正在生成摘要 |
| `summarized` | 摘要生成完成 |
| `error` | 处理出错 |

**索引**：`feed_id`, `guid`, `(feed_id, guid) unique`, `status`, `is_starred`, `published`

---

### 2.3 transcripts

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | MongoDB 主键 |
| `episode_id` | ObjectId | 关联单集（唯一索引，1 集只有 1 条转录）|
| `text` | string | 完整转录文本 |
| `segments` | array | 分段信息（含时间戳、说话人，来自 AssemblyAI）|
| `language` | string | 语言代码 |
| `word_count` | int | 词数 |
| `source` | string | `whisper` / `official` / `manual` |
| `model` | string | 使用的模型（如 assembly_ai）|
| `created_at` | datetime | 创建时间 |

**索引**：`episode_id (unique)`

---

### 2.4 summaries

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | MongoDB 主键 |
| `episode_id` | ObjectId | 关联单集 |
| `summary_type` | string | 旧版类型：`general` / `investment` / `learning`（v2）|
| `template_name` | string | 新版模板名（v3，如 `learning` / `investment`）|
| `version` | string | `v2`（legacy）/ `v3`（新模板引擎）|
| `enabled_blocks` | array\<string\> | 已启用的 block ID 列表（v3）|
| `params` | object | 生成参数（如 `{"length": "long"}`）（v3）|
| `tldr` | string | 一句话摘要 |
| `tags` | array\<string\> | 标签 |
| `content` | object | 完整结构化内容（根据模板/类型不同字段不同）|
| `content_zh` | object\|null | 中文翻译版本 |
| `model` | string | 生成使用的 LLM 模型 |
| `tokens_used` | object | Token 消耗：`{prompt, completion, total}` |
| `generation_time_seconds` | float | 生成耗时 |
| `translated_at` | datetime\|null | 翻译完成时间 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

**content 字段示例（general 类型）**：
```json
{
  "tldr": "...",
  "tags": ["AI", "技术"],
  "key_points": ["..."],
  "why_it_matters": "..."
}
```

**content 字段示例（investment 类型）**：
```json
{
  "tldr": "...",
  "investment_signals": ["..."],
  "mentioned_tickers": ["AAPL"],
  "market_insights": ["..."],
  "risk_alerts": ["..."]
}
```

**索引**：`episode_id`, `(episode_id, template_name)`, `(episode_id, summary_type)`

> 注意：summaries 无唯一约束，同一集可存在多条不同 template_name 的摘要。

---

### 2.5 tasks

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | MongoDB 主键 |
| `task_id` | string | UUID 字符串（唯一索引）|
| `task_type` | string | `download` / `transcribe` / `summarize` / `refresh` |
| `episode_id` | ObjectId\|null | 关联单集（download/transcribe/summarize）|
| `feed_id` | ObjectId\|null | 关联订阅源（refresh）|
| `status` | string | `pending` / `processing` / `completed` / `failed` |
| `progress` | int | 进度 0-100 |
| `result` | object\|null | 任务结果 |
| `error_message` | string\|null | 错误信息 |
| `created_at` | datetime | 创建时间 |
| `started_at` | datetime\|null | 开始执行时间 |
| `completed_at` | datetime\|null | 完成时间 |

**索引**：`task_id (unique)`, `status`, `created_at`

---

### 2.6 settings

存储应用级配置，以 key-value 模式组织。

| 主要 key | 说明 |
|----------|------|
| `llm_configs` | LLM 配置列表（最多 5 个）+ 活动配置索引 |
| `tavily` | Tavily API Key 配置 |

LLM 配置结构（存储在 `llm_configs` 文档中）：

```json
{
  "configs": [
    {
      "name": "OpenAI GPT-4",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-...",
      "model": "gpt-4o-mini"
    }
  ],
  "active_index": 0
}
```

---

### 2.7 prompt_templates

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | MongoDB 主键 |
| `name` | string | 模板唯一标识（如 `learning`）（唯一索引）|
| `display_name` | string | 显示名称 |
| `description` | string | 模板描述 |
| `locked` | object | 锁定区域：system_prompt + output_format_instruction + required_fields |
| `optional_blocks` | array | 可选 block 列表，每个 block 含 id / name / prompt_fragment / output_field |
| `parameters` | object | 可调参数定义（如 length: enum[short, medium, long]）|
| `user_prompt_template` | string | 用户侧 prompt 模板（含 {{变量}} 占位符）|
| `is_system` | boolean | 是否系统内置模板（不可修改/删除）|
| `is_active` | boolean | 是否启用 |
| `parent_id` | ObjectId\|null | 复制自哪个模板 |
| `version` | int | 版本号（每次更新递增）|
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

**索引**：`name (unique)`, `is_active`, `is_system`

**内置系统模板**：`learning` / `investment` / `tech` / `startup` / `interview`

---

### 2.8 briefings

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | MongoDB 主键 |
| `date` | string | 日期字符串（YYYY-MM-DD，唯一索引）|
| `briefing` | object | 简报内容，含 `markdownReport` 字段 |
| `created_at` | datetime | 创建时间 |

**索引**：`date (unique)`

---

## 3. 索引汇总

| 集合 | 索引字段 | 类型 |
|------|----------|------|
| feeds | rss_url | unique |
| feeds | status, is_starred, created_at | 普通 |
| episodes | (feed_id, guid) | unique |
| episodes | feed_id, guid, status, is_starred, published | 普通 |
| transcripts | episode_id | unique |
| summaries | episode_id | 普通 |
| summaries | (episode_id, template_name) | 普通 |
| summaries | (episode_id, summary_type) | 普通 |
| tasks | task_id | unique |
| tasks | status, created_at | 普通 |
| prompt_templates | name | unique |
| prompt_templates | is_active, is_system | 普通 |
| briefings | date | unique |

---

## 4. 已知问题

| 问题 | 说明 |
|------|------|
| v2/v3 摘要混存 | `summaries` 集合中同时存在 `summary_type` (v2) 和 `template_name` (v3) 字段，查询逻辑复杂 |
| summaries 无唯一约束 | 同一集的同一 template_name 可能写入多条（依靠 upsert 防重，若并发可能重复）|
| settings 无 schema 约束 | key-value 结构无 MongoDB Schema Validation |
| 无 TTL 索引 | tasks 集合历史记录无过期清理机制，长期运行后数据膨胀 |
| briefings 无 TTL | 日报缓存无过期，历史日报永久保存 |
