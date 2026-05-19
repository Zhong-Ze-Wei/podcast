# 03 - 数据流详解

> 生成日期: 2026-05-17
> 每条流程用 Mermaid sequenceDiagram 展示，包含具体文件路径和行号引用。

---

## 1. 添加 RSS 订阅流程

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as feeds.py:create_feed
    participant Model as Feed / Episode
    participant RSS as RSSService
    participant DB as MongoDB

    FE->>API: POST /api/feeds {rss_url}
    API->>Model: Feed.validate_rss_url(rss_url) [SSRF 防护]
    API->>DB: db.feeds.find_one({rss_url}) [检查是否已存在]
    DB-->>API: null (不存在)
    API->>RSS: RSSService.parse_feed(rss_url)
    RSS->>RSS: HTTP GET RSS → feedparser.parse()
    RSS->>RSS: _extract_feed_info() + _extract_episodes()
    RSS-->>API: (feed_info, episodes)
    API->>Model: Feed.create(rss_url, title, ...) → feed_doc
    API->>DB: db.feeds.insert_one(feed_doc)
    DB-->>API: feed_id
    API->>Model: Episode.create(feed_id, guid, ...) × N
    API->>DB: db.episodes.insert_many(episode_docs)
    API-->>FE: {feed_id, episode_count, status: 201}
```

**代码位置:**
- API 入口: `backend/app/api/feeds.py` 第 82-153 行 (`create_feed`)
- RSS 解析: `backend/app/services/rss_service.py` (`parse_feed`)
- Model: `backend/app/models/feed.py` (`Feed.validate_rss_url`, `Feed.create`), `backend/app/models/episode.py` (`Episode.create`)
- 前端调用: `frontend/src/services/api.js` 第 47 行 (`feedsApi.create`)

---

## 2. 刷新订阅流程

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as feeds.py:refresh_feed
    participant TQ as TaskQueue
    participant Sync as _refresh_feed_sync
    participant RSS as RSSService
    participant DB as MongoDB

    FE->>API: POST /api/feeds/:id/refresh
    API->>DB: db.feeds.find_one({id})
    API->>TQ: task_queue.submit("refresh", _refresh_feed_sync)
    TQ-->>API: task_id
    API-->>FE: {task_id, status: "queued"}

    Note over TQ,Sync: 异步线程执行
    TQ->>Sync: _refresh_feed_sync(feed_id, progress_callback)
    Sync->>RSS: RSSService.parse_feed(rss_url)
    RSS-->>Sync: (feed_info, episodes)
    Sync->>DB: db.episodes.find({feed_id}, {guid:1}) [获取已有 guid 列表]
    DB-->>Sync: existing_guids: Set

    loop 每个 episode
        alt guid 不在 existing_guids 中
            Sync->>DB: db.episodes.insert_many(new_episodes)
        else guid 已存在
            Note over Sync: 跳过，保留已有状态
        end
    end

    Sync->>DB: db.feeds.update_one() [更新 last_checked / episode_count / unread_count]
    Sync-->>TQ: {new_episodes, total_episodes}
    TQ->>DB: tasks.status = "completed"
```

**代码位置:**
- API 入口: `backend/app/api/feeds.py` 第 217-237 行 (`refresh_feed`)
- 同步逻辑: `backend/app/api/feeds.py` 第 240-328 行 (`_refresh_feed_sync`)
- 前端调用: `frontend/src/services/api.js` 第 50 行 (`feedsApi.refresh`)

---

