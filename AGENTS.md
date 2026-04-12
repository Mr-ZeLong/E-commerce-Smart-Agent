# AGENTS.md

> 本文件面向 AI Coding Agent。如果你正在使用 Claude Code、Kimi CLI、Cursor 或其他智能编程助手，请先阅读本文档。它总结了项目结构、技术栈、构建命令、代码规范和测试策略。

---

## 项目概览

**E-commerce Smart Agent v4.1** 是一个全栈·沉浸式人机协作智能客服系统，已完成 Phase 1 专家 Agent 扩展、Phase 2 Supervisor-based 多 Agent 编排重构，以及 **Phase 3 记忆系统与 Agent 配置中心**。核心能力包括：

- 基于 LLM（通义千问/Qwen）的智能问答（订单查询、政策咨询、商品查询、购物车管理）
- **Supervisor-based 多 Agent 编排**：LangGraph `Command` + `Send` API 实现串行/并行智能调度与多意图并行执行
- **Agent Subgraph 标准**：每个专家 Agent 封装为独立 `StateGraph`，标准化输入/输出接口
- **商品问答** (`ProductAgent`)：基于 Qdrant `product_catalog` 语义检索，支持直接参数回答 + LLM 回退
- **购物车管理** (`CartAgent`)：Redis 持久化，支持增删改查，24h TTL 保持一致性
- **结构化记忆系统**（Phase 3）：PostgreSQL 存储 `UserProfile` / `UserPreference` / `InteractionSummary` / `UserFact`，通过 `memory_context` 注入 Agent Prompt
- **向量对话记忆**（Phase 3）：Qdrant `conversation_memory` 集合支持语义检索历史上下文
- **记忆抽取 Pipeline**（Phase 3）：`FactExtractor` + Celery 异步任务，自动从会话中提取结构化事实
- **Agent 配置中心**（Phase 3）：B 端 Admin 后台支持热重载 Agent 路由规则、系统提示词、启用/禁用 Agent，带审计日志与版本回滚
- 智能风控与人工审核（按金额分级：¥500 / ¥2000 阈值）
- WebSocket 实时状态同步（用户端 + 管理员端）
- Celery 异步任务（退款支付、短信通知、管理员通知、知识库 ETL 同步、记忆抽取）
- 基于 Qdrant 的混合 RAG 检索（Dense + BM25 Sparse + Rerank）
- **B 端知识库管理**：Admin 后台支持 PDF/Markdown 上传、删除与手动同步到 Qdrant

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
| 稀疏嵌入 | fastembed>=0.6.0 | `app/retrieval/sparse_embedder.py` |
| 重试机制 | tenacity>=9.1.2 | 多处 LLM 调用 |
| HTTP 客户端 | httpx>=0.28.1 | 通用异步 HTTP |
| 表单解析 | python-multipart>=0.0.21 | FastAPI 文件上传 |
| 邮箱校验 | email-validator>=2.3.0 | Pydantic 字段验证 |
| 社区集成 | langchain-community>=0.4.1 | 文档加载器等 |
| WebSocket 服务端 | websockets>=14.1 | `app/api/v1/websocket.py` |

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
│   │   ├── admin.py                # 管理员 API（审核、任务队列、知识库 CRUD + 同步）
│   │   ├── admin/agent_config.py   # Agent 配置中心 API（路由规则 / 提示词 / 审计日志）
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
│   │   ├── llm_factory.py          # LLM 工厂（OpenAI-Compatible 适配器，默认通义千问）
│   │   └── utils.py                # utc_now 等工具函数
│   ├── models/                     # SQLModel 数据模型
│   │   ├── user.py                 # 用户模型
│   │   ├── order.py                # 订单模型
│   │   ├── refund.py               # 退款模型
│   │   ├── audit.py                # 审核日志模型
│   │   ├── message.py              # 消息模型
│   │   ├── knowledge_document.py   # 知识库文档模型
│   │   ├── observability.py        # 可观测性模型（GraphExecutionLog / SupervisorDecision）
│   │   ├── memory.py               # 记忆模型（UserProfile / UserPreference / InteractionSummary / UserFact / AgentConfig / AuditLog）
│   │   └── state.py                # AgentState TypedDict
│   ├── memory/                     # 记忆系统（Phase 3）
│   │   ├── __init__.py
│   │   ├── structured_manager.py   # 结构化记忆管理器（PostgreSQL）
│   │   ├── vector_manager.py       # 向量对话记忆管理器（Qdrant conversation_memory）
│   │   ├── extractor.py            # 事实抽取器（FactExtractor）
│   │   └── summarizer.py           # 会话摘要器（SessionSummarizer）
│   ├── graph/                      # LangGraph 工作流
│   │   ├── workflow.py             # 编译 StateGraph（含 Supervisor 与兼容模式）
│   │   ├── nodes.py                # router_node / supervisor_node / synthesis_node / evaluator_node / decider_node
│   │   ├── subgraphs.py            # Agent Subgraph 标准化封装
│   │   └── parallel.py             # 并行多意图调度（plan_dispatch + build_parallel_sends）
│   ├── confidence/                 # 置信度信号模块
│   │   ├── __init__.py
│   │   └── signals.py              # 置信度评估信号计算
│   ├── utils/                      # 通用工具函数
│   │   └── order_utils.py          # 订单相关工具
│   ├── agents/                     # Agent 实现层
│   │   ├── base.py                 # Agent 基类
│   │   ├── router.py               # IntentRouterAgent
│   │   ├── supervisor.py           # SupervisorAgent（串行/并行调度）
│   │   ├── order.py                # OrderAgent
│   │   ├── policy.py               # PolicyAgent
│   │   ├── product.py              # ProductAgent（商品问答）
│   │   ├── cart.py                 # CartAgent（购物车管理）
│   │   ├── logistics.py            # LogisticsAgent
│   │   ├── account.py              # AccountAgent
│   │   ├── payment.py              # PaymentAgent
│   │   └── evaluator.py            # ConfidenceEvaluator（置信度信号）
│   ├── tools/                      # Agent Tool 层
│   │   ├── __init__.py
│   │   ├── product_tool.py         # 商品检索 Tool（Qdrant product_catalog）
│   │   ├── cart_tool.py            # 购物车操作 Tool（Redis）
│   │   ├── logistics_tool.py       # 物流查询 Tool
│   │   ├── account_tool.py         # 账户查询 Tool
│   │   └── payment_tool.py         # 支付查询 Tool
│   ├── intent/                     # 意图识别模块
│   │   ├── service.py              # IntentRecognitionService（Redis 会话）
│   │   ├── models.py               # 意图/槽位/澄清状态模型
│   │   ├── config.py               # 意图识别配置
│   │   ├── classifier.py           # 意图分类器
│   │   ├── clarification.py        # 澄清引擎
│   │   ├── slot_validator.py       # 槽位验证器
│   │   ├── topic_switch.py         # 话题切换检测
│   │   ├── multi_intent.py         # 多意图处理器（含 are_independent 独立性判断）
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
│   │   ├── status_service.py       # 状态服务
│   │   ├── order_service.py        # 订单服务
│   │   ├── admin_service.py        # 管理员服务
│   │   └── auth_service.py         # 认证服务
│   ├── tasks/                      # Celery 异步任务
│   │   ├── __init__.py
│   │   ├── refund_tasks.py         # 退款相关任务
│   │   ├── knowledge_tasks.py      # 知识库同步任务
│   │   └── memory_tasks.py         # 记忆抽取与同步任务
│   ├── websocket/                  # WebSocket 连接管理
│   │   └── manager.py              # ConnectionManager（广播/单发）
│   └── schemas/                    # 共享 Schema
│       ├── auth.py                 # 认证相关 Schema
│       ├── admin.py                # 管理员相关 Schema
│       └── status.py               # 状态查询 Schema
│
├── frontend/                       # React 前端
│   ├── index.html                  # C端入口
│   ├── admin.html                  # B端入口
│   ├── vite.config.ts              # 多页面 Rollup 配置
│   ├── tailwind.config.ts          # Tailwind CSS 配置
│   ├── tsconfig.json               # TypeScript 配置
│   ├── tsconfig.node.json          # Vite Node 类型配置
│   ├── components.json             # shadcn/ui 组件注册表
│   ├── postcss.config.mjs          # PostCSS 配置
│   ├── eslint.config.js            # ESLint 配置
│   ├── playwright.config.ts        # Playwright E2E 配置
│   ├── package.json                # npm 依赖
│   ├── package-lock.json           # npm 锁定文件
│   └── src/
│       ├── apps/customer/          # C端用户聊天应用
│       ├── apps/admin/             # B端管理员后台
│       │   ├── pages/
│       │   │   ├── Login.tsx
│       │   │   ├── Dashboard.tsx
│       │   │   ├── KnowledgeBase.tsx          # 知识库管理页面
│       │   │   └── AgentConfig.tsx            # Agent 配置中心页面
│       │   └── components/
│       │       ├── DecisionPanel.tsx
│       │       ├── NotificationToast.tsx
│       │       ├── TaskDetail.tsx
│       │       ├── TaskList.tsx
│       │       ├── ConversationLogs.tsx
│       │       ├── EvaluationViewer.tsx
│       │       ├── Performance.tsx
│       │       ├── KnowledgeBaseManager.tsx   # 知识库上传/同步组件
│       │       └── AgentConfigEditor.tsx      # Agent 配置编辑器组件
│       ├── assets/                 # 前端静态资源
│       ├── components/ui/          # shadcn/ui 组件
│       ├── lib/                    # API 客户端、工具函数
│       ├── stores/                 # Zustand Store
│       ├── hooks/                  # 自定义 Hooks
│       │   ├── useKnowledgeBase.ts # 知识库管理 Hooks
│       │   └── useAgentConfig.ts   # Agent 配置管理 Hooks
│       └── types/                  # TypeScript 类型
│
├── tests/                          # 后端测试
│   ├── conftest.py                 # pytest 全局 fixtures
│   ├── _db_config.py               # 测试数据库配置
│   ├── test_*.py                   # API/Service 测试
│   ├── agents/                     # Agent 单元测试
│   ├── tools/                      # Tool 单元测试（product_tool / cart_tool）
│   ├── graph/                      # LangGraph 测试
│   ├── intent/                     # 意图模块测试
│   ├── retrieval/                  # RAG 检索测试
│   └── integration/                # 集成测试
│
├── scripts/                        # 辅助脚本
│   ├── __init__.py
│   ├── seed_data.py                # 数据库初始化数据
│   ├── seed_large_data.py          # 大批量测试数据
│   ├── seed_product_catalog.py     # 商品目录种子数据（→ Qdrant product_catalog）
│   ├── etl_qdrant.py               # 知识库 ETL（PDF/Markdown → Qdrant）
│   └── verify_db.py                # 数据库验证
│
├── docs/                           # 项目文档
│   └── resume-guide.md             # 简历写作指南
│
├── migrations/                     # Alembic 迁移脚本
├── data/                           # 静态数据（示例政策文档、products.json）
├── assets/                         # 截图与静态资源
├── .github/                        # GitHub Actions 工作流
├── docker-compose.yaml             # 本地/容器编排
├── Dockerfile                      # 基于 python:3.13-slim + uv
├── start.sh                        # 本地一键启动脚本
├── start_worker.sh                 # 单独启动 Celery Worker
├── architecture.md                 # 系统架构文档
├── alembic.ini                     # Alembic 迁移配置
├── pyproject.toml                  # Python 项目配置
└── uv.lock                         # uv 依赖锁定文件
```

---

## 环境变量

项目通过 `.env` 文件加载配置（由 `app/core/config.py` 解析）。复制 `.env.example` 为 `.env` 并填写真实值。

关键变量：

```bash
# 应用
PROJECT_NAME=E-commerce Smart Agent
API_V1_STR=/api/v1

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

