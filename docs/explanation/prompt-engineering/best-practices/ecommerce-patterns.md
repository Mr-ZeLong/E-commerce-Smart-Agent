# 电商场景特有的 Prompt 技巧

## 订单查询

- 必须验证 `user_id` 与订单归属关系
- 未找到订单时，引导用户提供订单号而非直接结束对话
- 高价值订单（>¥2000）自动附加风险提示

## 退货/退款

- 先检查退货资格（签收时间、商品类别）
- 明确告知退款金额和预计到账时间
- 高金额退款自动触发人工审核说明

## 投诉处理

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

## 商品问答

`ProductAgent` 的 `_should_use_llm()` 是一个务实的优化。建议进一步扩展直接回答的参数库：

```python
DIRECT_ATTRIBUTES = {
    "价格": "price",
    "库存": "in_stock",
    "颜色": "attributes.color",
    "尺寸": "attributes.size",
}
```
