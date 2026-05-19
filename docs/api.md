# API 接口文档

> 基于当前 `backend/app/api/` 代码整理，更新于 2026-05-20。

## 基础信息

| 项目 | 值 |
| --- | --- |
| Base URL | `http://localhost:5000/api` |
| 数据格式 | JSON |
| 编码 | UTF-8 |

## 通用响应

```json
{ "success": true, "data": {}, "message": null }
```

```json
{ "success": false, "data": null, "message": "...", "error_code": "..." }
```

## Feeds API

| 方法 | 端点 | 说明 |
| --- | --- | --- |
| `GET` | `/api/feeds` | 获取订阅列表，支持分页和筛选 |
| `GET` | `/api/feeds/<id>` | 获取单个订阅详情 |
| `POST` | `/api/feeds` | 添加订阅并解析 RSS |
| `PUT` | `/api/feeds/<id>` | 更新订阅状态、标签、备注 |
| `DELETE` | `/api/feeds/<id>` | 删除订阅并级联删除相关数据 |
| `POST` | `/api/feeds/<id>/refresh` | 异步刷新订阅，返回 `task_id` |
| `POST` | `/api/feeds/<id>/favorite` | 收藏或取消收藏订阅 |
| `GET` | `/api/feeds/<id>/episodes` | 获取订阅下的单集 |

## Episodes API

| 方法 | 端点 | 说明 |
| --- | --- | --- |
| `GET` | `/api/episodes` | 获取单集列表 |
| `GET` | `/api/episodes/<id>` | 获取单集详情 |
| `PUT` | `/api/episodes/<id>` | 更新已读、收藏、播放位置等字段 |
| `POST` | `/api/episodes/<id>/star` | 标星或取消标星 |
| `POST` | `/api/episodes/<id>/read` | 标记已读或未读 |
| `POST` | `/api/episodes/<id>/download` | 异步下载音频，返回 `task_id` |

`GET /api/episodes` 支持 `status` 逗号多值筛选，例如：

```text
/api/episodes?status=downloading,downloaded,transcribing,transcribed
```

## Transcripts API

| 方法 | 端点 | 说明 |
| --- | --- | --- |
| `GET` | `/api/transcripts/<episode_id>` | 获取已有转录 |
| `POST` | `/api/transcripts/<episode_id>` | 创建异步转录任务 |
| `DELETE` | `/api/transcripts/<episode_id>` | 删除已有转录 |
| `POST` | `/api/transcripts/<episode_id>/fetch` | 手动抓取官方/外部字幕 |
| `GET` | `/api/transcripts/<episode_id>/check-external` | 检查是否存在外部字幕 |

创建转录任务：

```json
{
  "provider": "local_whisper",
  "language": "zh"
}
```

`provider` 可选值：

| 值 | 说明 |
| --- | --- |
| `official` | 使用 RSS 暴露的官方字幕 URL |
| `local_whisper` | 使用本地 faster-whisper，需要本地音频 |
| `local_whisperx` | 使用本地 WhisperX，需要本地音频 |
| `assemblyai` | 使用 AssemblyAI 云端转录，需要显式开启云端配置 |
| `auto` | 后端辅助模式，有官方字幕时使用官方字幕，不自动 fallback 到付费云端 |
| `manual` | 预留，当前接口不支持直接创建 |

`language` 可选值：

```text
auto, zh, en, en_us, en_uk, ja, ko, es, fr, de
```

中文播客建议显式传：

```json
{ "provider": "local_whisper", "language": "zh" }
```

所有 provider 保存前都会经过统一转录后处理：

- 清理中文字符之间的异常空格。
- 清理中文标点前后的异常空格。
- 如果安装了 OpenCC，会尝试繁体转简体。
- 如果 `TRANSCRIPTION_AI_NORMALIZE_ENABLED=1`，会调用当前 LLM 配置做 AI 文本规范化。

进入单集详情页不会自动抓取外部字幕或启动转录；必须由用户主动点击。

## Summaries API

| 方法 | 端点 | 说明 |
| --- | --- | --- |
| `GET` | `/api/summaries/<episode_id>` | 获取摘要，支持 `template_name` |
| `POST` | `/api/summaries/<episode_id>` | 创建异步摘要任务 |
| `DELETE` | `/api/summaries/<episode_id>` | 删除摘要 |
| `POST` | `/api/summaries/<episode_id>/translate` | 翻译摘要为中文 |

