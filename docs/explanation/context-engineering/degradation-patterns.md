# Context Degradation 模式与项目风险

## Lost-in-the-Middle（信息埋没）

**风险点**：`memory_node` **获取**记忆的顺序是 profile → preferences → facts → summaries → vector messages，但最终注入 Prompt 的**渲染**顺序由 `BaseAgent._format_memory_prefix` 控制，当前为 summaries → facts/profile → preferences → vector messages。如果 summaries 和 facts 占据了大量 token，关键的 profile/preferences 可能落入 U 型曲线的低谷区。

> **注意**：fetch 逻辑与 render 逻辑是解耦的，token 预算优化需要同时协调 `memory_node` 和 `BaseAgent`。

**缓解策略**：
- 按重要性排序：profile（用户身份）> preferences（偏好）> facts（事实）> summaries（摘要）> messages（历史消息）
- 或者将最重要的内容同时放在开头和结尾进行"双锚定"

## Context Poisoning（上下文中毒）

**风险点**：Agent 子图中的工具输出通过 `sub_answers` 传递给 `synthesis_node`，中间没有事实校验层。如果某个子 Agent 产生了幻觉或工具调用错误，这个错误会被当作"事实"传递给合成节点。

**缓解策略**：
- 在 `synthesis_node` 前增加置信度过滤门（Confidence Gate）
- 对工具输出进行溯源标记（provenance），标注数据来源

## Context Distraction（上下文分心）

**风险点**：`vector_manager.search_similar()` 按相似度返回 top-k，但没有按任务相关性进行二次过滤。一个与用户问题"语义相似"但与当前任务无关的记忆片段，会导致模型表现显著下降。

**缓解策略**：
- 在向量检索后增加相关性阈值过滤
- 引入任务感知的重排序（reranking）

## Context Confusion（上下文混淆）

**风险点**：当 Supervisor 并行执行多个 intent 时，`synthesis_node` 会合并多个子 Agent 的响应。如果这些 intent 涉及不同的领域（如"退款"和"换货"），模型可能会混淆两个任务的约束条件。

**缓解策略**：
- 在并行执行时，为每个子 Agent 提供独立的上下文切片
- 在合成阶段明确标注每个 answer 的来源 intent

## Context Clash（上下文冲突）

**风险点**：结构化 facts 和向量检索的 messages 之间可能存在矛盾信息（如用户地址变更）。当前系统没有去重或冲突解决机制，模型会随机选择其中一个作为答案依据。

**缓解策略**：
- 增加时间戳和可信度权重
- 在记忆注入前执行轻量级的冲突检测

## Checkpointer State Bloat（检查点状态膨胀）

**风险点**：LangGraph 的 `checkpointer` 会在每一步都将完整的 `AgentState`（包括 `messages`、`sub_answers`、工具输出）持久化。在一个 50 轮的售后客服会话中，这会导致：
- Redis 中存储的 checkpoint 体积持续膨胀
- 每次图调用时反序列化延迟增加
- checkpointer 中保存的完整工具输出可能远超实际注入 LLM 的 masked 版本

**缓解策略**：
- 为 Redis checkpointer 设置 TTL/过期策略，或实现自定义的 checkpoint 修剪逻辑
- 在 checkpoint 持久化前对 `messages` 中的长工具输出进行 masking
- 定期对旧 checkpoint 进行 compaction 或删除
