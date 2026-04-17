# RAG 场景下的 Prompt 设计

## 处理检索结果缺失

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

## 幻觉抑制技巧

1. **显式禁止**：在 System Prompt 中加入 "严禁编造"、"若不确定请说明"
2. **引用标注**：要求 LLM 在回答中标注信息来源（如 "根据《退货政策》第3条..."）
3. **相关性评分前置**：在注入 RAG 结果前，先用轻量模型过滤低相关性 chunk

## Self-RAG 模式

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
