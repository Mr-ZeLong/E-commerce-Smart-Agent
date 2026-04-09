"""意图分类器

实现3层Fallback机制：
- Layer 1: Function Calling（使用OpenAI Function Calling）
- Layer 2: 普通LLM + JSON解析（降级方案）
- Layer 3: 规则匹配（保底方案）
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.llm_factory import create_openai_llm
from app.intent.config import TERTIARY_INTENT_CONFIG, validate_tertiary_intent
from app.intent.models import IntentAction, IntentCategory, IntentResult

logger = logging.getLogger(__name__)


class IntentClassifier:
    """意图分类器 - 3层Fallback机制"""

    # 类属性
    supports_multi_intent: bool = True

    # 类常量
    RULE_MATCH_CONFIDENCE = 0.5
    DEFAULT_FALLBACK_CONFIDENCE = 0.3

    FUNCTION_CALLING_THRESHOLD = 0.7
    JSON_PARSING_THRESHOLD = 0.6

    # Few-shot示例提示词
    FEW_SHOT_EXAMPLES = """
示例1:
用户输入: "我想查一下订单SN20240001到哪里了"
输出: {
    "primary_intent": "ORDER",
    "secondary_intent": "QUERY",
    "tertiary_intent": "ORDER_TRACKING_DETAIL",
    "confidence": 0.95,
    "slots": {"order_sn": "SN20240001", "query_type": "物流追踪"}
}

示例2:
用户输入: "这件衣服太大了，我想退货"
输出: {
    "primary_intent": "AFTER_SALES",
    "secondary_intent": "APPLY",
    "tertiary_intent": "REFUND",
    "confidence": 0.92,
    "slots": {"reason_category": "尺码不合适", "specific_item": "衣服"}
}

示例3:
用户输入: "你们运费怎么算？"
输出: {
    "primary_intent": "POLICY",
    "secondary_intent": "CONSULT",
    "tertiary_intent": "POLICY_SHIPPING_FEE",
    "confidence": 0.88,
    "slots": {"policy_topic": "运费政策"}
}

示例4:
用户输入: "给我推荐几款适合夏天的连衣裙"
输出: {
    "primary_intent": "RECOMMENDATION",
    "secondary_intent": "CONSULT",
    "tertiary_intent": "RECOMMEND_PERSONALIZED",
    "confidence": 0.85,
    "slots": {"product_category": "连衣裙", "season": "夏天"}
}

示例5:
用户输入: "购物车里的东西帮我结算"
输出: {
    "primary_intent": "CART",
    "secondary_intent": "QUERY",
    "tertiary_intent": "CART_CHECKOUT",
    "confidence": 0.90,
    "slots": {}
}
"""

    # 系统提示词
    SYSTEM_PROMPT = f"""你是一个电商客服意图识别专家。请分析用户输入，识别其意图并提取相关槽位。

意图层级定义:
1. 一级意图(primary_intent): 业务域 - ORDER(订单), AFTER_SALES(售后), POLICY(政策), PRODUCT(商品), RECOMMENDATION(推荐), CART(购物车), ACCOUNT(账户), PROMOTION(促销), PAYMENT(支付), LOGISTICS(物流), COMPLAINT(投诉), OTHER(其他)
2. 二级意图(secondary_intent): 动作类型 - QUERY(查询), APPLY(申请), MODIFY(修改), CANCEL(取消), CONSULT(咨询), ADD(添加), REMOVE(移除), COMPARE(比较)
3. 三级意图(tertiary_intent): 具体场景，如REFUND(退款), EXCHANGE(换货), ORDER_TRACKING_DETAIL(订单追踪详情)等

可用三级意图配置:
- AFTER_SALES/APPLY: REFUND, EXCHANGE, REPAIR
- AFTER_SALES/CONSULT: REFUND_SHIPPING_FEE, REFUND_TIMELINE, EXCHANGE_SIZE, WARRANTY_POLICY
- ORDER/QUERY: ORDER_TRACKING_DETAIL, ORDER_STATUS_ESTIMATE, ORDER_AMOUNT_DETAIL
- POLICY/CONSULT: POLICY_RETURN_EXCEPTION, POLICY_SHIPPING_FEE, POLICY_DELIVERY_TIME
- PRODUCT/QUERY: PRODUCT_STOCK, PRODUCT_SPEC, PRODUCT_DETAIL, PRODUCT_PRICE_COMPARE, PRODUCT_REVIEW
- PRODUCT/COMPARE: PRODUCT_PRICE_COMPARE, PRODUCT_SPEC_COMPARE
- RECOMMENDATION/CONSULT: RECOMMEND_SIMILAR, RECOMMEND_COMPLEMENTARY, RECOMMEND_PERSONALIZED, RECOMMEND_TRENDING
- CART/QUERY: CART_VIEW, CART_CHECKOUT
- CART/ADD: CART_ADD_ITEM, CART_ADD_BULK
- CART/REMOVE: CART_REMOVE_ITEM, CART_CLEAR_ALL

