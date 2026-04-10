# 🤖 E-commerce Smart Agent v4.1：全栈·沉浸式人机协作系统

## 🌟 项目介绍

E-commerce Smart Agent v4.0 是一个先进的全栈智能客服系统，旨在通过结合大型语言模型（LLM）和人工审核流程，为电商平台提供高效、精准、安全的客户服务。该系统支持用户进行订单查询、政策咨询、退货申请等操作，并能够自动识别高风险请求并转交人工审核，同时为管理员提供一个直观的工作台进行决策。

本项目采用 LangChain & LangGraph 构建核心 Agent 逻辑，通过 FastAPI 提供 API 服务，SQLModel 进行数据管理，Celery 处理异步任务。前端采用 React 19 + TypeScript + Vite + Tailwind CSS + shadcn/ui 构建现代化的 C 端用户界面和 B 端管理后台，支持 SSE 流式响应和 WebSocket 实时通知。WebSocket 的引入实现了实时状态同步和消息推送，打造了沉浸式人机协作体验。

## 🚀 主要特性

*   **智能问答**：基于 LLM 提供订单查询和政策咨询。
*   **退货申请流程**：引导用户完成退货申请，并进行资格校验。
*   **LangGraph 1.0+ 多节点编排**：使用 LangGraph `Command` API 显式编排 router_node → policy_agent/order_agent → evaluator_node → decider_node 工作流，替代黑盒式 Supervisor。
*   **智能风控与人工审核**：自动识别高风险退款申请（如大额退款），并转交管理员进行人工审核。
*   **实时状态同步**：通过 WebSocket 实现用户和管理员界面的实时状态更新。
*   **管理员工作台**：React + TypeScript 构建的现代化 B 端界面，支持任务队列、实时通知、一键决策。
*   **异步任务处理**：Celery 处理退款支付、短信通知等耗时操作。
*   **知识库管理**：支持从 PDF/Markdown 文件加载政策文档并进行 Embedding 检索。

## 🏗️ 项目结构

