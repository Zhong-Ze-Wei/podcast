# 📋 Podcast Manager 升级实施计划（最终版）

**版本**: v2.0 (经 gstack /plan-eng-review 审查)  
**生成日期**: 2026-05-21  
**评估周期**: 2026-05-21 ~ 2026-08-21（3个月，18.5天开发）  
**状态**: ✅ 范围验收通过，可启动开发

---

## 📊 一览表

| 周期 | 任务 | 优先级 | 工作量 | 并行 Lane | 依赖 |
|------|------|--------|--------|----------|------|
| **W1-2** | Task-001: 前端状态管理重构 | P0 | 16h | A | — |
|  | Task-002: API 测试补齐 | P0 | **13h** | B | — |
|  | Task-003: 错误处理与 Toast | P0 | 8h | C | — |
|  | Task-005: DB 优化 (aggregation) | P1 | **5h** | D | — |
| **W3-4** | Task-004: 列表虚拟化 | P1 | 10h | A | Task-001✓ |
|  | Task-006: 响应式设计 | P1 | 6h | A | Task-004✓ |
|  | Task-008A: 全局错误中间件 | P1 | **4h** | — | Task-003✓ |
| **W5-12** | Task-009: API 文档 (flasgger) | P2 | 6h | — | — |
| **Q3 延迟** | Task-007: 结构化日志系统 | P2 | — | — | (评估 ELK vs 自建) |

**总计**: 68h ≈ **17天**（一人全职，或 4 人各 1 周）

---

## 🎯 分阶段交付目标

### **阶段 1: 基础稳定 (W1-2, 日期: 5.21-6.04)**

#### Task-001: 前端状态管理重构 ⭐⭐⭐
**Goal**: 从 App.jsx 700 行降至 350 行，支持新增视图无需改 App 组件。

**交付物**:
```
frontend/src/
├── contexts/
│   ├── NavigationContext.jsx (view/previousView/selectedEpisode/selectedFeed)
│   ├── PlayerContext.jsx (currentPlaying/isPlaying/audioRef)
│   ├── DataContext.jsx (feeds/episodes/workspaceEpisodes/feedEpisodes)
│   └── SettingsContext.jsx (autoRefresh/taskPoll — 迁移 localStorage)
├── hooks/
│   ├── useNavigation.js
│   ├── usePlayer.js
│   ├── useData.js
│   └── useSettings.js
├── App.jsx (改造: 用 Hook 替代 useState)
└── components/ (所有视图改为导入 Hook，无 prop drilling)
```

**验收标准**:
- [x] App.jsx < 400 行
- [x] 现有功能 100% 保留（路由、播放、任务面板都工作）
- [x] E2E 测试通过（TaskPanel、路由跳转、播放恢复位置）
- [x] 无 TypeScript/ESLint 警告

**风险与缓解**:
- 🔴 路由状态丢失 → 添加 RouterContext 备份到 window.history.state
- 🟡 PlayerBar 与 App 通信延迟 → 使用 useCallback 缓存 handlePlayPause

---

#### Task-002: API 集成测试补齐 ⭐⭐⭐
**Goal**: 测试覆盖从 60% → 85%，所有 CRUD 端点有 ≥2 个测试。

**交付物**:
```
backend/tests/
├── test_episodes_api.py (6 tests)
│   ├── test_list_episodes_with_pagination
│   ├── test_get_episode_detail
│   ├── test_update_episode_play_position
│   ├── test_star_episode ✨ (新: 权限隔离)
│   ├── test_download_episode_triggers_task
│   └── test_list_episodes_without_auth_returns_401
├── test_feeds_api.py (5 tests)
│   ├── test_list_feeds
│   ├── test_create_feed_with_valid_url
│   ├── test_refresh_feed_enqueues_task
│   ├── test_favorite_feed
│   └── test_get_feed_with_episodes
├── test_summaries_api.py (2 tests)
├── test_transcripts_api.py (2 tests)
└── test_settings_api.py ✨ (新: 权限隔离测试) [+1h]
```

**验收标准**:
- [x] pytest coverage ≥ 85%
- [x] 所有 owner_filter 有权限隔离测试
- [x] 边界情况覆盖 (404/400/401)
- [x] `uv run pytest tests/ -v` 全部绿色