# Reranker
RERANK_BASE_URL=https://dashscope.aliyuncs.com/compatible-api/v1

# LLM（通义千问 / OpenAI-Compatible）
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
DASHSCOPE_API_KEY=...

# LLM 模型配置（可选，不填时使用默认值）
LLM_MODEL=qwen-plus
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_DIM=1024

# 安全
SECRET_KEY=...                    # 建议: openssl rand -hex 32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Celery
CELERY_BROKER_URL=redis://:devpassword@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:devpassword@localhost:6379/0

# 其他
ENABLE_OPENAPI_DOCS=True          # 生产环境设为 False
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

**注意**：`app/core/config.py` 中的 `Settings` 使用 `SettingsConfigDict(env_file=".env")`，支持嵌套配置（分隔符 `__`），例如 `CONFIDENCE__THRESHOLD=0.7`。大部分配置项（如 `LLM_MODEL`、`EMBEDDING_MODEL`、`EMBEDDING_DIM`）均有合理的默认值，本地开发时可不填。

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

# 商品目录种子数据（→ Qdrant product_catalog）
uv run python scripts/seed_product_catalog.py

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
- API 层测试：`test_auth_api.py`、`test_chat_api.py`、`test_admin_api.py`、`test_websocket.py`、`test_auth_rate_limit.py`、`test_knowledge_admin.py`
- Service 层测试：`test_order_service.py`、`test_refund_service.py`、`test_admin_service.py`、`test_auth_service.py`、`test_status_service.py`
- 工具/安全测试：`test_security.py`、`test_main_security.py`、`test_logging.py`、`test_chat_utils.py`、`test_refund_tasks.py`、`test_users.py`、`test_confidence_signals.py`
- 模块单元测试：`tests/agents/`、`tests/tools/`（`test_product_tool.py`、`test_cart_tool.py`）、`tests/graph/`、`tests/intent/`、`tests/retrieval/`
- 集成测试：`tests/integration/test_workflow_invoke.py` — LangGraph 工作流集成测试（含并行多意图场景）

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
- Celery 任务：使用同步数据库会话（`sync_session_maker`）执行异步任务的持久化操作

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
- Pydantic Schema 放在 `app/schemas/`（如 `auth.py`、`admin.py`、`status.py`）
- 大部分服务依赖直接通过 `Depends(ClassName)` 注入；当服务需要运行时依赖（如 `AdminService` 需要 `ConnectionManager`）时，仍使用工厂函数 `Depends(get_xxx_service)` 注入

