# 技术栈详情

## 后端

| 技术 | 用途 |
|------|------|
| **Python 3.12+** | 主要开发语言 |
| **FastAPI** | 高性能 Web 框架，RESTful API 与 WebSocket 服务 |
| **LangChain / LangGraph** | Agent 核心逻辑、意图识别、RAG、多步骤工作流编排 |
| **SQLModel** | 基于 Pydantic 和 SQLAlchemy 的 ORM |
| **PostgreSQL** | 结构化数据存储（订单、用户、退款、记忆等） |
| **Qdrant** | 向量数据库，混合 RAG 检索（Dense + BM25 Sparse + Rerank） |
| **Redis** | 缓存、Celery Broker、LangGraph Checkpointer |
| **Celery** | 异步任务队列（退款、短信、ETL、记忆抽取、告警） |
| **uv** | 现代化 Python 包管理器 |
| **JWT (PyJWT)** | 用户认证与授权 |
| **bcrypt** | 密码哈希 |
| **slowapi** | API 限流 |
| **OpenTelemetry** | 分布式链路追踪与可观测性 |
| **OpenAI API / Qwen** | LLM 与 Embedding 模型 |
| **Alembic** | 数据库迁移 |
| **ruff** | Python Linter + Formatter |
| **ty** | Python 类型检查器 |
| **pre-commit** | 提交前代码质量门禁 |

## 前端

| 技术 | 用途 |
|------|------|
| **React 19** | 现代前端框架 |
| **TypeScript** | 类型安全 |
| **Vite** | 前端构建工具，支持多页面配置 |
| **Tailwind CSS + PostCSS + shadcn/ui** | 原子化 CSS 与组件库 |
| **Zustand + TanStack Query** | 状态管理 |
| **React Router v7** | 前端路由管理 |
| **Playwright** | E2E 测试 |

## 基础设施与部署

| 技术 | 用途 |
|------|------|
| **Docker / Docker Compose** | 容器化部署 |
| **GitHub Actions** | CI/CD 流水线 |