```text

├── README.md
├── .env.example                    # 环境变量模板
├── app/                            # 主应用目录
│   ├── __init__.py
│   ├── main.py                     # FastAPI 主应用入口
│   ├── celery_app.py               # Celery 应用配置
│   │
│   ├── api/                        # API 接口定义
│   │   └── v1/                     # v1 版本 API
│   │       ├── __init__.py
│   │       ├── auth.py             # 认证接口 (登录)
│   │       ├── chat.py             # 聊天接口 (SSE 流式)
│   │       ├── chat_utils.py       # SSE 流式响应工具
│   │       ├── admin.py            # 管理员相关 API
│   │       ├── status.py           # 状态查询 API
│   │       ├── websocket.py        # WebSocket 连接端点
│   │       └── schemas.py          # Pydantic 数据模型
│   │
│   ├── core/                       # 核心模块
│   │   ├── __init__.py
│   │   ├── config.py               # 项目配置
│   │   ├── database.py             # 数据库连接
│   │   ├── redis.py                # 统一 Redis 客户端
│   │   ├── security.py             # JWT 认证
│   │   ├── limiter.py              # API 限流 (slowapi)
│   │   ├── llm_factory.py          # LLM 实例工厂
│   │   ├── logging.py              # 结构化日志
│   │   └── utils.py                # 工具函数（utc_now 等）
│   │
│   ├── graph/                      # LangGraph 核心逻辑
│   │   ├── __init__.py
│   │   ├── workflow.py             # 工作流定义
│   │   ├── nodes.py                # 节点定义
│   │   └── tools.py                # 工具定义
│   │
│   ├── agents/                     # Agent 实现层
│   │   ├── base.py                 # Agent 基类与 AgentResult
│   │   ├── router.py               # IntentRouterAgent
│   │   ├── order.py                # 订单 Agent
│   │   ├── policy.py               # 政策 Agent
│   │   └── evaluator.py            # ConfidenceEvaluator
│   │
│   ├── confidence/                 # 置信度信号模块
│   │   └── signals.py              # 置信度评估信号计算
│   │
│   ├── retrieval/                  # RAG 检索层
│   │   ├── client.py               # 检索客户端
│   │   ├── embeddings.py           # 向量嵌入
│   │   ├── retriever.py            # 检索器
│   │   ├── reranker.py             # 精排器
│   │   ├── rewriter.py             # 查询重写器
│   │   └── sparse_embedder.py      # 稀疏嵌入
│   │
│   ├── utils/                      # 通用工具函数
│   │   └── order_utils.py          # 订单相关工具
│   │
│   ├── intent/                     # 意图识别模块
│   │   ├── __init__.py
│   │   ├── service.py              # 意图识别服务 (Redis 会话/缓存)
│   │   ├── models.py               # 意图/槽位/澄清状态模型
│   │   ├── classifier.py           # 意图分类器
│   │   ├── clarification.py        # 澄清引擎
│   │   ├── slot_validator.py       # 槽位验证器
│   │   ├── topic_switch.py         # 话题切换检测
│   │   ├── multi_intent.py         # 多意图处理器
│   │   └── safety.py               # 安全过滤器
│   │
│   ├── models/                     # 数据库模型 (SQLModel)
│   │   ├── __init__.py
│   │   ├── user.py                 # 用户表
│   │   ├── order.py                # 订单表
│   │   ├── refund.py               # 退款申请表
│   │   ├── audit.py                # 审计日志表
│   │   ├── knowledge.py            # 知识库表
│   │   └── message.py              # 消息卡片表
│   │
│   ├── services/                   # 业务服务层
│   │   ├── __init__.py
│   │   ├── refund_service.py       # 退款业务逻辑
│   │   ├── refund_tool_service.py  # 退款工具服务
│   │   ├── status_service.py       # 状态服务
│   │   ├── order_service.py        # 订单服务
│   │   ├── admin_service.py        # 管理员服务
│   │   └── auth_service.py         # 认证服务
│   │
│   ├── schemas/                    # 共享 Schema
│   │   ├── admin.py
│   │   └── status.py
│   │
│   ├── tasks/                      # Celery 异步任务
│   │   ├── __init__.py
│   │   └── refund_tasks.py         # 退款相关任务
│   │
│   └── websocket/                  # WebSocket 服务
│       ├── __init__.py
│       └── manager.py              # 连接管理器
│
├── frontend/                       # React + TypeScript 前端
│   ├── package.json                # npm 依赖
│   ├── vite.config.ts              # Vite 配置
│   ├── tailwind.config.ts          # Tailwind 配置
│   ├── tsconfig.json               # TypeScript 配置
│   ├── index.html                  # C端入口
│   ├── admin.html                  # B端入口
│   └── src/
│       ├── apps/
│       │   ├── customer/           # C端用户应用
│       │   │   ├── App.tsx
│       │   │   ├── main.tsx
│       │   │   ├── pages/
│       │   │   │   ├── Login.tsx
│       │   │   │   └── Chat.tsx
│       │   │   ├── hooks/
│       │   │   │   └── useChat.ts
│       │   │   └── components/
│       │   │       ├── ChatMessageList.tsx
│       │   │       └── ChatInput.tsx
│       │   └── admin/              # B端管理后台
│       │       ├── App.tsx
│       │       ├── main.tsx
│       │       └── pages/
│       │           ├── Login.tsx
│       │           └── Dashboard.tsx
│       ├── components/ui/          # shadcn/ui 组件
│       │   ├── accordion.tsx
│       │   ├── alert.tsx
│       │   ├── avatar.tsx
│       │   ├── badge.tsx
│       │   ├── button.tsx
│       │   ├── card.tsx
│       │   ├── input.tsx
│       │   ├── label.tsx
│       │   ├── radio-group.tsx
│       │   ├── scroll-area.tsx
│       │   ├── separator.tsx
│       │   ├── sheet.tsx
│       │   ├── skeleton.tsx
│       │   └── textarea.tsx
│       ├── lib/                    # 共享基础设施
│       │   ├── api.ts              # 统一 API 客户端
│       │   ├── risk.ts             # 风险等级配置
│       │   ├── query-client.ts     # Query Client 配置
│       │   └── utils.ts            # 前端工具函数
│       ├── stores/                 # Zustand 状态管理
│       │   └── auth.ts             # 认证状态
│       ├── hooks/                  # 自定义 Hooks
│       │   ├── useAuth.ts
│       │   ├── useNotifications.ts
│       │   └── useTasks.ts
│       └── types/                  # TypeScript 类型
│           └── index.ts            # 统一类型导出
│
├── scripts/                        # 辅助脚本
│   ├── seed_data.py                # 数据库初始化
│   ├── seed_large_data.py          # 大批量测试数据
│   ├── etl_qdrant.py               # 知识库 ETL (PDF/Markdown → Qdrant)
│   └── verify_db.py                # 数据库验证脚本
│
├── tests/                          # 后端测试
│   ├── conftest.py                 # pytest 全局 fixtures
│   ├── test_auth_api.py            # 认证 API 测试
│   ├── test_chat_api.py            # 聊天 API 测试
│   ├── test_admin_api.py           # 管理员 API 测试
│   ├── agents/                     # Agent 单元测试
│   ├── graph/                      # LangGraph 测试
│   ├── intent/                     # 意图模块测试
│   ├── retrieval/                  # RAG 检索测试
│   └── integration/                # 集成测试
│
├── data/                           # 静态数据
├── migrations/                     # Alembic 数据库迁移
├── celery_worker.py                # Celery Worker 启动
├── start.sh                        # 项目一键启动脚本
├── start_worker.sh                 # 单独启动 Celery Worker
├── docker-compose.yaml             # Docker Compose 配置
├── .pre-commit-config.yaml         # pre-commit 配置
└── pyproject.toml                  # Python 项目配置 (uv)

```

