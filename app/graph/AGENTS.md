# app/graph KNOWLEDGE BASE

> Guidance for LangGraph workflow and node orchestration. Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules and commands.

## OVERVIEW
LangGraph 工作流编译器与运行时节点层，负责 Agent Subgraph 编排与多意图并行调度。

## WHERE TO LOOK
| 任务 | 文件 | 说明 |
|------|------|------|
| 编译整个图 | `workflow.py` | Supervisor 模式与兼容模式双路径编译 |
| 节点定义 | `nodes.py` | router / memory / supervisor / synthesis / evaluator / decider |
| Agent Subgraph 标准 | `subgraphs.py` | 将 `BaseAgent` 封装为独立 `StateGraph` |
| 并行调度 | `parallel.py` | 多意图独立判断与 `Send` 批量分发 |

## CONVENTIONS
- **双模式编译**：当 `supervisor_agent=None` 时回退到旧路径（`router_node` 直接路由到具体 Agent）。
- **节点返回值**：统一返回 `Command(goto=..., update=...)`。
- **Subgraph 标准**：每个专家 Agent 被包装为独立 `StateGraph`，消费 `AgentState` 子集，产出 `{"sub_answers": [...]}`，通过 `operator.add` 合并。
- **并行判定**：`parallel.py` 调用 `app.intent.multi_intent.are_independent()` 决定是否并行执行。

## ANTI-PATTERNS
- `nodes.py` 长达 522 行，包含 7 个样板化节点构建器，`decider_node` 耦合过多职责。
- `memory_node` 内存在大量重复 try/except 块。
- `graph/parallel.py` 与 `intent/multi_intent.py` 存在跨层直接导入耦合。
