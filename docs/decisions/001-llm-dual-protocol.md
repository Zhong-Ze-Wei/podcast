# ADR-001: LLM 客户端双协议支持

**状态**: 已实施

**背景**: 不同 AI 服务商使用不同 API 协议（OpenAI 格式 vs Anthropic 格式）。

**决策**: 在 `LLMClient` 中通过 `api_format` 字段分支：`openai_compatible` 使用 openai SDK，`anthropic_messages` 使用 requests HTTP。

**取舍**:
- 选了：统一接口，上层服务无需关心协议差异
- 没选：每种协议独立客户端类（过度抽象）
