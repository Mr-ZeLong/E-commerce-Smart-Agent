# tests KNOWLEDGE BASE

> Guidance for the backend test suite. Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules and commands.

## OVERVIEW
后端测试套件，采用扁平化目录结构（不严格镜像 `app/`），基于 pytest + pytest-asyncio。

## WHERE TO LOOK
| 任务 | 文件/目录 | 说明 |
|------|-----------|------|
| 全局 fixtures | `conftest.py` | `client`、`db_session`、`mock_redis`、`make_agent_state` |
| 测试库配置 | `_db_config.py` | 自动在 DB 名前加 `test_` 前缀 |
| API 测试 | `test_auth_api.py`、`test_chat_api.py`、`test_admin_api.py` 等 | 路由层验证 |
| Service 测试 | `test_order_service.py`、`test_refund_service.py` 等 | 业务逻辑验证 |
| 模块单元测试 | `agents/`、`graph/`、`intent/`、`tools/`、`retrieval/` | Agent/图/意图/RAG 测试 |
| 集成测试 | `integration/test_workflow_invoke.py` | LangGraph 集成（含并行多意图场景） |

## CONVENTIONS
- **扁平结构**：测试目录不强制一一对应 `app/` 子包路径。
- **Session-scoped DB**：`db_setup` fixture 负责建表/删表；`_db_config.py` 自动处理 test DB 命名。
- **异步测试**：每个 async 测试必须加 `@pytest.mark.asyncio`。
- **状态工厂**：`make_agent_state()` 在多个测试模块中被复用。
- **覆盖率门限**：CI 要求 `--cov=app --cov-fail-under=75`。
- **Bug-fix TDD**：修复 bug 时，先写失败的复现测试，确认失败后再修复。

## ANTI-PATTERNS
- `tests/intent/test_safety.py`（650 行）测试方法过多，建议按 concern 拆分。
- `tests/intent/test_service.py`（601 行）包含大量重复 mock state 块，应提取到 fixtures 中。
- 不要在测试中使用 `time.sleep` 等待异步结果；优先使用 `asyncio.wait_for` 或正确 mocking。