## 3. 下载音频流程

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as episodes.py:download_episode
    participant TQ as TaskQueue
    participant Sync as _download_episode_sync
    participant HTTP as Remote Audio
    participant FS as 文件系统
    participant DB as MongoDB

    FE->>API: POST /api/episodes/:id/download
    API->>DB: db.episodes.find_one({id})
    API->>API: Episode.can_download(status) [检查状态 == "new"]
    API->>DB: db.tasks.find_one({episode_id, type:"download", status:pending/processing})
    DB-->>API: null (无进行中任务)
    API->>DB: db.episodes.update_one({status: "downloading"})
    API->>TQ: task_queue.submit("download", _download_episode_sync)
    TQ-->>API: task_id
    API-->>FE: {task_id, status: "queued"}

    Note over TQ,FS: 异步线程执行
    TQ->>Sync: _download_episode_sync(episode_id, progress_callback)
    Sync->>Sync: progress_callback(10)
    Sync->>FS: 创建目录 media/audio/<feed_id>/
    Sync->>HTTP: requests.get(audio_url, stream=True, timeout=300)
    HTTP-->>Sync: response (streaming)

    loop 分块下载 (chunk_size=8192)
        Sync->>FS: 写入 chunk
        Sync->>TQ: progress_callback(10 → 90)
        Note over Sync: 实时检查文件大小 ≤ 500MB
    end

    Sync->>DB: db.episodes.update_one({status: "downloaded", local_path: "audio/feed_id/episode_id.mp3"})
    Sync->>Sync: progress_callback(100)
```

**代码位置:**
- API 入口: `backend/app/api/episodes.py` 第 221-284 行 (`download_episode`)
- 同步逻辑: `backend/app/api/episodes.py` 第 287-377 行 (`_download_episode_sync`)
- 配置: `backend/app/config.py` 第 20-21 行 (`MEDIA_ROOT`)
- 前端调用: `frontend/src/services/api.js` 第 65 行 (`episodesApi.download`)

---

## 4. 获取官方字幕流程

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as transcripts.py
    participant Fetcher as TranscriptFetcher
    participant Remote as 远程字幕源
    participant DB as MongoDB

    rect rgb(240, 248, 255)
        Note over FE,DB: 阶段 1: 检查是否有官方字幕
        FE->>API: GET /api/transcripts/:id/check-external
        API->>DB: db.episodes.find_one({id})
        alt episode.transcript_url 不存在
            API-->>FE: {has_external_transcript: false}
        else transcript_url 存在
            API->>Fetcher: TranscriptFetcher.validate_transcript_url(url) [HEAD 请求]
            Fetcher-->>API: true/false
            API-->>FE: {has_external_transcript: true/false, transcript_url}
        end
    end

    rect rgb(240, 255, 240)
        Note over FE,DB: 阶段 2: 获取官方字幕 (如果存在)
        FE->>API: POST /api/transcripts/:id/fetch
        API->>DB: db.episodes.find_one({id})
        API->>Fetcher: TranscriptFetcher.fetch_transcript(url)
        Fetcher->>Remote: HTTP GET
        Remote-->>Fetcher: SRT/VTT/JSON 内容

        alt URL 包含 .srt
            Fetcher->>Fetcher: _parse_srt(text)
        else URL 包含 .vtt
            Fetcher->>Fetcher: _parse_vtt(text)
        else URL 包含 .json
            Fetcher->>Fetcher: _parse_json_transcript(text)
        end

        Fetcher-->>API: (text, null)
        API->>DB: db.transcripts.update_one/upsert({episode_id}) [upsert]
        API->>DB: db.episodes.update_one({status: "transcribed", has_transcript: true})
        API-->>FE: {text_length, source: "external"}
    end
```

**代码位置:**
- 检查入口: `backend/app/api/transcripts.py` 第 463-490 行 (`check_external_transcript`)
- 获取入口: `backend/app/api/transcripts.py` 第 396-460 行 (`fetch_external_transcript`)
- 抓取服务: `backend/app/services/transcript_fetcher.py` (`TranscriptFetcher.fetch_transcript`, `validate_transcript_url`)
- 前端调用: `frontend/src/services/api.js` 第 73-74 行 (`transcriptsApi.checkExternal`, `transcriptsApi.fetch`)
- 前端自动获取逻辑: `frontend/src/components/views/EpisodeDetailView.jsx` 第 120-156 行 (`loadTranscriptWithAutoFetch`)

---