### 4. LangGraph 工作流

- `app/graph/workflow.py`：编译图并返回，由 `app/main.py` 存储在 `app.state.app_graph`
- `app/main.py` 的 `lifespan` 在启动时调用 `compile_app_graph()`
- 节点定义在 `app/graph/nodes.py`（含 router / supervisor / synthesis / evaluator / decider）
- Agent Subgraph 定义在 `app/graph/subgraphs.py`
- 并行调度定义在 `app/graph/parallel.py`
- 状态定义在 `app/models/state.py`
- Agent 实例在 `app/main.py` 的 `lifespan` 中初始化，通过依赖注入传递给 `nodes.py` 中的 builder 函数

**Phase 3 工作流节点顺序（Supervisor + Memory 模式）**：
`router_node` → `memory_node` → `supervisor_node` → (`Send` 并行/串行分发到 Agent Subgraphs) → `synthesis_node` → `evaluator_node` → (`低置信度重试 → router_node` | `通过 → decider_node`) → `END`

- `memory_node` 在 `router_node` 之后执行，负责从 PostgreSQL 加载结构化记忆（`UserProfile`、`UserPreference`、`UserFact`、`InteractionSummary`），并从 Qdrant `conversation_memory` 语义检索相关历史消息，生成 `memory_context` 写入 `AgentState`。
- `decider_node` 在最终回复/决策后，异步触发 Celery 任务（`extract_and_save_facts`）进行会话摘要与事实抽取。

