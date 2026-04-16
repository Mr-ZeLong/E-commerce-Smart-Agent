# Context Engineering 路线图

> **文档定位**：为 E-commerce Smart Agent 项目提供上下文工程（Context Engineering）的系统化说明、最佳实践，以及下一阶段的具体目标和任务规划。
>
> **适用读者**：后端/算法工程师、架构师、技术负责人。

---

## 1. 什么是 Context Engineering

### 1.1 定义与边界

Context Engineering 是一门**主动管理进入大模型上下文窗口的所有内容**的学科。它与传统的 Prompt Engineering 不同：

| 维度 | Prompt Engineering | Context Engineering |
|------|-------------------|---------------------|
| 关注点 | 提示词措辞、指令格式 | 上下文窗口中的 token 构成、位置、优先级 |
| 优化对象 | 单条提示 | 多轮对话中的动态内容组合 |
| 核心资源 | 模型能力 | 有限的注意力预算（Attention Budget） |

根据 Anthropic 的定义，Context Engineering 的核心是：
> "在模型的上下文窗口中选择最具信息量的 token 集合，以在给定任务上最大化性能。"

### 1.2 为什么对我们的项目至关重要

E-commerce Smart Agent 采用 **LangGraph + Supervisor 多 Agent 架构**，系统特点决定了上下文工程是我们的核心瓶颈：

- **多 Agent 编排**：Supervisor 路由 + 并行/串行执行，导致上下文在多个 Agent 之间传递
- **工具调用密集**：检索、改写、摘要、提取等工具产生大量输出
- **长会话场景**：电商客服往往需要 10~50 轮交互才能解决一个售后问题
- **记忆系统复杂**：结构化记忆（PostgreSQL）+ 向量记忆（Qdrant）+ 会话摘要三者共存

根据项目内部 `.opencode/skills/multi-agent-patterns/SKILL.md` 中记录的生产数据，在包含工具的 multi-agent 系统中，token 消耗可达单 Agent 对话的 **~15 倍**。如果不进行主动的上下文管理，成本、延迟和准确性都会迅速恶化。

### 1.3 内部研究成果与本项目前序工作

本项目在 `.opencode/skills/` 中已经积累了大量 Context Engineering 相关的系统化研究，这些是本路线图的重要基础：

| 技能模块 | 核心贡献 | 本路线图对应章节 |
|---------|---------|-----------------|
| `context-fundamentals` | 将上下文视为有限注意力预算；U 型注意力曲线（开头/结尾 85%~95% 回忆率，中间 76%~82%）；工具输出可占 83.9% token | 第 2 节 |
| `context-optimization` | KV-Cache 优先策略、Observation Masking 规则、Compaction 触发阈值（>70%）、Context Partitioning 四层策略 | 第 5 节 |
| `context-compression` | 压缩方法对比（迭代摘要 vs 再生摘要 vs 不透明压缩）；代码与 prose 的不同压缩策略 | 第 5 节 |
| `context-degradation` | 5 种降解模式（lost-in-the-middle、poisoning、distraction、confusion、clash）的识别与缓解 | 第 4 节 |
| `memory-systems` | Mem0/Zep/Graphiti/Letta/Cognee/LangMem 框架对比；Letta 文件系统代理在 LoCoMo 达 74%，超过 Mem0 的 68.5% | 第 5.1 节 |
| `multi-agent-patterns` | Supervisor/Swarm/Hierarchical 三种模式；多 Agent 系统 token 成本约为单 Agent 的 ~15 倍；上下文隔离是 multi-agent 的首要价值 | 第 5.4 节 |
| `tool-design` | 工具描述应回答"做什么、何时用、返回什么"；工具集膨胀会导致 JSON 序列化后占用 2~3 倍上下文 | 第 5.3 节 |

> **与 Prompt Engineering 的关系**：本项目已存在 [`docs/prompt-engineering-roadmap.md`](./prompt-engineering-roadmap.md)，其关注点在于 Prompt 措辞、模板结构和三层热重载机制。本文档则聚焦于**动态上下文的组装、预算、隔离与压缩**。两者互补：Prompt Engineering 决定"说什么"，Context Engineering 决定"放进什么、放多少、放在哪"。

---

## 2. 核心概念

### 2.1 U 型注意力曲线（Lost-in-the-Middle）

