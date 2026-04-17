# LangGraph 工作流详解

当前 Agent 层采用 **Supervisor-based Graph** 编排方式，并在工作流中嵌入 **记忆层** (`memory_node`)，实现长期上下文增强：

- `router_node` 负责意图识别与澄清，将结果写入 `AgentState`。
- `memory_node` 加载结构化记忆（`UserProfile`、`UserPreference`、`UserFact`、`InteractionSummary`）和向量对话记忆（`conversation_memory` 语义检索），生成 `memory_context` 并注入后续 Agent Prompt。
- `supervisor_node` 基于 `intent_result` 中的主意图和 `pending_intents`，通过 `plan_dispatch` 判断多个意图之间是否独立，决定**串行**或**并行**调度。
- 若为并行，通过 `build_parallel_sends` 生成多个 `LangGraph Send`，同时分发到不同的 `Agent Subgraph`。
- 各 `Agent Subgraph` 执行完毕后统一收敛到 `synthesis_node`，将多个专家回复融合为一段连贯回答。
- 之后进入 `evaluator_node` 进行置信度评估，低置信度时回到 `router_node` 重试。
- `decider_node` 在最终决策（人工接管/直接回复）后，触发 Celery 异步任务进行会话摘要与事实抽取。

```mermaid
flowchart LR
    START([START]) --> ROUTER["🎯 router_node\n意图路由"]

    ROUTER -->|"主意图 / slots"| MEMORY["🧠 memory_node\n记忆加载 / 摘要注入"]

    MEMORY -->|"memory_context"| SUPERVISOR["🧠 supervisor_node\n串行/并行调度"]

    SUPERVISOR -->|"串行"| POLICY["📚 policy_agent\nSubgraph"]
    SUPERVISOR -->|"串行"| ORDER["📦 order_agent\nSubgraph"]
    SUPERVISOR -->|"并行 Send"| PRODUCT["🛍️ product\nSubgraph"]
    SUPERVISOR -->|"并行 Send"| CART["🛒 cart\nSubgraph"]
    SUPERVISOR -->|"串行"| LOGISTICS["🚚 logistics\nSubgraph"]
    SUPERVISOR -->|"串行"| ACCOUNT["👤 account\nSubgraph"]
    SUPERVISOR -->|"串行"| PAYMENT["💳 payment\nSubgraph"]
    SUPERVISOR -->|"串行"| COMPLAINT["📋 complaint\nSubgraph"]

    POLICY --> SYNTHESIS["🔄 synthesis_node\n多 Agent 回复融合"]
    ORDER --> SYNTHESIS
    PRODUCT --> SYNTHESIS
    CART --> SYNTHESIS
    LOGISTICS --> SYNTHESIS
    ACCOUNT --> SYNTHESIS
    PAYMENT --> SYNTHESIS
    COMPLAINT --> SYNTHESIS

    SYNTHESIS --> EVAL["⚖️ evaluator_node\n置信度评估"]
    EVAL -->|"低置信度"| ROUTER
    EVAL -->|"通过"| DECIDER["🔀 decider_node\n人工接管决策 / 回复生成 / 记忆抽取触发"]

    DECIDER -->|"无需接管"| END_NORMAL([END])
    DECIDER -->|"需要审核"| END_AUDIT([END\n等待人工审核])

    style MEMORY fill:#e1bee7,stroke:#7b1fa2
    style SUPERVISOR fill:#bbdefb,stroke:#1565c0
    style EVAL fill:#ffeb3b,stroke:#f57f17
    style END_AUDIT fill:#ff9800,stroke:#e65100
```