当 `supervisor_agent=None` 时，工作流自动回退到旧路径：`router_node` 直接路由到具体的 `policy_agent` / `order_agent` / ...。

### 4.1 Agent Subgraph 标准（Phase 2 核心）

每个专家 Agent 被封装为独立的 `StateGraph` Subgraph（`app/graph/subgraphs.py::build_agent_subgraph(agent)`）：
- 消费 `AgentState` 的子集
- 返回 `{"sub_answers": [{"agent": ..., "response": ..., "updated_state": ..., "iteration": ...}]}`
- 支持串行与并行执行（通过 `operator.add` 合并 `sub_answers`）

### 4.2 Tool-Based Agent 舰队（Phase 1 + Phase 2）

所有专家 Agent 均基于 `BaseTool` + `ToolRegistry` 构建，由 `app/main.py` lifespan 初始化并注入到 LangGraph 工作流中。每个 Agent 的节点/Subgraph 均标记 `metadata={"tags": ["user_visible"]}`，确保 SSE 流式输出可正确转发。

- **ProductAgent** (`app/agents/product.py` + `app/tools/product_tool.py`)
  - 处理 `PRODUCT` / `RECOMMENDATION` 意图，基于 Qdrant `product_catalog` 语义检索。
  - 行为规则：精确参数命中目录元数据时直接回答；否则回退到 LLM 推理。

