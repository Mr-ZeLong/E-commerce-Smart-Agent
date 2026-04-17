# 项目当前 Prompt 现状分析

## 架构概览

当前项目采用 **"硬编码默认值 + DB 热重载 + Redis 缓存"** 的三层 Prompt 管理体系：

```
Redis Cache (TTL=60s)
         ↓ MISS
PostgreSQL (agent_configs 表)
         ↓ 无记录
硬编码模块常量 (*_SYSTEM_PROMPT)
```

**核心组件**：

| 组件 | 文件 | 职责 |
|------|------|------|
| Prompt 基类 | `app/agents/base.py` | `_load_config()`、记忆注入、消息构建 |
| 配置加载器 | `app/agents/config_loader.py` | Redis 缓存、DB 查询、热重载 |
| 配置模型 | `app/models/memory.py` | `AgentConfig`、`AgentConfigAuditLog` |
| 管理 API | `app/api/v1/admin/agent_config.py` | CRUD、回滚、审计日志 |

## 现有 Prompt 分布

| 类型 | 文件 | 技术特点 |
|------|------|----------|
| **Agent System Prompt** | `app/agents/order.py` 等 8 个 Agent | 硬编码字符串，支持热重载覆盖 |
| **意图分类 Prompt** | `app/intent/classifier.py` | Function Calling + JSON Schema |
| **查询重写 Prompt** | `app/retrieval/rewriter.py` | Structured Output (`with_structured_output`) |
| **置信度评估 Prompt** | `app/confidence/signals.py` | LLM 自评估 + Pydantic 结构化 |
| **投诉分类 Prompt** | `app/agents/complaint.py` | JSON 输出 + Pydantic 解析 |
| **事实抽取 Prompt** | `app/memory/extractor.py` | Zero-shot JSON 提取 |
| **会话摘要 Prompt** | `app/memory/summarizer.py` | 直接 LLM 调用 |
| **回复融合 Prompt** | `app/graph/nodes.py` | `synthesis_node` 硬编码 |

## 已采用的 Prompt Engineering 技巧

### 结构化输出（Structured Output）

- **ComplaintAgent**：prompt 末尾强制要求 JSON 格式，使用 Pydantic 解析
- **QueryRewriter**：使用 `llm.with_structured_output(_RewrittenQuery)` 绑定输出格式
- **IntentClassifier**：使用 `bind_tools()` + function calling 实现意图结构化提取

### 记忆注入（Memory Injection）

`BaseAgent._build_contextual_message()` 实现了多级记忆注入（按优先级，目前包含 4 个主要层级和若干附加信息）：

1. `[过往会话摘要]` - `interaction_summaries`
2. `[User Context]` - `structured_facts` + `user_profile`
3. `[用户偏好]` - `preferences`
4. `[来自你的历史对话]` - `relevant_past_messages`（向量检索）

### RAG Context Injection

`PolicyAgent` 将检索到的 `chunks` 直接注入到 `context` 参数中，与用户问题一并发送给 LLM。

### 查询重写（Query Rewriting）

`QueryRewriter` 支持：
- 单查询改写（口语化 → 检索友好）
- 多查询扩展（multi-query）
- 对话历史感知的改写

## 当前存在的问题与不足

### 问题 1：A/B 实验框架未完全激活

`ExperimentVariant.system_prompt` 字段已存在，流量分配器 `ExperimentAssigner` 也已实现，但**在实际的聊天请求处理流程中（`chat.py`），并未调用实验分配逻辑**。这导致：
- 变体 Prompt 无法生效
- A/B 测试只能停留在配置层面
- 无法通过实验数据验证 Prompt 优化效果

### 问题 2：Prompt 缺乏模板变量机制

当前所有 Prompt 都是纯文本字符串，无法动态注入运行时常量（如 `{{company_name}}`、`{{current_date}}`、`{{agent_name}}`）。这导致：
- 通用信息变更需要逐个修改 Prompt
- 无法根据用户属性动态调整边界约束
- 国际化/多租户支持受限

### 问题 3：缺少 Few-shot 示例管理

虽然 `IntentClassifier` 有规则匹配作为 fallback，但**没有正式的 Few-shot 示例库**。LLM 的意图识别完全依赖 function calling，在边界 case 上表现不稳定。

### 问题 4：Prompt 版本对比与 Diff 缺失

虽然有 `AgentConfigAuditLog` 记录变更历史，但：
- 没有可视化的版本对比（diff）
- 无法快速回滚到任意历史版本（只能回滚到上一版）
- 缺少 Prompt 性能与版本关联分析

### 问题 5：System Prompt 与 User Prompt 边界模糊

部分 Agent（如 `ProductAgent`）在调用 LLM 时，将大量上下文指令直接塞入 `HumanMessage`，而非通过 `SystemMessage` 设定角色和规则。这可能导致：
- 模型对指令的遵循度下降
- 多轮对话中角色一致性减弱
- 不同模型对 message role 的敏感度差异被放大
