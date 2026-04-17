# 当前代码库状态评估

## 现有能力

我们的系统已经具备了上下文工程的部分基础能力：

| 模块 | 文件 | 当前能力 |
|------|------|---------|
| 记忆注入 | `app/graph/nodes.py` | `memory_node` 按固定数量加载：profile(1) + facts(3) + summaries(2) + vector messages(5) |
| Prompt 渲染 | `app/agents/base.py` | `BaseAgent` 支持 `{{variable}}` 模板替换和实验 Prompt 覆盖；`_format_memory_prefix` 用于格式化记忆前缀 |
| 查询改写 | `app/retrieval/rewriter.py` | `QueryRewriter` 保留最近 3 轮对话进行历史感知改写 |
| 会话摘要 | `app/memory/summarizer.py` | 当历史消息 > 20 条时触发摘要生成 |
| 事实提取 | `app/memory/extractor.py` | 通过 LLM 从问答中提取结构化事实 |
| A/B 实验 | `app/models/experiment.py` | 支持 Prompt/Config 变体的实验框架 |

> **A/B 实验状态说明**：`app/api/v1/chat.py` 已集成 `ExperimentAssigner` 并为每个会话分配 `experiment_variant_id`，Prompt 级别的 A/B 测试**已经激活**。但上下文工程相关的实验策略（如 memory budget、compaction threshold、masking 策略）尚未纳入变体配置。

> **注意**：`_format_memory_prefix` 的使用方式在 Agent 之间存在不一致。`ProductAgent`、`PolicyAgent` 通过 `_build_contextual_message` 将其注入到 LLM Prompt 中；而 `OrderAgent`、`CartAgent` 则将其直接拼接到最终返回的 `response` 字符串上，这意味着 LLM 在生成这些 Agent 的回复时**看不到**记忆上下文。

## 已识别的关键差距（Gaps）

### G1 — 缺乏 Token 预算管理

`memory_node` 使用硬编码的数量限制（facts=3, summaries=2, messages=5）进行获取，而 `BaseAgent._format_memory_prefix` 在渲染时也没有 token 感知的动态预算管理。fetch 与 render 两层都需要协调的 token 预算控制。

### G2 — 历史记录截断过于激进

`build_decider_node` 返回的 async wrapper 在调用实际决策逻辑后，返回 `{"history": [{"role": "assistant", "content": answer}]}`。历史消息本身**不会丢失**，但主 Agent 舰队（`OrderAgent`、`CartAgent`、`ProductAgent`、`PolicyAgent`、`ComplaintAgent`）的 `_create_messages()` 根本不接收 `history` 参数，导致积累下来的对话历史对大多数 Agent 的 LLM 调用毫无作用。

### G3 — 没有 KV-Cache 优化

`BaseAgent._build_system_prompt()` 每次调用都会重新渲染模板，其中包含动态变量如 `current_date`（`DEFAULT_PROMPT_VARIABLES` 中的 lambda），导致 System Prompt 在每一天甚至每一秒都可能不同，无法利用前缀缓存。

### G4 — 缺乏 Observation Masking

> **例外**：`PolicyAgent` 的 RAG 检索已经实现了相关性阈值过滤（score ≥ 0.5）和 Self-RAG 文档评分，其检索结果相对干净。

对于其余 Agent，情况更复杂：
- **`CartAgent`、`LogisticsAgent`、`AccountAgent`、`PaymentAgent`** **不将任何工具输出送入 LLM Prompt**。它们通过 `ToolRegistry` 调用工具，直接解析返回的 JSON，格式化为人类可读的回复字符串后返回。
- **`ProductAgent`** 在 `use_llm=True` 时，会将格式化的商品检索结果以 `context_parts` 形式传入 `_create_messages()`，目前未做长度截断或引用替换。

Observation Masking 的优先级应放在：
1. `ProductAgent` 检索结果的摘要化/引用化
2. 持久化 checkpoint 前对 `updated_state` 中的大型工具输出进行 masking

### G5 — 缺乏上下文压缩（Compaction）策略

`SessionSummarizer.should_summarize()` 的触发条件是 `len(history) > 20` **或**（`len(history) >= 2` 且会话自然结束）。触发依据都是**消息数量**，而非上下文利用率（utilization）。在工具调用密集的场景中，可能 5 条消息就已经占满了上下文窗口。

### G6 — Agent 切换时缺乏上下文隔离

`supervisor_node` 将完整状态传递给所有子 Agent，没有根据 Agent 的职责进行上下文分区。这会导致其他 Agent 的中间输出混入当前 Agent 的上下文，造成干扰。

### G7 — A/B 实验框架未充分激活

虽然实验框架的数据库模型和变体加载已经存在，但上下文工程相关的实验策略（如不同的记忆限制、压缩阈值）还没有被纳入 A/B 测试范围。

### G8 — 当前轮次消息中的 PII 过滤缺失

`vector_manager.py` 在存储向量记忆时已跳过 PII（信用卡号、密码等），因此**检索回来的记忆几乎没有 PII 风险**。真正的风险在于**当前轮次的 transient messages**：用户可能在对话中直接发送敏感信息，这类内容尚未进入向量存储，但会原样出现在 `messages` 中并被直接送往 LLM。

### G9 — LangGraph Checkpointer 状态膨胀

`app/graph/workflow.py` 使用 `checkpointer`（当前实现为 `AsyncRedisSaver`）持久化完整的 `AgentState` 到 Redis。随着会话轮数增加，checkpoint 会存储完整的工具输出和历史记录，导致 Redis 中存储的 checkpoint 体积持续线性累积。

### G10 — 多数 Agent 的 LLM 调用未接入 Conversation History

代码审计显示，`BaseAgent._create_messages()` **没有 `history` 参数**。`OrderAgent`、`CartAgent` 的主流程完全不将历史记录送入 LLM；`ProductAgent`、`PolicyAgent` 传入 `question` + `context` + `memory_context`；`ComplaintAgent` 传入 `question` + `memory_context`。它们都不携带历史记录。

**修复方向**：要么显式将 `history` 线程化到 `_create_messages()` 中（再对其进行 budget/compaction 优化），要么在当前阶段将上下文预算重心从 history 重新分配到 memory/retrieval 的优化上。
