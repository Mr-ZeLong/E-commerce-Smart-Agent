# 核心概念

## U 型注意力曲线（Lost-in-the-Middle）

LLM 对上下文中不同位置的信息回忆能力呈 **U 型分布**：

- **开头和结尾**：回忆准确率 **85%~95%**
- **中间位置**：回忆准确率下降至 **76%~82%**

这意味着：如果我们把最关键的系统指令、安全约束或商品政策放在上下文的中间位置，模型很可能会"忽略"它们。

> **对本项目的启示**：`memory_node` 注入的记忆内容（profile、facts、preferences、messages）必须考虑位置优先级，而不是简单拼接。

## Token 经济学

| 架构模式 | Token 倍数（相对单 Agent 对话） |
|---------|-------------------------------|
| 单 Agent 纯对话 | 1x |
| 单 Agent + 工具调用 | ~4x |
| Multi-Agent 编排系统 | ~15x |

这背后的主要原因是：
- 根据项目内部 `.opencode/skills/context-fundamentals/SKILL.md`，工具输出在 Agent 轨迹中可占据 **83.9%** 的 token
- 多 Agent 之间的上下文传递会反复复制公共前缀
- 没有进行上下文隔离时，每个子 Agent 都会接收到完整的历史记录

## 上下文预算（Context Budget）

上下文预算是 Context Engineering 的核心约束。我们建议将上下文窗口划分为以下组成部分：

| 组件 | 建议预算占比 | 说明 |
|------|-------------|------|
| System Prompt | 5%~10% | 最稳定的前缀内容 |
| Tool Definitions | 15%~25% | 工具描述和参数 Schema |
| Few-shot Examples | 5%~10% | 可复用的示例模板 |
| Retrieved Memories | 20%~30% | 从数据库/向量库检索的记忆 |
| Conversation History | 剩余部分 | 多轮对话历史 |
| Output Buffer | 预留 20%~30% | 确保输入不会挤占输出空间 |