LLM 对上下文中不同位置的信息回忆能力呈 **U 型分布**：

- **开头和结尾**：回忆准确率 **85%~95%**
- **中间位置**：回忆准确率下降至 **76%~82%**

这意味着：如果我们把最关键的系统指令、安全约束或商品政策放在上下文的中间位置，模型很可能会"忽略"它们。

> **对本项目的启示**：`memory_node` 注入的记忆内容（profile、facts、preferences、messages）必须考虑位置优先级，而不是简单拼接。

### 2.2 Token 经济学

| 架构模式 | Token 倍数（相对单 Agent 对话） |
|---------|-------------------------------|
| 单 Agent 纯对话 | 1x |
| 单 Agent + 工具调用 | ~4x |
| Multi-Agent 编排系统 | ~15x |

这背后的主要原因是：
- 根据项目内部 `.opencode/skills/context-fundamentals/SKILL.md`，工具输出在 Agent 轨迹中可占据 **83.9%** 的 token
- 多 Agent 之间的上下文传递会反复复制公共前缀
- 没有进行上下文隔离时，每个子 Agent 都会接收到完整的历史记录

### 2.3 上下文预算（Context Budget）

上下文预算是 Context Engineering 的核心约束。我们建议将上下文窗口划分为以下组成部分：

| 组件 | 建议预算占比 | 说明 |
|------|-------------|------|
| System Prompt | 5%~10% | 最稳定的前缀内容 |
| Tool Definitions | 15%~25% | 工具描述和参数 Schema |
| Few-shot Examples | 5%~10% | 可复用的示例模板 |
| Retrieved Memories | 20%~30% | 从数据库/向量库检索的记忆 |
| Conversation History | 剩余部分 | 多轮对话历史（当前多数 Agent 的 LLM 调用未实际传入 history，因此预算可暂时向 Retrieved Memories 倾斜） |
| Output Buffer | 预留 20%~30% | 确保输入不会挤占输出空间 |

---

## 3. 当前代码库状态评估

### 3.1 现有能力

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

### 3.2 已识别的关键差距（Gaps）

通过代码审阅和理论研究，我们发现以下 10 个核心差距：

#### G1 — 缺乏 Token 预算管理
`memory_node` 使用硬编码的数量限制（facts=3, summaries=2, messages=5）进行获取，而 `BaseAgent._format_memory_prefix` 在渲染时也没有 token 感知的动态预算管理。这意味着：当某个 fact 很长时，记忆上下文可能远超安全阈值。fetch 与 render 两层都需要协调的 token 预算控制。

#### G2 — 历史记录截断过于激进
`build_decider_node` 返回的 async wrapper（`_async_decider_node`）在调用实际决策逻辑后，返回 `{"history": [{"role": "assistant", "content": answer}]}`。由于 `AgentState.history` 使用了 `operator.add` 作为 reducer，LangGraph 会将其**追加**到已有的 checkpoint 历史中，而不是替换。因此，历史消息本身**不会丢失**。

真正的问题是：**历史记录虽然被完整保留，但主 Agent 舰队（`OrderAgent`、`CartAgent`、`ProductAgent`、`PolicyAgent`、`ComplaintAgent`）的 `_create_messages()` 根本不接收 `history` 参数**。这意味着积累下来的对话历史对大多数 Agent 的 LLM 调用毫无作用，仅在意图识别和查询改写模块中被使用。

#### G3 — 没有 KV-Cache 优化
`BaseAgent._build_system_prompt()` 每次调用都会重新渲染模板，其中包含动态变量如 `current_date`（`DEFAULT_PROMPT_VARIABLES` 中的 lambda），导致 System Prompt 在每一天甚至每一秒都可能不同，无法利用前缀缓存。此外，`_build_contextual_message()` 将所有记忆和检索内容打包进单个 `HumanMessage`，使得用户消息部分变得臃肿且不稳定。

#### G4 — 缺乏 Observation Masking
> **例外**：`PolicyAgent` 的 RAG 检索已经实现了相关性阈值过滤（score ≥ 0.5）和 Self-RAG 文档评分，其检索结果相对干净。

