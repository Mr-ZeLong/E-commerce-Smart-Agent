"""意图分类器"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import settings
from app.core.llm_factory import create_openai_llm, maybe_add_cache_control
from app.core.tracing import build_llm_config
from app.intent.config import validate_tertiary_intent
from app.intent.few_shot_loader import (
    format_intent_examples_for_prompt,
    load_intent_examples,
    select_top_k_examples,
)
from app.intent.models import IntentAction, IntentCategory, IntentResult

logger = logging.getLogger(__name__)


class IntentClassifier:
    """意图分类器"""

    supports_multi_intent: bool = True
    RULE_MATCH_CONFIDENCE = 0.8
    DEFAULT_FALLBACK_CONFIDENCE = 0.3
    FUNCTION_CALLING_THRESHOLD = settings.FUNCTION_CALLING_THRESHOLD

    SYSTEM_PROMPT = """你是一个电商客服意图识别专家。请分析用户输入，识别其意图并提取相关槽位。

意图层级定义:
1. 一级意图(primary_intent): ORDER, AFTER_SALES, POLICY, PRODUCT, CART, OTHER
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
                    "enum": [c.value for c in IntentCategory],
                    "description": "一级意图",
                },
                "secondary_intent": {
                    "type": "string",
                    "enum": [a.value for a in IntentAction],
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
        ("CART", "QUERY"): [r"购物车.*(看|查|有什么|内容)", r"我的购物车", r"查看购物车"],
        ("CART", "ADD"): [r"(加|放|添加).*(购物车|车里)", r"购物车.*(加|添)"],
        ("CART", "REMOVE"): [r"(删|移除|清空).*(购物车|车里)"],
        ("ACCOUNT", "QUERY"): [
            r"账户.*(余额|信息|等级|会员|情况)",
            r"我的账户",
            r"我的余额",
            r"优惠券",
            r"会员.*(等级|信息)",
            r"积分",
            r"个人信息",
            r"用户.*信息",
        ],
        ("PAYMENT", "QUERY"): [
            r"支付.*(问题|失败|方式)",
            r"付款.*(问题|失败)",
            r"退款.*(进度|状态)",
            r"钱包",
        ],
        ("LOGISTICS", "QUERY"): [
            r"(物流|快递|包裹).*(哪|状态|进度)",
            r"到哪.*(了|了没)",
            r"什么时候.*(到|送达)",
        ],
        ("COMPLAINT", "QUERY"): [
            r"(投诉|举报|维权|申诉)",
            r"(商品|产品|东西|质量).*(问题|差|坏|不行|破损|瑕疵|缺陷|假货|骗子|欺诈)",
            r"(服务|客服|态度).*(差|恶劣|不好)",
            r"(虚假|夸大|欺骗).*(宣传|广告|描述)",
            r"(发货|物流|快递).*(慢|延迟|虚假)",
            r"要求.*(赔偿|补偿|道歉|处理|解决|给个说法)",
        ],
        ("OTHER", "CONSULT"): [r"^(你好|您好|hi|hello|在吗|有人吗)", r"谢谢|再见|拜拜"],
    }

    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self._fast_llm = llm if llm is not None else create_openai_llm(timeout=15.0, max_retries=1)
        self._compiled_rules = {
            key: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            for key, patterns in self.RULE_PATTERNS.items()
        }
        self._few_shot_examples = load_intent_examples()

    async def classify(
        self, query: str, context: dict[str, Any] | None = None, min_confidence: float = 0.5
    ) -> IntentResult:
        result = self._classify_with_rules(query)
        if result.confidence >= self.FUNCTION_CALLING_THRESHOLD:
            return self._finalize_result(result, query, min_confidence)

        llm_result = await self._classify_with_function_calling(query, context)
        if llm_result is not None and llm_result.confidence >= self.FUNCTION_CALLING_THRESHOLD:
            return self._finalize_result(llm_result, query, min_confidence)

        return self._finalize_result(result, query, min_confidence)

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
        tool_choice: Any = {"type": "function", "function": {"name": "classify_intent"}}
        if "dashscope" in settings.OPENAI_BASE_URL.lower() or settings.LLM_MODEL.startswith("qwen"):
            tool_choice = "auto"
        llm_with_tools = self._fast_llm.bind_tools(
            [self.INTENT_FUNCTION_SCHEMA],
            tool_choice=tool_choice,  # type: ignore
        )
        config = build_llm_config(
            agent_name="intent_classifier",
            tags=["intent", "internal"],
        )
        try:
            response = await asyncio.wait_for(
                llm_with_tools.ainvoke(messages, config=config),
                timeout=5.0,
            )
        except TimeoutError:
            logger.warning("Intent classification LLM call timed out after 5s")
            return None
        except Exception as exc:
            logger.warning("Intent classification LLM call failed: %s", exc)
            return None
        tool_calls = response.tool_calls or []
        if not tool_calls:
            return None
        tool_call = tool_calls[0]
        result_data = tool_call.get("args", {})
        try:
            return self._parse_result(result_data, query)
        except (KeyError, ValueError, AttributeError) as exc:
            logger.warning(f"Failed to parse LLM intent result: {exc}")
            return None

    def _classify_with_rules(self, query: str) -> IntentResult:
        query_lower = query.lower()
        for (primary, secondary), patterns in self._compiled_rules.items():
            for pattern in patterns:
                if pattern.search(query_lower):
                    slots: dict[str, Any] = {"matched_pattern": pattern.pattern}
                    if primary == "CART" and secondary in ("ADD", "REMOVE", "MODIFY", "QUERY"):
                        slots["action"] = secondary
                    return IntentResult(
                        primary_intent=IntentCategory[primary],
                        secondary_intent=IntentAction[secondary],
                        confidence=self.RULE_MATCH_CONFIDENCE,
                        slots=slots,
                        raw_query=query,
                    )
        return IntentResult(
            primary_intent=IntentCategory.OTHER,
            secondary_intent=IntentAction.CONSULT,
            confidence=self.DEFAULT_FALLBACK_CONFIDENCE,
            raw_query=query,
        )

    def _create_messages(self, query: str, context: dict[str, Any] | None = None) -> list:
        user_content = query
        if self._few_shot_examples:
            top_examples = select_top_k_examples(query, self._few_shot_examples, k=3)
            if top_examples:
                user_content = format_intent_examples_for_prompt(top_examples) + "\n" + query
        messages: list = [HumanMessage(content=user_content)]
        if context:
            context_str = "\n".join(f"{k}: {v}" for k, v in context.items())
            messages.insert(0, SystemMessage(content=self.SYSTEM_PROMPT + "\n" + context_str))
        else:
            messages.insert(0, SystemMessage(content=self.SYSTEM_PROMPT))
        return maybe_add_cache_control(messages)

    def _parse_result(self, data: dict[str, Any], query: str) -> IntentResult:
        primary = data.get("primary_intent", "OTHER")
        secondary = data.get("secondary_intent", "CONSULT")
        tertiary = data.get("tertiary_intent")
        confidence = data.get("confidence", 0.5)
        slots = data.get("slots", {})
        primary_intent = IntentCategory[primary]
        secondary_intent = IntentAction[secondary]
        if tertiary and not validate_tertiary_intent(primary_intent, secondary_intent, tertiary):
            tertiary = None
        return IntentResult(
            primary_intent=primary_intent,
            secondary_intent=secondary_intent,
            tertiary_intent=tertiary,
            confidence=confidence,
            slots=slots,
            raw_query=query,
        )

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
