# frontend/src/apps/customer KNOWLEDGE BASE

> Guidance for the Customer frontend. Read the root [`AGENTS.md`](../../../AGENTS.md) first for repo-wide rules and commands.

## OVERVIEW
C 端用户聊天界面 SPA，Vite 多页面入口 `index.html`，由 FastAPI 托管静态资源，访问路径为 `/app`。

## WHERE TO LOOK
| 任务 | 文件/目录 | 说明 |
|------|-----------|------|
| 页面路由 | `App.tsx` | 主聊天界面（React Router 单路由） |
| 业务组件 | `components/` | `ChatMessageList.tsx`（消息列表）、`ChatInput.tsx`（输入框） |
| 聊天逻辑 | `hooks/useChat.ts` | SSE 流式对话、消息状态管理 |
| 通用 UI | `../../components/ui/` | shadcn/ui 组件（Button、Input、ScrollArea 等） |
| API 封装 | `../../lib/api.ts` | 统一 axios 实例与请求头工厂 |
| 应用挂载 | `main.tsx` | Vite 多页面挂载点 |

## CONVENTIONS
- **技术栈**：React 19 + TypeScript ~6.0.2 + Tailwind CSS（dark-mode: class）+ shadcn/ui。
- **状态管理**：C 端状态简单，以组件本地 `useState` 为主；聊天状态封装在 `useChat.ts`。
- **流式响应**：`useChat.ts` 通过 `fetch` + `ReadableStream` 消费后端 `/api/v1/chat` SSE 流式返回。
- **API 代理**：开发模式下 Vite 将 `/api` 代理到 `localhost:8000`。
- **类型复用**：消息类型定义在 `../../types/index.ts`。

## ANTI-PATTERNS
- `useChat.ts` 中直接调用原生 `fetch`；应逐步统一为 `../../lib/api.ts` 提供的 axios/fetch 封装，以便统一处理错误、重试和拦截器。
- 避免在 Customer 端引入复杂全局状态；当前会话级状态（消息、加载态）保持在 `useChat.ts` 内即可。
