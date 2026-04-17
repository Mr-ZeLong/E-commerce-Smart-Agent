# Prompt Engineering 说明与要求

## 什么是 Prompt Engineering？

**Google Cloud** 将 Prompt Engineering 定义为[^1]：
> "设计和优化输入提示（prompts）以获得大语言模型（LLM）高质量、准确且相关输出的过程与实践。"

**OpenAI** 将其视为[^2]：
> "通过提供明确的指令、上下文和示例，引导模型生成期望结果的迭代过程。"

Prompt Engineering 不是"写一段好文字"那么简单，而是一个涉及**角色定义、上下文管理、输出约束、错误恢复**的系统工程。其核心目标是通过**清晰的指令、充分的上下文和恰当的格式**，最大化模型已有的知识和能力，而非"欺骗"模型。

## 核心概念

| 概念 | 说明 |
|------|------|
| **Prompt** | 发送给 LLM 的输入文本，可包含指令、上下文、示例、问题等 |
| **Completion** | LLM 基于 Prompt 生成的输出 |
| **Context Window** | 模型一次能处理的最大 Token 数，决定可用信息量 |
| **Temperature** | 控制输出随机性（0=确定性，1=高创造性） |
| **Token** | 模型的基本处理单元，中文约 1 个汉字 ≈ 0.5-1 Token |
| **Zero-shot / Few-shot** | 无示例 vs 提供少量示例的提示方式 |

## 基本原则（权威来源共识）

1. **明确性（Clarity）**：指令越具体，结果越可控
2. **上下文充分性（Context）**：提供模型完成任务所需的全部背景
3. **任务分解（Decomposition）**：复杂任务拆分为简单子任务
4. **迭代优化（Iteration）**：Prompt 是实验科学，需 A/B 测试调优
5. **格式引导（Formatting）**：使用分隔符、列表、Markdown 等明确结构

## 本项目对 Prompt Engineering 的核心要求

### 角色清晰（Role Clarity）

每个 Agent 的 System Prompt 必须明确回答三个问题：

1. **你是谁？** —— 角色身份、专业领域、服务范围
2. **你能做什么？** —— 明确的能力边界和可用工具
3. **你不能做什么？** —— 禁止行为、兜底策略、升级路径

### 事实准确（Grounded in Facts）

- 所有涉及订单、退款、物流的信息必须来自数据库/工具调用
- RAG 回答必须基于检索结果，**严禁编造**
- 若信息不足，应明确告知用户，而非推测

### 语气一致（Tone Consistency）

- 客服场景下，语气应为**专业、友好、耐心**
- 投诉处理需体现**同理心和安抚**
- 严禁使用敷衍、机械、冷漠的表达方式

### 输出可控（Output Controllability）

- 需要结构化数据的场景（意图分类、投诉分类、查询重写），必须使用 `with_structured_output` 或 `bind_tools`
- 所有 JSON 输出要求必须附带**明确的 Schema 说明和示例**
- 解析失败时必须有**优雅的 fallback 机制**

### 安全合规（Safety & Compliance）

- 严禁在 Prompt 中泄露系统内部架构、API 密钥、数据库结构
- 用户输入必须通过 `safety.py` 过滤后再进入 LLM
- 涉及 PII（信用卡号、密码）的场景需跳过记忆抽取
