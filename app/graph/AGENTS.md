# app/graph KNOWLEDGE BASE

> Guidance for LangGraph workflow and node orchestration. Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules and commands.

## OVERVIEW
LangGraph 工作流编译器与运行时节点层，负责 Agent Subgraph 编排与多意图并行调度。

## Key Files

| 任务 | 文件 | 说明 |
|------|------|------|
| 编译整个图 | `@app/graph/workflow.py` | Supervisor 模式与兼容模式双路径编译 |
| 节点定义 | `@app/graph/nodes.py` | router / memory / supervisor / synthesis / evaluator / decider |
| Agent Subgraph 标准 | `@app/graph/subgraphs.py` | 将 `BaseAgent` 封装为独立 `StateGraph` |
| 并行调度 | `@app/graph/parallel.py` | 多意图独立判断与 `Send` 批量分发 |

## Commands

```bash
# 运行图相关单元测试与集成测试
uv run pytest tests/graph/ tests/integration/
```

## Testing Patterns

- 节点单元测试应对 `LLM` 进行 mock，验证返回值符合 `Command(goto=..., update=...)` 结构。
- 使用 `@tests/graph/test_workflow.py` 验证工作流编译结果和状态转换。
- 集成测试在 `@tests/integration/test_workflow_invoke.py` 中覆盖端到端多意图场景。
- 测试并行调度时，构造包含多个意图的 `AgentState` 并断言 `Send` 列表长度与目标节点。

## Related Files

- `@app/intent/multi_intent.py` — `are_independent()` 控制 LangGraph 并行调度决策。

## CONVENTIONS

- **双模式编译**：当 `supervisor_agent=None` 时回退到旧路径（`router_node` 直接路由到具体 Agent）。
- **节点返回值**：统一返回 `Command(goto=..., update=...)`。
- **Subgraph 标准**：每个专家 Agent 被包装为独立 `StateGraph`，消费 `AgentState` 子集，产出 `{"sub_answers": [...]}`，通过 `operator.add` 合并。
- **并行判定**：`@app/graph/parallel.py` 调用 `@app/intent/multi_intent.py` 中的 `are_independent()` 决定是否并行执行。
- **节点纯性**：节点构建器内部应避免副作用；状态修改通过 `update` 字典显式返回。

## ANTI-PATTERNS

- `@app/graph/nodes.py` 长达 568 行，包含 14 个节点构建器（其中 8 个 Agent 相关为样板代码），`decider_node` 耦合过多职责。
- `memory_node` 内存在大量重复 try/except 块。
- `@app/graph/parallel.py` 与 `@app/intent/multi_intent.py` 存在跨层直接导入耦合。
- 节点文件应按职责拆分，避免单个文件超过 400 行。