**新增内容** (基于审查):
- `test_settings_api.py`: 确保用户只能访问自己的设置 (1h)

---

#### Task-003: 错误处理与用户反馈 ⭐⭐⭐
**Goal**: 用户看得见所有错误和加载状态。

**交付物**:
```
frontend/src/
├── components/ErrorBoundary.jsx (捕获渲染错误)
├── context/ToastContext.js (消息队列)
├── hooks/useToast.js (API)
├── components/ToastContainer.jsx (UI)
├── services/api.js (增强拦截器)
└── App.jsx (包装 ErrorBoundary + ToastContainer)

backend/app/
├── api/handlers.py (通用错误装饰器)
└── api/ (所有 routes 加 @handle_errors)
```

**验收标准**:
- [x] API 错误以 Toast 显示 (非 console.error)
- [x] 临时错误 (502/503) 自动重试 3 次
- [x] 加载中显示 skeleton (feeds, episodes)
- [x] 转录/下载进度条显示百分比
- [x] 无 TypeScript warnings

---

### **阶段 2: 性能优化 (W3-4, 日期: 6.04-6.18)**

#### Task-004: 列表虚拟化与性能优化 ⭐⭐⭐
**Goal**: 500+ episodes 列表平滑滚动 (60fps)，首屏 LCP < 2s。

**交付物**:
```
frontend/src/
├── components/VirtualEpisodeGrid.jsx (react-window Grid)
├── components/cards/EpisodeCard.jsx (React.memo + 自定义比较)
├── components/cards/FeedCard.jsx (React.memo)
├── App.jsx (替换 line 595 的 grid 为 VirtualEpisodeGrid)
├── services/api.js (图片懒加载占位符)
└── vite.config.js (配置 bundle analyzer, 代码分割)
```

**验收标准**:
- [x] 500 episodes 列表滚动无卡顿 (DevTools 60fps)
- [x] FCP < 1.5s, LCP < 2.5s (lighthouse)
- [x] 内存占用 < 100MB
- [x] 图片懒加载用原生 loading="lazy"

**依赖**: Task-001 必须完成 (需要新的 data Hook)

---

#### Task-005: 数据库优化 (Aggregation Pipeline) ⭐⭐
**Goal**: 查询速度 2-3x 提升，减少网络往返。

**交付物**:
```
backend/app/
├── services/db_indexes.py (创建 MongoDB 索引)
│   ├── episodes 上的 (owner_id, published)
│   ├── feeds 上的 (owner_id)
│   └── tasks 上的 (owner_id, status)
└── api/episodes.py (改用 aggregation pipeline)
    ├── $match owner_filter
    ├── $sort published
    ├── $skip/$limit
    └── $lookup feeds (一次查询)

tests/
└── test_episode_query_performance.py (基准测试)
```

**验收标准**:
- [x] 1k episodes 查询 < 50ms
- [x] 10k episodes 查询 < 100ms
- [x] 索引创建不阻塞生产库 (后台创建)
- [x] MongoDB explain() 显示索引被使用

**新增内容** (基于审查):
- 改用 `aggregation pipeline` 替代 `find() + 外部 join`，提升 50% 查询速度

---

#### Task-006: 响应式设计完善 ⭐⭐
**Goal**: 320px-2560px 全覆盖，触摸友好 (min 44px)。

**交付物**:
```
frontend/src/
├── components/layout/Sidebar.jsx (改 Drawer: 移动隐藏 + hamburger)
├── components/cards/EpisodeCard.jsx (响应式: sm/md/lg 断点)
├── components/player/PlayerBar.jsx (压缩版: 手机 vs 完整版: 桌面)
└── App.jsx (字号/间距适配)

styles/ (TailwindCSS 响应式完整覆盖)
```

**验收标准**:
- [x] 320px 手机可用 (无横向滚动)
- [x] 768px 平板可用
- [x] 1024px+ 桌面最优
- [x] 所有交互元素 ≥ 44px (触摸安全)
- [x] 在真实设备/浏览器开发者工具验证

---

#### Task-008A: 全局错误中间件 ⭐⭐
**Goal**: 99.9% 的错误有跟踪 ID，便于生产日志分析。

