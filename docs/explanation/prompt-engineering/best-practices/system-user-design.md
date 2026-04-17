# System Prompt vs User Prompt 设计原则

## 定义区分

| 类型 | 作用 | 设计重点 | 稳定性 |
|------|------|----------|--------|
| **System Prompt** | 设定模型的全局行为、角色、约束、安全策略 | 稳定、抽象、长期有效 | 高 |
| **User Prompt** | 表达用户的即时请求和具体输入 | 动态、具体、随请求变化 | 低 |

## System Prompt 设计原则

- **角色锚定**：清晰定义模型身份（如"你是一位资深的电商售后客服专家"）
- **行为约束**：列出必须遵守的规则（如"总是用中文回答"、"拒绝生成有害内容"）
- **输出格式规范**：统一指定回复风格（正式/ casual）、长度、结构
- **安全与边界**：注入安全策略、隐私保护要求、拒绝场景
- **保持精简**：避免过度冗长导致用户请求被稀释（Prompt Dilution）

## User Prompt 设计原则

- **具体而完整**：包含所有必要上下文（如订单号、用户历史、检索结果）
- **使用分隔符**：用 `"""`、`<xml>`、JSON 等包裹复杂输入
- **逐步引导**：对复杂请求，使用"第一步...第二步..."的格式
- **避免歧义**：消除指代不明、一词多义的问题

## 消息职责边界（LangChain / LangGraph 实践）

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

## "角色-规则-输出" 三段式结构

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
