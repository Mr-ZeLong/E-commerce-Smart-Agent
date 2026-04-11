# 第三阶段: 记忆系统与 Agent 协作

> **周期**: 2–3 个月 (M6–M8)  
> **主题**: *Agent 记得你。*  
> **目标**: 构建长期结构化记忆与向量记忆，使 Agent 能够个性化回复、避免重复提问，并在跨会话场景中更高效协作。

---

## 1. 阶段目标

通过在每次 Agent invocation 中集成两层记忆，实现**跨会话的个性化**:
1. **结构化记忆** (PostgreSQL): 用户画像、偏好事实、 recurring issue 模式、对话摘要。
2. **向量记忆** (Qdrant `conversation_memory`): 通过语义检索获取相关历史对话，辅助当前回答。

到第三阶段末，Agent 应能恰当地问候回头客、回忆过往的退款问题，并基于历史兴趣推荐政策。

---

## 2. 关键任务

### 2.1 结构化记忆 (M6)

**任务 P3-M1: 记忆 Schema 设计**
- 在 `app/models/memory.py` 中新增 SQLModel 表:
  - `UserProfile`: 会员等级、偏好语言、时区、总订单数、生命周期价值。
  - `UserPreference`: 键值对（`preferred_contact_time`、`common_categories`、`last_refund_reason`）。
  - `InteractionSummary`: 每个完成 thread 一行，含 `summary_text`、`resolved_intent`、`satisfaction_score`。
  - `UserFact`: 从对话中提取的原子事实（`user_id`、`fact_type`、`fact_value`、`confidence`、`source_thread_id`）。

**任务 P3-M2: 记忆抽取 Pipeline**
- 新增模块: `app/memory/extractor.py`。
- 在 `decider_node` 后增加异步抽取步骤（Celery 任务），解析整个会话并提取 0-N 条 `UserFact`。
- 使用轻量 LLM（`qwen-turbo`）配合结构化输出 JSON schema。
- `confidence < 0.7` 的事实丢弃或进入人工复核队列。

**任务 P3-M3: 记忆管理器**
- 新增模块: `app/memory/structured_manager.py`。
- API:
  ```python
  async def get_user_facts(user_id: int, fact_types: list[str] | None = None) -> list[UserFact]: ...
  async def get_user_profile(user_id: int) -> UserProfile | None: ...
  async def save_interaction_summary(user_id: int, thread_id: str, summary: str) -> None: ...
  ```

### 2.2 向量会话记忆 (M6–M7)

**任务 P3-V1: Qdrant Collection 搭建**
- 在现有 Qdrant 集群中创建 `conversation_memory` collection。
- 仅 dense vector（1024 维，Cosine）。
- Payload: `user_id`、`thread_id`、`message_role`、`content`、`timestamp`、`intent`。

**任务 P3-V2: 对话嵌入 Pipeline**
- 新增模块: `app/memory/vector_manager.py`。
- 每条 assistant 与 user 消息被异步嵌入并 upsert 到 `conversation_memory`。
- 处理新查询前，为同一 `user_id` 检索 top-k（k=5）语义最相近的历史消息。
- 检索到的消息以伪轮次形式注入 `AgentState.history`，前缀标记为 `[来自你的历史对话]`。

**任务 P3-V3: 记忆修剪**
- Celery 定时任务（每日）删除超过 90 天的向量消息。
- 通过 `MEMORY_RETENTION_DAYS` 环境变量可配置。

### 2.3 记忆感知的 Agent Prompting (M7)

**任务 P3-A1: BaseAgent 增强**
- 更新 `BaseAgent._create_messages()`，新增接受 `memory_context` 字典的参数。
- `memory_context` 包含:
  - `structured_facts`: 用户事实列表
  - `relevant_past_messages`: 检索到的历史轮次列表
  - `user_profile`: 用户画像摘要

**任务 P3-A2: Prompt 工程**
- 每个专家 Agent 的 system prompt 增加 "User Context" 区域:
  ```
  [User Context]
  - Membership: Gold
  - Frequent categories: Electronics, Home
  - Recent issue: Refund for order SN20240015 (resolved)
  ```
- 在当前用户问题前追加历史对话片段。

### 2.4 会话摘要 (M7)

**任务 P3-S1: 会话摘要器**
- 新增模块: `app/memory/summarizer.py`。
- 触发条件: thread 轮次 >20 或自然结束（`needs_human_transfer=False` 且无待澄清项）。
- 生成一段摘要并存入 `InteractionSummary`。
- 向量检索时优先使用摘要而非原始消息轮次。

### 2.5 B端 Agent 配置中心 (M7–M8)

