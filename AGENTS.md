# AGENTS.md

> 本文件面向 AI Coding Agent。如果你正在使用 Claude Code、Kimi CLI、Cursor 或其他智能编程助手，请先阅读本文档。它总结了项目结构、技术栈、构建命令、代码规范和测试策略。

---

## 项目概览

**E-commerce Smart Agent v4.0** 是一个全栈·沉浸式人机协作智能客服系统。核心能力包括：

- 基于 LLM（通义千问/Qwen）的智能问答（订单查询、政策咨询）
- LangGraph 显式节点编排的退货申请工作流
- 智能风控与人工审核（按金额分级：¥500 / ¥2000 阈值）
- WebSocket 实时状态同步（用户端 + 管理员端）
- Celery 异步任务（退款支付、短信通知、管理员通知）
- 基于 Qdrant 的混合 RAG 检索（Dense + BM25 Sparse + Rerank）

项目采用前后端分离架构：
- **后端**：FastAPI + SQLModel + LangChain/LangGraph + Celery
- **前端**：React 19 + TypeScript + Vite + Tailwind CSS + shadcn/ui
- **数据层**：PostgreSQL（结构化数据）+ Qdrant（向量检索）+ Redis（缓存/会话/Celery Broker）

---

## 技术栈与关键配置

### 后端

| 组件 | 版本/说明 | 配置文件 |
|------|----------|----------|
| Python | >=3.12, <3.14 | `pyproject.toml` |
| 包管理器 | `uv` (0.6.5+) | `pyproject.toml`, `uv.lock` |
| Web 框架 | FastAPI 0.115+ | `app/main.py` |
| Agent 框架 | LangChain + LangGraph 1.0+ | `app/graph/` |
| ORM | SQLModel (基于 Pydantic v2 + SQLAlchemy 2.0 async) | `app/models/` |
| 数据库驱动 | asyncpg + psycopg2-binary | `pyproject.toml` |
| 迁移 | Alembic | `alembic.ini`, `migrations/` |
| 缓存/消息 | Redis 7 | `app/core/redis.py` |
| 任务队列 | Celery 5.6+ | `app/celery_app.py`, `celery_worker.py` |
| 认证 | JWT (PyJWT) + bcrypt | `app/core/security.py` |
| 限流 | slowapi | `app/core/limiter.py` |
| 日志 | Python `logging` + Correlation ID | `app/core/logging.py` |

### 前端

| 组件 | 版本/说明 | 配置文件 |
|------|----------|----------|
| 框架 | React 19 + TypeScript 6.0 | `frontend/package.json` |
| 构建工具 | Vite 8 | `frontend/vite.config.ts` |
| 样式 | Tailwind CSS 3.4 + shadcn/ui | `frontend/tailwind.config.ts` |
| 状态管理 | Zustand 5 + TanStack Query 5 | `frontend/package.json` |
| 路由 | React Router v7 | `frontend/src/apps/...` |
| E2E 测试 | Playwright | `frontend/e2e/` |

### 基础设施（Docker Compose）

- `db`: PostgreSQL 16
- `redis`: Redis 7-alpine (带密码)
- `qdrant`: Qdrant v1.16.3
- `app`: FastAPI 服务（端口 8000）
- `celery_worker`: Celery Worker

---

## 项目目录结构