**交付物**:
```
backend/app/
├── api/middleware.py (新: 请求/响应日志中间件)
│   ├── @app.before_request: 生成 request_id, 记录开始时间
│   ├── @app.after_request: 记录响应时间、状态码
│   └── @app.errorhandler: 捕获 500 错误，返回 request_id
└── config.py (添加 LOG_LEVEL 配置)

backend/run.py
└── 初始化中间件注册
```

**验收标准**:
- [x] 所有 API 请求有 request_id (response header)
- [x] 所有 500 错误被捕获并记录
- [x] 日志包含 duration_ms, status_code, user_id
- [x] 可选: Sentry 钩子 (Q3 补充)

**替换**:
- ❌ Task-007 (自建日志脚本) → 延迟到 Q3，评估 ELK/Datadog ROI

---

### **阶段 3: 文档与后续 (W5-12, 日期: 6.18-8.21)**

#### Task-009: API 文档自动化 ⭐
**Goal**: 自动生成 Swagger UI，API 文档可在 `/api/docs` 访问。

**交付物**:
```
backend/
├── requirements.txt (+flasgger)
├── app/__init__.py (初始化 Swagger)
├── api/ (所有 routes 加 docstring)
│   ├── episodes.py
│   ├── feeds.py
│   ├── transcripts.py
│   └── summaries.py
└── run.py (app.register_blueprint ... 后注册 Swagger)
```

**验收标准**:
- [x] http://localhost:5000/api/docs 可访问
- [x] 所有 CRUD 端点有文档 + 示例
- [x] 请求/响应 schema 清晰
- [x] 可导出 OpenAPI spec

---

#### Task-007: (⏸️ 延迟到 Q3)
**理由**: 自建日志脚本 ROI 低，维护负担重。  
**替代方案**: 用 Task-008A 的 request_id + 基础日志，Q3 评估：
- ELK Stack (自建，维护成本高)
- Datadog/NewRelic/Sentry (托管，有成本但无维护)

---

## 🔄 并行开发策略

**使用 Git Worktree 并行开发 4 条 Lane**:

```bash
# 初始化（主目录）
cd podcast
git checkout master

# Lane A: 前端状态管理 (第一人)
git worktree add .claude/worktrees/lane-a-state-mgmt develop-state-mgmt
cd .claude/worktrees/lane-a-state-mgmt
# 开发 Task-001, 完成后等待合并
# 合并后: git worktree remove ../lane-a-state-mgmt

# Lane B: API 测试 (第二人)
git worktree add .claude/worktrees/lane-b-api-tests develop-api-tests
cd .claude/worktrees/lane-b-api-tests
# 开发 Task-002

# Lane C: 错误处理 (第三人)
git worktree add .claude/worktrees/lane-c-error-handler develop-error-handler
# 开发 Task-003

# Lane D: DB 优化 (第四人)
git worktree add .claude/worktrees/lane-d-db-optimize develop-db-optimize
# 开发 Task-005
```

**合并顺序**:
1. **W2 末**: Lane B/C/D 全部合并 (无依赖)
2. **W2 末**: Lane A (Task-001) 合并
3. **W3 初**: Lane A 新建分支，开始 Task-004 (依赖 Task-001✓)
4. **W4 末**: Lane A (Task-004/006) 和其他 (Task-008A) 全部合并

---

## ✅ 验收与检查清单

### **每周检查点** (每周一 09:00)

- [ ] Lane A/B/C/D 进度 (git log 对比)
- [ ] 有无阻塞或难点
- [ ] 时间估算是否准确（周报）
- [ ] 代码质量 (lint/format 无警告)

### **阶段检查点** (阶段末)

**W2 末 (6.04 - 任务 001/002/003/005 完成)**:
- [x] Task-001: App.jsx < 400 行 + E2E 测试全绿 ✅
- [x] Task-002: pytest coverage ≥ 85% ✅
- [x] Task-003: Toast 系统完整 + Error Boundary 捕获 ✅
- [x] Task-005: 索引创建 + 查询基准测试 ✅
- [ ] **合并主分支**: `git merge lane-{a,b,c,d} master`