## 5. AssemblyAI 转录流程

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as transcripts.py:create_transcript
    participant TQ as TaskQueue
    participant Sync as _transcribe_sync
    participant AAI as AssemblyAI
    participant DB as MongoDB

    FE->>API: POST /api/transcripts/:id
    API->>DB: db.episodes.find_one({id})
    API->>API: 检查状态 (非 transcribing/transcribed)
    API->>API: 检查 audio_url 存在
    API->>DB: db.tasks.find_one({episode_id, type:"transcribe", status:pending/processing})
    DB-->>API: null
    API->>DB: db.episodes.update_one({status: "transcribing"})
    API->>TQ: task_queue.submit("transcribe", _transcribe_sync)
    TQ-->>API: task_id
    API-->>FE: {task_id, status: "queued"}

    Note over TQ,AAI: 异步线程执行
    TQ->>Sync: _transcribe_sync(episode_id, progress_callback)

    alt episode.transcript_url 存在
        Note over Sync: 优先尝试下载官方字幕 (参见流程 4)
        Sync->>DB: _save_transcript()
        Sync-->>TQ: {source: "official"}
    else 无官方字幕
        Sync->>AAI: assemblyai.Transcriber().transcribe(audio_url, config)
        Note over AAI: config: speaker_labels=True, auto_chapters=True, entity_detection=True
        AAI-->>Sync: transcript (带 utterances, chapters, entities)

        Sync->>Sync: 构建 segments (含 speaker)
        Sync->>Sync: 构建 chapters
        Sync->>Sync: 构建 entities (去重, 最多 50 个)

        Sync->>DB: db.transcripts.update_one/upsert({episode_id})
        Sync->>DB: db.episodes.update_one({status: "transcribed", has_transcript: true, transcript_source: "assemblyai"})
        Sync-->>TQ: {text_length, source: "assemblyai", speakers, chapters}
    end
```

**代码位置:**
- API 入口: `backend/app/api/transcripts.py` 第 47-138 行 (`create_transcript`)
- 同步逻辑: `backend/app/api/transcripts.py` 第 212-252 行 (`_transcribe_sync`)
- AssemblyAI 调用: `backend/app/api/transcripts.py` 第 255-365 行 (`_transcribe_with_assemblyai`)
- 配置: `backend/app/api/transcripts.py` 第 275-279 行 (`TranscriptionConfig`)
- 前端调用: `frontend/src/services/api.js` 第 71 行 (`transcriptsApi.create`)

---

## 6. 生成 AI 摘要流程 (最重要)

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as summaries.py:create_summary
    participant TQ as TaskQueue
    participant Sync as _summarize_sync
    participant Svc as SummaryService
    participant Engine as SummarizationEngine
    participant PB as PromptBuilder
    participant LLM as LLMClient
    participant SV as SchemaValidator
    participant DB as MongoDB

    FE->>API: POST /api/summaries/:id {template_name, enabled_blocks, force}
    API->>DB: db.episodes.find_one({id})
    API->>DB: db.transcripts.find_one({episode_id}) [检查转录存在]
    API->>DB: db.summaries.find_one({episode_id, template_name}) [检查已有摘要]
    API->>DB: db.tasks.find_one({episode_id, type:"summarize", status:pending/processing})
    DB-->>API: null (无进行中任务)
    API->>DB: db.episodes.update_one({status: "summarizing"})
    API->>TQ: task_queue.submit("summarize", _summarize_sync)
    TQ-->>API: task_id
    API-->>FE: {task_id, status: "queued", template_name}

    Note over TQ,Sync: 异步线程执行
    TQ->>Sync: _summarize_sync(episode_id, template_name, ...)
    Sync->>Svc: get_summary_service(db)
    Sync->>Svc: service.generate_summary(episode_id, template_name, ...)

    Svc->>Svc: _map_legacy_type() → 确定 template_name
    Svc->>DB: db.prompt_templates.find_one({name, is_active: true})

    alt 找到模板 → v3 路径
        Svc->>Engine: engine.summarize_episode(episode_id, template_name, ...)
        Engine->>DB: db.episodes.find_one({id}) [加载 episode]
        Engine->>DB: db.transcripts.find_one({episode_id}) [加载 transcript]
        Engine->>PB: prompt_builder.build(template, transcript, enabled_blocks, params)
        PB-->>Engine: [system_msg, user_msg]
        Engine->>PB: prompt_builder.get_max_tokens(template, params)

        loop 最多 MAX_RETRIES+1=3 次
            Engine->>LLM: llm.chat_json(messages, max_tokens, temperature=0.2)
            LLM-->>Engine: {data, usage, model}
            Engine->>SV: validator.validate(data, template, enabled_blocks)
            SV-->>Engine: (is_valid, errors)

            alt is_valid == true
                Note over Engine: 返回结果
            else is_valid == false 且还有重试次数
                Engine->>Engine: _add_correction_hint(messages, errors) [追加修正提示]
            else is_valid == false 且已用完重试
                Engine->>SV: validator.ensure_required_fields(data, template) [填默认值]
                Note over Engine: 使用宽松结果
            end
        end

        Engine->>DB: db.summaries.update_one(upsert=True) [version: "v3"]
        Engine->>DB: db.episodes.update_one({status: "summarized", has_summary: true})
    else 未找到模板 → v2 路径
        Svc->>Svc: _generate_legacy(episode_id, summary_type)
        Svc->>Svc: PromptRouter.get_prompt(summary_type)
        Svc->>LLM: llm.chat_json(messages, temperature=0.2)
        Svc->>DB: db.summaries.update_one(upsert=True) [version: "v2"]
        Svc->>DB: db.episodes.update_one({status: "summarized", has_summary: true})
    end

    Svc-->>Sync: summary_doc

    Note over Sync: 自动触发翻译 (非关键)
    Sync->>Svc: service.translate_summary(episode_id, template_name)
    alt content_zh 已存在
        Svc-->>Sync: 直接返回
    else 未翻译
        Svc->>Svc: PromptRouter.get_translate_prompt()
        Svc->>LLM: llm.chat_json(temperature=0.2)
        Svc->>DB: db.summaries.update_one({content_zh, translated_at})
    end

    alt 翻译成功
        Sync-->>TQ: {summary_id, has_translation: true}
    else 翻译失败 (非关键)
        Note over Sync: logger.warning, 不影响主流程
        Sync-->>TQ: {summary_id, has_translation: false}
    end
```

