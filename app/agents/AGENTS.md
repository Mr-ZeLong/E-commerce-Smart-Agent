# app/agents KNOWLEDGE BASE

> Guidance for the expert Agent fleet. Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules and commands.

## OVERVIEW
专家 Agent 舰队，统一基于 `BaseAgent` ABC 构建，覆盖订单、政策、商品、购物车、物流、账户、支付等域。

## WHERE TO LOOK
| 任务 | 文件 | 说明 |
|------|------|------|
| 基类定义 | `base.py` | `BaseAgent` ABC，`process()` → `AgentProcessResult` |
| 商品问答 | `product.py` + `../tools/product_tool.py` | Qdrant `product_catalog` 语义检索 |
| 购物车 | `cart.py` + `../tools/cart_tool.py` | Redis 持久化，24h TTL |
| 投诉处理 | `complaint.py` + `../tools/complaint_tool.py` | LLM 自动分类 + 工单创建 |
| 调度器 | `supervisor.py` | 串行/并行调度逻辑 |
| 意图路由 | `router.py` | `IntentRouterAgent` |
| 配置热重载 | `config_loader.py` | Redis 缓存路由规则与系统提示词（60s TTL） |

## CONVENTIONS
- **统一入口**：所有 Agent 子类必须实现 `async process(self, state) -> AgentProcessResult`。
- **热重载**：每个 Agent 在 `process()` 内调用 `await self._load_config()` 读取最新配置。
- **记忆注入优先级**：summaries → facts/profile → preferences → vector messages。
- **用户隔离**：所有涉及订单/退款/购物车的查询必须按 `user_id` 过滤。

## ANTI-PATTERNS
- `supervisor.py` 直接导入 `app.graph.parallel.plan_dispatch`，与图调度层存在双向耦合。
- 避免在 Agent 内直接操作数据库；优先通过 Service 层或 Tool 层访问外部资源。
