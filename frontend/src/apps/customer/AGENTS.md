# AGENTS.md - Customer Frontend

> **IMPORTANT**: Read the root [`AGENTS.md`](../../../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- `AGENTS.md` is a living document.
- Keep this file concise and focused on Customer frontend specifics.
- Update this file when adding/modifying Customer frontend conventions, key files, or patterns.

## Read Order

1. Read the root [`AGENTS.md`](../../../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for Customer frontend-specific guidance.

## Overview

Customer-facing chat SPA. Vite multi-page entry via `index.html`, served by FastAPI static middleware at path `/app`. React 19 + TypeScript.

## Key Files

| Task         | File                                                        | Notes                                                  |
| ------------ | ----------------------------------------------------------- | ------------------------------------------------------ |
| Page routing | `frontend/src/apps/customer/App.tsx`                        | Single-route chat interface (React Router)             |
| App mount    | `frontend/src/apps/customer/main.tsx`                       | Vite multi-page mount point                            |
| Chat logic   | `frontend/src/apps/customer/hooks/useChat.ts`               | SSE streaming, message state management                |
| Message list | `frontend/src/apps/customer/components/ChatMessageList.tsx` | Message rendering                                      |
| Chat input   | `frontend/src/apps/customer/components/ChatInput.tsx`       | User input box                                         |
| Shared UI    | `frontend/src/components/ui/`                               | shadcn/ui components (Button, Input, ScrollArea, etc.) |
| API wrapper  | `frontend/src/lib/api.ts`                                   | Unified `fetch` with request header factory            |
| Shared types | `frontend/src/types/index.ts`                               | Message types and common TypeScript types              |

## Commands

```bash
# Development (port 5173, proxies /api → localhost:8000, accessed at /app)
cd frontend && npm run dev

# Production build
cd frontend && npm run build

# Lint with auto-fix
cd frontend && npm run lint

# Format
cd frontend && npm run format

# Unit tests
cd frontend && npm run test

# E2E tests
cd frontend && npm run test:e2e
```

## Code Style

General frontend rules are defined in the root `AGENTS.md`. Customer-specific conventions:

- **SSE handling**: `useChat.ts` uses `apiFetch` from `frontend/src/lib/api.ts` combined with `ReadableStream` to consume SSE. Error handling is centralized in `apiFetch` interceptors.
- **Component scope**: Keep Customer components focused on chat UI; avoid adding admin-specific logic.
- **Hook boundaries**: All chat-related async logic (stream parsing, message ordering) lives inside `hooks/useChat.ts`.

## Testing Patterns

- **Hook tests**: Use Vitest + `@testing-library/react` to test `hooks/useChat.ts`. Mock SSE stream data and event callbacks.
- **E2E tests**: Use Playwright to cover the main chat flow (send message, receive SSE streaming response, error display).
- **Component tests**: Verify message rendering and loading state in `ChatMessageList.tsx`, input validation and submission behavior in `ChatInput.tsx`.

## Conventions

- **State management**: Customer state is simple, primarily component-local `useState`. Chat state is encapsulated in `hooks/useChat.ts`.
- **API calls**: Always use `apiFetch` from `frontend/src/lib/api.ts`. Never use raw `fetch` directly.
- **Streaming**: `hooks/useChat.ts` consumes backend `/api/v1/chat` SSE stream via `apiFetch` + `ReadableStream`.
- **API proxy**: In dev mode, Vite proxies `/api` to `localhost:8000`.
- **Type reuse**: Message types are defined in `frontend/src/types/index.ts`.
- **Single source of truth**: All chat-related state (message list, loading, error) is managed in `hooks/useChat.ts`.

## Anti-Patterns

- Do not bypass `apiFetch` with raw `fetch` in Customer frontend components. All HTTP requests must go through `frontend/src/lib/api.ts`.
- Do not introduce complex global state. Session-level state (messages, loading) stays inside `hooks/useChat.ts`.
- Do not write business logic directly in JSX. Extract complex interactions into hooks or utility functions.