对于其余 Agent，情况比"原样注入"更复杂：
- **`CartAgent`、`LogisticsAgent`、`AccountAgent`、`PaymentAgent`** **不将任何工具输出送入 LLM Prompt**。它们通过 `ToolRegistry` 调用工具，直接解析返回的 JSON，格式化为人类可读的回复字符串后返回。`OrderAgent` 虽不经过 `ToolRegistry`，但同样直接调用 `OrderService` 并将服务返回的结构化数据格式化为回复。因此，对这些 Agent 的 LLM 调用而言，Observation Masking **暂时不影响 token 成本**；但原始工具/服务输出会以结构化数据形式存入 `AgentState.updated_state`，持续加剧 G9 的 checkpointer 膨胀。
- **`ProductAgent`** 在 `use_llm=True` 时，会将格式化的商品检索结果以 `context_parts` 形式传入 `_create_messages()`，目前未做长度截断或引用替换。当检索结果包含大量商品时，这部分会显著挤占上下文窗口。

因此，Observation Masking 的优先级应放在：
1. `ProductAgent` 检索结果的摘要化/引用化
2. 持久化 checkpoint 前对 `updated_state` 中的大型工具输出进行 masking（缓解 G9）

研究表明，经过 masking 后，工具输出 token 可减少 **60%~80%**。

#### G5 — 缺乏上下文压缩（Compaction）策略
`SessionSummarizer.should_summarize()` 的触发条件是 `len(history) > 20` **或**（`len(history) >= 2` 且会话自然结束、不需要转人工）。这意味着即使是 2 条消息的短对话也可能触发摘要。然而，无论哪种情况，触发依据都是**消息数量**，而非上下文利用率（utilization）。在工具调用密集的场景中，可能 5 条消息就已经占满了上下文窗口，但系统缺乏基于 token 预算或利用率指标的动态 compaction 机制。

#### G6 — Agent 切换时缺乏上下文隔离
`supervisor_node` 将完整状态传递给所有子 Agent，没有根据 Agent 的职责进行上下文分区。这会导致：
- 其他 Agent 的中间输出（如 `sub_answers`、不同领域的 `updated_state` 字段）混入当前 Agent 的上下文，造成干扰
- `ProductAgent` 可能看到 `OrderAgent` 产生的 `order_data`，`CartAgent` 可能继承 `PolicyAgent` 的 `retrieval_result` 残留值

#### G7 — A/B 实验框架未充分激活
虽然实验框架的数据库模型和变体加载已经存在，但上下文工程相关的实验策略（如不同的记忆限制、压缩阈值）还没有被纳入 A/B 测试范围。

#### G8 — 当前轮次消息中的 PII 过滤缺失
`vector_manager.py` 在存储向量记忆时已跳过 PII（信用卡号、密码等），因此**检索回来的记忆几乎没有 PII 风险**。真正的风险在于**当前轮次的 transient messages**：用户可能在对话中直接发送敏感信息（如"我的卡号是 6222..."），这类内容尚未进入向量存储，但会原样出现在 `messages` 中并被直接送往 LLM。当前系统没有在 LLM 调用前对 `messages` 进行 PII 脱敏。

#### G9 — LangGraph Checkpointer 状态膨胀
`app/graph/workflow.py` 使用 `checkpointer`（当前实现为 `AsyncRedisSaver`）持久化完整的 `AgentState` 到 Redis。随着会话轮数增加，checkpoint 会存储完整的工具输出和历史记录，导致：
- Redis 中存储的 checkpoint 体积随会话轮数**持续线性累积**
- 每次图调用时状态反序列化变慢
- checkpointer 中保存的上下文比实际注入 LLM 的上下文更臃肿

当前系统没有 checkpoint 修剪（pruning）或 compaction 策略。

#### G10 — 多数 Agent 的 LLM 调用未接入 Conversation History
代码审计显示，`BaseAgent._create_messages()` **没有 `history` 参数**。`OrderAgent`、`CartAgent` 的主流程完全不将历史记录送入 LLM；`ProductAgent`、`PolicyAgent` 传入 `question` + `context` + `memory_context`；`ComplaintAgent` 传入 `question` + `memory_context`。它们都不携带历史记录。这意味着：
- 当前主 Agent 舰队实际上是**单轮交互**，无法利用历史上下文进行连贯推理
- 对 "Conversation History" 的上下文预算优化（如 compaction）对大多数 Agent 的 LLM 调用**暂时不产生影响**
- `decider_node` 重置 `history` 的问题（G2）虽然存在，但受影响范围比预期更小——只有依赖历史的模块（如意图识别、查询改写）才会实际感知