```text
├── app/                            # 后端主应用
│   ├── main.py                     # FastAPI 入口， lifespan 中编译 LangGraph
│   ├── celery_app.py               # Celery 配置
│   ├── api/v1/                     # API 路由层
│   │   ├── auth.py                 # JWT 登录
│   │   ├── chat.py                 # 聊天接口（SSE 流式）
│   │   ├── chat_utils.py           # SSE 流式响应工具
│   │   ├── admin.py                # 管理员 API（审核、任务队列）
│   │   ├── status.py               # 状态查询
│   │   ├── websocket.py            # WebSocket 端点
│   │   └── schemas.py              # Pydantic 请求/响应模型
│   ├── core/                       # 核心基础设施
│   │   ├── config.py               # Pydantic Settings（.env 映射）
│   │   ├── database.py             # AsyncEngine + AsyncSessionLocal
│   │   ├── redis.py                # 统一 Redis 客户端
│   │   ├── security.py             # JWT 生成/验证
│   │   ├── limiter.py              # 限流器
│   │   ├── logging.py              # CorrelationIdFilter
│   │   ├── llm_factory.py          # LLM 工厂（OpenAI 适配器）
│   │   └── utils.py                # utc_now 等工具函数
│   ├── models/                     # SQLModel 数据模型
│   │   ├── user.py                 # 用户模型
│   │   ├── order.py                # 订单模型
│   │   ├── refund.py               # 退款模型
│   │   ├── audit.py                # 审核日志模型
│   │   ├── knowledge.py            # 知识库模型
│   │   ├── message.py              # 消息模型
│   │   └── state.py                # AgentState TypedDict
│   ├── graph/                      # LangGraph 工作流
│   │   ├── workflow.py             # 编译 StateGraph
│   │   ├── nodes.py                # router_node / policy_agent / order_agent / evaluator_node / decider_node
│   │   └── tools.py                # 工具函数（订单查询、退款创建等）
│   ├── confidence/                 # 置信度信号模块
│   │   └── signals.py              # 置信度评估信号计算
│   ├── utils/                      # 通用工具函数
│   │   └── order_utils.py          # 订单相关工具
│   ├── agents/                     # Agent 实现层
│   │   ├── base.py                 # Agent 基类与 AgentResult
│   │   ├── router.py               # IntentRouterAgent
│   │   ├── order.py                # OrderAgent
│   │   ├── policy.py               # PolicyAgent
│   │   └── evaluator.py            # ConfidenceEvaluator（置信度信号）
│   ├── intent/                     # 意图识别模块
│   │   ├── service.py              # IntentRecognitionService（Redis 会话）
│   │   ├── models.py               # 意图/槽位/澄清状态模型
│   │   ├── config.py               # 意图识别配置
│   │   ├── classifier.py           # 意图分类器
│   │   ├── clarification.py        # 澄清引擎
│   │   ├── slot_validator.py       # 槽位验证器
│   │   ├── topic_switch.py         # 话题切换检测
│   │   ├── multi_intent.py         # 多意图处理器
│   │   └── safety.py               # 安全过滤器
│   ├── retrieval/                  # RAG 检索层
│   │   ├── client.py               # 检索客户端
│   │   ├── embeddings.py           # 向量嵌入
│   │   ├── retriever.py            # 检索器
│   │   ├── reranker.py             # 精排器
│   │   ├── rewriter.py             # 查询重写器
│   │   └── sparse_embedder.py      # 稀疏嵌入
│   ├── services/                   # 业务服务层
│   │   ├── refund_service.py       # 退货业务逻辑
│   │   ├── refund_tool_service.py  # 退款工具服务
│   │   ├── status_service.py       # 状态服务
│   │   ├── order_service.py        # 订单服务
│   │   ├── admin_service.py        # 管理员服务
│   │   └── auth_service.py         # 认证服务
│   ├── tasks/                      # Celery 异步任务
│   │   └── refund_tasks.py         # 退款相关任务
│   ├── websocket/                  # WebSocket 连接管理
│   │   └── manager.py              # ConnectionManager（广播/单发）
│   └── schemas/                    # 共享 Schema
│       ├── admin.py, status.py
│
├── frontend/                       # React 前端
│   ├── index.html                  # C端入口
│   ├── admin.html                  # B端入口
│   ├── vite.config.ts              # 多页面 Rollup 配置
│   └── src/
│       ├── apps/customer/          # C端用户聊天应用
│       ├── apps/admin/             # B端管理员后台
│       ├── components/ui/          # shadcn/ui 组件
│       ├── lib/                    # API 客户端、工具函数
│       ├── stores/                 # Zustand Store
│       ├── hooks/                  # 自定义 Hooks
│       └── types/                  # TypeScript 类型
│
├── tests/                          # 后端测试
│   ├── conftest.py                 # pytest 全局 fixtures
│   ├── _db_config.py               # 测试数据库配置
│   ├── test_*.py                   # API/Service 测试
│   ├── agents/                     # Agent 单元测试
│   ├── graph/                      # LangGraph 测试
│   ├── intent/                     # 意图模块测试
│   ├── retrieval/                  # RAG 检索测试
│   └── integration/                # 集成测试
│
├── scripts/                        # 辅助脚本
│   ├── seed_data.py                # 数据库初始化数据
│   ├── seed_large_data.py          # 大批量测试数据
│   ├── etl_qdrant.py               # 知识库 ETL（PDF/Markdown → Qdrant）
│   └── verify_db.py                # 数据库验证
│
├── migrations/                     # Alembic 迁移脚本
├── data/                           # 静态数据（示例政策文档）
├── docker-compose.yaml             # 本地/容器编排
├── Dockerfile                      # 基于 python:3.13-slim + uv
├── start.sh                        # 本地一键启动脚本
├── start_worker.sh                 # 单独启动 Celery Worker
└── pyproject.toml                  # Python 项目配置
```

