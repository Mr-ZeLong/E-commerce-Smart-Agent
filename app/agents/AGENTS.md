# AGENTS.md - Expert Agents

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for the expert agent fleet.
- Update this file in the same PR when adding new agents, changing conventions, or modifying key file mappings.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for agent-specific guidance.

## Overview

Expert agent fleet based on `BaseAgent` ABC covering orders, policies, products, cart, logistics, account, and payments. Each agent exposes a unified `async process(state) -> AgentProcessResult` entry point and delegates I/O to dedicated tool layers.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Base class | `app/agents/base.py` | `BaseAgent` ABC; `process()` → `AgentProcessResult` |
| Product QA | `app/agents/product.py` + `app/tools/product_tool.py` | Qdrant `product_catalog` semantic retrieval |
| Cart | `app/agents/cart.py` + `app/tools/cart_tool.py` | Redis persistence, 24h TTL |
| Complaint | `app/agents/complaint.py` + `app/tools/complaint_tool.py` | LLM auto-classification + ticket creation |
| Order | `app/agents/order.py` | Order query and management |
| Payment | `app/agents/payment.py` + `app/tools/payment_tool.py` | Payment query and refund processing |
| Logistics | `app/agents/logistics.py` + `app/tools/logistics_tool.py` | Shipping and logistics tracking |
| Account | `app/agents/account.py` + `app/tools/account_tool.py` | User account management |
| Policy | `app/agents/policy.py` | Policy Q&A via RAG retrieval |
| Supervisor | `app/agents/supervisor.py` | Serial/parallel dispatch logic |
| Intent router | `app/agents/router.py` | `IntentRouterAgent` |
| Config hot-reload | `app/agents/config_loader.py` | Redis-cached routing rules and system prompts (60s TTL) |
| Evaluator | `app/agents/evaluator.py` | Agent response quality evaluation |

## Commands

```bash
# Run agent module tests
uv run pytest tests/agents/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Agent-specific conventions:

- **Type hints**: Mandatory on all `BaseAgent` subclass methods and `AgentProcessResult` fields.
- **Docstrings**: Google-style docstrings for all public agent classes and `process()` methods.
- **No sync I/O**: Agents must not perform synchronous blocking calls; all tool/service access is `async`.
- **Config isolation**: Agent-specific prompt templates and routing rules live in `config_loader.py`; never hardcode prompts inside `process()`.

## Testing Patterns

- Use `make_agent_state()` from `app/models/state.py` to construct agent state.
- Mock LLM calls and tool invocations; verify `AgentProcessResult` structure.
- Cover normal flows and edge cases (missing slots, permission checks).
- New agent → new test file under `tests/agents/`.

## Conventions

- **Unified entry**: All `BaseAgent` subclasses must implement `async process(self, state) -> AgentProcessResult`.
- **Hot-reload**: Each agent calls `await self._load_config()` inside `process()` to pick up config changes without restart.
- **Memory injection priority**: summaries → facts/profile → preferences → vector messages.
- **User isolation**: All order/refund/cart queries must filter by `user_id`. Never return cross-user data.
- **Return contract**: `AgentProcessResult` must include `response` (string); optionally carry `updated_state`.

## Anti-Patterns

- **Cross-layer coupling**: `supervisor.py` must not import from `app/graph/parallel.py`.
- **Direct DB access in agents**: Agents should not bypass the tool/service layer to access the database directly.
- **Stale AGENTS.md**: Adding a new agent without updating this file and the corresponding test suite.
