# AGENTS.md - WebSocket

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for WebSocket connection management.
- Update this file in the same PR when adding new WebSocket features or changing connection handling.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for WebSocket-specific guidance.

## Overview

WebSocket connection manager for real-time chat between users and the agent system. Supports both user connections (`/ws/{thread_id}`) and admin connections (`/ws/admin/{admin_id}`).

## Key Files

| Role | File | Notes |
|------|------|-------|
| Connection manager | `app/websocket/manager.py` | `ConnectionManager` for user/admin WebSocket connections |
| Redis bridge | `app/websocket/redis_bridge.py` | Redis pub/sub bridge for cross-instance WebSocket messaging |

## Code Style

General Python rules are defined in the root `AGENTS.md`. WebSocket-specific conventions:

- **Type hints**: All WebSocket handler methods must be fully typed.
- **Error handling**: Handle connection drops gracefully; clean up resources on disconnect.
- **Async**: All WebSocket operations must be `async`.

## Testing Patterns

- Mock WebSocket connections in unit tests.
- Test connection lifecycle (connect, message, disconnect).
- Verify message broadcasting and targeted delivery.
- Test error handling for dropped connections.

## Conventions

- **Connection isolation**: User and admin connections are isolated; never broadcast admin messages to users.
- **Message format**: Use structured JSON messages with `type` and `payload` fields.
- **Heartbeat**: Implement ping/pong heartbeat to detect stale connections.
- **Cleanup**: Remove disconnected clients from connection pools immediately.

## Anti-Patterns

- **Blocking in handlers**: Never perform blocking I/O inside WebSocket message handlers.
- **Unbounded connections**: Limit concurrent connections per user/admin to prevent resource exhaustion.
- **Missing cleanup**: Always clean up connection resources on disconnect to prevent memory leaks.

## Related Files

- `app/api/v1/websocket.py` — FastAPI WebSocket route definitions.
- `frontend/src/hooks/useWebSocket.ts` — Frontend WebSocket client.
