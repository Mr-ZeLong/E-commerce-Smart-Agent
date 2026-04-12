# frontend/src/apps/admin KNOWLEDGE BASE

> Guidance for the Admin frontend. Read the root [`AGENTS.md`](../../../AGENTS.md) first for repo-wide rules and commands.

## OVERVIEW
B 端管理员后台 SPA，Vite 多页面入口 `admin.html`，由 FastAPI 托管静态资源，访问路径为 `/admin/*`。

## WHERE TO LOOK
| 任务 | 文件/目录 | 说明 |
|------|-----------|------|
| 页面路由 | `pages/` | `Login.tsx`、`Dashboard.tsx`、`KnowledgeBase.tsx`、`AgentConfig.tsx` |
| 业务组件 | `components/` | `DecisionPanel.tsx`、`TaskList.tsx`、`ConversationLogs.tsx`、`AgentConfigEditor.tsx`、`KnowledgeBaseManager.tsx` 等 |
| 通用 UI | `../../components/ui/` | shadcn/ui 组件（Button、Card、Input、Sheet 等） |
| API 封装 | `../../lib/api.ts` | 统一 axios 实例与拦截器 |
| 服务端状态 | `../../hooks/` | `useAgentConfig.ts`、`useKnowledgeBase.ts`、`useTasks.ts`、`useNotifications.ts` 等 TanStack Query 封装 |
| 路由入口 | `App.tsx` | React Router 配置 |
| 应用挂载 | `main.tsx` | Vite 多页面挂载点 |

## CONVENTIONS
- **技术栈**：React 19 + TypeScript ~6.0.2 + Tailwind CSS（dark-mode: class）+ shadcn/ui + TanStack Query。
- **状态管理**：服务端状态统一使用 TanStack Query；客户端认证状态使用 `../../stores/auth.ts`（Zustand）。Admin 端避免引入冗余全局状态。
- **组件风格**：优先使用 shadcn/ui 基组件；业务组件保持单一职责， props 接口显式类型化。
- **API 代理**：开发模式下 Vite 将 `/api` 代理到 `localhost:8000`，无需手动处理 CORS。
- **热重载配置**：Agent 配置编辑后写入后端即生效（Redis 缓存失效），无需重启服务。
- **E2E 测试**：关键交互流（登录、任务决策、知识库同步）应覆盖 Playwright E2E 测试。

## ANTI-PATTERNS
- 不要在前端组件中直接调用 `fetch`；统一使用 `../../lib/api.ts` 或 TanStack Query hooks。
- 不要在 Admin 端引入复杂的客户端状态管理（如 Redux），已有 Zustand + TanStack Query 足够。
- 前端构建与测试步骤目前完全缺失于 CI，需手动确保 `npm run build` / `npm run test:e2e` 通过后再合并。
