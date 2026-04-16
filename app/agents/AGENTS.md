# app/agents KNOWLEDGE BASE

> Guidance for the expert Agent fleet. Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules and commands.

## OVERVIEW
专家 Agent 舰队，统一基于 `BaseAgent` ABC 构建，覆盖订单、政策、商品、购物车、物流、账户、支付等域。

## Key Files

| 任务 | 文件 | 说明 |
|------|------|------|
| 基类定义 | `@app/agents/base.py` | `BaseAgent` ABC，`process()` → `AgentProcessResult` |
| 商品问答 | `@app/agents/product.py` + `@app/tools/product_tool.py` | Qdrant `product_catalog` 语义检索 |
| 购物车 | `@app/agents/cart.py` + `@app/tools/cart_tool.py` | Redis 持久化，24h TTL |
| 投诉处理 | `@app/agents/complaint.py` + `@app/tools/complaint_tool.py` | LLM 自动分类 + 工单创建 |
| 调度器 | `@app/agents/supervisor.py` | 串行/并行调度逻辑 |
| 意图路由 | `@app/agents/router.py` | `IntentRouterAgent` |
| 配置热重载 | `@app/agents/config_loader.py` | Redis 缓存路由规则与系统提示词（60s TTL） |

## Commands

```bash
# 运行本模块相关测试
uv run pytest tests/agents/
```

## Testing Patterns

- 使用 `@app/models/state.py` 中的 `make_agent_state()` 构造 Agent 状态。
- 对 LLM 和 Tool 调用进行 mock，验证 `AgentProcessResult` 的结构。
- 每个 Agent 的测试应覆盖正常流程和异常边界（如槽位缺失、权限校验失败）。
- 新增 Agent 时，必须在 `tests/agents/` 下补充对应的单元测试。

## CONVENTIONS

- **统一入口**：所有 Agent 子类必须实现 `async process(self, state) -> AgentProcessResult`。
- **热重载**：每个 Agent 在 `process()` 内调用 `await self._load_config()` 读取最新配置。
- **记忆注入优先级**：summaries → facts/profile → preferences → vector messages。
- **用户隔离**：所有涉及订单/退款/购物车的查询必须按 `user_id` 过滤。
- **返回值契约**：`AgentProcessResult` 必须包含 `response`（字符串），可选携带 `updated_state` 更新状态。

## ANTI-PATTERNS

- `@app/agents/supervisor.py` 直接导入 `@app/graph/parallel.py`，与图调度层存在跨层耦合。
- 避免在 Agent 内直接操作数据库；优先通过 Service 层或 Tool 层访问外部资源。
- 新增 Agent 后未同步更新本文件和测试目录。