创建摘要任务：

```json
{
  "template_name": "learning",
  "enabled_blocks": ["key_points", "action_items"],
  "params": { "length": "long", "language": "zh" },
  "force": false
}
```

## Tasks API

| 方法 | 端点 | 说明 |
| --- | --- | --- |
| `GET` | `/api/tasks` | 获取任务列表，支持筛选 |
| `GET` | `/api/tasks/<task_id>` | 获取任务详情 |
| `POST` | `/api/tasks/<task_id>/cancel` | 取消 pending 任务 |

查询示例：

```text
/api/tasks?status=pending,processing&type=transcribe&episode_id=<episode_id>
```

任务响应会带上关联内容信息，供前端任务历史跳转：

```json
{
  "id": "task-id",
  "type": "transcribe",
  "status": "processing",
  "progress": 42,
  "episode_id": "...",
  "feed_id": "...",
  "episode_title": "Episode title",
  "episode_status": "transcribing",
  "feed_title": "Podcast title",
  "target_type": "episode",
  "target_id": "...",
  "target_exists": true
}
```

任务类型：

```text
download, transcribe, summarize, translate, refresh
```

任务状态：

```text
pending, processing, completed, failed
```

## Settings API

| 方法 | 端点 | 说明 |
| --- | --- | --- |
| `GET` | `/api/settings/llm` | 获取 LLM 配置列表 |
| `PUT` | `/api/settings/llm` | 保存 LLM 配置列表 |
| `PUT` | `/api/settings/llm/active` | 设置当前激活 LLM |
| `POST` | `/api/settings/llm/test` | 测试 OpenAI-compatible LLM 连接 |
| `GET` | `/api/settings/tavily` | 获取 Tavily 配置 |
| `PUT` | `/api/settings/tavily` | 保存 Tavily 配置 |
| `POST` | `/api/settings/tavily/test` | 测试 Tavily 连接 |

LLM 配置保存在 MongoDB：

```text
database: podcast
collection: settings
key: llm_configs
key: llm_active_index
```

接口返回时不会返回完整 `api_key`，只返回 `has_api_key`。当前数据库仍是明文保存 key，本地 demo 可接受；上线前应改为环境变量、加密保存或 secret manager。

## Prompt Templates API

| 方法 | 端点 | 说明 |
| --- | --- | --- |
| `GET` | `/api/prompt-templates` | 获取模板列表 |
| `GET` | `/api/prompt-templates/<id_or_name>` | 获取单个模板 |
| `POST` | `/api/prompt-templates` | 创建模板 |
| `PUT` | `/api/prompt-templates/<id>` | 更新模板 |
| `DELETE` | `/api/prompt-templates/<id>` | 删除模板 |
| `POST` | `/api/prompt-templates/<id>/duplicate` | 复制模板 |
| `POST` | `/api/prompt-templates/init` | 初始化系统模板 |

## Insights API

| 方法 | 端点 | 说明 |
| --- | --- | --- |
| `GET` | `/api/insights/briefing` | 获取每日简报 |
| `POST` | `/api/insights/briefing` | 重新生成每日简报 |
| `GET` | `/api/insights/briefing/export` | 导出 PDF |

## 常见错误码

| 错误码 | 说明 |
| --- | --- |
| `EPISODE_NOT_FOUND` | 单集不存在 |
| `TRANSCRIPT_NOT_FOUND` | 转录不存在 |
| `SUMMARY_NOT_FOUND` | 摘要不存在 |
| `TASK_NOT_FOUND` | 任务不存在 |
| `TASK_IN_PROGRESS` | 任务正在进行中 |
| `ALREADY_TRANSCRIBING` | 单集正在转录 |
| `ALREADY_TRANSCRIBED` | 单集已有转录 |
| `LOCAL_AUDIO_NOT_FOUND` | 本地音频文件不存在 |
| `CLOUD_TRANSCRIPTION_DISABLED` | 云端转录未开启 |
| `UNSUPPORTED_TRANSCRIPTION_PROVIDER` | 不支持的转录 provider |
| `UNSUPPORTED_TRANSCRIPTION_LANGUAGE` | 不支持的转录语言 |
