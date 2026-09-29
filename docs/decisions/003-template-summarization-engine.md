# ADR-003: 模板化摘要引擎

**状态**: 已实施

**背景**: 摘要需求多变（学习笔记、访谈纪要、新闻速览），硬编码 prompt 难以维护。

**决策**: 摘要引擎基于 MongoDB 中的 `prompt_templates` 集合。模板定义 system_prompt、required_blocks、optional_blocks、parameters。引擎动态构建 prompt，校验输出，失败自动重试 3 次。

**取舍**:
- 选了：用户可自定义模板、启用/禁用输出块
- 代价：模板 schema 复杂，校验逻辑较重
