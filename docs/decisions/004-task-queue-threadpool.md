# ADR-004: 异步任务用 ThreadPoolExecutor 而非 Celery

**状态**: 已实施

**背景**: 转录/摘要/下载是耗时操作，需要异步执行。

**决策**: 使用 Python 内置 `ThreadPoolExecutor` + MongoDB 持久化任务状态。启动时自动恢复中断任务。

**取舍**:
- 选了：零外部依赖（不需要 Redis/RabbitMQ）
- 限制：不支持分布式、不可水平扩展
- 适合：单机部署场景
