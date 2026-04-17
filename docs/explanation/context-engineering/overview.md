# 什么是 Context Engineering

## 定义与边界

Context Engineering 是一门**主动管理进入大模型上下文窗口的所有内容**的学科。它与传统的 Prompt Engineering 不同：

| 维度 | Prompt Engineering | Context Engineering |
|------|-------------------|---------------------|
| 关注点 | 提示词措辞、指令格式 | 上下文窗口中的 token 构成、位置、优先级 |
| 优化对象 | 单条提示 | 多轮对话中的动态内容组合 |
| 核心资源 | 模型能力 | 有限的注意力预算（Attention Budget） |

根据 Anthropic 的定义，Context Engineering 的核心是：
> "在模型的上下文窗口中选择最具信息量的 token 集合，以在给定任务上最大化性能。"

## 为什么对我们的项目至关重要

E-commerce Smart Agent 采用 **LangGraph + Supervisor 多 Agent 架构**，系统特点决定了上下文工程是我们的核心瓶颈：

- **多 Agent 编排**：Supervisor 路由 + 并行/串行执行，导致上下文在多个 Agent 之间传递
- **工具调用密集**：检索、改写、摘要、提取等工具产生大量输出
- **长会话场景**：电商客服往往需要 10~50 轮交互才能解决一个售后问题
- **记忆系统复杂**：结构化记忆（PostgreSQL）+ 向量记忆（Qdrant）+ 会话摘要三者共存

根据项目内部 `.opencode/skills/multi-agent-patterns/SKILL.md` 中记录的生产数据，在包含工具的 multi-agent 系统中，token 消耗可达单 Agent 对话的 **~15 倍**。如果不进行主动的上下文管理，成本、延迟和准确性都会迅速恶化。

## 内部研究成果与本项目前序工作

本项目在 `.opencode/skills/` 中已经积累了大量 Context Engineering 相关的系统化研究，这些是本路线图的重要基础：

| 技能模块 | 核心贡献 | 对应文档 |
|---------|---------|---------|
| `context-fundamentals` | 将上下文视为有限注意力预算；U 型注意力曲线；工具输出可占 83.9% token | [核心概念](./core-concepts.md) |
| `context-optimization` | KV-Cache 优先策略、Observation Masking、Compaction 阈值 | [最佳实践](./best-practices.md) |
| `context-compression` | 压缩方法对比（迭代摘要 vs 再生摘要 vs 不透明压缩） | [最佳实践](./best-practices.md) |
| `context-degradation` | 5 种降解模式的识别与缓解 | [Degradation 模式](./degradation-patterns.md) |
| `memory-systems` | Mem0/Zep/Graphiti/Letta/Cognee/LangMem 框架对比 | [最佳实践](./best-practices.md) |
| `multi-agent-patterns` | Supervisor/Swarm/Hierarchical 三种模式；上下文隔离是 multi-agent 的首要价值 | [代码库状态评估](./gap-analysis.md) |
| `tool-design` | 工具描述应回答"做什么、何时用、返回什么"；工具集膨胀会导致 JSON 序列化后占用 2~3 倍上下文 | [最佳实践](./best-practices.md) |

> **与 Prompt Engineering 的关系**：本项目已存在 Prompt Engineering 文档，其关注点在于 Prompt 措辞、模板结构和三层热重载机制。本文档则聚焦于**动态上下文的组装、预算、隔离与压缩**。两者互补：Prompt Engineering 决定"说什么"，Context Engineering 决定"放进什么、放多少、放在哪"。
