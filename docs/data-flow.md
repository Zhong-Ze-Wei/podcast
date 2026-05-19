# 数据流转报告

> 文档日期：2026-05-16

---

## 1. Episode 生命周期

Episode 状态机是整个系统的核心轴线：

```
new
 ↓ [用户点击"下载"] → 提交 download 任务
downloading
 ↓ [下载完成]
downloaded
 ↓ [用户点击"转录"] → 提交 transcribe 任务
 │  或 [检测到 transcript_url] → 直接抓取官方字幕
transcribing
 ↓ [转录完成]
transcribed
 ↓ [用户点击"生成摘要"] → 提交 summarize 任务
summarizing
 ↓ [摘要完成]
summarized

任意阶段发生错误 → error
```

---

## 2. 核心流程详解

### 2.1 订阅 RSS Feed

```
用户 → POST /api/feeds { rss_url }
  ↓
feeds.py → Feed.validate_rss_url()  [SSRF 防护]
  ↓
RSSService.parse_feed(rss_url)
  │  ├─ requests.get (模拟浏览器 UA)
  │  ├─ feedparser.parse()
  │  ├─ _extract_feed_info() → title/image/author/language
  │  └─ _extract_episodes() → guid/audio_url/duration/transcript_url
  ↓
写入 feeds 集合（upsert by rss_url）
写入 episodes 集合（upsert by feed_id+guid，保留已有状态）
返回 { feed_id, episode_count }
```

### 2.2 音频下载

```
用户 → POST /api/episodes/<id>/download
  ↓
episodes.py → task_queue.submit("download", download_func, episode_id)
返回 { task_id }
  ↓ [异步]
ThreadPoolExecutor Worker:
  requests.get(audio_url, stream=True)
  分块写入 backend/media/audio/<feed_id>/<episode_id>.mp3
  progress_callback(0→100)
  ↓
更新 episodes.status = "downloaded"
更新 episodes.audio_path = 相对路径
```

### 2.3 转录流程

```
用户 → POST /api/transcripts/<episode_id>
  ↓
transcripts.py 判断来源优先级：
  ├─ transcript_url 存在 → TranscriptFetcher.fetch_official()
  │    └─ 解析 SRT/VTT/JSON → 转换为统一 text + segments 格式
  └─ 无官方字幕 → AssemblyAI 转录
       └─ 提交音频 URL → 轮询结果 → 说话人分离 + 章节 + 实体
  ↓
写入 transcripts 集合（upsert by episode_id）
更新 episodes.status = "transcribed"
更新 episodes.has_transcript = true
```

### 2.4 AI 摘要生成

```
用户 → POST /api/summaries/<episode_id> { template_name, enabled_blocks, params }
  ↓
summaries.py → task_queue.submit("summarize", summarize_func)
返回 { task_id }
  ↓ [异步]
SummaryService.generate_summary()
  ↓
  判断路径：
  ├─ template_name 在数据库中存在 → SummarizationEngine (v3)
  │    ↓
  │    1. 加载 PromptTemplate 文档
  │    2. PromptBuilder.build()
  │         ├─ locked.system_prompt → system message
  │         ├─ 遍历 optional_blocks，追加已启用 block 的 prompt_fragment
  │         └─ 替换 parameters 变量（如 {length} → "详细"）
  │    3. LLMClient.chat_json() [JSON mode]
  │    4. SchemaValidator.validate()
  │         ├─ 通过 → 保存
  │         └─ 失败 → 追加纠错 Hint，最多重试 2 次
  │              最终失败 → lenient 模式填充默认值
  │    5. 写入 summaries（upsert by episode_id + template_name）
  └─ template_name 不存在 → Legacy PromptRouter (v2)
       ↓
       PromptRouter.get_prompt(summary_type) → 固定 Prompt
       LLMClient.chat_json()
       写入 summaries（upsert by episode_id + summary_type）
  ↓
更新 episodes.status = "summarized"
更新 episodes.has_summary = true
```

### 2.5 中文翻译