{FEW_SHOT_EXAMPLES}

请输出JSON格式，包含以下字段:
- primary_intent: 一级意图名称
- secondary_intent: 二级意图名称
- tertiary_intent: 三级意图名称(可选，如果没有合适的填null)
- confidence: 置信度(0-1之间)
- slots: 提取的槽位信息(对象格式)

注意:
1. 三级意图必须从允许列表中选择
2. 如果无法确定三级意图，设为null
3. 槽位提取应尽可能完整
4. 置信度反映你对分类结果的确信程度
"""

    # Function Calling 函数定义
    INTENT_FUNCTION_SCHEMA = {
        "name": "classify_intent",
        "description": "分析用户输入，识别电商客服意图并提取槽位",
        "parameters": {
            "type": "object",
            "properties": {
                "primary_intent": {
                    "type": "string",
                    "enum": [
                        "ORDER", "AFTER_SALES", "POLICY", "PRODUCT",
                        "RECOMMENDATION", "CART", "ACCOUNT", "PROMOTION",
                        "PAYMENT", "LOGISTICS", "COMPLAINT", "OTHER"
                    ],
                    "description": "一级意图：业务域"
                },
                "secondary_intent": {
                    "type": "string",
                    "enum": ["QUERY", "APPLY", "MODIFY", "CANCEL", "CONSULT", "ADD", "REMOVE", "COMPARE"],
                    "description": "二级意图：动作类型"
                },
                "tertiary_intent": {
                    "type": "string",
                    "description": "三级意图：具体场景(可选)"
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "置信度(0-1)"
                },
                "slots": {
                    "type": "object",
                    "description": "提取的槽位信息"
                }
            },
            "required": ["primary_intent", "secondary_intent", "confidence", "slots"]
        }
    }

    # 规则匹配关键词
    # 注意：顺序很重要！更具体的规则应该放在前面
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
        # POLICY规则放在AFTER_SALES/CONSULT之前，避免"运费怎么算"被错误匹配
        ("POLICY", "CONSULT"): [
            r"^(运费|邮费|快递费).*(多少|怎么算|政策)",
            r"(退换货|退货).*(政策|规则)",
            r"多久.*(到|发货|送达)",
            r"支持.*(退换|退货)"
        ],
        ("AFTER_SALES", "CONSULT"): [
            r"(退货|退款|换货).*(政策|规则|条件|多久)",
            r"怎么.*(退|换)",
            r"(运费|邮费).*(谁出)",  # 仅匹配"谁出"，不包含"怎么算"
        ],
        ("PRODUCT", "QUERY"): [
            r"(商品|产品|东西).*(有货|库存|价格|多少钱)",
            r"这个.*(怎么样|好不好)",
            r"有.*(货|库存)"
        ],
        ("PRODUCT", "COMPARE"): [
            r"(对比|比较|哪个好|区别)",
            r"和.*(比|区别)"
        ],
        ("RECOMMENDATION", "CONSULT"): [
            r"推荐.*(商品|东西|产品)",
            r"有.*(推荐|好的)",
            r"适合.*(我|用)"
        ],
        ("CART", "QUERY"): [
            r"购物车.*(看|查|有什么)",
            r"我的购物车"
        ],
        ("CART", "ADD"): [
            r"(加|放|添加).*(购物车|车里)",
            r"购物车.*(加|添)"
        ],
        ("CART", "REMOVE"): [
            r"(删|移除|清空).*(购物车|车里)"
        ],
        ("LOGISTICS", "QUERY"): [
            r"(物流|快递|包裹).*(哪|状态|进度)",
            r"到哪.*(了|了没)",
            r"什么时候.*(到|送达)"
        ],
        ("OTHER", "CONSULT"): [
            r"^(你好|您好|hi|hello|在吗|有人吗)",
            r"谢谢|再见|拜拜"
        ]
    }

    def __init__(self, llm: ChatOpenAI | None = None):
        """
        初始化意图分类器

        Args:
            llm: 可选的LLM实例，用于测试时注入mock
        """
        if llm is not None:
            self.llm = llm
        else:
            self.llm = create_openai_llm()

        self._intent_function = self.INTENT_FUNCTION_SCHEMA

        # 预编译正则表达式
        self._compiled_rules: dict[tuple[str, str], list[re.Pattern]] = {
            key: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            for key, patterns in self.RULE_PATTERNS.items()
        }

    async def classify(self, query: str, context: dict[str, Any] | None = None) -> IntentResult:
        """
        分类用户意图 - 3层Fallback机制

        Args:
            query: 用户输入
            context: 可选的上下文信息

        Returns:
            IntentResult: 意图识别结果
        """
        # Layer 1: Function Calling
        try:
            result = await self._classify_with_function_calling(query, context)
            if result is not None and result.confidence >= self.FUNCTION_CALLING_THRESHOLD:
                return result
        except Exception as e:
            # Function Calling失败，继续降级
            logger.warning(f"Function calling failed: {e}, falling back to JSON parsing")

        # Layer 2: JSON解析
        try:
            result = await self._classify_with_json(query, context)
            if result is not None and result.confidence >= self.JSON_PARSING_THRESHOLD:
                return result
        except Exception as e:
            # JSON解析失败，继续降级
            logger.warning(f"JSON parsing failed: {e}, falling back to rule matching")

        # Layer 3: 规则匹配
        return self._classify_with_rules(query)

    async def _classify_with_function_calling(
        self,
        query: str,
        context: dict[str, Any] | None = None
    ) -> IntentResult | None:
        """
        Layer 1: 使用Function Calling分类

        Args:
            query: 用户输入
            context: 可选的上下文信息

        Returns:
            IntentResult或None（如果失败）
        """
        messages = self._create_messages(query, context)

        # 绑定工具并强制使用classify_intent函数
        llm_with_tools = self.llm.bind_tools(
            [self._intent_function],
            tool_choice={"type": "function", "function": {"name": "classify_intent"}}
        )

        response = await llm_with_tools.ainvoke(messages)

        # 提取工具调用结果
        tool_calls = response.additional_kwargs.get("tool_calls", [])
        if not tool_calls:
            return None

        # 解析第一个工具调用
        tool_call = tool_calls[0]
        function_args = tool_call.get("function", {}).get("arguments", "")

        if isinstance(function_args, str):
            result_data = json.loads(function_args)
        else:
            result_data = function_args

        return self._parse_result(result_data, query)

    async def _classify_with_json(
        self,
        query: str,
        context: dict[str, Any] | None = None
    ) -> IntentResult | None:
        """
        Layer 2: 使用普通LLM + JSON解析

        Args:
            query: 用户输入
            context: 可选的上下文信息

        Returns:
            IntentResult或None（如果失败）
        """
        messages = self._create_messages(query, context)

        response = await self.llm.ainvoke(messages)
        content = str(response.content)

        # 提取JSON部分
        json_match = re.search(r'\{[\s\S]*\}', content)
        if not json_match:
            return None

        result_data = json.loads(json_match.group())
        return self._parse_result(result_data, query)

    def _classify_with_rules(self, query: str) -> IntentResult:
        """
        Layer 3: 使用规则匹配

        Args:
            query: 用户输入

        Returns:
            IntentResult（保底方案）
        """
        query_lower = query.lower()

        for (primary, secondary), patterns in self._compiled_rules.items():
            for pattern in patterns:
                if pattern.search(query_lower):
                    # 匹配成功，构建结果
                    return IntentResult(
                        primary_intent=IntentCategory[primary],
                        secondary_intent=IntentAction[secondary],
                        tertiary_intent=None,
                        confidence=self.RULE_MATCH_CONFIDENCE,
                        slots={"matched_pattern": pattern.pattern},
                        raw_query=query
                    )

        # 默认返回OTHER/CONSULT
        return IntentResult(
            primary_intent=IntentCategory.OTHER,
            secondary_intent=IntentAction.CONSULT,
            tertiary_intent=None,
            confidence=self.DEFAULT_FALLBACK_CONFIDENCE,
            slots={},
            raw_query=query
        )

    def _create_messages(
        self,
        query: str,
        context: dict[str, Any] | None = None
    ) -> list[SystemMessage | HumanMessage]:
        """
        创建消息列表

        Args:
            query: 用户输入
            context: 可选的上下文信息

        Returns:
            消息列表
        """
        messages: list[SystemMessage | HumanMessage] = [
            SystemMessage(content=self.SYSTEM_PROMPT)
        ]

        if context:
            # 添加上下文信息
            context_str = self._format_context(context)
            messages.append(HumanMessage(content=f"上下文信息:\n{context_str}\n\n用户输入: {query}"))
        else:
            messages.append(HumanMessage(content=f"用户输入: {query}"))

        return messages

    def _format_context(self, context: dict[str, Any]) -> str:
        """格式化上下文信息"""
        parts = []
        if "session_id" in context:
            parts.append(f"会话ID: {context['session_id']}")
        if "history" in context:
            parts.append(f"历史对话: {context['history']}")
        if "user_info" in context:
            parts.append(f"用户信息: {context['user_info']}")
        return "\n".join(parts) if parts else "无"

    def _parse_result(self, data: dict[str, Any], query: str) -> IntentResult | None:
        """
        解析分类结果

        Args:
            data: 解析后的JSON数据
            query: 原始查询

        Returns:
            IntentResult或None（如果解析失败）
        """
        try:
            primary = data.get("primary_intent", "OTHER")
            secondary = data.get("secondary_intent", "CONSULT")
            tertiary = data.get("tertiary_intent")
            confidence = data.get("confidence", 0.5)
            slots = data.get("slots", {})

            # 验证并转换枚举
            try:
                primary_intent = IntentCategory[primary]
                secondary_intent = IntentAction[secondary]
            except KeyError:
                # 无效的意图值，返回None触发降级
                return None

            # 验证三级意图
            if tertiary and not validate_tertiary_intent(
                primary_intent, secondary_intent, tertiary
            ):
                # 无效的三级意图，设为None
                tertiary = None

            return IntentResult(
                primary_intent=primary_intent,
                secondary_intent=secondary_intent,
                tertiary_intent=tertiary,
                confidence=confidence,
                slots=slots,
                raw_query=query
            )
        except (KeyError, ValueError, TypeError):
            return None

    def validate_intent_result(self, result: IntentResult) -> tuple[bool, str]:
        """
        验证意图结果的有效性

        Args:
            result: 意图识别结果

        Returns:
            (是否有效, 错误信息)
        """
        # 验证一级意图
        if not isinstance(result.primary_intent, IntentCategory):
            return False, f"无效的一级意图: {result.primary_intent}"

        # 验证二级意图
        if not isinstance(result.secondary_intent, IntentAction):
            return False, f"无效的二级意图: {result.secondary_intent}"

        # 验证三级意图
        if result.tertiary_intent and not validate_tertiary_intent(
            result.primary_intent,
            result.secondary_intent,
            result.tertiary_intent
        ):
            allowed = TERTIARY_INTENT_CONFIG.get(
                (result.primary_intent.value, result.secondary_intent.value),
                {}
            ).get("tertiary_intents", [])
            return False, f"无效的三级意图: {result.tertiary_intent}, 允许的值: {allowed}"

        # 验证置信度
        if not 0 <= result.confidence <= 1:
            return False, f"置信度超出范围: {result.confidence}"

        return True, ""


class IntentClassifierWithFallback:
    """带完整Fallback机制的意图分类器包装器"""

    def __init__(self, llm: ChatOpenAI | None = None):
        self.classifier = IntentClassifier(llm)

    async def classify(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        min_confidence: float = 0.5
    ) -> IntentResult:
        """
        分类用户意图，包含完整验证

        Args:
            query: 用户输入
            context: 可选的上下文信息
            min_confidence: 最低置信度阈值

        Returns:
            IntentResult: 意图识别结果
        """
        result = await self.classifier.classify(query, context)

        # 验证结果
        is_valid, error_msg = self.classifier.validate_intent_result(result)

        if not is_valid:
            # 验证失败，降级到规则匹配
            result = self.classifier._classify_with_rules(query)
            # 确保slots是可变的，并添加validation_error
            slots = dict(result.slots or {})
            slots["validation_error"] = error_msg
            result.slots = slots

        # 如果置信度低于阈值，标记需要澄清
        if result.confidence < min_confidence:
            result.needs_clarification = True
            result.clarification_question = self._generate_clarification_question(result)

        return result

    def _generate_clarification_question(self, result: IntentResult) -> str:
        """生成澄清问题"""
        primary = result.primary_intent.value
        secondary = result.secondary_intent.value

        clarification_map = {
            ("ORDER", "QUERY"): "请问您想查询哪个订单的信息？可以提供订单号吗？",
            ("AFTER_SALES", "APPLY"): "请问您需要办理退货、换货还是维修服务？",
            ("PRODUCT", "QUERY"): "请问您想了解商品的哪方面信息？",
            ("POLICY", "CONSULT"): "请问您想了解哪方面的政策？",
            ("CART", "ADD"): "请问您想添加什么商品到购物车？",
        }

        return clarification_map.get(
            (primary, secondary),
            "抱歉，我没有完全理解您的意思，能否再说详细一些？"
        )
