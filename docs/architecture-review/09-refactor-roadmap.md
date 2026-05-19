# 重构路线图

> 基于 BACKLOG.md + 08-technical-debt.md 分析，2026-05-17

---

## 1. 重构总原则

- **先统一数据契约，再拆 UI** — 后端输出格式统一后，前端拆分才有基础
- **先加兼容层，再迁移旧数据** — 新字段和旧字段并存，渐进切换
- **先文档化，再改核心链路** — 架构文档（本目录）是重构的依据
- **AI 相关逻辑要和展示逻辑解耦** — SummaryBlock 是桥梁
- **每一步可独立验证，不做大爆炸式重构** — 每个原子提交都能跑测试

---

## 2. Phase 1：稳定现有功能（1-2 周）

### 目标
修明显 bug，补齐缺失入口，降低误用。

### 任务清单

| 任务 | 涉及文件 | 改动量 | 状态 |
|------|----------|--------|------|
| language 默认中文 | backend/app/core/summarization/defaults/templates.py | 极小 | ✅ 已完成 |
| Block 选择 UI 渲染 | frontend/src/components/views/EpisodeDetailView.jsx | 小 | ✅ 已完成 |
| 摘要 force regenerate 按钮 | EpisodeDetailView.jsx | 小 | ✅ 已完成 |
| 转录删除/重新生成按钮 | EpisodeDetailView.jsx | 小 | ✅ 已完成 |
| 简报优先选有摘要的单集 | backend/app/services/briefing_service.py | 小 | ✅ 已完成 |
| LLM Provider 预设下拉 | LlmConfigPanel.jsx | 中 | ✅ 已完成 |
| PDF 下载错误提示 | AIBriefingView.jsx | 小 | ✅ 已完成 |
| 本地音频播放修复 | App.jsx handlePlay, episodes.py | 中 | 待做 |
| 清理死代码（LlmSettingsView, DownloadedView, TranscribedView） | 3 个 JSX 文件 | 小 | 待做 |
| TranscriptFetcher Content-Type 嗅探 | backend/app/services/transcript_fetcher.py | 中 | 待做 |
| console.log 调试代码清理 | EpisodeDetailView.jsx 第 690 行 | 极小 | 待做 |
| 未使用状态变量清理 | EpisodeDetailView showTemplateOptions, AIBriefingView selectedTopic | 极小 | 待做 |

### 不需要数据库迁移
### 完成标准
所有 BACKLOG.md 高优先级项完成，无死代码，无调试残留。

---

## 3. Phase 2：前后端解耦（2-3 周）

### 目标
摘要结果改成 block-based response，前端使用通用 SummaryBlockRenderer。

### 后端任务

1. **summary.py:to_response 新增 `blocks` 数组字段**
   - 文件：backend/app/models/summary.py
   - 格式：`[{id: "key_points", title: "核心要点", title_zh: "核心要点", type: "list", content: [...]}]`
   - 不删除旧字段（key_points, investment_signals 等保留作为兼容层）

2. **SummarizationEngine 输出 blocks**
   - 文件：backend/app/core/summarization/engine.py
   - 生成后将 content dict 转换为 blocks 数组

3. **旧数据兼容**
   - 数据库中的旧文档不需要迁移
   - to_response 检测无 blocks 字段时动态生成

### 前端任务

1. **SummaryBlockRenderer 通用组件**
   - 按 block.type 渲染：
     - `list` → 编号列表（如 key_points）
     - `string` → 段落（如 core_content）
     - `quote` → 引用块（如 key_quotes）
     - `tags` → 标签云
     - `signal` → 看多/看空卡片（如 investment_signals）
     - `risk` → 警告卡片（如 risk_alerts）

2. **EpisodeDetailView 拆分**
   - `useEpisodeDetail(episodeId)` — 数据加载 hook
   - `useSummary(episodeId, templateName)` — 摘要相关 hook
   - `TranscriptPanel` — 转录展示
   - `SummaryPanel` — 使用 SummaryBlockRenderer
   - `TemplateSelector` — 模板选择
   - `BlockSelector` — Block 切换
   - `EpisodeHeader` — 标题 + 操作按钮

3. **渐进适配**
   - 优先读 response.blocks，无则 fallback 到旧字段渲染

### 测试方法
- 新生成的摘要同时有 blocks 和旧字段
- 前端可以渐进切换渲染方式
- 回滚只需前端切回旧字段渲染

### 数据库不需要迁移
### 回滚方案
前端切回旧字段渲染即可，后端 blocks 和旧字段并存。

---

## 4. Phase 3：领域模型升级（3-4 周）

### 目标
引入 Recipe/Run/Result 思路，让用户"一次配置，长期复用"。

### 新概念

**SummaryRecipe**（用户保存的摘要配置）
- template_name, enabled_blocks, params, custom_instructions
- 保存后自动用于同类型的播客
- 存储在 MongoDB 新集合 `recipes`

**SummaryRun**（某次生成任务）
- recipe_id, episode_id, model, tokens, elapsed, status
- 关联到现有的 tasks 集合

**SummaryResult**（生成结果）
- 完全基于 blocks 数组
- 不再有 content dict 展开到顶层的逻辑

### 迁移方案
- 现有 summaries 文档已在 Phase 2 补充了 blocks 字段
- 新增 recipes 集合
- v2 路径代码保留为兼容层（Phase 3 后期清理）
- 前端新增"保存为我的配方"按钮

### 数据库迁移
- 新增 recipes 集合（无破坏性变更）
- summaries 集合的 v2 文档：Phase 2 已补 blocks，无需额外迁移

---

## 5. 第一周推荐开发计划

| 天 | 任务 | 涉及文件 | 完成标准 |
|----|------|----------|----------|
| Day 1 | 清理死代码 | LlmSettingsView.jsx, DownloadedView.jsx, TranscribedView.jsx | 3 个文件删除，App.jsx 无引用报错 |
| Day 2 | TranscriptFetcher 改 Content-Type 嗅探 | transcript_fetcher.py | URL 无后缀也能识别 SRT/VTT/JSON |
| Day 3 | 本地音频播放修复 | App.jsx handlePlay, episodes.py | 下载过的音频优先播放本地文件 |
| Day 4 | summary.to_response 新增 blocks 字段 | summary.py | 新生成的摘要响应包含 blocks 数组 |
| Day 5 | SummaryBlockRenderer 通用组件 | 新建 SummaryBlockRenderer.jsx | 按 type 渲染 list/string/quote/tags |

---

## 6. 暂时不要做的事

| 不做 | 原因 |
|------|------|
| 不急着上用户系统 | 个人项目，无多用户需求 |
| 不急着引入 Redux/MobX | App.jsx 状态过重但可用 hooks 渐进拆分 |
| 不急着把 Flask 换 FastAPI | Flask 足够，迁移成本高收益低 |
| 不急着上 Redis | MongoDB upsert 策略足够用 |
| 不急着做完整微服务化 | 个人项目，单体足够 |
| 不急着引入 LangChain/LangGraph | LLMClient + 模板引擎足够灵活 |
| 不急着加 Docker Compose | run.py 已自动管理 MongoDB 容器 |
| 不急着加全文搜索 | 数据量小，前端内存过滤够用 |
