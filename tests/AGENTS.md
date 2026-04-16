# tests KNOWLEDGE BASE

> Guidance for the backend test suite. Read the root [`AGENTS.md`](../AGENTS.md) first for repo-wide rules and commands.

## OVERVIEW
后端测试套件，采用扁平化目录结构（不严格镜像 `app/`），基于 pytest + pytest-asyncio。

## Key Files

| 任务 | 文件/目录 | 说明 |
|------|-----------|------|
| 全局 fixtures | `@tests/conftest.py` | `client`、`db_session`、`redis_client` |
| 测试库配置 | `@tests/_db_config.py` | 自动在 DB 名前加 `test_` 前缀 |
| Agent Mock | `@tests/_agents.py` | Agent mock 工厂和测试辅助函数 |
| LLM Mock | `@tests/_llm.py` | LLM 调用 mock 与响应辅助 |
| API 测试 | `@tests/test_auth_api.py`、`@tests/test_chat_api.py`、`@tests/test_admin_api.py` 等 | 路由层验证 |
| Service 测试 | `@tests/test_order_service.py`、`@tests/test_refund_service.py` 等 | 业务逻辑验证 |
| 模块单元测试 | `@tests/agents/`、`@tests/graph/`、`@tests/intent/`、`@tests/tools/`、`@tests/retrieval/` | Agent/图/意图/RAG 测试 |
| 集成测试 | `@tests/integration/test_workflow_invoke.py` | LangGraph 集成（含并行多意图场景） |

## Commands

```bash
# 全部后端测试
uv run pytest

# 带覆盖率检查
uv run pytest --cov=app --cov-fail-under=75

# 按模块运行
uv run pytest tests/agents/
uv run pytest tests/graph/
uv run pytest tests/intent/
uv run pytest tests/memory/
uv run pytest tests/evaluation/

# 前端单元测试
cd frontend && npm run test

# 前端 E2E 测试
cd frontend && npm run test:e2e
```

## Testing Patterns

- **状态工厂**：使用 `@app/models/state.py` 中的 `make_agent_state()` 构造 Agent 状态，避免在各测试中重复拼接地组装状态对象。
- **异步测试**：每个 async 测试必须加 `@pytest.mark.asyncio`。
- **Session-scoped DB**：`db_setup` fixture 负责建表/删表；`@tests/_db_config.py` 自动处理 test DB 命名。
- **LLM Mock**：优先使用 `@tests/_llm.py` 提供的辅助函数构造 mock 响应，避免在测试中硬编码大量 JSON。
- **Bug-fix TDD**：修复 bug 时，先写失败的复现测试，确认失败后再修复。
- **外部服务隔离**：单元测试中禁止调用真实 LLM、数据库、Redis、Qdrant；集成测试可在受控环境下访问 test DB。
- **覆盖率门限**：CI 要求 `--cov=app --cov-fail-under=75`。本地运行也应保持该门限，发现未覆盖代码应补充测试而非调低阈值。

## CONVENTIONS

- **扁平结构**：测试目录不强制一一对应 `app/` 子包路径。
- **测试命名**：使用 `test_<module>_<scenario>_<expected_outcome>` 描述性命名。
- **fixtures 复用**：优先使用 `@tests/conftest.py` 中的 session-scoped fixtures，避免重复初始化数据库连接。

## Related Files

- `@frontend/` — 前端测试独立运行（Vitest + Playwright），不纳入后端 pytest 覆盖率统计。

## ANTI-PATTERNS

- `@tests/intent/test_safety.py`（538 行）测试方法过多，建议按 concern 拆分。
- `@tests/intent/test_service.py`（483 行）包含大量重复 mock state 块，应提取到 fixtures 中。
- 不要在测试中使用 `time.sleep` 等待异步结果；优先使用 `asyncio.wait_for` 或正确 mocking。
- 不要在本地跳过覆盖率检查；发现未覆盖代码应补充测试而非调低阈值。