```
用户 → POST /api/summaries/<episode_id>/translate
  ↓
SummaryService.translate_summary()
  ↓
找到已有 summary（按 template_name 或 summary_type）
  ↓
若 content_zh 已存在 → 直接返回（不重复翻译）
  ↓
PromptRouter.get_translate_prompt()
  └─ 将整个 content 对象序列化为 JSON 传入 LLM
LLMClient.chat_json() → 返回翻译后的 content_zh 对象
  ↓
更新 summaries.content_zh
更新 summaries.translated_at
```

### 2.6 AI 简报生成

```
用户 → GET /api/insights/briefing
  ↓
BriefingService.get_or_generate(force=False)
  ↓
  检查 briefings 集合中今天（YYYY-MM-DD）是否有缓存
  ├─ 有缓存且 force=False → 直接返回缓存
  └─ 无缓存或 force=True →
       ↓
       查询今天所有 status=summarized 的 episodes
       查询对应 summaries（取最新一条）
       ↓
       拼装 context：每集的 tldr + tags + content
       调 LLMClient.chat() → 生成 Markdown 综合报告
       ↓
       写入 briefings（upsert by date）
       返回结果
```

---

## 3. 异步任务系统数据流

```
API 请求
  ↓
task_queue.submit(task_type, func, episode_id/feed_id)
  ├─ 生成 task_id (UUID)
  ├─ 内存写入：self.tasks[task_id] = {...status: "pending"}
  └─ MongoDB 写入：db.tasks.insert_one(...)
     ↓
     ThreadPoolExecutor.submit(wrapper)

Worker 线程执行：
  wrapper()
    ├─ _update_status("processing")    → 内存 + MongoDB
    ├─ func(..., progress_callback)
    │    └─ 业务逻辑中调用 progress_callback(n) → _update_progress(n)
    ├─ 成功：_update_status("completed", result=...)
    └─ 失败：_update_status("failed", error_message=...)

前端轮询（TaskPanel）：
  每 N 秒 → GET /api/tasks?status=pending,processing
  任务完成 → 触发 App.jsx loadData() 刷新数据
```

---

## 4. LLM 配置读取流程

```
任意需要 LLM 的操作
  ↓
get_llm_client()
  ├─ 尝试从 Flask app context 获取 db
  │    └─ SettingModel.get_active_llm_config()
  │         └─ 查 settings 集合，取 active_index 对应的配置
  ├─ Flask context 不可用时 → 直接 MongoClient 连接
  └─ 数据库无配置 → fallback 到环境变量
       LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
  ↓
LLMClient(base_url, api_key, model)
```

---

## 5. 自动刷新流程

```
应用启动
  ↓
start_auto_refresher(db, interval_hours=1, stale_threshold_hours=6)
  └─ 后台 Thread（daemon=True）
      每 interval_hours 小时唤醒：
        查询 feeds 中 last_checked < (now - stale_threshold_hours)
        对每个过期 feed：
          RSSService.parse_feed(rss_url)
          对比已有 episodes（by guid）
          插入新单集（upsert 保护已有状态）
          更新 feed.last_checked / episode_count / unread_count
```

---

## 6. 前后端数据流

```
浏览器
  ↓ axios (src/services/api.js)
  ↓ /api/* → Vite dev proxy → http://localhost:5000
Flask API Layer (api/*.py)
  ↓ 参数校验
Service Layer (services/*.py)
  ├─ MongoDB (pymongo)
  ├─ LLMClient → 外部 LLM API
  ├─ RSSService → 外部 RSS 源
  └─ TranscriptFetcher → AssemblyAI / 外部字幕 URL
  ↓
Model.to_response() → 格式化为 JSON
  ↓
{ success: true, data: {...} }
  ↓
前端 Response Interceptor → response.data
  ↓
React 状态更新 → 重渲染
```

---

## 7. 数据一致性说明

| 场景 | 处理方式 |
|------|----------|
| 重复添加同一 RSS | feeds 集合 `rss_url` 唯一索引，API 返回已存在的 feed |
| 重复拉取同一单集 | `(feed_id, guid)` 复合唯一索引，upsert 保护 |
| 重复生成摘要 | `force=false` 时先查已有，存在则直接返回 |
| 重复转录 | 同上，`episode_id` 唯一 |
| 任务并发 | Episode 状态检查（`is_processing()`），处理中不允许重复提交 |
| 删除订阅 | feeds.py 级联删除 episodes / transcripts / summaries / tasks |
