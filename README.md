# 🤖 E-commerce Smart Agent：全栈·沉浸式人机协作系统

## 🌟 项目介绍

E-commerce Smart Agent 是一个先进的全栈智能客服系统，旨在通过结合大型语言模型（LLM）和人工审核流程，为电商平台提供高效、精准、安全的客户服务。该系统支持用户进行订单查询、政策咨询、商品查询、购物车管理、退货申请、投诉工单等操作，并能够自动识别高风险请求并转交人工审核，同时为管理员提供一个直观的工作台进行决策与知识库管理。

本项目采用 LangChain & LangGraph 构建核心 Agent 逻辑，引入基于 `SupervisorAgent` 的多 Agent 编排架构，支持串行/并行智能调度与多意图并行执行；进一步构建**结构化记忆系统**（PostgreSQL 用户画像/偏好/事实 + Qdrant 向量对话记忆）和**Agent 配置中心**（B 端热重载、路由规则、审计日志）。通过 FastAPI 提供 API 服务，SQLModel 进行数据管理，Celery 处理异步任务。前端采用 React 19 + TypeScript + Vite + Tailwind CSS + shadcn/ui 构建现代化的 C 端用户界面和 B 端管理后台，支持 SSE 流式响应和 WebSocket 实时通知。WebSocket 的引入实现了实时状态同步和消息推送，打造了沉浸式人机协作体验。

## 🚀 主要特性

*   **智能问答**：基于 LLM 提供订单查询、政策咨询、商品查询和购物车管理。
*   **商品问答与目录检索** (`ProductAgent`)：基于 Qdrant `product_catalog` 集合进行语义搜索，支持直接参数回答与 LLM 推理回退。
*   **购物车管理** (`CartAgent`)：通过 Redis 支持购物车查询、添加、删除、修改，状态 24h 内保持一致。
*   **退货申请流程**：引导用户完成退货申请，并进行资格校验。
*   **Supervisor 多 Agent 编排** (`SupervisorAgent`)：基于 `SupervisorAgent` + Agent Subgraph 的串行/并行智能调度，支持多意图独立识别与 LangGraph `Send` 并行执行，替代固定路由。
*   **结构化记忆系统** (`StructuredMemoryManager`)：基于 PostgreSQL 存储用户画像 (`UserProfile`)、偏好 (`UserPreference`)、交互摘要 (`InteractionSummary`) 和原子事实 (`UserFact`)；通过 `memory_context` 自动注入 Agent Prompt，实现个性化回复与长期记忆。
*   **向量对话记忆** (`VectorMemoryManager`)：基于 Qdrant `conversation_memory` 集合存储全量对话消息向量，支持语义检索历史上下文，实现跨会话记忆召回。
*   **记忆抽取 Pipeline** (`FactExtractor` + Celery)：在 `decider_node` 后通过 Celery 异步任务调用轻量 LLM，自动提取会话中的结构化事实并落盘到 `UserFact` 表。
*   **Agent 配置中心** (`AgentConfig`)：B 端 Admin 后台支持热重载 Agent 路由规则、系统提示词、启用/禁用特定 Agent；变更写入审计日志 (`AgentConfigAuditLog`)，支持版本回滚与 A/B 实验流量分配。
*   **智能投诉处理** (`ComplaintAgent`)：基于 LLM 自动识别用户投诉意图并分类（商品质量、物流问题、服务态度等），自动创建投诉工单 (`ComplaintTicket`) 并支持紧急度分级与管理员分配。
*   **A/B 测试框架** (`Experiment`)：支持多版本 Agent 配置对比实验，基于用户 ID 哈希实现确定性流量分配，提供实验结果统计与转化率分析。
*   **在线评估与反馈** (`OnlineEval`)：支持用户对每条助手回复进行 👍/👎 反馈，自动计算 CSAT 分数，基于 LLM 对对话质量进行自动评分。
*   **自动告警系统** (`AutoAlert`)：Celery Beat 定时检测服务质量下降（CSAT 低于阈值、投诉量激增），通过邮件和 WebSocket 实时通知管理员。
*   **高级分析面板** (`AnalyticsV2`)：B 端 Analytics V2 页面展示 CSAT 趋势、投诉根因分析、Agent 性能对比、LangSmith Trace 链路追踪。
*   **离线评估 Pipeline** (`EvaluationPipeline`)：基于 Golden Dataset 进行意图准确率、槽位召回、RAG 精确率、回答正确性等多维度离线评估。
*   **可观测性建设** (`OpenTelemetry`)：集成 OpenTelemetry tracing，支持 OTLP 导出与 FastAPI 自动埋点，实现全链路可观测。
*   **智能风控与人工审核**：按金额分级风控（<¥500 低风险 / ¥500~<¥2000 中风险 / ≥¥2000 高风险），自动识别高风险退款申请并转交管理员进行人工审核。
*   **实时状态同步**：通过 WebSocket 实现用户和管理员界面的实时状态更新。
*   **管理员工作台**：React + TypeScript 构建的现代化 B 端界面，支持任务队列、实时通知、一键决策、知识库文档上传与同步、Agent 配置管理、投诉工单管理、A/B 实验管理、高级数据分析。
*   **异步任务处理**：Celery 处理退款支付、短信通知、知识库 ETL 同步、记忆抽取、告警通知等耗时操作。
*   **知识库管理**：支持从 PDF/Markdown 文件加载政策文档并进行 Embedding 检索；Admin 后台可对知识库文档进行上传、删除与手动同步。