**代码位置:**
- API 入口: `backend/app/api/summaries.py` 第 74-201 行 (`create_summary`)
- 同步逻辑: `backend/app/api/summaries.py` 第 204-269 行 (`_summarize_sync`)
- Service 门面: `backend/app/services/summary_service.py` 第 42-102 行 (`generate_summary`)
- v3 引擎: `backend/app/core/summarization/engine.py` 第 46-118 行 (`summarize`) + 第 120-218 行 (`summarize_episode`)
- Prompt 构建: `backend/app/core/summarization/prompt_builder.py` (`build`)
- Schema 校验: `backend/app/core/summarization/schema_validator.py` (`validate`, `ensure_required_fields`)
- 重试逻辑: `backend/app/core/summarization/engine.py` 第 227-275 行 (`_call_with_retry`)
- v2 Legacy: `backend/app/services/summary_service.py` 第 121-201 行 (`_generate_legacy`)
- 翻译: `backend/app/services/summary_service.py` 第 203-268 行 (`translate_summary`)
- 前端调用: `frontend/src/services/api.js` 第 84-86 行 (`summariesApi.create`)

---

## 7. 翻译摘要流程

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as summaries.py:translate_summary
    participant TQ as TaskQueue
    participant Sync as _translate_sync
    participant Svc as SummaryService
    participant LLM as LLMClient
    participant DB as MongoDB

    FE->>API: POST /api/summaries/:id/translate {template_name}
    API->>DB: db.summaries.find_one({episode_id, template_name})
    DB-->>API: summary

    alt summary.content_zh 已存在
        API-->>FE: {message: "Translation already exists", summary}
    else 未翻译
        API->>TQ: task_queue.submit("translate", _translate_sync)
        TQ-->>API: task_id
        API-->>FE: {task_id, status: "queued"}

        Note over TQ,Sync: 异步线程执行
        TQ->>Sync: _translate_sync(episode_id, template_name)
        Sync->>Svc: service.translate_summary(episode_id, template_name)
        Svc->>DB: db.summaries.find_one({episode_id, template_name})

        alt content_zh 已存在 (二次检查)
            Svc-->>Sync: 直接返回
        else 未翻译
            Svc->>Svc: PromptRouter.get_translate_prompt()
            Svc->>Svc: translate_prompt.build_messages(content)
            Svc->>LLM: llm.chat_json(messages, temperature=0.2)
            LLM-->>Svc: {data: translated_content}
            Svc->>DB: db.summaries.update_one({content_zh, translation_model, translation_tokens, translated_at})
        end

        Sync-->>TQ: {summary_id, has_translation: true}
    end
