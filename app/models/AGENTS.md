# AGENTS.md - Models

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for data models.
- Update this file in the same PR when adding new models or changing model conventions.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for model-specific guidance.

## Overview

SQLModel/Pydantic data models for database entities and agent state. Defines the data layer used by services, tools, and memory managers.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Agent state | `app/models/state.py` | `AgentState` TypedDict, `AgentProcessResult`, `make_agent_state()` factory |
| Memory models | `app/models/memory.py` | `UserProfile`, `UserPreference`, `InteractionSummary`, `UserFact`, `AgentConfig`, `RoutingRule` |
| User model | `app/models/user.py` | User account model |
| Order model | `app/models/order.py` | Order entity model |
| Refund model | `app/models/refund.py` | Refund request model |
| Complaint model | `app/models/complaint.py` | Complaint ticket model |
| Message model | `app/models/message.py` | Chat message model |
| Evaluation models | `app/models/evaluation.py` | Evaluation run and result models |
| Knowledge document | `app/models/knowledge_document.py` | Knowledge base document model |
| Experiment models | `app/models/experiment.py` | A/B experiment and variant models |
| Observability | `app/models/observability.py` | `SupervisorDecision`, `GraphExecutionLog` models |
| Multi-intent log | `app/models/multi_intent_log.py` | `MultiIntentDecisionLog` model |
| Prompt effect | `app/models/prompt_effect_report.py` | Prompt effect report model |
| Audit log | `app/models/audit.py` | Audit log model |

## Commands

```bash
# Run model tests
uv run pytest tests/models/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Model-specific conventions:

- **Type hints**: All model fields must have explicit type annotations.
- **Validation**: Use Pydantic validators for complex field validation.
- **Relationships**: Use SQLModel relationship fields with explicit back-populates.
- **Defaults**: Provide sensible defaults for optional fields.

## Testing Patterns

- Test model validation with valid and invalid data.
- Verify relationship cascading behavior.
- Test `make_agent_state()` factory with various configurations.

## Conventions

- **Table names**: Use plural snake_case for table names (e.g., `users`, `orders`).
- **Primary keys**: Use auto-incrementing integers for primary keys.
- **Timestamps**: Include `created_at` and `updated_at` on all models.
- **Soft deletes**: Use `is_deleted` flag rather than hard deletion where appropriate.

## Anti-Patterns

- **Business logic in models**: Keep models as data containers; no business logic.
- **Circular imports**: Avoid circular imports between model files.
- **Missing indexes**: Add database indexes on frequently queried fields.

## Related Files

- `app/core/database.py` — Database engine and session configuration.
- `app/memory/structured_manager.py` — CRUD operations for memory models.
- `migrations/` — Alembic migrations for model changes.