## 🏗️ 项目结构

```text

├── README.md
├── architecture.md                 # 系统架构文档
├── .env.example                    # 环境变量模板
├── alembic.ini                     # Alembic 迁移配置
├── Dockerfile                      # 容器构建配置
├── docs/                           # 文档目录
│   └── resume-guide.md             # 简历写作指南
├── .github/                        # GitHub 工作流
│   └── workflows/ci.yml            # CI 配置
├── pyproject.toml                  # Python 项目配置 (uv)
├── uv.lock                         # uv 依赖锁定文件
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
│   │       ├── admin/              # 管理员相关 API (含知识库 CRUD + 同步)
│   │       │   ├── agent_config.py # Agent 配置中心 API (路由规则 / 系统提示词 / 审计日志)
│   │       │   ├── complaints.py   # 投诉工单管理 API
│   │       │   ├── experiments.py  # A/B 实验管理 API
│   │       │   ├── feedback.py     # 用户反馈与质量评估 API
│   │       │   └── analytics.py    # 高级分析 API
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
│   │   ├── email.py                # 邮件发送工具
│   │   └── utils.py                # 工具函数（utc_now 等）
│   │
│   ├── graph/                      # LangGraph 核心逻辑
│   │   ├── __init__.py
│   │   ├── workflow.py             # 工作流定义
│   │   ├── nodes.py                # 节点定义 (router / supervisor / synthesis / evaluator / decider / memory)
│   │   ├── subgraphs.py            # Agent Subgraph 标准化封装
│   │   └── parallel.py             # 并行多意图调度 (plan_dispatch + build_parallel_sends)
│   │
│   ├── agents/                     # Agent 实现层
│   │   ├── base.py                 # Agent 基类
│   │   ├── router.py               # IntentRouterAgent
│   │   ├── supervisor.py           # SupervisorAgent (串行/并行调度)
│   │   ├── order.py                # 订单 Agent
│   │   ├── policy.py               # 政策 Agent
│   │   ├── product.py              # 商品 Agent (ProductAgent)
│   │   ├── cart.py                 # 购物车 Agent (CartAgent)
│   │   ├── logistics.py            # 物流 Agent
│   │   ├── account.py              # 账户 Agent
│   │   ├── payment.py              # 支付 Agent
│   │   ├── complaint.py            # 投诉 Agent (ComplaintAgent)
│   │   ├── evaluator.py            # ConfidenceEvaluator
│   │   └── config_loader.py        # Agent 配置加载器
│   │
│   ├── tools/                      # Agent Tool 层
│   │   ├── __init__.py
│   │   ├── base.py                 # Tool 基类与接口
│   │   ├── registry.py             # Tool 注册中心
│   │   ├── product_tool.py         # 商品检索 Tool (Qdrant product_catalog)
│   │   ├── cart_tool.py            # 购物车操作 Tool (Redis)
│   │   ├── logistics_tool.py       # 物流查询 Tool
│   │   ├── account_tool.py         # 账户查询 Tool
│   │   ├── payment_tool.py         # 支付查询 Tool
│   │   └── complaint_tool.py       # 投诉工单创建 Tool
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
│   │   ├── config.py               # 意图识别配置（兼容性矩阵、槽位优先级）
│   │   ├── classifier.py           # 意图分类器
│   │   ├── clarification.py        # 澄清引擎
│   │   ├── slot_validator.py       # 槽位验证器
│   │   ├── topic_switch.py         # 话题切换检测
│   │   ├── multi_intent.py         # 多意图处理器 (含独立性判断)
│   │   └── safety.py               # 安全过滤器
│   │
│   ├── models/                     # 数据库模型 (SQLModel)
│   │   ├── __init__.py
│   │   ├── user.py                 # 用户表
│   │   ├── order.py                # 订单表
│   │   ├── refund.py               # 退款申请表
│   │   ├── audit.py                # 审计日志表
│   │   ├── message.py              # 消息卡片表
│   │   ├── knowledge_document.py   # 知识库文档表
│   │   ├── observability.py        # 可观测性模型 (GraphExecutionLog / SupervisorDecision)
│   │   ├── memory.py               # 记忆模型 (UserProfile / UserPreference / InteractionSummary / UserFact / AgentConfig)
│   │   ├── complaint.py            # 投诉工单模型 (ComplaintTicket)
│   │   ├── experiment.py           # A/B 实验模型 (Experiment / Variant / Assignment)
│   │   ├── evaluation.py           # 在线评估模型 (MessageFeedback / QualityScore)
│   │   └── state.py                # AgentState (LangGraph 状态定义)
│   │
│   ├── memory/                     # 记忆系统
│   │   ├── __init__.py
│   │   ├── structured_manager.py   # 结构化记忆管理器 (PostgreSQL)
│   │   ├── vector_manager.py       # 向量对话记忆管理器 (Qdrant conversation_memory)
│   │   ├── extractor.py            # 事实抽取器 (FactExtractor)
│   │   └── summarizer.py           # 会话摘要器 (SessionSummarizer)
│   │
│   ├── services/                   # 业务服务层
│   │   ├── __init__.py
│   │   ├── refund_service.py       # 退款业务逻辑
│   │   ├── status_service.py       # 状态服务
│   │   ├── order_service.py        # 订单服务
│   │   ├── admin_service.py        # 管理员服务
│   │   ├── auth_service.py         # 认证服务
│   │   ├── experiment.py           # A/B 实验服务
│   │   ├── experiment_assigner.py  # 实验流量分配
│   │   └── online_eval.py          # 在线评估服务
│   │
│   ├── schemas/                    # 共享 Schema
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── admin.py
│   │   ├── status.py
│   │   └── agent_config.py
│   │
│   ├── tasks/                      # Celery 异步任务
│   │   ├── __init__.py
│   │   ├── refund_tasks.py         # 退款相关任务
│   │   ├── knowledge_tasks.py      # 知识库同步任务
│   │   ├── memory_tasks.py         # 记忆抽取与同步任务
│   │   └── notifications.py        # 告警通知任务
│   │
│   ├── websocket/                  # WebSocket 服务
│   │   ├── __init__.py
│   │   └── manager.py              # 连接管理器
│   │
│   ├── observability/              # 可观测性
│   │   ├── __init__.py
│   │   ├── otel_setup.py           # OpenTelemetry 初始化
│   │   └── execution_logger.py     # 执行日志记录器
│   │
│   └── evaluation/                 # 离线评估
│       ├── __init__.py
│       ├── pipeline.py             # 评估流水线 (Golden Dataset)
│       └── metrics.py              # 评估指标计算
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
│       │   │   ├── AGENTS.md
│       │   │   ├── hooks/
│       │   │   │   └── useChat.ts
│       │   │   └── components/
│       │   │       ├── ChatMessageList.tsx
│       │   │       └── ChatInput.tsx
│       │   └── admin/              # B端管理后台
│       │       ├── App.tsx
│       │       ├── main.tsx
│       │       ├── AGENTS.md
│       │       ├── pages/
│       │       │   ├── Login.tsx
│       │       │   ├── Dashboard.tsx
│       │       │   ├── KnowledgeBase.tsx     # 知识库管理页面
│       │       │   └── AgentConfig.tsx       # Agent 配置中心页面
│       │       └── components/
│       │           ├── DecisionPanel.tsx
│       │           ├── NotificationToast.tsx
│       │           ├── TaskDetail.tsx
│       │           ├── TaskList.tsx
│       │           ├── ConversationLogs.tsx
│       │           ├── EvaluationViewer.tsx
│       │           ├── Performance.tsx
│       │           ├── KnowledgeBaseManager.tsx  # 知识库文档上传/同步组件
│       │           ├── AgentConfigEditor.tsx     # Agent 配置编辑器组件
│       │           ├── ComplaintQueue.tsx        # 投诉工单管理
│       │           ├── ExperimentManager.tsx     # A/B 实验管理
│       │           └── AnalyticsV2.tsx           # 高级分析面板
│       │
│       ├── components/
│       │   ├── ui/                 # shadcn/ui 组件
│       │   │   ├── accordion.tsx
│       │   │   ├── alert.tsx
│       │   │   ├── avatar.tsx
│       │   │   ├── badge.tsx
│       │   │   ├── button.tsx
│       │   │   ├── card.tsx
│       │   │   ├── dialog.tsx
│       │   │   ├── input.tsx
│       │   │   ├── label.tsx
│       │   │   ├── radio-group.tsx
│       │   │   ├── scroll-area.tsx
│       │   │   ├── separator.tsx
│       │   │   ├── sheet.tsx
│       │   │   ├── skeleton.tsx
│       │   │   ├── switch.tsx
│       │   │   ├── table.tsx
│       │   │   ├── tabs.tsx
│       │   │   └── textarea.tsx
│       │   └── ErrorBoundary.tsx   # 错误边界组件
│       │
│       ├── assets/                 # 静态资源
│       ├── globals.css             # 全局样式
│       ├── env.d.ts                # Vite 环境类型声明
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
│       │   ├── useTasks.ts
│       │   ├── useKnowledgeBase.ts # 知识库管理 Hooks
│       │   ├── useAgentConfig.ts   # Agent 配置管理 Hooks
│       │   ├── useComplaints.ts    # 投诉工单 Hooks
│       │   ├── useEvaluation.ts    # 在线评估 Hooks
│       │   ├── useMetrics.ts       # 指标监控 Hooks
│       │   ├── useAnalytics.ts     # 高级分析 Hooks
│       │   ├── useConversations.ts # 会话日志 Hooks
│       │   └── useExperiments.ts   # A/B 实验 Hooks
│       └── types/                  # TypeScript 类型定义
│           └── index.ts            # 统一类型导出
│
├── scripts/                        # 辅助脚本
│   ├── seed_data.py                # 数据库初始化
│   ├── seed_large_data.py          # 大批量测试数据
│   ├── seed_product_catalog.py     # 商品目录种子数据 (→ Qdrant product_catalog)
│   ├── etl_qdrant.py               # 知识库 ETL (PDF/Markdown → Qdrant)
│   ├── run_evaluation.py           # 离线评估脚本 (Golden Dataset)
│   └── verify_db.py                # 数据库验证脚本
│
├── tests/                          # 后端测试
│   ├── conftest.py                 # pytest 全局 fixtures
│   ├── _db_config.py               # 测试数据库配置
│   ├── AGENTS.md                   # 测试规范
│   ├── test_auth_api.py            # 认证 API 测试
│   ├── test_chat_api.py            # 聊天 API 测试
│   ├── test_admin_api.py           # 管理员 API 测试
│   ├── test_websocket.py           # WebSocket 测试
│   ├── test_auth_rate_limit.py     # 认证限流测试
│   ├── test_order_service.py       # 订单服务测试
│   ├── test_refund_service.py      # 退款服务测试
│   ├── test_admin_service.py       # 管理员服务测试
│   ├── test_auth_service.py        # 认证服务测试
│   ├── test_status_service.py      # 状态服务测试
│   ├── test_security.py            # 安全测试
│   ├── test_main_security.py       # 主应用安全测试
│   ├── test_logging.py             # 日志测试
│   ├── test_chat_utils.py          # 聊天工具测试
│   ├── test_refund_tasks.py        # 退款任务测试
│   ├── test_knowledge_admin.py     # 知识库管理 API 测试
│   ├── test_users.py               # 用户模型测试
│   ├── test_confidence_signals.py  # 置信度信号测试
│   ├── test_observability_api.py   # 可观测性 API 测试
│   ├── admin/                      # 管理员相关测试
│   │   └── test_agent_config_api.py
│   ├── agents/                     # Agent 单元测试
│   ├── tools/                      # Tool 单元测试
│   ├── graph/                      # LangGraph 测试
│   ├── intent/                     # 意图模块测试
│   ├── memory/                     # 记忆系统测试
│   ├── evaluation/                 # 离线评估测试
│   ├── retrieval/                  # RAG 检索测试
│   └── integration/                # 集成测试
│       └── test_workflow_invoke.py
│
├── data/                           # 静态数据
│   ├── shipping_policy.md          # 示例政策文档
│   ├── return_policy.md            # 退货政策文档
│   └── products.json               # 商品目录种子数据
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
*   **LangChain / LangGraph**：用于构建和编排 Agent 的核心逻辑、意图识别、RAG 和多步骤工作流。
*   **SQLModel**：基于 Pydantic 和 SQLAlchemy 的数据库 ORM，提供类型安全的数据模型。
*   **PostgreSQL**：关系型数据库，用于订单、用户、退款、记忆等结构化数据存储。
*   **Qdrant**：向量数据库，用于混合 RAG 检索（Dense + BM25 Sparse + Rerank）。
*   **Redis**：缓存、Celery 消息代理和 LangGraph Checkpointer。
*   **Celery**：异步任务队列，处理耗时操作（如退款支付、短信通知、知识库 ETL 同步、记忆抽取、告警通知）。
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
*   **OpenTelemetry**：分布式链路追踪与可观测性。
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
# 项目配置
PROJECT_NAME=E-commerce Smart Agent
API_V1_STR=/api/v1

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

# Reranker
RERANK_BASE_URL=https://dashscope.aliyuncs.com/compatible-api/v1

# LLM
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
DASHSCOPE_API_KEY=...

# LLM 模型配置（可选，不填时使用默认值）
LLM_MODEL=qwen-plus
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_DIM=1024

# Celery
CELERY_BROKER_URL=redis://:devpassword@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:devpassword@localhost:6379/0

# 安全
SECRET_KEY=...                    # openssl rand -hex 32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# 其他
ENABLE_OPENAPI_DOCS=True
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
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
- 服务：PostgreSQL 16、Redis 7、Qdrant v1.16.3
- 步骤：检出代码 → 设置 Python 3.12 + uv 0.6.5 → 创建 test database → Cache uv dependencies → `uv sync` 安装依赖 → Lint (`uv run ruff check app tests`) → 测试 (`uv run pytest --cov=app --cov-fail-under=75`)

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