```

**代码位置:**
- API 入口: `backend/app/api/summaries.py` 第 272-329 行 (`translate_summary`)
- 同步逻辑: `backend/app/api/summaries.py` 第 332-363 行 (`_translate_sync`)
- Service: `backend/app/services/summary_service.py` 第 203-268 行 (`translate_summary`)
- 翻译 prompt: `backend/app/services/prompts/translate.py`
- 前端调用: `frontend/src/services/api.js` 第 88-89 行 (`summariesApi.translate`)

---

## 8. 生成 AI Briefing 流程

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as insights.py:get_briefing
    participant Svc as BriefingService
    participant LLM as LLMClient
    participant DB as MongoDB

    FE->>API: GET /api/insights/briefing
    API->>Svc: service.get_or_generate(force=False)

    Svc->>DB: db.briefings.find_one({date: today})

    alt 有今日缓存
        DB-->>Svc: cached briefing
        Svc-->>API: {success: true, briefing: cached, cached: true}
    else 无缓存
        Svc->>Svc: _collect_recent_episodes(days=7)

        Svc->>DB: db.feeds.find({status: "active"}) [获取所有 feed_id]

        Svc->>DB: db.episodes.find({has_summary: true}).sort(published, -1).limit(30)
        Note over Svc: 优先选有 AI 摘要的 episodes

        alt 有摘要的 episodes ≥ 5 条
            Note over Svc: 只用这些高质量 episodes
        else 不足 5 条
            Svc->>DB: db.episodes.find({补充未摘要的}).sort(published, -1).limit(N)
            Note over Svc: 拼接两组
        end

        Svc->>DB: db.summaries.find({episode_id: {$in: ids}}) [批量获取摘要]
        Svc->>DB: db.feeds.find({_id: {$in: feed_ids}}) [批量获取 feed 信息]

        loop 每个 episode
            alt 有 AI 摘要
                Note over Svc: 使用 AI 摘要 (tldr + blocks)
            else 无 AI 摘要
                Note over Svc: 使用 RSS summary/content (截取前 2000-3000 字符)
            end
        end

        Svc->>Svc: _generate(episodes) → 拼接 SUMMARY_ENTRY_TEMPLATE
        Svc->>LLM: llm.chat_json(messages, temperature=0.3, max_tokens=8192)
        LLM-->>Svc: {data: briefing_data}

        Svc->>DB: db.briefings.update_one({date: today}, upsert=True)
        Svc-->>API: {success: true, briefing: saved, cached: false}
    end

    API-->>FE: JSON response
```

**代码位置:**
- API 入口: `backend/app/api/insights.py` 第 19-28 行 (`get_briefing`)
- Service: `backend/app/services/briefing_service.py` 第 36-77 行 (`get_or_generate`)
- 数据收集: `backend/app/services/briefing_service.py` 第 91-213 行 (`_collect_recent_episodes`)
- 生成逻辑: `backend/app/services/briefing_service.py` 第 215-266 行 (`_generate`)
- 提示词: `backend/app/services/briefing_prompts.py`
- 前端调用: `frontend/src/services/api.js` 第 135 行 (`insightsApi.getBriefing`)

---