**修复方向**：要么显式将 `history` 线程化到 `_create_messages()` 中（再对其进行 budget/compaction 优化），要么在当前阶段将上下文预算重心从 history 重新分配到 memory/retrieval 的优化上。

---

## 4. Context Degradation 模式与项目风险

### 4.1 Lost-in-the-Middle（信息埋没）

**风险点**：`memory_node` **获取**记忆的顺序是 profile → preferences → facts → summaries → vector messages，但最终注入 Prompt 的**渲染**顺序由 `BaseAgent._format_memory_prefix`（`app/agents/base.py`）控制，当前为 summaries → facts/profile → preferences → vector messages。如果 summaries 和 facts 占据了大量 token，关键的 profile/preferences 可能落入 U 型曲线的低谷区。

> **注意**：fetch 逻辑与 render 逻辑是解耦的，token 预算优化需要同时协调 `memory_node` 和 `BaseAgent`。

**缓解策略**：
- 按重要性排序：profile（用户身份）> preferences（偏好）> facts（事实）> summaries（摘要）> messages（历史消息）
- 或者将最重要的内容同时放在开头和结尾进行"双锚定"

### 4.2 Context Poisoning（上下文中毒）

**风险点**：Agent 子图中的工具输出通过 `sub_answers` 传递给 `synthesis_node`，中间没有事实校验层。如果某个子 Agent 产生了幻觉或工具调用错误，这个错误会被当作"事实"传递给合成节点。

**缓解策略**：
- 在 `synthesis_node` 前增加置信度过滤门（Confidence Gate）
- 对工具输出进行溯源标记（provenance），标注数据来源

### 4.3 Context Distraction（上下文分心）

**风险点**：`vector_manager.search_similar()` 按相似度返回 top-k，但没有按任务相关性进行二次过滤。一个与用户问题"语义相似"但与当前任务无关的记忆片段，会导致模型表现显著下降。

**缓解策略**：
- 在向量检索后增加相关性阈值过滤
- 引入任务感知的重排序（reranking）

### 4.4 Context Confusion（上下文混淆）

**风险点**：当 Supervisor 并行执行多个 intent 时，`synthesis_node` 会合并多个子 Agent 的响应。如果这些 intent 涉及不同的领域（如"退款"和"换货"），模型可能会混淆两个任务的约束条件。

**缓解策略**：
- 在并行执行时，为每个子 Agent 提供独立的上下文切片
- 在合成阶段明确标注每个 answer 的来源 intent

### 4.5 Context Clash（上下文冲突）

**风险点**：结构化 facts 和向量检索的 messages 之间可能存在矛盾信息（如用户地址变更）。当前系统没有去重或冲突解决机制，模型会随机选择其中一个作为答案依据。

**缓解策略**：
- 增加时间戳和可信度权重
- 在记忆注入前执行轻量级的冲突检测

### 4.6 Checkpointer State Bloat（检查点状态膨胀）

**风险点**：LangGraph 的 `checkpointer` 会在每一步都将完整的 `AgentState`（包括 `messages`、`sub_answers`、工具输出）持久化。在一个 50 轮的售后客服会话中，这会导致：
- Redis 中存储的 checkpoint 体积持续膨胀
- 每次图调用时反序列化延迟增加
- checkpointer 中保存的完整工具输出可能远超实际注入 LLM 的 masked 版本

**缓解策略**：
- 为 Redis checkpointer 设置 TTL/过期策略，或实现自定义的 checkpoint 修剪逻辑（如仅保留最近 N 个 checkpoint）
- 在 checkpoint 持久化前对 `messages` 中的长工具输出进行 masking
- 定期对旧 checkpoint 进行 compaction 或删除

---

## 5. 最佳实践与要求

### 5.1 记忆系统（Memory System）

#### 要求 M1：实施 Token 预算驱动的优先级淘汰
记忆注入必须基于 token 预算，而不是固定数量。当总 token 超过阈值时，按以下优先级淘汰：
1. 最旧的 vector messages
2. 最旧的 interaction summaries
3. 置信度最低的 facts
4. 非核心 preferences

