"""意图分类器"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.llm_factory import create_openai_llm
from app.intent.config import validate_tertiary_intent
from app.intent.models import IntentAction, IntentCategory, IntentResult

logger = logging.getLogger(__name__)


class IntentClassifier:
    """意图分类器"""

    supports_multi_intent: bool = True
    RULE_MATCH_CONFIDENCE = 0.5
    DEFAULT_FALLBACK_CONFIDENCE = 0.3
    FUNCTION_CALLING_THRESHOLD = settings.FUNCTION_CALLING_THRESHOLD
    JSON_PARSING_THRESHOLD = settings.JSON_PARSING_THRESHOLD

    SYSTEM_PROMPT = """你是一个电商客服意图识别专家。请分析用户输入，识别其意图并提取相关槽位。

意图层级定义:
1. 一级意图(primary_intent): ORDER, AFTER_SALES, POLICY, PRODUCT, RECOMMENDATION, CART, OTHER
2. 二级意图(secondary_intent): QUERY, APPLY, MODIFY, CANCEL, CONSULT, ADD, REMOVE, COMPARE
3. 三级意图(tertiary_intent): 具体场景，可选

请输出JSON格式: primary_intent, secondary_intent, tertiary_intent, confidence, slots
"""

    INTENT_FUNCTION_SCHEMA = {
        "name": "classify_intent",
        "description": "分析用户输入，识别电商客服意图并提取槽位",
        "parameters": {
            "type": "object",
            "properties": {
                "primary_intent": {
                    "type": "string",
                    "enum": [
                        "ORDER",
                        "AFTER_SALES",
                        "POLICY",
                        "PRODUCT",
                        "RECOMMENDATION",
                        "CART",
                        "ACCOUNT",
                        "PROMOTION",
                        "PAYMENT",
                        "LOGISTICS",
                        "COMPLAINT",
                        "OTHER",
                    ],
                    "description": "一级意图",
                },
                "secondary_intent": {
                    "type": "string",
                    "enum": [
                        "QUERY",
                        "APPLY",
                        "MODIFY",
                        "CANCEL",
                        "CONSULT",
                        "ADD",
                        "REMOVE",
                        "COMPARE",
                    ],
                    "description": "二级意图",
                },
                "tertiary_intent": {"type": "string", "description": "三级意图"},
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "置信度",
                },
                "slots": {"type": "object", "description": "槽位"},
            },
            "required": ["primary_intent", "secondary_intent", "confidence", "slots"],
        },
    }

    RULE_PATTERNS: dict[tuple[str, str], list[str]] = {
        ("ORDER", "QUERY"): [
            r"订单.*(状态|进度|情况)",
            r"查.*订单",
            r"订单.*到哪",
            r"SN\d+",
            r"我的订单",
        ],
        ("AFTER_SALES", "APPLY"): [
            r"(退货|退款|换货|售后).*(申请|办理|要)",
            r"想.*(退|换)",
            r"(不要|不满意).*(了|的)",
        ],
        ("POLICY", "CONSULT"): [
            r"^(运费|邮费|快递费).*(多少|怎么算|政策)",
            r"(退换货|退货).*(政策|规则)",
            r"多久.*(到|发货|送达)",
            r"支持.*(退换|退货)",
        ],
        ("AFTER_SALES", "CONSULT"): [
            r"(退货|退款|换货).*(政策|规则|条件|多久)",
            r"怎么.*(退|换)",
            r"(运费|邮费).*(谁出)",
        ],
        ("PRODUCT", "QUERY"): [
            r"(商品|产品|东西).*(有货|库存|价格|多少钱)",
            r"这个.*(怎么样|好不好)",
            r"有.*(货|库存)",
        ],
        ("PRODUCT", "COMPARE"): [r"(对比|比较|哪个好|区别)", r"和.*(比|区别)"],
        ("RECOMMENDATION", "CONSULT"): [
            r"推荐.*(商品|东西|产品)",
            r"有.*(推荐|好的)",
            r"适合.*(我|用)",
        ],
        ("CART", "QUERY"): [r"购物车.*(看|查|有什么)", r"我的购物车"],
        ("CART", "ADD"): [r"(加|放|添加).*(购物车|车里)", r"购物车.*(加|添)"],
        ("CART", "REMOVE"): [r"(删|移除|清空).*(购物车|车里)"],
        ("LOGISTICS", "QUERY"): [
            r"(物流|快递|包裹).*(哪|状态|进度)",
            r"到哪.*(了|了没)",
            r"什么时候.*(到|送达)",
        ],
        ("OTHER", "CONSULT"): [r"^(你好|您好|hi|hello|在吗|有人吗)", r"谢谢|再见|拜拜"],
    }

    def __init__(self, llm: ChatOpenAI | None = None):
        if llm is not None:
            self.llm = llm
        else:
            self.llm = create_openai_llm()
        self._compiled_rules = {
            key: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            for key, patterns in self.RULE_PATTERNS.items()
        }

    async def classify(
        self, query: str, context: dict[str, Any] | None = None, min_confidence: float = 0.5
    ) -> IntentResult:
        # Layer 1: Function Calling
        try:
            result = await self._classify_with_function_calling(query, context)
            if result is not None and result.confidence >= self.FUNCTION_CALLING_THRESHOLD:
                return self._finalize_result(result, query, min_confidence)
        except Exception as e:
            logger.warning(f"Function calling failed: {e}, falling back")

        # Layer 2: JSON解析
        try:
            result = await self._classify_with_json(query, context)
            if result is not None and result.confidence >= self.JSON_PARSING_THRESHOLD:
                return self._finalize_result(result, query, min_confidence)
        except Exception as e:
            logger.warning(f"JSON parsing failed: {e}, falling back to rules")

        # Layer 3: 规则匹配
        return self._finalize_result(self._classify_with_rules(query), query, min_confidence)

    def _finalize_result(
        self, result: IntentResult, query: str, min_confidence: float
    ) -> IntentResult:
        is_valid, _ = self._validate_result(result)
        if not is_valid:
            result = self._classify_with_rules(query)

        if result.confidence < min_confidence:
            result.needs_clarification = True
            result.clarification_question = self._generate_clarification_question(result)

        return result

    def _validate_result(self, result: IntentResult) -> tuple[bool, str]:
        if not isinstance(result.primary_intent, IntentCategory):
            return False, f"无效的一级意图: {result.primary_intent}"
        if not isinstance(result.secondary_intent, IntentAction):
            return False, f"无效的二级意图: {result.secondary_intent}"
        if result.tertiary_intent and not validate_tertiary_intent(
            result.primary_intent, result.secondary_intent, result.tertiary_intent
        ):
            return False, f"无效的三级意图: {result.tertiary_intent}"
        if not 0 <= result.confidence <= 1:
            return False, f"置信度超出范围: {result.confidence}"
        return True, ""

    validate_intent_result = _validate_result

    async def _classify_with_function_calling(
        self, query: str, context: dict[str, Any] | None = None
    ) -> IntentResult | None:
        messages = self._create_messages(query, context)
        llm_with_tools = self.llm.bind_tools(
            [self.INTENT_FUNCTION_SCHEMA],
            tool_choice={"type": "function", "function": {"name": "classify_intent"}},
        )
        response = await llm_with_tools.ainvoke(messages)
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls and hasattr(response, "additional_kwargs"):
            tool_calls = response.additional_kwargs.get("tool_calls", [])
        if not tool_calls:
            return None
        tool_call = tool_calls[0]
        function_args = tool_call.get("args", {})
        if isinstance(function_args, str):
            result_data = json.loads(function_args)
        else:
            result_data = function_args
        return self._parse_result(result_data, query)

    async def _classify_with_json(
        self, query: str, context: dict[str, Any] | None = None
    ) -> IntentResult | None:
        messages = self._create_messages(query, context)
        response = await self.llm.ainvoke(messages)
        content = str(response.content)
        json_match = re.search(r"\{[\s\S]*\}", content)
        if not json_match:
            return None
        result_data = json.loads(json_match.group())
        return self._parse_result(result_data, query)

    def _classify_with_rules(self, query: str) -> IntentResult:
        query_lower = query.lower()
        for (primary, secondary), patterns in self._compiled_rules.items():
            for pattern in patterns:
                if pattern.search(query_lower):
                    return IntentResult(
                        primary_intent=IntentCategory[primary],
                        secondary_intent=IntentAction[secondary],
                        confidence=self.RULE_MATCH_CONFIDENCE,
                        slots={"matched_pattern": pattern.pattern},
                        raw_query=query,
                    )
        return IntentResult(
            primary_intent=IntentCategory.OTHER,
            secondary_intent=IntentAction.CONSULT,
            confidence=self.DEFAULT_FALLBACK_CONFIDENCE,
            raw_query=query,
        )

    def _create_messages(self, query: str, context: dict[str, Any] | None = None) -> list:
        messages: list = [HumanMessage(content=query)]
        if context:
            context_str = "\n".join(f"{k}: {v}" for k, v in context.items())
            messages.insert(0, SystemMessage(content=self.SYSTEM_PROMPT + "\n" + context_str))
        else:
            messages.insert(0, SystemMessage(content=self.SYSTEM_PROMPT))
        return messages

    def _parse_result(self, data: dict[str, Any], query: str) -> IntentResult | None:
        try:
            primary = data.get("primary_intent", "OTHER")
            secondary = data.get("secondary_intent", "CONSULT")
            tertiary = data.get("tertiary_intent")
            confidence = data.get("confidence", 0.5)
            slots = data.get("slots", {})
            primary_intent = IntentCategory[primary]
            secondary_intent = IntentAction[secondary]
            if tertiary and not validate_tertiary_intent(
                primary_intent, secondary_intent, tertiary
            ):
                tertiary = None
            return IntentResult(
                primary_intent=primary_intent,
                secondary_intent=secondary_intent,
                tertiary_intent=tertiary,
                confidence=confidence,
                slots=slots,
                raw_query=query,
            )
        except (KeyError, ValueError, TypeError):
            return None

    def _generate_clarification_question(self, result: IntentResult) -> str:
        clarification_map = {
            ("ORDER", "QUERY"): "请问您想查询哪个订单的信息？可以提供订单号吗？",
            ("AFTER_SALES", "APPLY"): "请问您需要办理退货、换货还是维修服务？",
            ("PRODUCT", "QUERY"): "请问您想了解商品的哪方面信息？",
            ("POLICY", "CONSULT"): "请问您想了解哪方面的政策？",
            ("CART", "ADD"): "请问您想添加什么商品到购物车？",
        }
        return clarification_map.get(
            (result.primary_intent.value, result.secondary_intent.value),
            "抱歉，我没有完全理解您的意思，能否再说详细一些？",
        )
