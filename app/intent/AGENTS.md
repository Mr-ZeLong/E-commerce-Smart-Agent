# app/intent KNOWLEDGE BASE

> Guidance for intent recognition pipeline. Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules and commands.

## OVERVIEW
意图识别 Pipeline 与多意图处理模块，决定用户输入如何被路由以及是否允许并行执行。

## Key Files

| 任务 | 文件 | 说明 |
|------|------|------|
| 主 Pipeline | `@app/intent/service.py` | `IntentRecognitionService`，Redis 会话缓存 |
| 意图分类 | `@app/intent/classifier.py` | 意图分类器实现 |
| 多意图/独立性 | `@app/intent/multi_intent.py` | `are_independent()` 控制 LangGraph 并行调度 |
| 澄清引擎 | `@app/intent/clarification.py` | 槽位缺失时的澄清交互 |
| 槽位验证 | `@app/intent/slot_validator.py` | 槽位值校验 |
| 话题切换 | `@app/intent/topic_switch.py` | 检测话题漂移 |
| 安全过滤 | `@app/intent/safety.py` | 输入安全审查 |

## Commands

```bash
# 运行意图模块相关测试
uv run pytest tests/intent/
```

## Testing Patterns

- 意图分类器测试使用 mock LLM 响应，覆盖单意图、多意图和未知意图场景。
- `@tests/intent/test_multi_intent.py` 验证 `are_independent()` 的独立性判定矩阵。
- 澄清引擎测试覆盖槽位缺失、追问生成和澄清结束条件。
- 安全过滤测试应按 concern（敏感词、注入攻击、隐私信息）拆分为独立测试文件或 describe 块。

## Related Files

- `@app/graph/parallel.py` — 消费 `are_independent()` 的结果构造 `Send` 实现多意图并行执行。

## CONVENTIONS

- **Pipeline 顺序**：SafetyFilter → Redis cache → Classifier / MultiIntent → TopicSwitchDetector → SlotValidator → ClarificationEngine。
- **并行判定**：`are_independent()` 返回 `True` 时，`@app/graph/parallel.py` 会构造多个 `Send` 实现多意图并行执行。
- **状态模型**：意图与槽位结果显式写入 `AgentState.intent_result` / `AgentState.slots`。
- **安全优先**：`safety.py` 在任何 LLM 调用之前执行，拦截违规输入。

## ANTI-PATTERNS

- `@app/graph/parallel.py` 直接导入 `@app/intent/multi_intent.py`，意图层与图编排层耦合。
- 避免在 `@app/intent/safety.py` 中堆积大量规则导致性能下降；高频规则应前置或缓存。
- 不要在 `classifier.py` 中直接修改全局状态，所有输出应写入传入的 `state` 对象。