#### 要求 M2：引入记忆新鲜度（Freshness）
`UserProfile`、`UserPreference`、`InteractionSummary`、`UserFact` 等结构化记忆模型已经具备 `updated_at` 字段。当前缺少的是**检索时的新鲜度过滤**：`StructuredMemoryManager` 的查询方法尚未支持按 `updated_at` 过滤（如 `max_age_days` 参数）。需要为记忆检索增加时间窗口过滤能力，例如只返回最近 30 天内的交互摘要或事实。

#### 要求 M3：扩展 A/B 实验到记忆策略
将 `memory_context_config` 作为 JSON 字段加入 `ExperimentVariant` 模型，支持 A/B 测试不同的：
- 记忆预算上限
- 记忆注入顺序
- 淘汰策略

### 5.2 检索与 RAG

#### 要求 R1：增加向量记忆检索的相关性阈值过滤
`PolicyAgent` 的 RAG 检索已经实现了相关性阈值（score ≥ 0.5）和 Self-RAG 评分，但 `vector_manager.search_similar()`（被 `memory_node` 调用）返回的向量记忆仍然没有任何阈值过滤。需要为向量记忆注入增加 similarity score > threshold 的门控。

#### 要求 R2：实施 Observation Masking
对超过 500 字符的工具输出进行 masking，保留：
- 引用 ID
- 关键结论摘要（1~2 句话）
- 完整数据的检索路径

#### 要求 R3：扩展 QueryRewriter 的压缩能力
当前 `QueryRewriter` 只压缩最近 3 轮对话。需要支持更广泛的 compaction：当历史对话 token 超过阈值时，将早期对话替换为结构化摘要。

### 5.3 Agent Prompt 设计

#### 要求 P1：实施 KV-Cache 优化
`BaseAgent._create_messages()` 当前只生成 `[SystemMessage, HumanMessage]`，其中 System Prompt 的稳定性是 KV-Cache 优化的关键：
1. **BaseAgent System Prompt 完全确定化**：移除 `DEFAULT_PROMPT_VARIABLES` 中的动态 lambda（如 `current_date`），将日期等动态内容移到 `HumanMessage` 中传递；避免在 System Prompt 中嵌入随机 ID、请求计数器或时间戳。
2. **保持消息结构稳定**：`_build_contextual_message()` 的拼接格式应使用确定性模板（固定分隔符、固定字段顺序），避免因空白字符变化破坏缓存。
3. **IntentClassifier 与 ComplaintAgent 的 System Prompt 稳定化**：
   - `app/intent/classifier.py` 的 `_create_messages()` 会根据查询动态挑选 top-k few-shot 示例并追加到 `SystemMessage` 中，导致每次请求的系统提示前缀都不同。由于意图分类在每一轮都会被调用，这实际上**完全破坏了前缀缓存**。修复方案：将 few-shot 示例移到 `HumanMessage` 中，或使用固定的 canonical 示例集。
   - `app/agents/complaint.py` 使用完全相同的模式（`select_top_k_examples(query, self._few_shot_examples, k=3)` 追加到 system prompt），因此 `ComplaintAgent` 的每次调用也会因 few-shot 示例不同而导致 KV-Cache 前缀失效。修复方案与 `IntentClassifier` 一致。

**关键注意**：在 LangGraph/LangChain 架构中，Tool Definitions 是通过 `bind_tools()` 绑定到 LLM 实例上的，不是作为显式消息传入 `_create_messages()` 的。因此 KV-Cache 优化的核心在于让 `SystemMessage` 的前缀高度稳定，而不是调整消息列表中的工具定义位置。

#### 要求 P2：增加 Token 数量 guardrails
在 `BaseAgent._create_messages()` 中加入 token 计数检查。当总 token 超过窗口的 80% 时，触发 compaction 或返回明确的错误信息。

### 5.4 多 Agent 编排

#### 要求 A1：Agent 切换时的上下文隔离
`supervisor_node` 在调用子 Agent 时，应该只传递与该 Agent 职责相关的状态切片：
- 只包含该 Agent 需要的工具定义
- 过滤掉其他 Agent 的 intermediate reasoning
- 保留用户原始 query 和必要的记忆上下文

#### 要求 A2：增加上下文利用率指标
在 `AgentState` 中增加 `context_tokens` 和 `context_utilization` 字段，用于：
- 驱动 compaction 决策
- 记录到可观测性系统（OpenTelemetry）
- 支持 A/B 实验的效果评估

