# frontend/src/apps/customer KNOWLEDGE BASE

> Guidance for the Customer frontend. Read the root [`AGENTS.md`](../../../../AGENTS.md) first for repo-wide rules and commands.

## OVERVIEW
C 端用户聊天界面 SPA，Vite 多页面入口 `index.html`，由 FastAPI 托管静态资源，访问路径为 `/app`。

## Key Files

| 任务 | 文件/目录 | 说明 |
|------|-----------|------|
| 页面路由 | `@frontend/src/apps/customer/App.tsx` | 主聊天界面（React Router 单路由） |
| 业务组件 | `@frontend/src/apps/customer/components/ChatMessageList.tsx` | 消息列表渲染 |
| 业务组件 | `@frontend/src/apps/customer/components/ChatInput.tsx` | 用户输入框 |
| 聊天逻辑 | `@frontend/src/apps/customer/hooks/useChat.ts` | SSE 流式对话、消息状态管理 |
| 通用 UI | `@frontend/src/components/ui/` | shadcn/ui 组件（Button、Input、ScrollArea 等） |
| API 封装 | `@frontend/src/lib/api.ts` | 统一 `fetch` 封装与请求头工厂 |
| 类型定义 | `@frontend/src/types/index.ts` | 消息类型与通用 TypeScript 类型 |
| 应用挂载 | `@frontend/src/apps/customer/main.tsx` | Vite 多页面挂载点 |

## Commands

```bash
# 开发模式（端口 5173，代理 /api → localhost:8000，访问 /app）
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
- **SSE 处理**：`useChat.ts` 使用 `@frontend/src/lib/api.ts` 提供的 `apiFetch` 结合 `ReadableStream` 消费 SSE，错误处理统一在 `apiFetch` 拦截器中完成。

## Testing Patterns

- **Hook 测试**：使用 Vitest + `testing-library/react` 测试 `@frontend/src/apps/customer/hooks/useChat.ts`，mock SSE 流数据和事件回调。
- **E2E 测试**：使用 Playwright 覆盖聊天主流程（发送消息、接收 SSE 流式响应、错误提示）。
- **组件测试**：验证 `ChatMessageList.tsx` 的消息渲染和加载态，`ChatInput.tsx` 的输入校验与提交行为。

## CONVENTIONS

- **技术栈**：React 19 + TypeScript ~6.0.2 + Tailwind CSS（dark-mode: class）+ shadcn/ui。
- **状态管理**：C 端状态简单，以组件本地 `useState` 为主；聊天状态封装在 `@frontend/src/apps/customer/hooks/useChat.ts`。
- **流式响应**：`@frontend/src/apps/customer/hooks/useChat.ts` 通过 `apiFetch` + `ReadableStream` 消费后端 `/api/v1/chat` SSE 流式返回。
- **API 代理**：开发模式下 Vite 将 `/api` 代理到 `localhost:8000`。
- **类型复用**：消息类型定义在 `@frontend/src/types/index.ts`。
- **单一数据源**：所有聊天相关状态（消息列表、加载态、错误态）集中在 `@frontend/src/apps/customer/hooks/useChat.ts` 管理。

## ANTI-PATTERNS

- 禁止在 Customer 端组件中绕过 `apiFetch` 直接调用原生 `fetch`；所有 HTTP 请求应通过 `@frontend/src/lib/api.ts` 封装完成。
- 避免在 Customer 端引入复杂全局状态；当前会话级状态（消息、加载态）保持在 `@frontend/src/apps/customer/hooks/useChat.ts` 内即可。
- 禁止将业务逻辑直接写在 JSX 中；复杂交互应抽离为 hook 或工具函数。