---

## 环境变量

项目通过 `.env` 文件加载配置（由 `app/core/config.py` 解析）。复制 `.env.example` 为 `.env` 并填写真实值。

关键变量：

```bash
# 数据库
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=...
POSTGRES_DB=knowledge_base

# Redis（必填，本地 docker-compose 默认密码 devpassword）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=devpassword

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=...

# LLM（通义千问）
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
DASHSCOPE_API_KEY=...

# 安全
SECRET_KEY=...                    # 建议: openssl rand -hex 32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# 其他
ENABLE_OPENAPI_DOCS=True          # 生产环境设为 False
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

**注意**：`app/core/config.py` 中的 `Settings` 使用 `SettingsConfigDict(env_file=".env")`，支持嵌套配置（分隔符 `__`），例如 `CONFIDENCE__THRESHOLD=0.7`。

---

## 构建与运行命令

### 1. 完整本地启动（推荐首次使用）

```bash
# 启动基础设施 + 迁移 + FastAPI + Celery + 构建前端
./start.sh
```

访问地址：
- API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- C端用户界面: http://localhost:8000/app
- B端管理后台: http://localhost:8000/admin

### 2. Docker Compose 启动

```bash
# 仅启动基础设施（开发调试）
docker compose up -d db redis qdrant

# 启动全部服务（包含 app + celery_worker）
docker compose up -d
```

### 3. 手动分步启动

```bash
# 安装依赖
uv sync

# 数据库迁移
uv run alembic upgrade head

# 启动 FastAPI
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 启动 Celery Worker（另开终端）
uv run celery -A app.celery_app worker --loglevel=info --concurrency=4 --pool=solo
# Linux/Mac 可用 prefork 替代 solo
```

### 4. 前端开发模式

```bash
cd frontend
npm install
npm run dev        # 端口 5173，代理 /api → localhost:8000
```

### 5. 数据初始化

```bash
# 初始化基础数据（用户、订单等）
uv run python scripts/seed_data.py

# 大批量测试数据
uv run python scripts/seed_large_data.py

# 知识库 ETL（PDF/Markdown → Qdrant）
uv run python scripts/etl_qdrant.py
```

---

## 测试策略与命令

### 后端测试

使用 **pytest + pytest-asyncio + pytest-cov**。测试配置文件位于 `pyproject.toml`：

```toml
[tool.pytest.ini_options]
asyncio_default_test_loop_scope = "session"
testpaths = ["tests"]
```

运行命令：

```bash
# 运行全部测试
uv run pytest