- **CartAgent** (`app/agents/cart.py` + `app/tools/cart_tool.py`)
  - 处理 `CART` 意图，支持购物车 `QUERY` / `ADD` / `REMOVE` / `MODIFY`。
  - 行为规则：Redis 持久化 (`cart:{user_id}`)，24h TTL；严格多租户隔离。

- **LogisticsAgent** (`app/agents/logistics.py` + `app/tools/logistics_tool.py`)
  - 处理 `LOGISTICS` 意图，查询 `Order.tracking_number` 与物流状态。
  - 行为规则：必须按 `user_id` 过滤订单；若订单不存在返回明确的 "未找到相关订单"。

- **AccountAgent** (`app/agents/account.py` + `app/tools/account_tool.py`)
  - 处理 `ACCOUNT` 意图，查询用户资料、会员等级、账户余额与优惠券。
  - 行为规则：仅返回当前登录用户的资料；余额/优惠券在 Phase 1 以 mock 数据返回。

- **PaymentAgent** (`app/agents/payment.py` + `app/tools/payment_tool.py`)
  - 处理 `PAYMENT` 意图，查询支付状态、发票信息、退款支付记录。
  - 行为规则：查询 `RefundApplication` 与 `Order` 表必须按 `user_id` 过滤。

### 4.3 记忆系统开发约定（Phase 3）

- **结构化记忆 (`app/memory/structured_manager.py`)**
  - `UserProfile` / `UserPreference` / `InteractionSummary` / `UserFact` 统一通过 `StructuredMemoryManager` 进行 CRUD。
  - 所有查询必须按 `user_id` 过滤，禁止越权访问其他用户记忆。
  - `memory_context` 生成规则：按优先级拼接（Profile → Facts → Preferences → Summary），控制总长度避免污染 Prompt。

- **向量对话记忆 (`app/memory/vector_manager.py`)**
  - Qdrant Collection 名为 `conversation_memory`，每条消息独立存储向量和元数据（`thread_id`, `role`, `created_at`）。
  - `upsert_message` 在 `chat.py` 的 SSE 流前后调用，实现消息向量持久化。
  - `retrieve_similar_messages` 默认按 `user_id` + `thread_id` 过滤，召回 TopK 相关历史上下文。