#### 要求 A3：为 Synthesis Node 增加置信度过滤
`SynthesisNode` 在合并 `sub_answers` 之前，应该：
- 过滤掉置信度低于阈值的 answer
- 标注每个 answer 的来源 Agent
- 当多个 answer 冲突时，触发降级策略（如请求用户澄清）

---

## 6. 下一阶段目标与任务（Q2/Q3 路线图）

> **架构约束说明**：所有上下文工程的实现任务必须遵守相关 `AGENTS.md` 中的不变量，包括但不限于：
> - 根 `AGENTS.md` 和 `app/memory/AGENTS.md` 的 **Multi-Tenant Isolation**：任何涉及用户数据（orders、carts、memories）的查询必须按 `user_id` 过滤，不允许跨用户数据泄露。
> - 根 `AGENTS.md` 的 **Async-First**：所有 I/O 操作（LLM 调用、数据库查询、缓存读写）必须使用 `async`。
> - 根 `AGENTS.md` 的 **No Hardcoded Secrets**：所有阈值、预算上限必须通过 `app/core/config.py` 读取，禁止在代码中硬编码。
> - 根 `AGENTS.md` 的 **Type Safety**：禁止用 `typing.Any` 或 `# type: ignore` 抑制类型错误（第三方包兼容问题除外）。

### 6.1 Q2 阶段：基础能力建设（Token 预算、KV-Cache、压缩）

| 编号 | 任务 | 目标文件 | 建议测试 | 成功标准 |
|------|------|---------|---------|---------|
| **T1** | 实现 TokenBudget 管理器 | 新建 `app/context/token_budget.py` | `tests/context/test_token_budget.py` | 记忆上下文 token 数不超过 2048（可配置） |
| **T2** | 将 TokenBudget 集成到 memory_node | `app/graph/nodes.py` | `tests/graph/test_memory_node.py` | 动态限制替换 facts=3/summaries=2 的硬编码 |
| **T3** | 为 BaseAgent 增加 KV-Cache 优化 | `app/agents/base.py`<br>`app/agents/complaint.py`<br>`app/intent/classifier.py`<br>`app/core/llm_factory.py` | `tests/agents/test_base_agent.py` | 第一阶段：移除 System Prompt 中的动态内容（时间戳、随机 ID），确保前缀确定性；同步修复 `IntentClassifier` 和 `ComplaintAgent` 的动态 few-shot 追加问题。第二阶段：在 `llm_factory.py` 中通过 LangChain 构造器的 `model_kwargs` / `extra_headers` 注入 provider 特定的缓存参数（如 Anthropic 的 `anthropic-beta: prompt-caching-2024-07-31` 和 `cache_control` 消息字段，OpenAI 的自动缓存则记录验证结果）。如果 LangChain 封装不足以传递所需字段，则在工厂中返回原生 SDK 客户端的轻量包装 |
| **T4** | 实现上下文压缩触发器 | 新建 `app/memory/compactor.py`<br>修改 `app/memory/summarizer.py` | `tests/memory/test_compactor.py` | 利用率 > 75% 时触发压缩，而非仅消息数 > 20 |
| **T5** | 为工具输出增加 Observation Masking | `app/tools/product_tool.py`<br>`app/tools/cart_tool.py`<br>`app/tools/logistics_tool.py`<br>`app/graph/nodes.py`<br>`app/graph/subgraphs.py` | `tests/tools/test_observation_masking.py` | 超过 500 字符的输出在传入 LLM Prompt（如 `ProductAgent`）或持久化 checkpoint/`updated_state`（如 `Cart/Order Agent`）前被替换为引用+摘要 |

### 6.2 Q3 阶段：高级能力（上下文隔离、A/B 激活、评估）

