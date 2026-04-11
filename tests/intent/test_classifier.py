"""意图分类器测试

测试场景:
- Function Calling成功
- Function Calling失败降级到JSON解析
- 规则匹配（无LLM时）
- 三级意图验证（合法和非法）
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_openai import ChatOpenAI

from app.intent.classifier import IntentClassifier
from app.intent.models import IntentAction, IntentCategory, IntentResult

# ========== Fixtures ==========


@pytest.fixture
def mock_llm():
    """创建Mock LLM"""
    mock = MagicMock(spec=ChatOpenAI)
    return mock


@pytest.fixture
def classifier(mock_llm):
    """创建带Mock LLM的分类器"""
    return IntentClassifier(llm=mock_llm)


# ========== Helper Functions ==========


def create_mock_response_with_tool_calls(tool_args: dict):
    """创建带工具调用的Mock响应（兼容新版 LangChain API）"""
    mock_response = MagicMock()
    arguments = json.dumps(tool_args) if isinstance(tool_args, dict) else tool_args
    mock_response.additional_kwargs = {
        "tool_calls": [
            {
                "id": "call_123",
                "type": "function",
                "function": {"name": "classify_intent", "arguments": arguments},
            }
        ]
    }
    # 新版 API: response.tool_calls
    mock_response.tool_calls = [
        {
            "name": "classify_intent",
            "args": tool_args if isinstance(tool_args, dict) else json.loads(arguments),
            "id": "call_123",
            "type": "tool_call",
        }
    ]
    return mock_response


def create_mock_response_with_content(content: str):
    """创建带文本内容的Mock响应"""
    mock_response = MagicMock()
    mock_response.additional_kwargs = {}  # 无工具调用
    mock_response.content = content
    return mock_response


# ========== Layer 1: Function Calling Tests ==========


@pytest.mark.asyncio
async def test_function_calling_success(classifier, mock_llm):
    """测试Function Calling成功场景"""
    # 准备Mock响应
    tool_args = {
        "primary_intent": "ORDER",
        "secondary_intent": "QUERY",
        "tertiary_intent": "ORDER_TRACKING_DETAIL",
        "confidence": 0.95,
        "slots": {"order_sn": "SN20240001"},
    }
    mock_response = create_mock_response_with_tool_calls(tool_args)

    # 设置Mock
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    # 执行测试
    result = await classifier.classify("我想查订单SN20240001")

    # 验证结果
    assert result.primary_intent == IntentCategory.ORDER
    assert result.secondary_intent == IntentAction.QUERY
    assert result.tertiary_intent == "ORDER_TRACKING_DETAIL"
    assert result.confidence == 0.95
    assert result.slots.get("order_sn") == "SN20240001"


@pytest.mark.asyncio
async def test_function_calling_no_tool_calls(classifier, mock_llm):
    """测试Function Calling无工具调用时降级到JSON解析"""
    # 第一层：Function Calling返回无工具调用
    mock_response_no_tools = MagicMock()
    mock_response_no_tools.additional_kwargs = {}  # 无工具调用
    mock_response_no_tools.content = ""

    # 第二层：JSON解析成功
    json_response = create_mock_response_with_content(
        json.dumps(
            {
                "primary_intent": "AFTER_SALES",
                "secondary_intent": "APPLY",
                "tertiary_intent": "REFUND",
                "confidence": 0.88,
                "slots": {"reason": "不喜欢"},
            }
        )
    )

    # 设置Mock - 第一次调用无工具，第二次调用返回JSON
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(side_effect=[mock_response_no_tools, json_response])

    # 执行测试
    result = await classifier.classify("我想退货")

    # 验证降级到JSON解析成功
    assert result.primary_intent == IntentCategory.AFTER_SALES
    assert result.secondary_intent == IntentAction.APPLY
    assert result.tertiary_intent == "REFUND"


@pytest.mark.asyncio
async def test_function_calling_exception_fallback(classifier, mock_llm):
    """测试Function Calling异常时降级"""
    # 第一层：Function Calling抛出异常
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(
        side_effect=[
            Exception("Function calling failed"),
            # 降级到JSON解析
            create_mock_response_with_content(
                json.dumps(
                    {
                        "primary_intent": "POLICY",
                        "secondary_intent": "CONSULT",
                        "tertiary_intent": "POLICY_SHIPPING_FEE",
                        "confidence": 0.85,
                        "slots": {},
                    }
                )
            ),
        ]
    )

    # 执行测试
    result = await classifier.classify("运费怎么算")

    # 验证降级成功
    assert result.primary_intent == IntentCategory.POLICY
    assert result.secondary_intent == IntentAction.CONSULT


# ========== Layer 2: JSON Parsing Tests ==========


@pytest.mark.asyncio
async def test_json_parsing_success(classifier, mock_llm):
    """测试JSON解析成功"""
    # 设置Mock - Function Calling失败，JSON解析成功
    mock_response_no_tools = MagicMock()
    mock_response_no_tools.additional_kwargs = {}
    mock_response_no_tools.content = ""

    json_response = create_mock_response_with_content(
        json.dumps(
            {
                "primary_intent": "PRODUCT",
                "secondary_intent": "QUERY",
                "tertiary_intent": "PRODUCT_STOCK",
                "confidence": 0.82,
                "slots": {"product_name": "iPhone 15"},
            }
        )
    )

    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(side_effect=[mock_response_no_tools, json_response])

    # 执行测试
    result = await classifier.classify("iPhone 15有货吗")

    # 验证结果
    assert result.primary_intent == IntentCategory.PRODUCT
    assert result.secondary_intent == IntentAction.QUERY
    assert result.confidence == 0.82


@pytest.mark.asyncio
async def test_json_parsing_with_markdown_code_block(classifier, mock_llm):
    """测试解析Markdown代码块中的JSON"""
    mock_response_no_tools = MagicMock()
    mock_response_no_tools.additional_kwargs = {}
    mock_response_no_tools.content = ""

    # LLM返回带Markdown格式的JSON
    markdown_json = create_mock_response_with_content("""
