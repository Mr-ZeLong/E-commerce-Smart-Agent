# Context Engineering 路线图

## Q2 阶段：基础能力建设（Token 预算、KV-Cache、压缩）

| 编号 | 任务 | 目标文件 | 建议测试 | 成功标准 |
|------|------|---------|---------|---------|
| **T1** | 实现 TokenBudget 管理器 | 新建 `app/context/token_budget.py` | `tests/context/test_token_budget.py` | 记忆上下文 token 数不超过 2048（可配置） |
| **T2** | 将 TokenBudget 集成到 memory_node | `app/graph/nodes.py` | `tests/graph/test_memory_node.py` | 动态限制替换 facts=3/summaries=2 的硬编码 |
| **T3** | 为 BaseAgent 增加 KV-Cache 优化 | `app/agents/base.py`<br>`app/agents/complaint.py`<br>`app/intent/classifier.py`<br>`app/core/llm_factory.py` | `tests/agents/test_base_agent.py` | 第一阶段：移除 System Prompt 中的动态内容（时间戳、随机 ID），确保前缀确定性；同步修复 `IntentClassifier` 和 `ComplaintAgent` 的动态 few-shot 追加问题。第二阶段：在 `llm_factory.py` 中通过 LangChain 构造器的 `model_kwargs` / `extra_headers` 注入 provider 特定的缓存参数 |
| **T4** | 实现上下文压缩触发器 | 新建 `app/memory/compactor.py`<br>修改 `app/memory/summarizer.py` | `tests/memory/test_compactor.py` | 利用率 > 75% 时触发压缩，而非仅消息数 > 20 |
| **T5** | 为工具输出增加 Observation Masking | `app/tools/product_tool.py`<br>`app/tools/cart_tool.py`<br>`app/tools/logistics_tool.py`<br>`app/graph/nodes.py`<br>`app/graph/subgraphs.py` | `tests/tools/test_observation_masking.py` | 超过 500 字符的输出在传入 LLM Prompt 或持久化 checkpoint/`updated_state` 前被替换为引用+摘要 |

## Q3 阶段：高级能力（上下文隔离、A/B 激活、评估）

| 编号 | 任务 | 目标文件 | 建议测试 | 成功标准 |
|------|------|---------|---------|---------|
| **T6** | 在 supervisor_node 中实现上下文隔离切换 | `app/agents/supervisor.py`<br>`app/graph/subgraphs.py`<br>`app/graph/workflow.py`<br>`app/graph/nodes.py` | `tests/graph/test_subgraphs.py` | 为每个子 Agent 构建过滤后的状态切片，只传递相关状态键和工具定义 |
| **T7** | 扩展 A/B 框架支持上下文策略实验 | `app/models/experiment.py`<br>`app/services/experiment.py` | `tests/services/test_experiment.py` | 可 A/B 测试记忆限制和压缩策略 |
| **T8** | 增加上下文利用率遥测 | `app/models/state.py`<br>`app/observability/execution_logger.py` | `tests/observability/test_logger.py` | 每次图执行记录上下文 token 数 |
| **T9** | 实现向量记忆检索相关性门控 | `app/memory/vector_manager.py`<br>`app/graph/nodes.py` | `tests/memory/test_vector_manager.py` | 为 `memory_node` 的向量记忆注入增加 score > threshold 过滤 |

## 依赖关系图

```
Q2 基础阶段：
    T1 (TokenBudget)
      │
      ▼
    T2 (memory_node 集成) ◄────┐
      │                        │
      ▼                        │
    T3 (KV-Cache)              │
      │                        │
      ▼                        │
    T4 (Compactor)             │
      │                        │
      ▼                        │
    T5 (Observation Masking)   │
                               │
Q3 高级阶段：                  │
    T6 (上下文隔离) ◄──────────┘
      │
      ▼
    T7 (A/B 框架扩展)
      │
      ▼
    T8 (利用率遥测)
      │
      ▼
    T9 (检索门控)
```

> 架构约束说明：所有上下文工程的实现任务必须遵守相关 `AGENTS.md` 中的不变量，包括但不限于 Async-First、Multi-Tenant Isolation、No Hardcoded Secrets、Type Safety。
