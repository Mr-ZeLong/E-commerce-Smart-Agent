# 最佳实践与要求

## 记忆系统（Memory System）

### 要求 M1：实施 Token 预算驱动的优先级淘汰

记忆注入必须基于 token 预算，而不是固定数量。当总 token 超过阈值时，按以下优先级淘汰：
1. 最旧的 vector messages
2. 最旧的 interaction summaries
3. 置信度最低的 facts
4. 非核心 preferences

### 要求 M2：引入记忆新鲜度（Freshness）

`UserProfile`、`UserPreference`、`InteractionSummary`、`UserFact` 等结构化记忆模型已经具备 `updated_at` 字段。当前缺少的是**检索时的新鲜度过滤**：`StructuredMemoryManager` 的查询方法尚未支持按 `updated_at` 过滤（如 `max_age_days` 参数）。需要为记忆检索增加时间窗口过滤能力，例如只返回最近 30 天内的交互摘要或事实。

### 要求 M3：扩展 A/B 实验到记忆策略

将 `memory_context_config` 作为 JSON 字段加入 `ExperimentVariant` 模型，支持 A/B 测试不同的：
- 记忆预算上限
- 记忆注入顺序
- 淘汰策略

## 检索与 RAG

### 要求 R1：增加向量记忆检索的相关性阈值过滤

`PolicyAgent` 的 RAG 检索已经实现了相关性阈值（score ≥ 0.5）和 Self-RAG 评分，但 `vector_manager.search_similar()`（被 `memory_node` 调用）返回的向量记忆仍然没有任何阈值过滤。需要为向量记忆注入增加 similarity score > threshold 的门控。

### 要求 R2：实施 Observation Masking

对超过 500 字符的工具输出进行 masking，保留：
- 引用 ID
- 关键结论摘要（1~2 句话）
- 完整数据的检索路径

### 要求 R3：扩展 QueryRewriter 的压缩能力

当前 `QueryRewriter` 只压缩最近 3 轮对话。需要支持更广泛的 compaction：当历史对话 token 超过阈值时，将早期对话替换为结构化摘要。

## Agent Prompt 设计

### 要求 P1：实施 KV-Cache 优化

`BaseAgent._create_messages()` 当前只生成 `[SystemMessage, HumanMessage]`，其中 System Prompt 的稳定性是 KV-Cache 优化的关键：
1. **BaseAgent System Prompt 完全确定化**：移除 `DEFAULT_PROMPT_VARIABLES` 中的动态 lambda（如 `current_date`），将日期等动态内容移到 `HumanMessage` 中传递；避免在 System Prompt 中嵌入随机 ID、请求计数器或时间戳。
2. **保持消息结构稳定**：`_build_contextual_message()` 的拼接格式应使用确定性模板（固定分隔符、固定字段顺序），避免因空白字符变化破坏缓存。
3. **IntentClassifier 与 ComplaintAgent 的 System Prompt 稳定化**：
   - `app/intent/classifier.py` 的 `_create_messages()` 会根据查询动态挑选 top-k few-shot 示例并追加到 `SystemMessage` 中，导致每次请求的系统提示前缀都不同。修复方案：将 few-shot 示例移到 `HumanMessage` 中，或使用固定的 canonical 示例集。
   - `app/agents/complaint.py` 使用完全相同的模式（`select_top_k_examples(query, self._few_shot_examples, k=3)` 追加到 system prompt），修复方案与 `IntentClassifier` 一致。

> **关键注意**：在 LangGraph/LangChain 架构中，Tool Definitions 是通过 `bind_tools()` 绑定到 LLM 实例上的，不是作为显式消息传入 `_create_messages()` 的。因此 KV-Cache 优化的核心在于让 `SystemMessage` 的前缀高度稳定。

### 要求 P2：增加 Token 数量 guardrails

在 `BaseAgent._create_messages()` 中加入 token 计数检查。当总 token 超过窗口的 80% 时，触发 compaction 或返回明确的错误信息。

## 多 Agent 编排

### 要求 A1：Agent 切换时的上下文隔离

`supervisor_node` 在调用子 Agent 时，应该只传递与该 Agent 职责相关的状态切片：
- 只包含该 Agent 需要的工具定义
- 过滤掉其他 Agent 的 intermediate reasoning
- 保留用户原始 query 和必要的记忆上下文

### 要求 A2：增加上下文利用率指标

在 `AgentState` 中增加 `context_tokens` 和 `context_utilization` 字段，用于：
- 驱动 compaction 决策
- 记录到可观测性系统（OpenTelemetry）
- 支持 A/B 实验的效果评估

### 要求 A3：为 Synthesis Node 增加置信度过滤

`SynthesisNode` 在合并 `sub_answers` 之前，应该：
- 过滤掉置信度低于阈值的 answer
- 标注每个 answer 的来源 Agent
- 当多个 answer 冲突时，触发降级策略（如请求用户澄清）