- **记忆抽取 (`app/memory/extractor.py` + `app/tasks/memory_tasks.py`)**
  - `FactExtractor` 使用轻量 LLM (`qwen-turbo`) 配合 JSON Schema 结构化输出，提取 `fact_type` / `content` / `confidence`。
  - `confidence < 0.7` 的事实直接丢弃，不入库。
  - PII 保护：`extractor.py` 内置正则过滤身份证号、手机号、银行卡号，命中时整句事实会被丢弃。
  - Celery 任务 `extract_and_save_facts` 由 `decider_node` 在回合结束后异步触发，不阻塞 SSE 响应。

### 4.4 Agent 配置中心开发约定（Phase 3）

- **后端 API** (`app/api/v1/admin/agent_config.py`)
  - 提供 Agent 配置的 CRUD、路由规则管理、版本回滚、审计日志查询。
  - 配置读取带 Redis 缓存（60s TTL），写入时主动失效缓存，实现热重载。
  - 禁用某个 Agent 时，需要在 Supervisor 调度层或兼容路由层正确处理 fallback（默认转 `policy_agent` 或直接提示）。
  - 所有配置变更必须写入 `AgentConfigAuditLog`，包含 `old_value` / `new_value` / `changed_by`。

- **前端集成** (`frontend/src/apps/admin/pages/AgentConfig.tsx` + `AgentConfigEditor.tsx`)
  - 使用 `useAgentConfig.ts` 封装 TanStack Query 进行服务端状态管理。
  - 路由规则编辑支持 intent_category / target_agent / priority 的表单输入；`condition_json` 当前为只读 JSON 展示。
  - 版本回滚交互：在 `AgentConfigEditor.tsx` 中选择历史版本并一键回滚。

### 5. 日志规范

统一使用 `logging.getLogger(__name__)`，日志格式包含 `correlation_id`：

```python
logger = logging.getLogger(__name__)
logger.info("示例日志")
```

### 6. 配置管理

所有环境相关配置集中放在 `app/core/config.py` 的 `Settings` 类中。不要在代码中直接读取 `os.environ`，应通过 `from app.core.config import settings` 使用。

### 7. Redis 使用

通过 `app/core/redis.py` 获取统一客户端：`create_redis_client()`。Redis 用于：
- 意图识别会话缓存
- LangGraph Checkpoint（`langgraph-checkpoint-redis`）
- Celery Broker & Backend

### 8. 静态文件

FastAPI 托管 `frontend/dist` 中的构建产物：
- `/app/*` → C端 SPA
- `/admin/*` → B端 SPA
- `/` → 重定向到 `/app`

前端构建输出根目录为 `frontend/dist/`。Vite 将资源文件输出到 `customer/` 和 `admin/` 子目录（JS/CSS），而入口 HTML 文件直接位于根目录：`dist/index.html`（C端）和 `dist/admin.html`（B端），由 `vite.config.ts` 的 `rollupOptions.input` 控制。

---

## 安全注意事项

1. **CORS 安全**：`app/main.py` 在启动时会检查 `CORS_ORIGINS` 是否包含 `"*"`，若与 `allow_credentials=True` 同时存在会直接抛出 `RuntimeError`。
2. **JWT 密钥**：生产环境必须修改 `SECRET_KEY`，建议使用 `openssl rand -hex 32` 生成。
3. **OpenAPI 文档**：生产环境应设置 `ENABLE_OPENAPI_DOCS=False`，避免暴露接口文档。
4. **Rate Limiting**：已集成 `slowapi`，部分敏感接口（如登录）已配置限流。
5. **多租户隔离**：所有订单/退款/购物车查询必须根据当前登录用户的 `user_id` 过滤，防止横向越权。
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