# 带覆盖率（CI 要求 >=75%）
uv run pytest --cov=app --cov-fail-under=75

# 运行特定模块
uv run pytest tests/graph/
uv run pytest tests/intent/
uv run pytest tests/integration/
```

测试结构说明：
- `tests/conftest.py`：提供全局 fixtures（如 `client`、`db_session`、`mock_redis`）
- `tests/_db_config.py`：测试数据库连接与配置覆盖
- API 层测试：`test_auth_api.py`、`test_chat_api.py`、`test_admin_api.py`、`test_websocket.py`、`test_auth_rate_limit.py`
- Service 层测试：`test_order_service.py`、`test_refund_service.py`、`test_admin_service.py`、`test_auth_service.py`、`test_status_service.py`、`test_refund_tool_service.py`
- 工具/安全测试：`test_security.py`、`test_main_security.py`、`test_logging.py`、`test_chat_utils.py`、`test_refund_tasks.py`、`test_users.py`、`test_confidence_signals.py`
- 模块单元测试：`tests/agents/`、`tests/graph/`、`tests/intent/`、`tests/retrieval/`
- 集成测试：`tests/integration/test_workflow_invoke.py` — LangGraph 工作流集成测试

### 前端测试

```bash
cd frontend
npm run test:e2e      # Playwright 命令行模式
npm run test:e2e:ui   # Playwright UI 模式
```

E2E 测试文件：`frontend/e2e/customer-chat.spec.ts`、`frontend/e2e/admin-dashboard.spec.ts`

---

## 代码风格与规范

### Python

项目使用 **Ruff** 作为 linter 和 formatter，**ty** 作为类型检查器。

配置见 `pyproject.toml`：

```toml
[tool.ruff]
target-version = "py312"
line-length = 100
exclude = ["migrations/", "scripts/", "celery_worker.py"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
ignore = ["E501", "N802", "UP042", "B904", "E722", "SIM108", "SIM116", "B008"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

常用命令：

```bash
# 检查并自动修复
uv run ruff check app tests --fix

# 格式化
uv run ruff format app tests

# 类型检查
uv run ty check --error-on-warning
```

Pre-commit 已配置（`.pre-commit-config.yaml`）：
- `ruff`（check --fix + format）
- `ty check --error-on-warning`

### TypeScript / 前端

```bash
cd frontend
npm run lint
npm run lint:fix
npm run format
npm run format:check
```

---

## 关键开发约定

### 1. 异步优先

后端全部使用 **async/await**：
- 数据库：`AsyncSession` + `asyncpg`
- LLM 调用：`await llm.ainvoke(...)`
- FastAPI 路由：默认 async
- Celery 任务：使用 `async_to_sync` 包装异步代码

### 2. 数据库模型

所有模型继承自 `SQLModel`，同时使用 `table=True` 创建表。示例模式：

```python
from sqlmodel import Field, SQLModel
from datetime import datetime

class User(SQLModel, table=True):
    __tablename__ = "users"
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)
```

新增模型后需要：
1. 在 `app/models/__init__.py` 中导出
2. 运行 `uv run alembic revision --autogenerate -m "msg"`
3. 运行 `uv run alembic upgrade head`

### 3. API 路由组织

- 所有路由以 `/api/v1` 为前缀（由 `settings.API_V1_STR` 控制）
- 路由文件位于 `app/api/v1/`
- Pydantic Schema 尽量放在 `app/api/v1/schemas.py` 或 `app/schemas/`

### 4. LangGraph 工作流

- `app/graph/workflow.py`：编译图，赋值给 `workflow_module.app_graph`
- `app/main.py` 的 `lifespan` 在启动时调用 `compile_app_graph()`
- 节点定义在 `app/graph/nodes.py`
- 状态定义在 `app/models/state.py`
- 工具函数在 `app/graph/tools.py`

工作流节点顺序：
`router_node` → (`policy_agent` | `order_agent`) → `evaluator_node` → `decider_node` → `END`

### 5. 日志规范

统一使用 `logging.getLogger(__name__)`，日志格式包含 `correlation_id`：

```python
logger = logging.getLogger(__name__)
logger.info("示例日志")
```

### 6. 配置管理

所有环境相关配置集中放在 `app/core/config.py` 的 `Settings` 类中。不要在代码中直接读取 `os.environ`，应通过 `from app.core.config import settings` 使用。

### 7. Redis 使用

通过 `app/core/redis.py` 获取统一客户端：`get_redis_client()`。Redis 用于：
- 意图识别会话缓存
- LangGraph Checkpoint（`langgraph-checkpoint-redis`）
- Celery Broker & Backend
- WebSocket 状态广播辅助

### 8. 静态文件

FastAPI 托管 `frontend/dist` 中的构建产物：
- `/app/*` → C端 SPA
- `/admin/*` → B端 SPA
- `/` → 重定向到 `/app`

前端构建输出根目录为 `frontend/dist/`，其中包含 `customer/` 和 `admin/` 两个子目录，分别对应 C 端和 B 端 SPA，由 `vite.config.ts` 的 `rollupOptions.input` 控制。

---

## 安全注意事项

1. **CORS 安全**：`app/main.py` 在启动时会检查 `CORS_ORIGINS` 是否包含 `"*"`，若与 `allow_credentials=True` 同时存在会直接抛出 `RuntimeError`。
2. **JWT 密钥**：生产环境必须修改 `SECRET_KEY`，建议使用 `openssl rand -hex 32` 生成。
3. **OpenAPI 文档**：生产环境应设置 `ENABLE_OPENAPI_DOCS=False`，避免暴露接口文档。
4. **Rate Limiting**：已集成 `slowapi`，部分敏感接口（如登录）已配置限流。
5. **多租户隔离**：所有订单/退款查询必须根据当前登录用户的 `user_id` 过滤，防止横向越权。
6. **密码存储**：用户密码使用 `bcrypt` 哈希，不存储明文。
7. **依赖安全**：`pyproject.toml` 中固定了 `typer<0.16.0` 和 `click-plugins==1.1.1`，防止恶意包注入。

---

## CI / CD

GitHub Actions 工作流位于 `.github/workflows/ci.yml`：

- 触发条件：`push` / `pull_request` 到 `main` 分支
- 服务：PostgreSQL 16、Redis 7、Qdrant v1.16.3
- 步骤：
  1. 检出代码
  2. 设置 Python 3.12 + uv 0.6.5
  3. 创建 test database
  4. Cache uv dependencies (`actions/cache@v4`)
  5. `uv sync` 安装依赖
  6. `uv run ruff check app tests`
  7. `uv run pytest --cov=app --cov-fail-under=75`

---

## 常见操作速查

| 操作 | 命令 |
|------|------|
| 安装依赖 | `uv sync` |
| 运行后端 | `uv run uvicorn app.main:app --reload` |
| 运行 Celery | `uv run celery -A app.celery_app worker --loglevel=info --concurrency=4 --pool=solo` |
| 数据库迁移 | `uv run alembic upgrade head` |
| 生成迁移 | `uv run alembic revision --autogenerate -m "描述"` |
| 运行测试 | `uv run pytest` |
| 运行测试（带覆盖率） | `uv run pytest --cov=app --cov-fail-under=75` |
| 代码检查 | `uv run ruff check app tests --fix` |
| 类型检查 | `uv run ty check --error-on-warning` |
| 前端开发 | `cd frontend && npm run dev` |
| 前端构建 | `cd frontend && npm run build` |
| E2E 测试 | `cd frontend && npm run test:e2e` |
| 一键启动 | `./start.sh` |

---

## 参考文档

- `README.md`：项目介绍与功能截图
- `architecture.md`：系统架构图、数据模型关系图、交互时序图、技术栈分层图