## 🛠️ 技术栈

*   **Python**：主要开发语言。
*   **FastAPI**：高性能 Python Web 框架，用于构建 RESTful API 和 WebSocket 服务。
*   **LangChain / LangGraph**：用于构建和编排 Agent 的核心逻辑、意图识别、RAG和多步骤工作流。
*   **SQLModel**：基于 Pydantic 和 SQLAlchemy 的数据库 ORM，提供类型安全的数据模型。
*   **PostgreSQL**：关系型数据库，用于订单、用户、退款等结构化数据存储。
*   **Qdrant**：向量数据库，用于混合 RAG 检索（Dense + BM25 Sparse）。
*   **Redis**：缓存、Celery 消息代理和 LangGraph Checkpointer。
*   **Celery**：异步任务队列，处理耗时操作（如退款支付、短信通知）。
*   **React 19 + TypeScript**：现代前端框架，构建 C 端用户界面和 B 端管理后台。
*   **Vite**：前端构建工具，支持多页面配置。
*   **Tailwind CSS + shadcn/ui**：原子化 CSS 和组件库，实现现代化设计系统。
*   **Zustand + TanStack Query**：状态管理，区分客户端状态和服务端状态。
*   **React Router v7**：前端路由管理。
*   **Python >= 3.12**：后端运行环境。
*   **uv**：现代化 Python 包管理器。
*   **JWT (PyJWT)**：用于用户认证和授权。
*   **bcrypt**：密码哈希。
*   **slowapi**：API 限流。
*   **OpenAI API / Qwen (通义千问)**：LLM 和 Embedding 模型 (通过适配器支持)。
*   **Docker / Docker Compose**：容器化部署工具。
*   **Alembic**：数据库迁移工具。
*   **ruff**：Python Linter + Formatter。
*   **ty**：Python 类型检查器。
*   **pre-commit**：提交前代码质量门禁。
*   **Playwright**：前端 E2E 测试。
*   **Python `logging`**：统一日志方案（带 correlation_id）。

## 🚀 快速开始

### 一键启动（推荐首次使用）

```bash
./start.sh
```

访问地址：
- API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- C端用户界面: http://localhost:8000/app
- B端管理后台: http://localhost:8000/admin

### 手动分步启动

```bash
# 1. 安装 Python 依赖
uv sync

# 2. 启动基础设施
docker compose up -d db redis qdrant

# 3. 数据库迁移
uv run alembic upgrade head

# 4. 启动 FastAPI
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. 启动 Celery Worker（另开终端）
uv run celery -A app.celery_app worker --loglevel=info --concurrency=4 --pool=solo
```

### 前端开发模式

```bash
cd frontend
npm install
npm run dev        # 端口 5173，代理 /api → localhost:8000
```

## ⚙️ 环境变量

复制 `.env.example` 为 `.env` 并填写真实值：

```bash
# 数据库
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=...
POSTGRES_DB=knowledge_base

# Redis（本地 docker-compose 默认密码 devpassword）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=devpassword

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=...

# LLM
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
DASHSCOPE_API_KEY=...

# 安全
SECRET_KEY=...                    # openssl rand -hex 32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# 其他
ENABLE_OPENAPI_DOCS=True
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

## 🧪 测试

```bash
# 后端测试
uv run pytest
uv run pytest --cov=app --cov-fail-under=75

# 前端 E2E 测试
cd frontend
npm run test:e2e
```

## 🛠️ 代码质量

```bash
# 安装 pre-commit hook
pre-commit install

# 手动检查
uv run ruff check app tests --fix
uv run ruff format app tests
uv run ty check --error-on-warning
```

## 🔄 CI/CD

GitHub Actions 工作流位于 `.github/workflows/ci.yml`：
- 触发条件：`push` / `pull_request` 到 `main`
- 步骤：lint (ruff) → 类型检查 (ty, 通过 pre-commit) → 测试 (pytest, 覆盖率 >=75%)

### 订单查询
<img src="assets/image/order_query.png" width="600" alt="订单查询" />

### 退货申请
<img src="assets/image/refund_apply.png" width="600" alt="退货申请" />

### 政策咨询
<img src="assets/image/policy_ask.png" width="600" alt="政策咨询" />

### 意图识别
<img src="assets/image/intent_detect.png" width="600" alt="意图识别" />

### 非法查询他人订单
<img src="assets/image/illegal_query.png" width="600" alt="非法查询" />