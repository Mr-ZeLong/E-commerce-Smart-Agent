# LLM Agent Prompt 设计模式

## ReAct（Reasoning + Acting）

**核心模式**：模型在每一步输出 `Thought`（思考）→ `Action`（动作/工具调用）→ `Observation`（观察结果），循环直至完成任务[^6]。

**Prompt 设计要点**：
- 提供清晰的 ReAct 格式示例
- 限定可选的 Action 列表
- 要求 Thought 必须放在 Action 之前
- 设置最大迭代次数，防止无限循环

**典型模板**：
```markdown
你可以使用以下工具：[工具列表]

请按以下格式思考并行动：
Thought: 我需要...
Action: [工具名]
Action Input: [参数]
Observation: [工具返回结果]
...（重复直到有最终答案）
Final Answer: [最终回答]
```

## Tool Use（工具使用）

**设计模式**：
- **工具注册**：在 System Prompt 或 API 中注册所有可用工具及其 Schema
- **意图识别**：先让模型判断是否需要调用工具，还是直接回答
- **结果注入**：将工具返回结果以 Observation 形式重新输入 Prompt
- **错误反馈**：工具失败时，将错误信息返回给模型，允许其重试或调整策略

## Memory Injection（记忆注入）

**设计模式**：
- **短期记忆**：将最近 N 轮对话历史直接拼入 Prompt
- **长期记忆**：通过向量检索（RAG）从外部记忆库中召回相关信息
- **记忆摘要**：当对话过长时，对历史进行摘要压缩后再注入
- **记忆标注**：区分用户画像、历史摘要、原子事实、向量记忆等不同类型

**本项目实践建议**：

| 类型 | 来源 | 注入位置 | 有效期 |
|------|------|----------|--------|
| 用户画像 | `user_profiles` | System Prompt / Memory Prefix | 长期 |
| 历史摘要 | `interaction_summaries` | Memory Prefix | 长期 |
| 原子事实 | `user_facts` | Memory Prefix | 长期 |
| 向量记忆 | `conversation_memory` | Memory Prefix | 跨会话 |
| 当前会话历史 | `state.history` | `MessagesPlaceholder` | 单会话 |

**避免记忆污染**：
- 记忆信息应以**第三方视角**描述，避免让模型误以为是用户当前输入
- 使用明确的标记隔离记忆与当前问题：

```markdown
[以下是你了解到的关于该用户的背景信息]
{memory_context}
[/背景信息]

[用户当前问题]
{question}
[/用户当前问题]
```