根据您的输入，分析结果如下:

```json
{
    "primary_intent": "CART",
    "secondary_intent": "ADD",
    "tertiary_intent": "CART_ADD_ITEM",
    "confidence": 0.90,
    "slots": {"product_name": "运动鞋", "quantity": 2}
}
```
""")

    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(side_effect=[mock_response_no_tools, markdown_json])

    # 执行测试
    result = await classifier.classify("加2双运动鞋到购物车")

    # 验证结果
    assert result.primary_intent == IntentCategory.CART
    assert result.secondary_intent == IntentAction.ADD
    assert result.slots.get("product_name") == "运动鞋"


@pytest.mark.asyncio
async def test_json_parsing_invalid_json_fallback(classifier, mock_llm):
    """测试JSON解析失败时降级到规则匹配"""
    # 所有LLM调用都失败
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(
        side_effect=[Exception("Function calling failed"), Exception("JSON parsing failed")]
    )

    # 执行测试 - 使用规则能匹配的关键词
    result = await classifier.classify("我想查订单状态")

    # 验证降级到规则匹配
    assert result.primary_intent == IntentCategory.ORDER
    assert result.secondary_intent == IntentAction.QUERY
    assert result.confidence == 0.5  # 规则匹配的置信度


# ========== Layer 3: Rule Matching Tests ==========


@pytest.mark.asyncio
async def test_rule_matching_order_query(classifier, mock_llm):
    """测试规则匹配 - 订单查询"""
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM failed"))

    result = await classifier.classify("我的订单SN12345到哪了")

    assert result.primary_intent == IntentCategory.ORDER
    assert result.secondary_intent == IntentAction.QUERY
    assert "matched_pattern" in result.slots


@pytest.mark.asyncio
async def test_rule_matching_after_sales_apply(classifier, mock_llm):
    """测试规则匹配 - 售后申请"""
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM failed"))

    result = await classifier.classify("我想申请退货")

    assert result.primary_intent == IntentCategory.AFTER_SALES
    assert result.secondary_intent == IntentAction.APPLY


@pytest.mark.asyncio
async def test_rule_matching_policy_consult(classifier, mock_llm):
    """测试规则匹配 - 政策咨询"""
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM failed"))

    result = await classifier.classify("运费怎么算")

    assert result.primary_intent == IntentCategory.POLICY
    assert result.secondary_intent == IntentAction.CONSULT


@pytest.mark.asyncio
async def test_rule_matching_cart_add(classifier, mock_llm):
    """测试规则匹配 - 添加购物车"""
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM failed"))

    result = await classifier.classify("把这个加入购物车")

    assert result.primary_intent == IntentCategory.CART
    assert result.secondary_intent == IntentAction.ADD


@pytest.mark.asyncio
async def test_rule_matching_default_other(classifier, mock_llm):
    """测试规则匹配 - 无匹配时默认OTHER"""
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM failed"))

    # 使用无法匹配任何规则的关键词
    result = await classifier.classify("xyzabc123")

    assert result.primary_intent == IntentCategory.OTHER
    assert result.secondary_intent == IntentAction.CONSULT
    assert result.confidence == 0.3


@pytest.mark.asyncio
async def test_rule_matching_logistics_query(classifier, mock_llm):
    """测试规则匹配 - 物流查询"""
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM failed"))

    result = await classifier.classify("快递到哪了")

    assert result.primary_intent == IntentCategory.LOGISTICS
    assert result.secondary_intent == IntentAction.QUERY


@pytest.mark.asyncio
async def test_rule_matching_greeting(classifier, mock_llm):
    """测试规则匹配 - 问候语"""
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM failed"))

    result = await classifier.classify("你好")

    assert result.primary_intent == IntentCategory.OTHER
    assert result.secondary_intent == IntentAction.CONSULT


# ========== Tertiary Intent Validation Tests ==========


@pytest.mark.asyncio
async def test_valid_tertiary_intent(classifier, mock_llm):
    """测试合法的三级意图"""
    tool_args = {
        "primary_intent": "AFTER_SALES",
        "secondary_intent": "APPLY",
        "tertiary_intent": "REFUND",  # 合法的三级意图
        "confidence": 0.90,
        "slots": {},
    }
    mock_response = create_mock_response_with_tool_calls(tool_args)

    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    result = await classifier.classify("我要退款")

    assert result.tertiary_intent == "REFUND"


@pytest.mark.asyncio
async def test_invalid_tertiary_intent_filtered(classifier, mock_llm):
    """测试非法的三级意图被过滤"""
    tool_args = {
        "primary_intent": "AFTER_SALES",
        "secondary_intent": "APPLY",
        "tertiary_intent": "INVALID_TERTIARY",  # 非法的三级意图
        "confidence": 0.90,
        "slots": {},
    }
    mock_response = create_mock_response_with_tool_calls(tool_args)

    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    result = await classifier.classify("我要退款")

    # 非法的三级意图应该被设为None
    assert result.tertiary_intent is None


@pytest.mark.asyncio
async def test_none_tertiary_intent_allowed(classifier, mock_llm):
    """测试None三级意图是合法的"""
    tool_args = {
        "primary_intent": "ORDER",
        "secondary_intent": "QUERY",
        "tertiary_intent": None,
        "confidence": 0.85,
        "slots": {"order_sn": "SN123"},
    }
    mock_response = create_mock_response_with_tool_calls(tool_args)

    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    result = await classifier.classify("查订单")

    assert result.tertiary_intent is None


# ========== Intent Validation Tests ==========


def test_validate_intent_result_valid(classifier):
    """测试验证有效的意图结果"""
    result = IntentResult(
        primary_intent=IntentCategory.ORDER,
        secondary_intent=IntentAction.QUERY,
        tertiary_intent="ORDER_TRACKING_DETAIL",
        confidence=0.85,
        slots={},
        raw_query="测试",
    )

    is_valid, error_msg = classifier.validate_intent_result(result)

    assert is_valid is True
    assert error_msg == ""


def test_validate_intent_result_invalid_primary(classifier):
    """测试验证无效的一级意图"""
    result = IntentResult(
        primary_intent="INVALID",  # type: ignore  # 无效的枚举值
        secondary_intent=IntentAction.QUERY,
        confidence=0.85,
        slots={},
        raw_query="测试",
    )

    is_valid, error_msg = classifier.validate_intent_result(result)

    assert is_valid is False
    assert "无效的一级意图" in error_msg


def test_validate_intent_result_invalid_tertiary(classifier):
    """测试验证无效的三级意图"""
    result = IntentResult(
        primary_intent=IntentCategory.AFTER_SALES,
        secondary_intent=IntentAction.APPLY,
        tertiary_intent="INVALID_TERTIARY",
        confidence=0.85,
        slots={},
        raw_query="测试",
    )

    is_valid, error_msg = classifier.validate_intent_result(result)

    assert is_valid is False
    assert "无效的三级意图" in error_msg


def test_validate_intent_result_invalid_confidence(classifier):
    """测试验证无效的置信度"""
    result = IntentResult(
        primary_intent=IntentCategory.ORDER,
        secondary_intent=IntentAction.QUERY,
        confidence=1.5,  # 超出范围
        slots={},
        raw_query="测试",
    )

    is_valid, error_msg = classifier.validate_intent_result(result)

    assert is_valid is False
    assert "置信度超出范围" in error_msg


# ========== Context Tests ==========


@pytest.mark.asyncio
async def test_classification_with_context(classifier, mock_llm):
    """测试带上下文的分类"""
    tool_args = {
        "primary_intent": "ORDER",
        "secondary_intent": "QUERY",
        "tertiary_intent": "ORDER_TRACKING_DETAIL",
        "confidence": 0.90,
        "slots": {"order_sn": "SN20240001"},
    }
    mock_response = create_mock_response_with_tool_calls(tool_args)

    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    context = {
        "session_id": "sess_123",
        "history": "用户之前查询过订单",
        "user_info": {"vip": True},
    }

    result = await classifier.classify("那个订单到哪了", context=context)

    assert result.primary_intent == IntentCategory.ORDER


# ========== Edge Case Tests ==========


@pytest.mark.asyncio
async def test_empty_query(classifier, mock_llm):
    """测试空输入"""
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("Empty query"))

    result = await classifier.classify("")

    # 应该降级到规则匹配，默认OTHER
    assert result.primary_intent == IntentCategory.OTHER


@pytest.mark.asyncio
async def test_very_long_query(classifier, mock_llm):
    """测试超长输入"""
    tool_args = {
        "primary_intent": "COMPLAINT",
        "secondary_intent": "CONSULT",
        "tertiary_intent": None,
        "confidence": 0.80,
        "slots": {"complaint_content": "很长的内容"},
    }
    mock_response = create_mock_response_with_tool_calls(tool_args)

    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    long_query = "我要投诉" + "!" * 1000

    result = await classifier.classify(long_query)

    assert result is not None


@pytest.mark.asyncio
async def test_special_characters_query(classifier, mock_llm):
    """测试特殊字符输入"""
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("Special chars"))

    # 使用规则能匹配的关键词
    result = await classifier.classify("订单!@#$%^&*()")

    assert result is not None


@pytest.mark.asyncio
async def test_multiple_keywords_match(classifier, mock_llm):
    """测试多个关键词匹配"""
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM failed"))

    # 同时包含订单和退货关键词
    result = await classifier.classify("订单SN123我想退货")

    # 应该匹配其中一个规则
    assert result.confidence == 0.5  # 规则匹配的置信度