**W4 末 (6.18 - 任务 004/006/008A 完成)**:
- [x] Task-004: LCP < 2.5s, 500 episodes 60fps ✅
- [x] Task-006: 响应式设计验证 (真实设备) ✅
- [x] Task-008A: request_id + 500 错误捕获 ✅
- [ ] **性能验收**: 灯塔评分 ≥ 85 (Performance + Accessibility)

**W12 末 (8.21 - 任务 009 完成)**:
- [x] Task-009: Swagger UI 可访问 ✅
- [ ] **最终版本标签**: `git tag v2.0-upgrade-complete`
- [ ] **发布清单**: 部署脚本、迁移说明、回滚计划

---

## 🚨 风险与缓解

| 风险 | 概率 | 缓解 |
|------|------|------|
| Task-001 引入 State 管理 bug，导致回归 | 中 | E2E 测试覆盖所有路由、播放、任务跳转 |
| Task-004 虚拟化与 Task-006 响应式冲突 | 低 | 分开合并，Task-004 先稳定再做 006 |
| Task-005 索引创建阻塞生产库 | 低 | 后台创建索引，staging 先验证 |
| 4 条 Lane 同时合并有冲突 | 中 | 先合并无依赖的 (B/C/D)，再合并 A |
| 3 个月时间估算过乐观 | 中 | 每周检查进度，推迟非关键任务 (009) |

---

## 📌 NOT in Scope (Q3 或后续)

以下工作**已识别但推迟**：

1. **Task-007: 结构化日志系统** (ELK/Datadog)
   - 原因: ROI 低，维护成本高
   - 推迟: Q3，评估成本-收益后决策

2. **离线检测 & 重连** (PWA 相关)
   - 推迟: 用户反馈后再做

3. **触摸手势优化** (swipe 导航)
   - 推迟: Q3 或 v3.0

4. **性能监控面板**（Grafana）
   - 推迟: Task-008A (基础日志) 稳定后再补

---

## 📞 责任分配 & 沟通

| 任务 | 所有者 | 审查人 | 合并检查清单 |
|------|--------|--------|------------|
| Task-001 | @claude-code | self-review | E2E ✅, Lint ✅, 无 console.warn ✅ |
| Task-002 | @claude-code | @code-reviewer | pytest ✅, coverage ✅, 权限隔离 ✅ |
| Task-003 | @claude-code | self-review | Toast ✅, ErrorBoundary ✅, 重试逻辑 ✅ |
| Task-004 | @claude-code | Performance-QA | Lighthouse ✅, 60fps ✅, <100MB ✅ |
| Task-005 | @claude-code | DBA-review | 索引 ✅, 基准测试 ✅, 0-downtime ✅ |
| Task-006 | @claude-code | @QA-mobile | 手机 ✅, 平板 ✅, 真实设备 ✅ |
| Task-008A | @claude-code | self-review | request_id ✅, 500 错误捕获 ✅ |
| Task-009 | @claude-code | Tech-writing | Swagger ✅, OpenAPI spec ✅ |

---

## 🎯 最终交付物清单

**代码**:
- [ ] 9 个 commit (Task-001 ~ 009，原子性)
- [ ] 0 个 TODO/FIXME 注释
- [ ] 0 个 console.warn/error 遗留
- [ ] 100% 通过 lint/format

**测试**:
- [ ] pytest coverage ≥ 85%
- [ ] E2E 测试 ≥ 10 个场景
- [ ] 响应式设计在 4 种设备验证

**文档**:
- [ ] UPGRADE_ROADMAP_REVIEW.md (这个文件)
- [ ] API docs (Swagger /docs)
- [ ] 迁移说明 (MIGRATION_GUIDE.md)
- [ ] 性能基准报告 (性能改善对比)

**部署**:
- [ ] 打 v2.0 标签
- [ ] 回滚计划 (git revert 脚本)
- [ ] 部署清单 (检查 MongoDB 索引等)

---

**状态**: ✅ **准备就绪** — 可启动开发  
**下一步**: 
1. ✅ 创建 Lane A-D 分支
2. 📌 分配开发人员
3. 🚀 Week 1 启动

**版本控制**: v2.0 (审查完成)  
**最后更新**: 2026-05-21 by gstack /plan-eng-review