## 9. 前端进入 Episode 详情页流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant App as App.jsx
    participant Detail as EpisodeDetailView
    participant API as Backend API
    participant DB as MongoDB

    User->>App: 点击 episode 卡片
    App->>App: setView('detail'), setSelectedEpisode(episode)
    App->>Detail: 渲染 EpisodeDetailView (episode, onBack, onRefresh, onPlay)

    rect rgb(240, 248, 255)
        Note over Detail,DB: useEffect: loadTemplates (挂载时执行一次)
        Detail->>API: GET /api/prompt-templates
        API-->>Detail: templates[]
        Detail->>Detail: 默认选择 name="learning" 的模板
        Detail->>API: GET /api/prompt-templates/:id
        API-->>Detail: 模板详情 (含 optional_blocks)
        Detail->>Detail: setEnabledBlocks(enabled_by_default 的 blocks)
        Detail->>Detail: setTemplateBlocks(all optional_blocks)
    end

    rect rgb(255, 248, 240)
        Note over Detail,DB: useEffect: loadTranscriptWithAutoFetch (episode 变化时执行)
        Detail->>API: GET /api/transcripts/:episodeId
        alt 有转录
            API-->>Detail: transcript data
            Detail->>Detail: setTranscript(data)
        else 无转录 (404)
            Detail->>API: GET /api/transcripts/:episodeId/check-external
            alt 有外部字幕 URL
                API-->>Detail: {has_external_transcript: true}
                Detail->>API: POST /api/transcripts/:episodeId/fetch [自动获取]
                API->>DB: TranscriptFetcher.fetch_transcript(url) + upsert
                API-->>Detail: success
                Detail->>API: GET /api/transcripts/:episodeId [重新获取]
                API-->>Detail: transcript data
                Detail->>Detail: setTranscript(data)
                Detail->>App: onRefresh() [更新 episode 状态]
            else 无外部字幕
                Detail->>Detail: 显示 "生成转录" 按钮
            end
        end
    end

    rect rgb(240, 255, 240)
        Note over Detail,DB: useEffect: loadSummary (episode 变化时执行)
        Detail->>API: GET /api/summaries/:episodeId?template_name=learning
        alt 有摘要
            API-->>Detail: summary data
            Detail->>Detail: setSummary(data)
        else 无摘要 (404)
            Detail->>Detail: setSummary(null)
        end
    end
```

**代码位置:**
- App.jsx 入口: `frontend/src/App.jsx` (handleEpisodeClick → setView + setSelectedEpisode)
- 详情视图: `frontend/src/components/views/EpisodeDetailView.jsx`
- 模板加载: `EpisodeDetailView.jsx` 第 52-77 行 (useEffect `loadTemplates`)
- 转录加载: `EpisodeDetailView.jsx` 第 120-156 行 (`loadTranscriptWithAutoFetch`)
- 摘要加载: `EpisodeDetailView.jsx` 第 167-176 行 (`loadSummary`)
- 前端 API: `frontend/src/services/api.js` (transcriptsApi, summariesApi, promptTemplatesApi)

---

## 10. 任务轮询流程

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant TP as TaskProgress.jsx
    participant Panel as TaskPanel.jsx
    participant API as tasksApi
    participant DB as MongoDB

    rect rgb(240, 248, 255)
        Note over FE,DB: TaskProgress.jsx — 每 2 秒轮询 (绑定到具体 episode)
        loop 每 2 秒
            TP->>API: GET /api/tasks?episode_id=X&type=summarize&per_page=1
            API->>DB: db.tasks.find({episode_id, task_type}).sort(created_at, -1).limit(1)
            DB-->>API: [task]
            API-->>TP: {data: [task]}

            TP->>TP: 更新进度条 (task.progress %)
            TP->>TP: 计算已运行时间 (started_at → now)

            alt task.status == "completed"
                TP->>FE: onComplete() → loadTranscript() / loadSummary() + onRefresh()
            else task.status == "failed"
                TP->>FE: onError(error_message) → 显示错误信息
            else Date.now() - lastUpdate > 30s
                TP->>FE: 显示 "可能卡住" 警告 (黄色)
            end
        end
    end

    rect rgb(240, 255, 240)
        Note over FE,DB: TaskPanel.jsx — 每 3 秒轮询 (全局，浮动面板)
        loop 每 3 秒
            Panel->>API: GET /api/tasks?status=pending,processing [活跃任务]
            API->>DB: db.tasks.find({status: {$in: ["pending","processing"]}})
            DB-->>Panel: activeTasks[]

            Panel->>API: GET /api/tasks?per_page=10 [最近任务]
            API->>DB: db.tasks.find({}).sort(created_at, -1).limit(10)
            DB-->>Panel: allTasks[]

            Panel->>Panel: 过滤最近 5 分钟内完成的任务
            Panel->>Panel: 合并活跃 + 最近完成 → 显示浮动面板

            alt 有新完成的任务
                Panel->>FE: onTaskComplete() → 触发数据刷新
            end
        end
    end
```

