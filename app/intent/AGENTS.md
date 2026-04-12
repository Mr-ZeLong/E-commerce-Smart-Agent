# app/intent KNOWLEDGE BASE

> Guidance for intent recognition pipeline. Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules and commands.

## OVERVIEW
意图识别 Pipeline 与多意图处理模块，决定用户输入如何被路由以及是否允许并行执行。

## WHERE TO LOOK
| 任务 | 文件 | 说明 |
|------|------|------|
| 主 Pipeline | `service.py` | `IntentRecognitionService`，Redis 会话缓存 |
| 意图分类 | `classifier.py` | 意图分类器实现 |
| 多意图/独立性 | `multi_intent.py` | `are_independent()` 控制 LangGraph 并行调度 |
| 澄清引擎 | `clarification.py` | 槽位缺失时的澄清交互 |
| 槽位验证 | `slot_validator.py` | 槽位值校验 |
| 话题切换 | `topic_switch.py` | 检测话题漂移 |
| 安全过滤 | `safety.py` | 输入安全审查 |

## CONVENTIONS
- **Pipeline 顺序**：SafetyFilter → Redis cache → Classifier / MultiIntent → TopicSwitchDetector → SlotValidator → ClarificationEngine。
- **并行判定**：`are_independent()` 返回 `True` 时，`app/graph/parallel.py` 会构造多个 `Send` 实现多意图并行执行。
- **状态模型**：意图与槽位结果写入 `AgentState.intent` / `AgentState.slots`。

## ANTI-PATTERNS
- `app/graph/parallel.py` 直接导入 `app.intent.multi_intent.are_independent`，意图层与图编排层耦合。
- 避免在 `safety.py` 中堆积大量规则导致性能下降；高频规则应前置或缓存。
