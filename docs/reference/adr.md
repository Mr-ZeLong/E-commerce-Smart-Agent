# 架构决策记录 (ADR)

## ADR-001: 使用 LangGraph 作为对话编排引擎

**决策**: 采用 LangGraph 构建对话状态机，支持多意图并行执行与状态持久化。

**原因**:
- 电商客服场景存在明显的多轮对话与分支决策需求
- LangGraph 的 `Send` 机制天然支持多意图并行调度
- 与 LangChain 生态无缝集成，便于接入多种 LLM

**权衡**:
- 学习曲线较陡峭，但长期可维护性优于纯手写状态机
- 引入了对 Redis Checkpointer 的依赖

## ADR-002: WebSocket + Redis Pub/Sub 实现实时通知

**决策**: 使用原生 WebSocket 连接，跨进程广播通过 Redis Pub/Sub 桥接。

**原因**:
- FastAPI 原生支持 WebSocket，实现简单
- Celery worker 需要向管理员推送告警，必须支持跨进程通信
- Redis 已是项目依赖组件，无需引入额外消息队列

**权衡**:
- 不支持 WebSocket 会话的持久化恢复（用户断连后消息可能丢失）
- 对于超大规模并发，可能需要升级到专用消息队列（如 RabbitMQ）

## ADR-003: 前后端分离 + Vite 多页面

**决策**: 前端使用 Vite 构建为 SPA，通过 `admin.html` 与 `index.html` 区分管理员与用户入口。

**原因**:
- 管理员后台与用户端交互模式差异大，分离页面减少代码耦合
- Vite 开发体验好，构建速度快
- FastAPI 托管静态资源，部署简单

**权衡**:
- 不采用 SSR，SEO 能力弱（但后台管理系统对 SEO 无需求）
