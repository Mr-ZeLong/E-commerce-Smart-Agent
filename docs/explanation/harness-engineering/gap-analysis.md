# Harness Engineering差距分析

> **文档版本**: 1.0  
> **生成日期**: 2026-04-17

---

## 1. 已有能力（Strengths）

### 1.1 评估基础设施

| 能力 | 文件 | 状态 | 说明 |
|------|------|------|------|
| **评估Pipeline** | `app/evaluation/pipeline.py` | ✅ 已实现 | 支持Golden Dataset批量评估 |
| **核心Metrics** | `app/evaluation/metrics.py` | ✅ 已实现 | intent_accuracy, slot_recall, rag_precision, answer_correctness |
| **幻觉检测** | `app/evaluation/hallucination.py` | ✅ 已实现 | LLM-as-Judge幻觉检测 |
| **Few-shot评估** | `app/evaluation/few_shot_eval.py` | ✅ 已实现 | Few-shot示例效果对比 |
| **评估任务** | `app/tasks/evaluation_tasks.py` | ✅ 已实现 | Celery异步评估任务 |
| **Prompt效果报告** | `app/tasks/prompt_effect_tasks.py` | ✅ 已实现 | 月度Prompt效果报告生成 |

### 1.2 测试框架

| 能力 | 文件 | 状态 | 说明 |
|------|------|------|------|
| **单元测试** | `tests/` (100+文件) | ✅ 已实现 | pytest + pytest-asyncio |
| **覆盖率检查** | CI配置 | ✅ 已实现 | 要求 ≥75% |
| **集成测试** | `tests/integration/` | ✅ 已实现 | LangGraph工作流集成测试 |
| **Mock工具** | `tests/_llm.py`, `tests/_agents.py` | ✅ 已实现 | LLM和Agent的Mock辅助函数 |

### 1.3 可观测性

| 能力 | 文件 | 状态 | 说明 |
|------|------|------|------|
| **执行日志** | `app/models/observability.py` | ✅ 已实现 | `GraphExecutionLog`记录每次执行 |
| **OpenTelemetry** | `app/observability/` | ✅ 已实现 | 全链路追踪 |
| **A/B实验** | `app/services/experiment.py` | ✅ 已实现 | 实验分配和追踪 |

### 1.4 上下文工程基础

| 能力 | 文件 | 状态 | 说明 |
|------|------|------|------|
| **Token预算管理** | `app/context/token_budget.py` | ✅ **已实现** | `MemoryTokenBudget`类，支持优先级淘汰 |
| **Observation Masking** | `app/context/masking.py` | ✅ **已实现** | `mask_observation()`和`mask_context_parts()` |
| **上下文压缩** | `app/memory/compactor.py` | ✅ **已实现** | `ContextCompactor`类，基于token利用率触发 |

---

## 2. 关键差距（Gaps）

### G1 — Token预算管理未完全集成

**现状**: `MemoryTokenBudget`已实现，但`memory_node`中可能仍使用硬编码限制  
**影响**: Token预算能力未充分发挥  
**优先级**: P1

### G2 — KV-Cache未优化

**现状**: `BaseAgent._build_system_prompt()`包含动态变量（`current_date` lambda）  
**影响**: System Prompt不稳定，无法利用前缀缓存  
**优先级**: P0

### G3 — Golden Dataset覆盖不足

**现状**: 当前Golden Dataset覆盖有限，缺少边界case和长对话场景  
**影响**: 无法充分验证边缘场景和复杂对话  
**优先级**: P1

### G4 — 回归测试自动化不完善

**现状**: CI运行单元测试和覆盖率检查，但缺少：
- Golden Dataset自动评估
- Prompt变更性能对比
- Benchmark性能趋势追踪  
**影响**: 变更可能引入性能退化而无法及时发现  
**优先级**: P1

### G5 — 生产监控看板缺失

**现状**: `GraphExecutionLog`记录基础指标，但缺少实时可视化看板  
**影响**: 无法实时监控Agent性能趋势  
**优先级**: P2

### G6 — 多维度评估指标不完善

**现状**: 已实现的指标覆盖功能性评估，但缺少：
- 语气一致性（Tone Consistency）
- 对话保持率（Containment Rate）
- Token成本追踪
- 延迟趋势分析  
**影响**: 无法全面评估Agent质量和运营效率  
**优先级**: P2

### G7 — Agent切换时上下文隔离不足

**现状**: `supervisor_node`传递完整状态给所有子Agent  
**影响**: 其他Agent的中间输出混入当前Agent上下文  
**优先级**: P2

### G8 — 当前轮次PII过滤缺失

**现状**: `vector_manager.py`在存储向量记忆时已跳过PII，但当前轮次的transient messages未过滤  
**影响**: 用户可能在对话中直接发送敏感信息，原样送往LLM  
**优先级**: P1

### G9 — LangGraph Checkpointer状态膨胀

**现状**: `AsyncRedisSaver`持久化完整`AgentState`到Redis，体积随轮数线性增长  
**影响**: Redis存储压力增大，checkpoint读取延迟增加  
**优先级**: P2

### G10 — 多数Agent的LLM调用未接入Conversation History

**现状**: `BaseAgent._create_messages()`没有`history`参数，多数Agent不携带历史记录  
**影响**: LLM无法利用对话上下文，影响多轮交互质量  
**优先级**: P2

---

## 3. 差距总结

| 优先级 | 差距数量 | 主要领域 |
|--------|----------|----------|
| **P0** | 1 | KV-Cache优化 |
| **P1** | 4 | Token预算集成、Golden Dataset、回归测试、PII过滤 |
| **P2** | 5 | 监控看板、多维度指标、上下文隔离、Checkpointer膨胀、History接入 |

**与Context Engineering差距的关系**：

本差距分析聚焦于**Harness Engineering维度**（评估、测试、监控）。Context Engineering差距（如T1-T9任务）已在[Context Engineering路线图](../context-engineering/roadmap.md)中详细描述。两者互补但不重复。
