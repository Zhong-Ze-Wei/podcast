# 待确认问题

> 项目中需要产品决策、架构决策或代码确认的问题，2026-05-17

---

## 1. 产品问题

### Q1: 用户是以"播客"为中心，还是以"知识卡片/摘要"为中心？

- **当前代码倾向**：以播客为中心（Feed 是一级实体，Sidebar 展示订阅列表）
- **证据**：`frontend/src/components/layout/Sidebar.jsx` — 导航按 feed 组织；`App.jsx` — activeFeed 驱动列表过滤
- **影响**：决定后续是加强播客管理功能，还是加强摘要/知识库视角
- **推荐答案**：短期保持播客中心，长期增加"知识库"视图（按主题/标签聚合摘要）
- **需要用户确认**：产品方向优先级

### Q2: Briefing 的价值定位是什么？

- **当前**：跨播客热点聚合（`backend/app/services/briefing_service.py`）
- **问题**：数据来源有限（只有用户订阅的播客），个性化程度低
- **推荐答案**：保持当前定位，增加筛选条件（只看某些播客/主题）
- **需要用户确认**：Briefing 功能是否需要投入更多开发

---

## 2. 摘要系统问题

### Q3: 用户是选择模板，还是描述长期偏好？

- **当前**：选模板 + 手动切 blocks（`EpisodeDetailView.jsx` 模板按钮组 + block toggle）
- **问题**：5 个模板对用户来说选择成本高，block 切换的发现成本更高
- **推荐答案**：Phase 3 引入 SummaryRecipe（保存偏好，自动应用）
- **需要用户确认**：是否接受"模板 → 配方"的演进路线

### Q4: 摘要结果应该固定字段，还是 block schema？

- **当前**：固定字段（`summary.py:to_response` 展开 content dict 到顶层）
- **问题**：新增 block 需要改 3 处（templates.py 定义 → summary.py 展开 → EpisodeDetailView.jsx 渲染）
- **推荐答案**：block schema（`blocks: [{id, title, type, content}]`，前端按 type 通用渲染）
- **需要用户确认**：Phase 2 是否启动 block-based response 改造

### Q5: 中文输出是否应该作为默认行为？

- **当前**：已改为默认 `zh`（`templates.py` language default）
- **遗留问题**：已有的英文摘要不受影响，是否需要自动翻译？
- **推荐答案**：新摘要默认中文即可，旧摘要用户手动点翻译
- **需要用户确认**：无（已决策）

### Q6: 重新生成是否覆盖旧摘要？

- **当前**：覆盖（`force=true` 时 upsert，`summaries.py:127`）
- **问题**：无法回退到之前的版本
- **推荐答案**：短期保持覆盖（个人项目够用），长期可考虑版本历史
- **需要用户确认**：是否需要摘要版本历史

---

## 3. 数据模型问题

### Q7: v2 summary 数据是否要迁移？

- **当前**：summaries 集合中同时存在 `version="v2"` 和 `version="v3"` 文档
- **证据**：`backend/app/api/summaries.py:get_summary` 同时检查 `template_name` 和 `summary_type`
- **推荐答案**：Phase 2 补充 blocks 字段，不删除旧字段，v2 文档动态生成 blocks
- **需要用户确认**：v2 数据是否可以只读保留

### Q8: briefings 是缓存还是正式内容？

- **当前**：按日期 upsert，无过期清理，存在 MongoDB
- **证据**：`briefings` 集合无 TTL 索引（`backend/app/__init__.py:ensure_indexes`）
- **推荐答案**：加 TTL 索引（30 天后自动清理），或加手动清理 API
- **需要用户确认**：历史简报是否需要永久保留

### Q9: tasks 是否需要 TTL？

- **当前**：无 TTL，历史任务永久保存
- **证据**：`backend/app/__init__.py:ensure_indexes` — tasks 只有 status 和 created_at 索引
- **推荐答案**：加 TTL 索引（7 天后自动清理 completed/failed 任务）
- **需要用户确认**：无（技术决策，建议加）

---

## 4. 前端交互问题

### Q10: EpisodeDetailView 是否拆成多个组件？

- **当前**：850+ 行，承担 7+ 职责
- **证据**：`frontend/src/components/views/EpisodeDetailView.jsx`
- **推荐答案**：Phase 2 拆分（TranscriptPanel, SummaryPanel, EpisodeHeader 等）
- **需要用户确认**：拆分方案是否可接受

### Q11: Block 选择出现在生成前还是模板设置里？

- **当前**：生成前（摘要 tab 中，模板选择器下方）
- **问题**：模板设置里（PromptTemplatesPanel）也有 block 启用/禁用，两处逻辑不一致
- **推荐答案**：模板设置定义默认，生成前可临时调整
- **需要用户确认**：两处 block 切换是否需要同步

### Q12: 搜索功能是否需要后端 API？

- **当前**：前端内存过滤（`App.jsx` searchQuery 仅过滤当前页数据）
- **证据**：`filteredEpisodes` 在 `App.jsx` 中基于 activeFeed 过滤
- **推荐答案**：短期不需要，数据量增大后加 MongoDB text index + 搜索端点
- **需要用户确认**：当前数据量是否需要后端搜索

---

## 5. 架构问题

### Q13: 是否继续使用 ThreadPoolExecutor？

- **当前**：`backend/app/services/task_queue.py` 使用 ThreadPoolExecutor(max_workers=3)
- **问题**：无任务恢复机制（重启后内存状态丢失），无优先级
- **推荐答案**：短期够用；如果需要任务恢复/优先级，考虑 Celery + Redis
- **需要用户确认**：是否需要任务恢复机制

### Q14: 是否需要 Docker Compose？

- **当前**：`run.py` 自动管理 MongoDB Docker 容器
- **推荐答案**：加 docker-compose.yml 更规范（MongoDB + 后端 + 前端）
- **需要用户确认**：部署方式偏好

### Q15: 是否需要后端搜索 API？

- **当前**：无全文搜索
- **推荐答案**：短期不需要，长期加 MongoDB text index
- **需要用户确认**：搜索场景优先级

---

## 决策优先级

| 优先级 | 问题 | 影响 | 建议处理时间 |
|--------|------|------|-------------|
| 高 | Q4 摘要 block schema | 决定 Phase 2 方向 | Phase 1 期间确认 |
| 高 | Q3 用户偏好模型 | 决定 Phase 3 方向 | Phase 2 期间确认 |
| 中 | Q7 v2 数据迁移 | 数据兼容性 | Phase 2 开始前确认 |
| 中 | Q10 EpisodeDetail 拆分 | 前端可维护性 | Phase 2 开始前确认 |
| 中 | Q11 Block 选择位置 | 用户交互一致性 | Phase 1 期间确认 |
| 低 | Q6 版本历史 | 功能完整性 | Phase 3 考虑 |
| 低 | Q8/Q9 TTL 索引 | 数据膨胀 | 任意时间点 |
| 低 | Q13/Q14/Q15 基础设施 | 运维便利性 | 有需求时再做 |
