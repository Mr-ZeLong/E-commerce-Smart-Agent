# E-commerce Smart Agent Prompt Engineering 调研与下一阶段规划

> 文档版本：v2.0
> 生成日期：2026-04-16
> 适用范围：E-commerce Smart Agent 项目全体开发人员

---

## 目录

1. [前言](#1-前言)
2. [项目当前 Prompt 现状分析](#2-项目当前-prompt-现状分析)
3. [Prompt Engineering 说明与要求](#3-prompt-engineering-说明与要求)
4. [Prompt Engineering 最佳实践指南](#4-prompt-engineering-最佳实践指南)
5. [下一阶段目标与任务](#5-下一阶段目标与任务)
6. [附录](#附录)

---

## 1. 前言

本系统采用 **FastAPI + LangGraph + Qwen** 技术栈构建电商智能客服，核心交互完全依赖大语言模型（LLM）的 Prompt 工程。Prompt 的质量直接决定了：

- 意图识别准确率
- RAG 检索回答的幻觉率
- 多 Agent 协作的稳定性
- 用户满意度（CSAT）与人工接管率

因此，建立系统化的 Prompt Engineering 规范、识别当前短板并规划下一阶段改进路径，是提升系统智能化水平的关键。本文档整合了 Google Cloud[^1]、OpenAI[^2]、Anthropic[^3]、DAIR.AI（PromptingGuide.ai）[^4] 等权威来源的最新实践，为项目提供可落地的工程指南。

---

## 2. 项目当前 Prompt 现状分析

### 2.1 架构概览

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

### 2.2 现有 Prompt 分布

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

### 2.3 已采用的 Prompt Engineering 技巧

#### 2.3.1 结构化输出（Structured Output）

- **ComplaintAgent**：prompt 末尾强制要求 JSON 格式，使用 Pydantic 解析
- **QueryRewriter**：使用 `llm.with_structured_output(_RewrittenQuery)` 绑定输出格式
- **IntentClassifier**：使用 `bind_tools()` + function calling 实现意图结构化提取

#### 2.3.2 记忆注入（Memory Injection）

`BaseAgent._build_contextual_message()` 实现了多级记忆注入（按优先级，目前包含 4 个主要层级和若干附加信息）：

1. `[过往会话摘要]` - `interaction_summaries`
2. `[User Context]` - `structured_facts` + `user_profile`
3. `[用户偏好]` - `preferences`
4. `[来自你的历史对话]` - `relevant_past_messages`（向量检索）

#### 2.3.3 RAG Context Injection

`PolicyAgent` 将检索到的 `chunks` 直接注入到 `context` 参数中，与用户问题一并发送给 LLM。

#### 2.3.4 查询重写（Query Rewriting）

`QueryRewriter` 支持：
- 单查询改写（口语化 → 检索友好）
- 多查询扩展（multi-query）
- 对话历史感知的改写

### 2.4 当前存在的问题与不足

#### 问题 1：A/B 实验框架未完全激活

`ExperimentVariant.system_prompt` 字段已存在，流量分配器 `ExperimentAssigner` 也已实现，但**在实际的聊天请求处理流程中（`chat.py`），并未调用实验分配逻辑**。这导致：
- 变体 Prompt 无法生效
- A/B 测试只能停留在配置层面
- 无法通过实验数据验证 Prompt 优化效果

#### 问题 2：Prompt 缺乏模板变量机制

当前所有 Prompt 都是纯文本字符串，无法动态注入运行时常量（如 `{{company_name}}`、`{{current_date}}`、`{{agent_name}}`）。这导致：
- 通用信息变更需要逐个修改 Prompt
- 无法根据用户属性动态调整边界约束
- 国际化/多租户支持受限

#### 问题 3：缺少 Few-shot 示例管理

虽然 `IntentClassifier` 有规则匹配作为 fallback，但**没有正式的 Few-shot 示例库**。LLM 的意图识别完全依赖 function calling，在边界 case 上表现不稳定。

#### 问题 4：Prompt 版本对比与 Diff 缺失

虽然有 `AgentConfigAuditLog` 记录变更历史，但：
- 没有可视化的版本对比（diff）
- 无法快速回滚到任意历史版本（只能回滚到上一版）
- 缺少 Prompt 性能与版本关联分析

#### 问题 5：System Prompt 与 User Prompt 边界模糊

部分 Agent（如 `ProductAgent`）在调用 LLM 时，将大量上下文指令直接塞入 `HumanMessage`，而非通过 `SystemMessage` 设定角色和规则。这可能导致：
- 模型对指令的遵循度下降
- 多轮对话中角色一致性减弱
- 不同模型对 message role 的敏感度差异被放大

---

## 3. Prompt Engineering 说明与要求

### 3.1 什么是 Prompt Engineering？

**Google Cloud** 将 Prompt Engineering 定义为[^1]：
> "设计和优化输入提示（prompts）以获得大语言模型（LLM）高质量、准确且相关输出的过程与实践。"

**OpenAI** 将其视为[^2]：
> "通过提供明确的指令、上下文和示例，引导模型生成期望结果的迭代过程。"

Prompt Engineering 不是"写一段好文字"那么简单，而是一个涉及**角色定义、上下文管理、输出约束、错误恢复**的系统工程。其核心目标是通过**清晰的指令、充分的上下文和恰当的格式**，最大化模型已有的知识和能力，而非"欺骗"模型。

### 3.2 核心概念

| 概念 | 说明 |
|------|------|
| **Prompt** | 发送给 LLM 的输入文本，可包含指令、上下文、示例、问题等 |
| **Completion** | LLM 基于 Prompt 生成的输出 |
| **Context Window** | 模型一次能处理的最大 Token 数，决定可用信息量 |
| **Temperature** | 控制输出随机性（0=确定性，1=高创造性） |
| **Token** | 模型的基本处理单元，中文约 1 个汉字 ≈ 0.5-1 Token |
| **Zero-shot / Few-shot** | 无示例 vs 提供少量示例的提示方式 |

### 3.3 基本原则（权威来源共识）

1. **明确性（Clarity）**：指令越具体，结果越可控
2. **上下文充分性（Context）**：提供模型完成任务所需的全部背景
3. **任务分解（Decomposition）**：复杂任务拆分为简单子任务
4. **迭代优化（Iteration）**：Prompt 是实验科学，需 A/B 测试调优
5. **格式引导（Formatting）**：使用分隔符、列表、Markdown 等明确结构

### 3.4 本项目对 Prompt Engineering 的核心要求

基于电商客服场景的高标准，所有 Prompt 设计必须满足以下要求：

#### 3.4.1 角色清晰（Role Clarity）

每个 Agent 的 System Prompt 必须明确回答三个问题：

1. **你是谁？** —— 角色身份、专业领域、服务范围
2. **你能做什么？** —— 明确的能力边界和可用工具
3. **你不能做什么？** —— 禁止行为、兜底策略、升级路径

#### 3.4.2 事实准确（Grounded in Facts）

- 所有涉及订单、退款、物流的信息必须来自数据库/工具调用
- RAG 回答必须基于检索结果，**严禁编造**
- 若信息不足，应明确告知用户，而非推测

#### 3.4.3 语气一致（Tone Consistency）

- 客服场景下，语气应为**专业、友好、耐心**
- 投诉处理需体现**同理心和安抚**
- 严禁使用敷衍、机械、冷漠的表达方式

#### 3.4.4 输出可控（Output Controllability）

- 需要结构化数据的场景（意图分类、投诉分类、查询重写），必须使用 `with_structured_output` 或 `bind_tools`
- 所有 JSON 输出要求必须附带**明确的 Schema 说明和示例**
- 解析失败时必须有**优雅的 fallback 机制**

#### 3.4.5 安全合规（Safety & Compliance）

- 严禁在 Prompt 中泄露系统内部架构、API 密钥、数据库结构
- 用户输入必须通过 `safety.py` 过滤后再进入 LLM
- 涉及 PII（信用卡号、密码）的场景需跳过记忆抽取

---

## 4. Prompt Engineering 最佳实践指南

### 4.1 System Prompt vs User Prompt 设计原则

#### 4.1.1 定义区分

| 类型 | 作用 | 设计重点 | 稳定性 |
|------|------|----------|--------|
| **System Prompt** | 设定模型的全局行为、角色、约束、安全策略 | 稳定、抽象、长期有效 | 高 |
| **User Prompt** | 表达用户的即时请求和具体输入 | 动态、具体、随请求变化 | 低 |

#### 4.1.2 System Prompt 设计原则

- **角色锚定**：清晰定义模型身份（如"你是一位资深的电商售后客服专家"）
- **行为约束**：列出必须遵守的规则（如"总是用中文回答"、"拒绝生成有害内容"）
- **输出格式规范**：统一指定回复风格（正式/ casual）、长度、结构
- **安全与边界**：注入安全策略、隐私保护要求、拒绝场景
- **保持精简**：避免过度冗长导致用户请求被稀释（Prompt Dilution）

#### 4.1.3 User Prompt 设计原则

- **具体而完整**：包含所有必要上下文（如订单号、用户历史、检索结果）
- **使用分隔符**：用 `"""`、`<xml>`、JSON 等包裹复杂输入
- **逐步引导**：对复杂请求，使用"第一步...第二步..."的格式
- **避免歧义**：消除指代不明、一词多义的问题

#### 4.1.4 消息职责边界（LangChain / LangGraph 实践）

**推荐做法**：

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

customer_service_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),           # 角色定义、规则约束
    MessagesPlaceholder(variable_name="chat_history"),  # 历史对话
    ("human", "{user_input}"),           # 用户当前请求
])
```

**不推荐做法**：

```python
# 将所有内容硬编码为单一 HumanMessage
messages = [HumanMessage(content=f"你是客服助手。{context}\n{question}")]
```

#### 4.1.5 "角色-规则-输出" 三段式结构

所有 System Prompt 建议按以下结构组织：

```markdown
## 角色
你是{role}，负责{responsibility}。

## 规则
1. {rule_1}
2. {rule_2}
3. {rule_3}

## 输出要求
- {output_requirement_1}
- {output_requirement_2}
```

**示例：OrderAgent 优化版 System Prompt**

```markdown
你是专业的电商订单处理助手，隶属于{company_name}。

## 职责范围
- 查询用户订单状态和物流信息
- 协助用户提交退货/换货申请
- 解答订单相关的售后政策

## 行为规则
1. 所有订单数据必须来自数据库查询结果，严禁编造
2. 处理退货申请前，必须核对订单状态是否为"已签收"或"已完成"
3. 若用户未提供订单号，主动引导用户提供
4. 遇到金额超过¥2000的退款申请，告知需要人工审核

## 输出要求
- 回答简洁，优先列出关键信息（订单号、状态、金额）
- 使用友好、专业的中文表达
- 对于无法处理的问题，明确告知并建议转人工客服
```

### 4.2 结构化输出（JSON Mode / Function Calling）设计技巧

#### 4.2.1 JSON Mode 设计技巧（OpenAI / Anthropic / Google 共识）

1. **显式声明输出格式**
   - 在 Prompt 中明确要求："请以 JSON 格式输出"
   - 提供完整的 JSON Schema 或示例结构

2. **提供示例（Example/Dummy Output）**
   ```
   请按以下格式返回结果：
   {
     "summary": "string",
     "items": [
       {"name": "string", "score": number}
     ]
   }
   ```

3. **使用 `response_format={"type": "json_object"}`**（OpenAI 兼容接口）
   - 确保模型被强制输出合法 JSON
   - 仍需在 Prompt 中说明期望结构

4. **处理嵌套与可选字段**
   - 对可选字段注明 `"description": "可选，如无则留空或省略"`
   - 避免过深的嵌套（>3 层易导致错误）

5. **验证与容错**
   - 始终在后端对模型输出做 JSON 解析和 Schema 校验
   - 准备重试/降级策略

#### 4.2.2 Function Calling 设计技巧

1. **函数描述要自解释**
   - `description` 字段必须清晰说明函数用途、参数含义、返回值
   - 这是模型决定是否调用的唯一依据

2. **参数 Schema 精确化**
   - 使用 `enum` 限制可选值
   - 明确 `required` 字段
   - 提供参数示例

3. **分离"思考"与"调用"**
   - 使用 `tool_choice` 控制调用行为
   - 让模型先输出推理（Chain-of-Thought），再决定函数调用

4. **错误处理注入**
   - 在 System Prompt 中告知模型：如果参数不足，应反问用户而非随意调用

### 4.3 高级技术：CoT、Few-shot、Role-play

#### 4.3.1 链式思考（Chain-of-Thought, CoT）

**定义**：通过在 Prompt 中要求模型"逐步思考"（如 "Let's think step by step"），显式展示推理过程，从而提升复杂问题的准确率[^5]。

**最佳实践**：
- **Zero-shot CoT**：在问题末尾追加 `Let's think step by step.`（Kojima et al., 2022）[^7]
- **Few-shot CoT**：在示例中展示完整的中间推理步骤，引导模型模仿
- **Self-Consistency**：生成多条 CoT 路径，通过投票选出最一致的答案
- **应用场景**：数学推理、逻辑判断、代码调试、决策分析

**电商场景示例**（退款资格审核）：
```markdown
请逐步分析该用户是否符合退货条件：
1. 订单状态是否为"已签收"或"已完成"？
2. 当前时间是否在签收后 7 天内？
3. 商品是否属于不支持退货的品类？
4. 综合以上，给出最终结论。
```

#### 4.3.2 少样本学习（Few-shot Prompting）

**定义**：在 Prompt 中提供 1~10 个输入-输出示例，让模型从示例中推断任务模式。

**最佳实践**：
- **示例质量 > 数量**：选择边界案例、代表性强的示例
- **输入输出分布对齐**：示例应覆盖真实场景的主要变体
- **标签空间一致**：示例中的输出格式必须严格统一
- **动态示例检索（Dynamic Few-shot）**：使用向量检索从知识库中实时获取最相关的示例

**IntentClassifier 改进示例**：
```markdown
你是一个电商客服意图识别专家。请分析用户输入，识别其意图并提取相关槽位。

意图层级定义:
1. 一级意图(primary_intent): ORDER, AFTER_SALES, POLICY, PRODUCT, CART, OTHER
2. 二级意图(secondary_intent): QUERY, APPLY, MODIFY, CANCEL, CONSULT, ADD, REMOVE, COMPARE

## 示例
用户: "我的订单到哪了"
→ {"primary_intent": "ORDER", "secondary_intent": "QUERY", "confidence": 0.95}

用户: "这个手机支持5G吗"
→ {"primary_intent": "PRODUCT", "secondary_intent": "QUERY", "confidence": 0.92}

用户: "我不喜欢这个颜色，想换"
→ {"primary_intent": "AFTER_SALES", "secondary_intent": "APPLY", "tertiary_intent": "EXCHANGE", "confidence": 0.88}

请输出JSON格式...
```

#### 4.3.3 角色扮演（Role-play）

**定义**：通过 System Prompt 为模型设定特定角色，以激活该角色相关的知识和表达风格。

**最佳实践**：
- **角色具体化**：避免笼统的"专家"，而是"有 5 年经验的电商售后客服主管"
- **场景嵌入**：描述角色所处的具体情境（如在处理用户投诉工单）
- **语气和风格约束**：指定专业术语密度、表达正式程度
- **避免过度拟人**：明确告知模型这是角色扮演，防止模型产生错误的自我意识

### 4.4 LLM Agent Prompt 设计模式

#### 4.4.1 ReAct（Reasoning + Acting）

**核心模式**：模型在每一步输出 `Thought`（思考）→ `Action`（动作/工具调用）→ `Observation`（观察结果），循环直至完成任务[^6]。

**Prompt 设计要点**：
- 提供清晰的 ReAct 格式示例
- 限定可选的 Action 列表
- 要求 Thought 必须放在 Action 之前
- 设置最大迭代次数，防止无限循环

**典型模板**：
```markdown
你可以使用以下工具：[工具列表]

请按以下格式思考并行动：
Thought: 我需要...
Action: [工具名]
Action Input: [参数]
Observation: [工具返回结果]
...（重复直到有最终答案）
Final Answer: [最终回答]
```

#### 4.4.2 Tool Use（工具使用）

**设计模式**：
- **工具注册**：在 System Prompt 或 API 中注册所有可用工具及其 Schema
- **意图识别**：先让模型判断是否需要调用工具，还是直接回答
- **结果注入**：将工具返回结果以 Observation 形式重新输入 Prompt
- **错误反馈**：工具失败时，将错误信息返回给模型，允许其重试或调整策略

#### 4.4.3 Memory Injection（记忆注入）

**设计模式**：
- **短期记忆**：将最近 N 轮对话历史直接拼入 Prompt
- **长期记忆**：通过向量检索（RAG）从外部记忆库中召回相关信息
- **记忆摘要**：当对话过长时，对历史进行摘要压缩后再注入
- **记忆标注**：区分用户画像、历史摘要、原子事实、向量记忆等不同类型

**本项目实践建议**：

| 类型 | 来源 | 注入位置 | 有效期 |
|------|------|----------|--------|
| 用户画像 | `user_profiles` | System Prompt / Memory Prefix | 长期 |
| 历史摘要 | `interaction_summaries` | Memory Prefix | 长期 |
| 原子事实 | `user_facts` | Memory Prefix | 长期 |
| 向量记忆 | `conversation_memory` | Memory Prefix | 跨会话 |
| 当前会话历史 | `state.history` | `MessagesPlaceholder` | 单会话 |

**避免记忆污染**：
- 记忆信息应以**第三方视角**描述，避免让模型误以为是用户当前输入
- 使用明确的标记隔离记忆与当前问题：

```markdown
[以下是你了解到的关于该用户的背景信息]
{memory_context}
[/背景信息]

[用户当前问题]
{question}
[/用户当前问题]
```

### 4.5 RAG 场景下的 Prompt 设计

#### 4.5.1 处理检索结果缺失

`PolicyAgent` 当前已要求："如果参考信息为空，直接回答'抱歉，暂未查询到相关规定'"。建议进一步优化为：

```markdown
你是一位电商政策咨询专家。请根据以下提供的参考信息回答用户问题。

## 规则
1. 只能依据[参考信息]回答问题，严禁编造
2. 如果[参考信息]为空或与问题无关，直接回答："抱歉，暂未查询到相关规定，建议您联系人工客服获取准确信息。"
3. 如果参考信息部分相关但不够完整，请回答已知的部分，并说明"根据现有资料，还无法确认..."
4. 引用具体政策条款时，请注明来源文档名称

## 参考信息
{retrieved_chunks}

## 用户问题
{question}
```

#### 4.5.2 幻觉抑制技巧

1. **显式禁止**：在 System Prompt 中加入 "严禁编造"、"若不确定请说明"
2. **引用标注**：要求 LLM 在回答中标注信息来源（如 "根据《退货政策》第3条..."）
3. **相关性评分前置**：在注入 RAG 结果前，先用轻量模型过滤低相关性 chunk

#### 4.5.3 Self-RAG 模式

引入 Self-RAG 模式：LLM 先判断检索结果是否充分，再决定生成或拒绝回答。

```python
# 1. 文档相关性评分
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

class GradeDocuments(BaseModel):
    binary_score: str = Field(description="'yes' or 'no'")

grade_prompt = ChatPromptTemplate.from_messages([
    ("system", "评估以下文档与用户问题的相关性，回答 'yes' 或 'no'。"),
    ("human", "问题：{question}\n\n文档：{document}"),
])
grader = grade_prompt | llm.with_structured_output(GradeDocuments)

# 2. 若相关性不足，触发补充检索或拒绝回答
result = await grader.ainvoke({"question": question, "document": document})
if result.binary_score == "no":
    return "抱歉，暂未找到准确答案..."
```

### 4.6 电商场景特有的 Prompt 技巧

#### 4.6.1 订单查询

- 必须验证 `user_id` 与订单归属关系
- 未找到订单时，引导用户提供订单号而非直接结束对话
- 高价值订单（>¥2000）自动附加风险提示

#### 4.6.2 退货/退款

- 先检查退货资格（签收时间、商品类别）
- 明确告知退款金额和预计到账时间
- 高金额退款自动触发人工审核说明

#### 4.6.3 投诉处理

`ComplaintAgent` 的 JSON 输出设计是良好实践，建议增加**情感强度评分**：

```python
from pydantic import BaseModel, Field

class ComplaintClassification(BaseModel):
    category: str
    urgency: str
    sentiment_score: float = Field(description="用户负面情绪强度 0-1")
    summary: str
    expected_resolution: str
    empathetic_response: str
```

#### 4.6.4 商品问答

`ProductAgent` 的 `_should_use_llm()` 是一个务实的优化。建议进一步扩展直接回答的参数库：

```python
DIRECT_ATTRIBUTES = {
    "价格": "price",
    "库存": "in_stock",
    "颜色": "attributes.color",
    "尺寸": "attributes.size",
}
```

### 4.7 中文大模型（Qwen）Prompt 技巧

#### 4.7.1 中文场景核心原则：真诚 + 直接

Qwen 在中文客服场景下表现优异的核心要诀是：**"把 AI 当人看"**。不要堆砌复杂的英文提示词技巧，而应采用真诚、直接的表达方式。

**推荐原则**：
- 使用自然的口语化中文，避免翻译腔
- 指令清晰明确，不要绕弯子
- 用"请"、"需要"等礼貌用语，但不要过度客套
- 结构化表达优先于长段落描述

#### 4.7.2 充分利用 Qwen 的指令遵循能力

Qwen 对结构化指令的遵循度较高，适合使用：
- 明确的编号列表（1. 2. 3.）
- Markdown 层级标题（## 规则、## 输出格式）
- 代码块包裹 JSON 示例

#### 4.7.3 Function Calling 兼容性

`IntentClassifier` 中已经做了兼容性处理：

```python
if "dashscope" in settings.OPENAI_BASE_URL.lower() or settings.LLM_MODEL.startswith("qwen"):
    tool_choice = "auto"  # Qwen 使用 auto 而非强制 function
```

**建议**：在使用 Qwen 的 `bind_tools` 时，优先使用 `"auto"` 模式，避免 `"required"` 导致的兼容性问题。

#### 4.7.4 温度参数控制

| 场景 | 推荐 temperature |
|------|------------------|
| 意图分类 / 路由 | `0.0` - `0.2` |
| 结构化输出（JSON） | `0.0` - `0.3` |
| RAG 回答生成 | `0.3` - `0.5` |
| 会话摘要 / 创意回复 | `0.5` - `0.7` |

### 4.8 常见反模式与避免方法

| 反模式 | 表现 | 避免方法 |
|--------|------|----------|
| **Prompt 稀释（Prompt Dilution）** | System Prompt 过长或用户请求被大量上下文淹没 | 控制 Prompt 长度，使用摘要和检索 |
| **模糊指令（Vague Instructions）** | "写得好一点"、"分析一下" | 使用可衡量的标准（字数、格式、角度） |
| **示例不一致（Inconsistent Examples）** | Few-shot 示例的输出格式不统一 | 建立示例模板，严格校验一致性 |
| **过度假设（Over-assumption）** | 假设模型知道专有名词或内部背景 | 在 Prompt 中提供必要的定义和上下文 |
| **幻觉诱导（Hallucination Induction）** | 要求模型回答超出其知识边界的问题而不提供检索 | 明确允许模型说"不知道"，结合 RAG |
| **角色越狱风险（Jailbreak Vulnerability）** | 用户通过角色扮演绕过安全限制 | 在 System Prompt 中强化核心安全策略 |
| **忽视 Token 限制** | 输入超过 Context Window 导致截断 | 监控 Token 使用量，设计分段处理策略 |
| **没有错误处理** | 假设模型每次都能输出完美 JSON | 始终对结构化输出做校验和重试 |
| **链式调用无边界** | Agent 无限循环调用工具 | 设置最大步数、超时、人工介入机制 |
| **System/User 边界模糊** | 将角色定义塞入 HumanMessage | 严格分离 SystemMessage 和 HumanMessage 职责 |

### 4.9 Prompt 评估与测试方法论

Prompt Engineering 不是一次性写作任务，而是需要**持续度量、回归测试和版本控制**的工程实践。参考 OpenAI Evals、Anthropic 内部测试协议以及 Google Cloud 的生成式 AI 评估指南[^1]，建议建立以下评估体系：

#### 4.9.1 建立 Golden Dataset（基准测试集）

- 为每个核心 Agent 维护 50~200 条覆盖典型场景和边界 case 的测试用例
- 测试集应包含：用户输入、期望意图/槽位、期望回答模式、禁止行为清单
- 每次 Prompt 变更前，必须在 Golden Dataset 上运行回归测试，确保无退化

#### 4.9.2 LLM-as-Judge 自动评分

- 使用独立的轻量模型（如 `qwen-turbo`）作为评判器，对 Agent 输出进行多维度评分
- 评分维度示例：
  - **准确性（Accuracy）**：回答是否与事实/检索结果一致
  - **遵循度（Instruction Following）**：是否严格遵守 System Prompt 中的格式和规则
  - **安全性（Safety）**：是否泄露敏感信息或产生有害内容
  - **语气一致性（Tone）**：是否符合电商客服的专业友好标准
- 推荐使用结构化输出绑定评分Schema，实现可批量运行的自动化评判

#### 4.9.3 A/B 实验与指标关联

- 每个 Prompt 变体必须关联明确的北极星指标：意图准确率、RAG 幻觉率、CSAT、人工接管率
- 实验周期至少 7 天或 500 次对话，确保统计显著性
- 实验结果需记录到 `Experiment` + `GraphExecutionLog` 中，支持按 Prompt 版本追溯指标变化

#### 4.9.4 人工抽检与反馈闭环

- 每周从生产环境中抽检 5% 的对话记录，由业务专家标注质量等级
- 建立"差评/低置信度对话 → Prompt 根因分析 → 测试用例补充 → Prompt 迭代"的闭环
- 将人工标注结果反向注入 Golden Dataset，持续扩充边界 case

---

## 5. 下一阶段目标与任务

### 5.1 总体目标

在 **Q2 季度内**，将本系统的 Prompt Engineering 能力从 "可用" 提升到 "可度量、可实验、可快速迭代" 的水平，核心指标：

- 意图识别准确率 ≥ 92%
- RAG 回答幻觉率 ≤ 5%
- 人工接管率 ≤ 15%
- Prompt A/B 实验覆盖全部核心 Agent

### 5.2 任务分解

#### 任务 1：激活 A/B 实验的 Prompt 变体能力
**优先级**：P0
**负责人**：后端 Agent 团队
**验收标准**：
- [ ] `ExperimentAssigner.assign()` 返回类型从 `str | None`（variant name）改为 `int | None`（variant id）
- [ ] `AgentState` / `make_agent_state()` 增加 `experiment_variant_id: int | None` 字段
- [ ] `chat.py` 请求入口处（或 graph 入口节点中）获取用户对应的实验 `variant_id` 并写入 `AgentState`
- [ ] `BaseAgent` 新增 `async def _resolve_experiment_prompt(self, state: AgentState) -> str | None` 方法；各 Agent 子类在 `process()` 中调用该方法并将结果写入 `self._dynamic_system_prompt`
- [ ] 补充单元测试：验证实验变体 prompt 的生效逻辑

**参考实现思路**：

```python
# 1. 在 BaseAgent 中新增解析方法（由子类 process() 调用）
from app.core.database import async_session_maker
from app.models.experiment import ExperimentVariant

class BaseAgent:
    ...
    async def _resolve_experiment_prompt(self, state: AgentState) -> str | None:
        """根据 AgentState 中的 experiment_variant_id 返回对应的覆盖 prompt."""
        variant_id = state.get("experiment_variant_id")
        if not variant_id:
            return None
        async with async_session_maker() as session:
            variant = await session.get(ExperimentVariant, variant_id)
            if variant and variant.system_prompt:
                return variant.system_prompt
        return None

# 2. 在 graph 入口节点（已确定目标 agent 后）写入 experiment_variant_id
from app.services.experiment_assigner import ExperimentAssigner

assigner = ExperimentAssigner()
variant_id = await assigner.assign(str(user_id), experiment_key, db=db)
state = make_agent_state(
    ...
    experiment_variant_id=variant_id,
)

# 3. 子类示例：OrderAgent.process() 中调用
async def process(self, state: AgentState) -> AgentProcessResult:
    await self._load_config()
    override = await self._resolve_experiment_prompt(state)
    if override:
        self._dynamic_system_prompt = override
    messages = self._create_messages(state["question"])
    ...
```

---

#### 任务 2：引入 Prompt 模板变量系统
**优先级**：P1
**负责人**：后端 Agent 团队 + B 端前端
**验收标准**：
- [ ] 在 `AgentConfig.system_prompt` 中支持 `{{variable}}` 语法
- [ ] 定义标准变量库：`{{company_name}}`、`{{current_date}}`、`{{user_membership_level}}`
- [ ] `BaseAgent._create_messages()` 中自动替换变量
- [ ] Admin 配置页面增加变量提示和实时预览

**参考实现思路**：

```python
import datetime
import re

DEFAULT_PROMPT_VARIABLES = {
    "company_name": "XX电商平台",
    "current_date": lambda: datetime.date.today().isoformat(),
}

_VARIABLE_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")

def render_prompt(template: str, user_context: dict) -> str:
    variables = {**DEFAULT_PROMPT_VARIABLES, **user_context}
    resolved = {k: v() if callable(v) else v for k, v in variables.items()}

    def _replacer(match: re.Match) -> str:
        key = match.group(1)
        return str(resolved.get(key, match.group(0)))

    return _VARIABLE_PATTERN.sub(_replacer, template)
```

---

#### 任务 3：建立 Few-shot 示例库（Intent + Complaint）
**优先级**：P1
**负责人**：算法/数据团队
**验收标准**：
- [ ] 收集并标注 50+ 条意图分类边界 case
- [ ] 将示例按 Agent / 场景分类存储（建议新建 `data/prompt_examples/`）
- [ ] `IntentClassifier` 支持动态注入 top-k 相似示例
- [ ] 评估：加入 few-shot 后意图准确率提升 ≥ 3%

**参考目录结构**：

```
data/prompt_examples/
├── intent/
│   ├── order_query.jsonl
│   ├── refund_apply.jsonl
│   └── product_compare.jsonl
└── complaint/
    ├── product_defect.jsonl
    └── logistics_delay.jsonl
```

---

#### 任务 4：增强 Prompt 版本管理与 Diff 能力
**优先级**：P1
**负责人**：后端 + B 端前端
**现状说明**：`AgentConfigAuditLog` 已经以字段级 diff 的形式记录了所有历史变更（`field_name`, `old_value`, `new_value`），但缺少**快照版本**机制和从审计日志快速重建完整 Prompt 快照的能力，目前回滚只能替换 `previous_system_prompt`（即上一版）。

**验收标准**：
- [ ] 新增 `agent_config_versions` 表（或扩展审计日志），存储每次变更后的完整 Prompt 快照
- [ ] Admin API 新增 `GET /admin/agents/{agent_name}/versions` 获取所有历史快照版本
- [ ] Admin 前端新增 Prompt 版本对比（diff）页面
- [ ] 支持回滚到任意历史版本

---

#### 任务 5：优化 System / Human Message 职责边界
**优先级**：P2
**负责人**：后端 Agent 团队
**验收标准**：
- [ ] 所有 Agent 的 `_create_messages()` 中，角色定义必须通过 `SystemMessage` 发送
- [ ] 动态上下文（检索结果、记忆、用户问题）通过 `HumanMessage` 发送
- [ ] 新增 `BaseAgent` 的 `_build_system_prompt()` 和 `_build_user_prompt()` 方法，规范拆分逻辑
- [ ] 修复 `ProductAgent` 中直接拼接 prompt 到 `HumanMessage` 的问题

---

#### 任务 6：RAG Prompt 幻觉抑制专项
**优先级**：P1
**负责人**：RAG + Agent 团队
**验收标准**：
- [ ] `PolicyAgent` System Prompt 增加 "引用标注" 要求
- [ ] 在检索结果注入前增加相关性过滤（score < 0.5 的 chunk 不注入）
- [ ] 引入 Self-RAG 模式：LLM 先判断检索结果是否充分，再决定生成或拒绝回答
- [ ] 评估：RAG 回答幻觉率从当前估计的 ~10% 降至 ≤ 5%

**参考实现思路**（基于 LangGraph Self-RAG）：

```python
# 1. 文档相关性评分
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

class GradeDocuments(BaseModel):
    binary_score: str = Field(description="'yes' or 'no'")

grade_prompt = ChatPromptTemplate.from_messages([
    ("system", "评估以下文档与用户问题的相关性，回答 'yes' 或 'no'。"),
    ("human", "问题：{question}\n\n文档：{document}"),
])
grader = grade_prompt | llm.with_structured_output(GradeDocuments)

# 2. 若相关性不足，触发补充检索或拒绝回答
result = await grader.ainvoke({"question": question, "document": document})
if result.binary_score == "no":
    return "抱歉，暂未找到准确答案..."
```

---

#### 任务 7：建立 Prompt 效果评估体系
**优先级**：P2
**负责人**：算法 + 数据团队
**验收标准**：
- [ ] 每次 Prompt 变更自动关联 `AgentConfigAuditLog` 与 `GraphExecutionLog`
- [ ] 建立 Prompt 版本 → 置信度分数 → 人工接管率的关联看板
- [ ] 每月输出《Prompt 优化效果报告》，量化评估每次变更的影响

---

#### 任务 8：多意图独立判定的 LLM 辅助
**优先级**：P2
**负责人**：后端 Agent 团队
**验收标准**：
- [ ] 在 `multi_intent.py` 中增加 LLM 辅助判定逻辑
- [ ] 当硬编码规则不确定时，调用轻量模型进行独立性判断
- [ ] 记录 LLM 判定结果与人工标注的一致性，持续优化规则

**参考 Prompt**：
```python
INDEPENDENCE_PROMPT = """判断以下两个用户意图是否可以独立处理（并行执行）。
意图A: {intent_a}
意图B: {intent_b}

标准:
- 若两个意图不需要共享同一订单/商品上下文，且答案互不依赖，回答 "independent"
- 若存在依赖关系或需要统一上下文，回答 "dependent"

只输出一个单词: independent 或 dependent"""
```

---

### 5.3 时间规划

| 周次 | 重点任务 | 里程碑 |
|------|----------|--------|
| W1-W2 | 任务 1（A/B 实验激活）+ 任务 5（消息边界优化） | Prompt 变体可生效 |
| W3-W4 | 任务 2（模板变量）+ 任务 4（版本 Diff） | Admin 配置中心升级完成 |
| W5-W6 | 任务 3（Few-shot 库）+ 任务 6（Self-RAG） | 意图准确率、RAG 质量提升 |
| W7-W8 | 任务 7（效果评估体系）+ 任务 8（多意图 LLM 辅助）+ 全链路测试 | 评估看板上线上报 |

---

## 附录

### A. 关键文件清单

#### A.1 Prompt 核心管理

| 文件 | 说明 |
|------|------|
| `app/agents/base.py` | Agent 基类，含 `_load_config()`、记忆注入 |
| `app/agents/config_loader.py` | Prompt 配置加载器（Redis + DB） |
| `app/models/memory.py` | `AgentConfig`、`AgentConfigAuditLog` 模型 |
| `app/api/v1/admin/agent_config.py` | Prompt 管理 API |

#### A.2 Agent Prompt 定义

| 文件 | 说明 |
|------|------|
| `app/agents/order.py` | `ORDER_SYSTEM_PROMPT` |
| `app/agents/policy.py` | `POLICY_SYSTEM_PROMPT` |
| `app/agents/product.py` | `PRODUCT_SYSTEM_PROMPT` |
| `app/agents/cart.py` | `CART_SYSTEM_PROMPT` |
| `app/agents/logistics.py` | `LOGISTICS_SYSTEM_PROMPT` |
| `app/agents/account.py` | `ACCOUNT_SYSTEM_PROMPT` |
| `app/agents/payment.py` | `PAYMENT_SYSTEM_PROMPT` |
| `app/agents/complaint.py` | `COMPLAINT_SYSTEM_PROMPT`（Structured JSON） |

#### A.3 Prompt 工程组件

| 文件 | 说明 |
|------|------|
| `app/intent/classifier.py` | 意图分类 Prompt + Function Calling |
| `app/retrieval/rewriter.py` | 查询重写 / 多查询扩展 Prompt |
| `app/confidence/signals.py` | LLM 置信度自评估 Prompt |
| `app/memory/extractor.py` | 事实抽取 Prompt |
| `app/memory/summarizer.py` | 会话摘要 Prompt |
| `app/graph/nodes.py` | `synthesis_node` 融合 Prompt |

#### A.4 实验系统

| 文件 | 说明 |
|------|------|
| `app/models/experiment.py` | `ExperimentVariant.system_prompt` |
| `app/services/experiment_assigner.py` | 确定性流量分配器 |
| `app/api/v1/admin/experiments.py` | 实验管理 API |

### B. 推荐学习资源

#### B.1 官方文档

| 资源 | 链接 | 说明 |
|------|------|------|
| OpenAI Prompt Engineering Guide | https://platform.openai.com/docs/guides/prompt-engineering | OpenAI 官方提示工程指南 |
| OpenAI Structured Outputs | https://platform.openai.com/docs/guides/structured-outputs | JSON Mode / Function Calling 官方文档 |
| Anthropic Prompt Engineering | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering | Claude 官方提示工程最佳实践 |
| Anthropic Interactive Tutorial | https://github.com/anthropics/prompt-eng-interactive-tutorial | 交互式 Prompt Engineering 教程 |
| Google Cloud Prompt Engineering | https://cloud.google.com/discover/what-is-prompt-engineering | Google Cloud 权威定义与原则 |

#### B.2 综合学习资源

| 资源 | 链接 | 说明 |
|------|------|------|
| PromptingGuide.ai (DAIR.AI) | https://www.promptingguide.ai | 最全面的开源 Prompt Engineering 指南 |
| Learn Prompting | https://learnprompting.org | 免费的 Prompt Engineering 课程 |
| OpenAI Cookbook | https://github.com/openai/openai-cookbook | 大量实战代码示例 |
| LangChain Prompt Templates | https://python.langchain.com/docs/concepts/prompt_templates/ | 工程化 Prompt 管理 |

#### B.3 学术论文

- **Chain-of-Thought Prompting Elicits Reasoning in LLMs** (Wei et al., 2022)
- **ReAct: Synergizing Reasoning and Acting in Language Models** (Yao et al., 2023)
- **Tree of Thoughts: Deliberate Problem Solving with Large Language Models** (Yao et al., 2023)

### C. 引用来源

[^1]: Google Cloud. "What is prompt engineering?" https://cloud.google.com/discover/what-is-prompt-engineering
[^2]: OpenAI. "Prompt engineering." https://platform.openai.com/docs/guides/prompt-engineering
[^3]: Anthropic. "Prompt engineering overview." https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering
[^4]: DAIR.AI. "PromptingGuide.ai." https://www.promptingguide.ai
[^5]: Wei, J., et al. "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models." NeurIPS 2022. https://arxiv.org/abs/2201.11903
[^6]: Yao, S., et al. "ReAct: Synergizing Reasoning and Acting in Language Models." ICLR 2023. https://arxiv.org/abs/2210.03629
[^7]: Kojima, T., et al. "Large Language Models are Zero-Shot Reasoners." NeurIPS 2022. https://arxiv.org/abs/2205.11916

---

*文档结束*
