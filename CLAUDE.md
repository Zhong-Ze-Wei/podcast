# Podcast Manager - 项目约束

## 技术栈
- **后端**: Python 3.12 + Flask + MongoDB + Docker
- **前端**: React 18 + Vite + TailwindCSS
- **AI**: OpenAI 兼容 API (LLMClient)

## 核心工作流

### TDD 迭代流程
每个任务严格遵循 Red → Green → Refactor 循环：
1. **写失败测试** — 明确要实现什么
2. **最小实现** — 只让测试通过，不多写
3. **重构** — 测试保护下安全重构

### 原子提交规则
- 每完成一个原子任务，立即 git commit
- commit message 格式: `<type>(<scope>): <描述>`
  - type: feat / fix / refactor / test / docs / chore
  - scope: api / service / model / component / view
- 示例: `test(api): add briefing endpoint tests` → `feat(service): implement briefing generation`

## 架构约束

### 后端分层
```
api/        → 薄路由层，只做参数校验和调 service
services/   → 业务逻辑，调 LLMClient / MongoDB
models/     → 纯数据模型，不含业务逻辑
core/       → 可复用的领域逻辑（如 summarization engine）
```

### AI 调用规范
- 统一通过 `LLMClient` 调用，不直接 import openai
- 每个 AI 功能是独立的 Service（如 BriefingService、SummaryService）
- 不引入中间抽象层（如 LangGraph），除非有真实需求
- 不写 placeholder / TODO — 要么实现，要么不写

### 数据库
- 所有 MongoDB 操作通过 service 层，api 层不直接操作 db
- Model 只负责文档结构定义和格式转换

### 前端
- API 调用统一在 `services/api.js`，组件不直接用 axios
- 视图组件（views/）只负责渲染，状态提升到 App.jsx

## 代码规范
- 不写 mock 数据 — 前端要么接真实 API，要么显示空状态
- 不写 try/catch 包裹不会失败的代码
- 不添加没有真实需求的防御性分支
- 函数单一职责，名称即文档

## 测试规范
- 后端测试: `pytest`，放在 `backend/tests/`
- 测试文件命名: `test_<module>.py`
- 每个 API 端点至少一个集成测试
- LLM 调用用 mock，不实际请求
- MongoDB 用 mongomock 或 mock
- 运行: `cd backend && python -m pytest tests/ -v`

## Git 规范
- 主分支: master
- 原子提交：一个 commit 只做一件事
- 不提交 .env、.venv、node_modules、__pycache__
- 提交前确认测试通过