**任务 P3-B1: 配置 Schema**
- 新表: `AgentConfig`（`agent_name`、`system_prompt`、`confidence_threshold`、`max_retries`、`enabled`、`updated_at`）。
- 新表: `RoutingRule`（`intent_category`、`target_agent`、`priority`、`condition_json`）。

**任务 P3-B2: 配置 API**
- `GET /api/v1/admin/agents/config` — 列出所有 Agent 配置
- `POST /api/v1/admin/agents/config/{agent_name}` — 更新配置
- `POST /api/v1/admin/agents/config/{agent_name}/rollback` — 回滚到上一版本
- 变更**无需重启**即可生效: 下次请求时从 DB 重新加载（内存缓存 60s）。

**任务 P3-B3: 配置 UI**
- Admin Dashboard 新增 "Agent 配置" Tab。
- 可编辑 system prompt，支持实时预览。
- confidence threshold 滑块。
- 启用/禁用 Agent 开关。
- 配置变更审计日志（谁在何时改了什么）。

---

## 3. 核心交付物

| 交付物 | 位置 |
|--------|------|
| 结构化记忆模型 | `app/models/memory.py` |
| 结构化记忆管理器 | `app/memory/structured_manager.py` |
| 事实抽取器 (Celery) | `app/memory/extractor.py` |
| 向量记忆管理器 | `app/memory/vector_manager.py` |
| Qdrant conversation_memory collection | `conversation_memory` |
| 记忆感知的 BaseAgent | `app/agents/base.py`（更新） |
| 会话摘要器 | `app/memory/summarizer.py` |
| Agent 配置中心后端 | `app/api/v1/admin/agent_config.py` |
| Agent 配置中心 UI | `frontend/src/apps/admin/pages/AgentConfig.tsx` |

---

## 4. 验收标准

### 记忆检索
- [ ] 向量记忆检索延迟 p99 <200ms。
- [ ] 在需要引用过往交互的查询中，Agent 能正确引用历史对话的比例 ≥70%（Golden Dataset + 人工评估）。

### 事实抽取
- [ ] 事实抽取器在 50 条会话的 hold-out 测试集上精确率 ≥80%。
- [ ] 绝不抽取或存储 PII（密码、完整信用卡号）（通过正则扫描 + 人工审计验证）。

### 配置中心
- [ ] 更新 system prompt 后 60 秒内对新会话生效。
- [ ] 禁用某个 Agent 后，Supervisor 将对应意图路由到兜底 Agent 或人工转接。
- [ ] 配置变更历史不可篡改且可查询。

### 摘要
- [ ] 超过 20 轮的 thread 100% 生成摘要。
- [ ] 带摘要的 thread 在向量搜索中的检索速度优于全消息 thread。

---

## 5. 风险与依赖

| 风险 | 发生概率 | 缓解措施 |
|------|----------|----------|
| PII 泄漏进记忆存储 | 中 | 抽取前实施基于正则的 PII 脱敏；每季度人工审计已存储事实 |
| 向量记忆检索返回无关旧对话 | 中 | 按 `user_id` 过滤 + 时间衰减打分；使用摘要提升信噪比 |
| 配置热重载引发竞态条件 | 低 | 内存缓存带 TTL；不修改运行中的 graph 实例，仅更新 prompt 字符串 |
| 记忆存储成本暴增 | 低 | 向量 90 天 TTL；结构化事实体积极小；监控 Qdrant 存储增长 |

### 依赖项
- 第二阶段的 Supervisor pattern 必须稳定，才能在其上叠加记忆能力。
- Qdrant 集群必须能承载 `conversation_memory`（估算: 每消息约 1KB）。
- 长期对话存储需通过法务/隐私审查（GDPR/CCPA 合规）。

---

## 6. Agent 相关重点

第三阶段将 Agent 从**无状态函数**转变为**有状态协作者**。

### 6.1 记忆作为依赖项（而非事后补丁）
每个专家 Agent 必须通过与其他依赖（`llm`、`retriever`）相同的注入模式接收记忆上下文。不存在全局记忆状态。这保证了:
- 可测试性: 单元测试注入 mock memory。
- 隔离性: 用户 A 的记忆绝不泄漏到用户 B 的 thread。
- 可观测性: LangSmith trace 精确记录检索到了哪些记忆。

### 6.2 "回头客" 体验
新会话的首条用户消息应触发一次轻量记忆查询。若用户在上次会话中有未解决的退款，router 或 Supervisor 应主动提及。第三阶段的核心产品指标即 **returning-user proactive relevance rate**。

### 6.3 Agent 认知负荷
过多记忆反而有害。我们上限为:
- 3 条结构化事实
- 2 条过往会话摘要
- 5 条相关向量检索轮次
超出上限的记忆按相关性排序后丢弃。这防止 prompt 膨胀与延迟劣化。