| 编号 | 任务 | 目标文件 | 建议测试 | 成功标准 |
|------|------|---------|---------|---------|
| **T6** | 在 supervisor_node 中实现上下文隔离切换 | `app/agents/supervisor.py`<br>`app/graph/subgraphs.py`<br>`app/graph/workflow.py`<br>`app/graph/nodes.py` | `tests/graph/test_subgraphs.py` | 为每个子 Agent 构建过滤后的状态切片（如通过 `build_filtered_subgraph` 包装器或 per-agent 的 slim state schema），只传递相关状态键和工具定义 |
| **T7** | 扩展 A/B 框架支持上下文策略实验 | `app/models/experiment.py`<br>`app/services/experiment.py` | `tests/services/test_experiment.py` | 可 A/B 测试记忆限制和压缩策略 |
| **T8** | 增加上下文利用率遥测 | `app/models/state.py`<br>`app/observability/execution_logger.py` | `tests/observability/test_logger.py` | 每次图执行记录上下文 token 数 |
| **T9** | 实现向量记忆检索相关性门控 | `app/memory/vector_manager.py`<br>`app/graph/nodes.py` | `tests/memory/test_vector_manager.py` | 为 `memory_node` 的向量记忆注入增加 score > threshold 过滤。注意：`PolicyAgent` 的 RAG 检索已具备 Self-RAG + 0.5 阈值，本任务仅针对向量记忆路径 |

### 6.3 依赖关系图

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

### 6.4 评估框架（验证上下文工程效果）

上下文工程是经验驱动的学科，任何优化都需要通过定量评估验证。建议建立以下三类基准测试：

#### 6.4.1 Needle-in-HayStack 准确性测试
- **目的**：验证关键信息（如用户身份、安全策略）在不同记忆负载和位置下能否被正确回忆
- **方法**：构造合成会话，在大量填充文本中插入一个关键事实，检查 Agent 是否能正确回答相关问题
- **指标**：Recall@K、Answer Accuracy
- **目标阈值**：
  - 在 75% 上下文利用率下，关键事实回忆准确率 ≥ **90%**
  - 在 90% 上下文利用率下，关键事实回忆准确率 ≥ **75%**
- **测试位置**：`tests/benchmarks/test_context_needle.py`

#### 6.4.2 Token 成本回归测试
- **目的**：量化 compaction、masking 等措施对 token 消耗的降低效果
- **方法**：使用代表性的多轮客服对话（≥20 轮，含工具调用）作为基准，在执行上下文工程优化前后分别统计：
  - 每次 LLM 调用的平均输入 token 数
  - 单次完整会话的总输入 token 数
  - checkpointer 中存储的平均状态体积
- **指标**：平均输入 token 减少百分比、checkpoint 体积减少百分比
- **目标阈值**：
  - 启用 Observation Masking + Compaction 后，单次会话平均输入 token 减少 ≥ **30%**
  - checkpointer 中平均状态体积减少 ≥ **25%**
- **测试位置**：`tests/benchmarks/test_token_regression.py`

#### 6.4.3 延迟回归测试
- **目的**：验证 KV-Cache 优化和 checkpointer 压缩是否降低了端到端延迟
- **方法**：在相同对话 trace 上运行 10 次取平均
- **指标**：
  - 首 token 延迟（TTFT）
  - 图执行总耗时
  - checkpoint 反序列化耗时
- **目标阈值**：
  - 启用 KV-Cache（前缀命中）后，TTFT 降低 ≥ **20%**
  - 启用 checkpoint compaction 后，单步图调用总耗时增长控制在 **5%** 以内（避免 compaction 本身引入过多开销）
- **测试位置**：`tests/benchmarks/test_latency_regression.py`

#### 6.4.4 评估基础设施
- 建议复用现有 `tests/integration/test_workflow_invoke.py` 的集成测试模式
- 在 CI 中增加可选的 benchmark 任务（不阻塞 PR，但定期运行并记录趋势）

---

## 7. 关键阈值速查表

| 技术 | 触发条件 | 目标效果 | 注意事项 |
|------|---------|---------|---------|
| **Compaction** | 上下文利用率 > 75% | 减少 50%~70% token | 不要在利用率 > 85% 时压缩 |
| **Observation Masking** | 工具输出 > 500 字符 | 减少 60%~80% token | 调试过程中不要 mask |
| **KV-Cache** | 稳定的前缀内容 | 命中率达到 70%+ | 空白字符会破坏缓存 |
| **渐进式披露** | 任务边界 | 只加载需要的内容 | 预先加载会适得其反 |
| **Token Budget** | 每次请求 | 预留 20%~30% 输出空间 | 监控每个任务的完整成本 |

---

## 8. 参考文件与文档

### 8.1 项目内相关文件

