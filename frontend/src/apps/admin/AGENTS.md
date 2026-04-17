# AGENTS.md - Admin Frontend

> **IMPORTANT**: Read the root [`AGENTS.md`](../../../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- `AGENTS.md` is a living document.
- Keep this file focused on admin-frontend-specific guidance.
- Update this file when adding pages, changing conventions, or modifying build/test commands.

## Read Order

1. Read the root [`AGENTS.md`](../../../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for admin frontend specifics.
3. For architecture details, read [`docs/explanation/architecture/`](../../../../docs/explanation/architecture/).

## Overview

Admin dashboard SPA. Vite multi-page entry via `admin.html`, served by FastAPI as static assets at path `/admin/*`.

## Key Files

| Concern | File / Directory | Notes |
|---------|-------------------|-------|
| Pages | `frontend/src/apps/admin/pages/Login.tsx` | Admin login |
| Pages | `frontend/src/apps/admin/pages/Dashboard.tsx` | Main dashboard |
| Pages | `frontend/src/apps/admin/pages/KnowledgeBase.tsx` | Knowledge base management |
| Pages | `frontend/src/apps/admin/pages/AgentConfig.tsx` | Agent routing & config |
| Pages | `frontend/src/apps/admin/pages/Feedback.tsx` | User feedback management |
| Business components | `frontend/src/apps/admin/components/DecisionPanel.tsx` | Human-in-the-loop task decisions |
| Business components | `frontend/src/apps/admin/components/TaskList.tsx` | Task queue list |
| Business components | `frontend/src/apps/admin/components/ConversationLogs.tsx` | Conversation audit logs |
| Business components | `frontend/src/apps/admin/components/AgentConfigEditor.tsx` | Config editor with hot-reload |
| Business components | `frontend/src/apps/admin/components/KnowledgeBaseManager.tsx` | KB upload & sync |
| Business components | `frontend/src/apps/admin/components/ComplaintQueue.tsx` | Complaint queue |
| Business components | `frontend/src/apps/admin/components/ExperimentManager.tsx` | A/B experiment manager |
| Business components | `frontend/src/apps/admin/components/AnalyticsV2.tsx` | Analytics dashboard |
| Business components | `frontend/src/apps/admin/components/FeedbackManager.tsx` | Feedback management |
| Shared UI | `frontend/src/components/ui/` | shadcn/ui base components (Button, Card, Input, Sheet, etc.) |
| API layer | `frontend/src/lib/api.ts` | Centralized `fetch` wrapper with interceptors |
| Server state hooks | `frontend/src/hooks/` | TanStack Query hooks (useAgentConfig, useTasks, useComplaints, useFeedback, etc.) |
| WebSocket | `frontend/src/hooks/useWebSocket.ts` | WebSocket connection & message listener |
| Auth state | `frontend/src/stores/auth.ts` | Zustand store for auth |
| Router | `frontend/src/apps/admin/App.tsx` | React Router configuration |
| App mount | `frontend/src/apps/admin/main.tsx` | Vite multi-page entry point |

## Commands

```bash
# Development (port 5173, Vite proxies /api → localhost:8000)
cd frontend && npm run dev

# Production build
cd frontend && npm run build

# Lint + auto-fix
cd frontend && npm run lint

# Format
cd frontend && npm run format

# Unit tests (Vitest)
cd frontend && npm run test

# E2E tests (Playwright)
cd frontend && npm run test:e2e
```

## Code Style

General frontend rules are defined in the root `AGENTS.md`. Admin-specific conventions:

- **shadcn/ui**: Prefer base components in `frontend/src/components/ui/`. Do not re-invent primitives.
- **Server-state hooks**: TanStack Query hooks should live in `frontend/src/hooks/` and be reused across admin pages.
- **Auth boundaries**: Admin pages requiring authentication must gate rendering via `frontend/src/stores/auth.ts`.

## Testing Patterns

- **E2E**: Playwright for critical flows (login, task decisions, knowledge sync, agent config editing).
- **Unit**: Vitest for hooks and pure utilities. Mock API calls in unit tests.
- **Component**: Verify props rendering, user interaction callbacks, and error boundary behavior.

## Conventions

- **State**: Server state via TanStack Query; client auth state via `frontend/src/stores/auth.ts` (Zustand). Do not introduce redundant global state.
- **API calls**: Never call `fetch` directly in components. Use `frontend/src/lib/api.ts` or TanStack Query hooks.
- **Hot-reload config**: Agent config edits are written to the backend and take effect immediately (Redis cache invalidation). No service restart required.
- **Vite proxy**: In dev mode, `/api` is proxied to `localhost:8000`; no manual CORS handling needed.
- **Merge requirements**: All merges require `npm run build`, `npm run lint`, `npm run format`, and `npm run test:e2e` to pass.

## Anti-Patterns

- Do not call `fetch` directly in components — use `frontend/src/lib/api.ts` or TanStack Query hooks.
- Do not introduce Redux or other complex client-side state managers. Zustand + TanStack Query is sufficient.
