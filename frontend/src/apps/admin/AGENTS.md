# frontend/src/apps/admin KNOWLEDGE BASE

> Guidance for the Admin frontend. Read the root [`AGENTS.md`](../../../../AGENTS.md) first for repo-wide rules and commands.

## OVERVIEW
B 端管理员后台 SPA，Vite 多页面入口 `admin.html`，由 FastAPI 托管静态资源，访问路径为 `/admin/*`。

## Key Files

| 任务 | 文件/目录 | 说明 |
|------|-----------|------|
| 页面路由 | `@frontend/src/apps/admin/pages/Login.tsx`、`@frontend/src/apps/admin/pages/Dashboard.tsx`、`@frontend/src/apps/admin/pages/KnowledgeBase.tsx`、`@frontend/src/apps/admin/pages/AgentConfig.tsx` | 主要页面组件 |
| 业务组件 | `@frontend/src/apps/admin/components/DecisionPanel.tsx`、`@frontend/src/apps/admin/components/TaskList.tsx`、`@frontend/src/apps/admin/components/ConversationLogs.tsx`、`@frontend/src/apps/admin/components/AgentConfigEditor.tsx`、`@frontend/src/apps/admin/components/KnowledgeBaseManager.tsx`、`@frontend/src/apps/admin/components/ComplaintQueue.tsx`、`@frontend/src/apps/admin/components/ExperimentManager.tsx`、`@frontend/src/apps/admin/components/AnalyticsV2.tsx`、`@frontend/src/apps/admin/components/FeedbackManager.tsx` | 业务逻辑组件 |
| 反馈页面 | `@frontend/src/apps/admin/pages/Feedback.tsx` | 用户反馈管理页面 |
| 通用 UI | `@frontend/src/components/ui/` | shadcn/ui 组件（Button、Card、Input、Sheet 等） |
| API 封装 | `@frontend/src/lib/api.ts` | 统一 `fetch` 封装与拦截器 |
| 服务端状态 | `@frontend/src/hooks/` | TanStack Query 封装（useAgentConfig、useTasks、useComplaints、useFeedback 等） |
| WebSocket | `@frontend/src/hooks/useWebSocket.ts` | WebSocket 连接管理与消息监听 |
| 认证状态 | `@frontend/src/stores/auth.ts` | Zustand 认证状态 |
| 路由入口 | `@frontend/src/apps/admin/App.tsx` | React Router 配置 |
| 应用挂载 | `@frontend/src/apps/admin/main.tsx` | Vite 多页面挂载点 |

## Commands

```bash
# 开发模式（端口 5173，代理 /api → localhost:8000）
cd frontend && npm run dev

# 生产构建
cd frontend && npm run build

# 代码检查与自动修复
cd frontend && npm run lint

# 代码格式化
cd frontend && npm run format

# 单元测试
cd frontend && npm run test

# E2E 测试
cd frontend && npm run test:e2e
```

## Code Style

- **TypeScript**：遵循 `tsconfig.json` 的 strict 模式，禁止隐式 `any`。
- **组件**：优先使用函数式组件，props 接口必须显式定义。
- **Hooks**：自定义 hook 和工具函数必须声明显式返回类型。
- **样式**：统一使用 Tailwind CSS 工具类；暗色模式使用 `dark:` 前缀配合 `dark-mode: class` 策略。
- **shadcn/ui**：优先使用 `@frontend/src/components/ui/` 中的基础组件，避免重复造轮子。

## Testing Patterns

- **E2E 测试**：使用 Playwright 覆盖关键交互流（登录、任务决策、知识库同步、Agent 配置编辑）。
- **单元测试**：使用 Vitest 测试 hooks 和纯工具函数；API 调用在单元测试中应被 mock。
- **组件测试**：验证 props 渲染、用户交互回调和错误边界行为。

## CONVENTIONS

- **技术栈**：React 19 + TypeScript ~6.0.2 + Tailwind CSS（dark-mode: class）+ shadcn/ui + TanStack Query。
- **状态管理**：服务端状态统一使用 TanStack Query；客户端认证状态使用 `@frontend/src/stores/auth.ts`（Zustand）。Admin 端避免引入冗余全局状态。
- **组件风格**：优先使用 shadcn/ui 基组件；业务组件保持单一职责，props 接口显式类型化。
- **API 代理**：开发模式下 Vite 将 `/api` 代理到 `localhost:8000`，无需手动处理 CORS。
- **热重载配置**：Agent 配置编辑后写入后端即生效（Redis 缓存失效），无需重启服务。
- **API 调用**：禁止在组件中直接调用 `fetch`；统一使用 `@frontend/src/lib/api.ts` 或 TanStack Query hooks。

## ANTI-PATTERNS

- 不要在前端组件中直接调用 `fetch`；统一使用 `@frontend/src/lib/api.ts` 或 TanStack Query hooks。
- 不要在 Admin 端引入复杂的客户端状态管理（如 Redux），已有 Zustand + TanStack Query 足够。
- 前端代码合并前需确保 `npm run build`、`npm run lint`、`npm run format` 和 `npm run test:e2e` 通过。
