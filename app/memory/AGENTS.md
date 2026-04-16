# app/memory KNOWLEDGE BASE

> Guidance for the memory system. Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules and commands.

## OVERVIEW
记忆系统，包含结构化记忆（PostgreSQL）、向量对话记忆（Qdrant）以及记忆抽取 Pipeline。

## Key Files

| 任务 | 文件 | 说明 |
|------|------|------|
| 结构化记忆 CRUD | `@app/memory/structured_manager.py` | `UserProfile` / `UserPreference` / `InteractionSummary` / `UserFact` |
| 向量对话记忆 | `@app/memory/vector_manager.py` | Qdrant `conversation_memory` 集合，语义检索历史消息 |
| 事实抽取 | `@app/memory/extractor.py` | `FactExtractor`（`qwen-turbo` + Prompt-based JSON 输出解析） |
| 会话摘要 | `@app/memory/summarizer.py` | `SessionSummarizer`，摘要双写 PostgreSQL + Qdrant |
| 异步任务 | `@app/tasks/memory_tasks.py` | Celery 记忆抽取与同步任务 |
| 数据模型 | `@app/models/memory.py` | 记忆相关 SQLModel 定义 |

## Commands

```bash
# 运行记忆系统相关测试
uv run pytest tests/memory/
```

## Testing Patterns

- 结构化记忆单元测试中 mock PostgreSQL 会话，验证 CRUD 和 `user_id` 隔离。
- 向量记忆单元测试中 mock Qdrant 客户端，验证写入、检索和删除逻辑。
- `FactExtractor` 测试使用 stubbed LLM 响应，覆盖 Prompt JSON 输出解析和置信度过滤。
- PII 过滤测试应覆盖信用卡号（`\\b\\d{13,19}\\b`）和密码（`password[:\\s]*\\S+`）的命中与跳过行为。
- Celery 任务测试在 `@tests/memory/test_memory_tasks.py` 中验证 `extract_and_save_facts` 的异步执行流程。

## Related Files

- `@app/graph/nodes.py` — `memory_node` 负责在图执行前后注入/存储记忆。
- `@app/tasks/memory_tasks.py` — `extract_and_save_facts` 在 `decider_node` 后异步触发。

## CONVENTIONS

- **置信度过滤**：`FactExtractor` 提取的事实 `confidence < 0.7` 直接丢弃。
- **PII 保护**：`@app/memory/extractor.py` 使用正则过滤信用卡号（`\\b\\d{13,19}\\b`）和密码（`password[:\\s]*\\S+`），命中时跳过事实抽取。
- **异步触发**：`decider_node` 回合结束后通过 Celery 任务 `extract_and_save_facts` 异步抽取，不阻塞 SSE。
- **查询隔离**：所有结构化记忆查询必须按 `user_id` 过滤，禁止越权访问。
- **摘要双写**：`SessionSummarizer` 将摘要同时写入 PostgreSQL（`InteractionSummary`）和 Qdrant（向量形式）。

## ANTI-PATTERNS

- 避免在 Prompt 中一次性塞入过长的 `memory_context`，应控制总长度防止污染对话。
- 避免在记忆抽取任务中同步调用外部 LLM；始终通过 Celery 异步执行。
- 不要在 `structured_manager.py` 中返回未按 `user_id` 过滤的批量查询结果。
