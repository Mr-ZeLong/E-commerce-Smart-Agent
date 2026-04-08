# 🤖 E-commerce Smart Agent v4.0：全栈·沉浸式人机协作系统

## 🌟 项目介绍

E-commerce Smart Agent v4.0 是一个先进的全栈智能客服系统，旨在通过结合大型语言模型（LLM）和人工审核流程，为电商平台提供高效、精准、安全的客户服务。该系统支持用户进行订单查询、政策咨询、退货申请等操作，并能够自动识别高风险请求并转交人工审核，同时为管理员提供一个直观的工作台进行决策。

本项目采用 LangChain & LangGraph 构建核心 Agent 逻辑，通过 FastAPI 提供 API 服务，SQLModel 进行数据管理，Celery 处理异步任务。前端采用 React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui 构建现代化的 C 端用户界面和 B 端管理后台，支持 SSE 流式响应和 WebSocket 实时通知。WebSocket 的引入实现了实时状态同步和消息推送，打造了沉浸式人机协作体验。

## 🚀 主要特性

*   **智能问答**：基于 LLM 提供订单查询和政策咨询。
*   **退货申请流程**：引导用户完成退货申请，并进行资格校验。
*   **智能风控与人工审核**：自动识别高风险退款申请（如大额退款），并转交管理员进行人工审核。
*   **实时状态同步**：通过 WebSocket 实现用户和管理员界面的实时状态更新。
*   **管理员工作台**：React + TypeScript 构建的现代化 B 端界面，支持任务队列、实时通知、一键决策。
*   **异步任务处理**：Celery 处理退款支付、短信通知等耗时操作。
*   **知识库管理**：支持从 PDF/Markdown 文件加载政策文档并进行 Embedding 检索。

## 🏗️ 项目结构

```text

├── README.md
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
│   │       ├── admin.py            # 管理员相关 API
│   │       ├── status.py           # 状态查询 API
│   │       ├── websocket.py        # WebSocket 连接端点
│   │       └── schemas.py          # Pydantic 数据模型
│   │
│   ├── core/                       # 核心模块
│   │   ├── __init__.py
│   │   ├── config.py               # 项目配置
│   │   ├── database.py             # 数据库连接
│   │   └── security.py             # JWT 认证
│   │
│   ├── graph/                      # LangGraph 核心逻辑
│   │   ├── __init__.py
│   │   ├── workflow.py             # 工作流定义
│   │   ├── state.py                # 状态定义
│   │   ├── nodes.py                # 节点定义
│   │   └── tools.py                # 工具定义
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
│   │   └── refund_service.py       # 退款业务逻辑
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
│       │   │   └── pages/
│       │   │       ├── Login.tsx
│       │   │       └── Chat.tsx
│       │   └── admin/              # B端管理后台
│       │       ├── App.tsx
│       │       ├── main.tsx
│       │       └── pages/
│       │           ├── Login.tsx
│       │           └── Dashboard.tsx
│       ├── components/ui/          # shadcn/ui 组件
│       ├── api/                    # API 客户端
│       ├── stores/                 # Zustand 状态管理
│       ├── hooks/                  # 自定义 Hooks
│       └── types/                  # TypeScript 类型
│
├── scripts/                        # 辅助脚本
│   ├── seed_data.py                # 数据库初始化
│   └── etl_policy.py               # 知识库 ETL
│
├── data/                           # 静态数据
├── migrations/                     # Alembic 数据库迁移
├── celery_worker.py                # Celery Worker 启动
├── start.sh                        # 项目启动脚本
├── docker-compose.yaml             # Docker Compose 配置
└── pyproject.toml                  # Python 项目配置

```

## 🛠️ 技术栈

*   **Python**：主要开发语言。
*   **FastAPI**：高性能 Python Web 框架，用于构建 RESTful API 和 WebSocket 服务。
*   **LangChain / LangGraph**：用于构建和编排 Agent 的核心逻辑、意图识别、RAG和多步骤工作流。
*   **SQLModel**：基于 Pydantic 和 SQLAlchemy 的数据库 ORM，提供类型安全的数据模型。
*   **PostgreSQL with PgVector**：关系型数据库，结合 PgVector 插件用于存储和检索 Embedding 向量。
*   **Redis**：缓存、Celery 消息代理和 LangGraph Checkpointer。
*   **Celery**：异步任务队列，处理耗时操作（如退款支付、短信通知）。
*   **React 18 + TypeScript**：现代前端框架，构建 C 端用户界面和 B 端管理后台。
*   **Vite**：前端构建工具，支持多页面配置。
*   **Tailwind CSS + shadcn/ui**：原子化 CSS 和组件库，实现现代化设计系统。
*   **Zustand + TanStack Query**：状态管理，区分客户端状态和服务端状态。
*   **React Router v6**：前端路由管理。
*   **JWT (PyJWT)**：用于用户认证和授权。
*   **OpenAI API / Qwen (通义千问)**：LLM 和 Embedding 模型 (通过适配器支持)。
*   **Docker / Docker Compose**：容器化部署工具。
*   **Alembic**：数据库迁移工具。

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