# app/memory KNOWLEDGE BASE

> Guidance for the memory system. Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules and commands.

## OVERVIEW
Phase 3 记忆系统，包含结构化记忆（PostgreSQL）、向量对话记忆（Qdrant）以及记忆抽取 Pipeline。

## WHERE TO LOOK
| 任务 | 文件 | 说明 |
|------|------|------|
| 结构化记忆 CRUD | `structured_manager.py` | `UserProfile` / `UserPreference` / `InteractionSummary` / `UserFact` |
| 向量对话记忆 | `vector_manager.py` | Qdrant `conversation_memory` 集合，语义检索历史消息 |
| 事实抽取 | `extractor.py` | `FactExtractor`（`qwen-turbo` + JSON Schema） |
| 会话摘要 | `summarizer.py` | `SessionSummarizer`，摘要双写 PostgreSQL + Qdrant |

## CONVENTIONS
- **置信度过滤**：`FactExtractor` 提取的事实 `confidence < 0.7` 直接丢弃。
- **PII 保护**：内置正则过滤身份证号、手机号、银行卡号，命中时整句事实被丢弃。
- **异步触发**：`decider_node` 回合结束后通过 Celery 任务 `extract_and_save_facts` 异步抽取，不阻塞 SSE。
- **查询隔离**：所有结构化记忆查询必须按 `user_id` 过滤，禁止越权访问。

## ANTI-PATTERNS
- 避免在 Prompt 中一次性塞入过长的 `memory_context`，应控制总长度防止污染对话。
- 避免在记忆抽取任务中同步调用外部 LLM；始终通过 Celery 异步执行。