| 文件 | 用途 | 相关 AGENTS.md |
|------|------|---------------|
| `app/graph/nodes.py` | Graph 节点定义（memory_node, supervisor_node, decider_node） | `app/graph/AGENTS.md` |
| `app/graph/parallel.py` | 并行多意图分发 | `app/graph/AGENTS.md` |
| `app/graph/subgraphs.py` | Agent 子图定义 | `app/graph/AGENTS.md` |
| `app/graph/workflow.py` | LangGraph 工作流编译与 checkpointer 配置 | `app/graph/AGENTS.md` |
| `app/agents/base.py` | BaseAgent 基类与 Prompt 渲染 | `app/agents/AGENTS.md` |
| `app/agents/supervisor.py` | SupervisorAgent 编排逻辑 | `app/agents/AGENTS.md` |
| `app/agents/complaint.py` | 投诉处理 Agent（动态 few-shot 破坏 KV-Cache） | `app/agents/AGENTS.md` |
| `app/core/llm_factory.py` | LLM 工厂（OpenAI / DashScope 多后端） | — |
| `app/tools/product_tool.py` | 商品查询工具 | `app/agents/AGENTS.md` |
| `app/tools/cart_tool.py` | 购物车操作工具 | `app/agents/AGENTS.md` |
| `app/tools/logistics_tool.py` | 物流查询工具 | `app/agents/AGENTS.md` |
| `app/intent/classifier.py` | 意图分类器（动态 few-shot 破坏 KV-Cache） | `app/intent/AGENTS.md` |
| `app/memory/structured_manager.py` | PostgreSQL 结构化记忆管理 | `app/memory/AGENTS.md` |
| `app/memory/vector_manager.py` | Qdrant 向量记忆管理 | `app/memory/AGENTS.md` |
| `app/memory/summarizer.py` | 会话摘要生成器 | `app/memory/AGENTS.md` |
| `app/memory/extractor.py` | 事实提取器 | `app/memory/AGENTS.md` |
| `app/memory/compactor.py` | 上下文压缩器（规划中） | `app/memory/AGENTS.md` |
| `app/context/token_budget.py` | Token 预算管理器（规划中） | — |
| `app/retrieval/rewriter.py` | 查询改写器 | — |
| `app/models/state.py` | AgentState 定义 | — |
| `app/models/experiment.py` | A/B 实验模型 | — |
| `app/services/experiment.py` | ExperimentService | — |
| `app/observability/execution_logger.py` | 执行日志与遥测 | — |
| `tests/benchmarks/test_context_needle.py` | Needle-in-Haystack 基准测试（规划中） | — |
| `tests/benchmarks/test_token_regression.py` | Token 成本回归测试（规划中） | — |
| `tests/benchmarks/test_latency_regression.py` | 延迟回归测试（规划中） | — |
| `architecture.md` | 系统架构图 | — |
| `README.md` | 项目概览 | — |

### 8.2 外部参考来源

- **Anthropic** — [Context Windows](https://docs.anthropic.com/en/docs/build-with-claude/context-windows)、[Prompt Caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- **Stanford/Berkeley/Samaya AI** — "Lost in the Middle: How Language Models Use Long Contexts" (2023)
- **Anthropic / General CE Literature** — Write / Select / Compress / Isolate 四策略框架（主动写入外部存储、选择性检索、上下文压缩、子 Agent 隔离）
- **vLLM** — Prefix Caching 与 KV-Cache 优化实践

---

## 9. 附录：中英文术语对照

| 中文 | 英文 |
|------|------|
| 上下文工程 | Context Engineering |
| 上下文降解 | Context Degradation |
| 信息埋没（中间遗忘） | Lost-in-the-Middle |
| 上下文中毒 | Context Poisoning |
| 上下文分心 | Context Distraction |
| 上下文混淆 | Context Confusion |
| 上下文冲突 | Context Clash |
| 观察掩码 | Observation Masking |
| 上下文压缩/压实 | Context Compaction |
| 渐进式披露 | Progressive Disclosure |
| Token 预算 | Token Budget |
| 前缀缓存 | Prefix Caching / KV-Cache |
| 上下文隔离 | Context Isolation |
| 记忆新鲜度 | Memory Freshness |
| 置信度门控 | Confidence Gate |

---

*文档版本：v1.0*  
*最后更新：2026-04-17*  
*维护责任：后端架构组*