### 轮询参数对比

| 属性 | TaskProgress | TaskPanel |
|------|-------------|-----------|
| **轮询间隔** | 2 秒 | 3 秒 |
| **作用域** | 单个 episode | 全局 |
| **查询参数** | `episode_id` + `task_type` | `status=pending,processing` + 全量 |
| **卡住检测** | 30 秒无更新 | 无 |
| **位置** | 嵌入 EpisodeDetailView | 浮动面板 (fixed bottom-right) |
| **代码位置** | `frontend/src/components/common/TaskProgress.jsx` 第 91-95 行 | `frontend/src/components/tasks/TaskPanel.jsx` 第 50-54 行 |

### 任务状态流转

```
pending → processing → completed
                    → failed
pending → failed (用户取消: task_queue.cancel())
```

**代码位置:**
- TaskQueue 状态管理: `backend/app/services/task_queue.py` 第 82-123 行 (wrapper 函数)
- 任务 API: `backend/app/api/tasks.py`
- TaskProgress: `frontend/src/components/common/TaskProgress.jsx` 第 53-88 行 (`fetchTaskStatus`)
- TaskPanel: `frontend/src/components/tasks/TaskPanel.jsx` 第 21-47 行 (`fetchTasks`)
- 前端 API: `frontend/src/services/api.js` 第 114-118 行 (`tasksApi`)

---

## 附录: 数据集合关系

```mermaid
erDiagram
    feeds ||--o{ episodes : "1:N (feed_id)"
    episodes ||--o| transcripts : "1:1 (episode_id, unique)"
    episodes ||--o{ summaries : "1:N (episode_id, 按 template_name/summary_type 区分)"
    episodes ||--o{ tasks : "1:N (episode_id)"

    feeds {
        ObjectId _id PK
        string rss_url UK
        string title
        string status "active / error"
        int episode_count
        int unread_count
        boolean is_starred
        boolean is_favorite
        datetime last_checked
    }

    episodes {
        ObjectId _id PK
        ObjectId feed_id FK
        string guid "(feed_id + guid) unique"
        string title
        string status "new / downloading / downloaded / transcribing / transcribed / summarizing / summarized"
        string audio_url
        string local_path
        boolean has_transcript
        boolean has_summary
        boolean is_read
        boolean is_starred
    }

    transcripts {
        ObjectId _id PK
        ObjectId episode_id FK "unique"
        string text
        array segments "speaker, start, end, text"
        array chapters
        array entities
        string source "assemblyai / external / official"
    }

    summaries {
        ObjectId _id PK
        ObjectId episode_id FK
        string template_name "v3"
        string summary_type "v2"
        string version "v2 / v3"
        object content "摘要内容 (blocks)"
        string tldr
        array tags
        object content_zh "中文翻译"
    }

    tasks {
        ObjectId _id PK
        string task_id "unique"
        string task_type "download / transcribe / summarize / translate / refresh"
        string episode_id
        string status "pending / processing / completed / failed"
        int progress "0-100"
        string error_message
    }

    briefings {
        ObjectId _id PK
        string date "unique"
        object briefing
        int episode_count
    }

    settings {
        ObjectId _id PK
        string key "unique"
        object value
    }

    prompt_templates {
        ObjectId _id PK
        string name "unique"
        object locked
        array optional_blocks
        object parameters
        boolean is_system
        boolean is_active
    }
```

**索引定义位置:** `backend/app/__init__.py` 第 63-107 行 (`ensure_indexes`)
