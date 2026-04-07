from enum import Enum

from app.agents.base import AgentResult, BaseAgent


class Intent(str, Enum):
    """意图枚举"""
    ORDER = "ORDER"
    POLICY = "POLICY"
    REFUND = "REFUND"
    OTHER = "OTHER"


ROUTER_PROMPT = """你是一个电商客服分类器。根据用户输入，归类为以下四种意图之一：

- "ORDER": 用户询问关于他们自己的订单状态、物流、详情等（但不是退货）。
  示例："我的订单到哪了？"、"查询订单 SN20240001"

- "POLICY": 用户询问关于平台通用的退换货、运费、时效等政策信息。
  示例："内衣可以退货吗？"、"运费怎么算？"

- "REFUND": 用户明确表示要办理退货、退款、换货等售后服务。
  示例："我要退货"、"申请退款"、"这个订单我不要了"

- "OTHER": 用户进行闲聊、打招呼或提出与上述无关的问题。
  示例："你好"、"讲个笑话"

只返回分类标签（ORDER/POLICY/REFUND/OTHER），不要返回任何其他文字。"""


class RouterAgent(BaseAgent):
    """
    路由 Agent

    职责：
    1. 识别用户意图
    2. 决定调用哪个 Specialist Agent
    3. 处理简单的闲聊/问候
    """

    def __init__(self):
        super().__init__(
            name="router",
            system_prompt=ROUTER_PROMPT
        )

    async def process(self, state: dict) -> AgentResult:
        """处理用户输入，识别意图并路由"""
        question = state.get("question", "")

        # 简单的规则前置过滤（减少 LLM 调用）
        quick_intent = self._quick_intent_check(question)
        if quick_intent:
            intent = quick_intent
        else:
            # 调用 LLM 进行意图识别
            intent = await self._llm_intent_recognition(question)

        # 根据意图决定下一个 Agent
        next_agent = self._decide_next_agent(intent)

        # 如果是闲聊，直接返回回复
        if intent == Intent.OTHER:
            return AgentResult(
                response="您好！我是您的智能客服助手，可以帮您查询订单、咨询政策或处理退货。请问有什么可以帮您？",
                updated_state={
                    "intent": intent,
                    "next_agent": next_agent
                }
            )

        return AgentResult(
            response="",  # 空响应，由下一个 Agent 生成
            updated_state={
                "intent": intent,
                "next_agent": next_agent
            }
        )

    def _quick_intent_check(self, question: str) -> Intent | None:
        """快速意图检查（规则匹配，减少 LLM 调用）"""
        q = question.lower()

        # 退货关键词
        refund_keywords = ["退货", "退款", "退钱", "不要了", "换货"]
        if any(kw in q for kw in refund_keywords):
            return Intent.REFUND

        # 订单关键词
        order_keywords = ["订单", "物流", "到哪了", "快递", "发货", "签收", "SN"]
        if any(kw in q for kw in order_keywords):
            return Intent.ORDER

        # 简单的问候检测
        greeting_keywords = ["你好", "您好", "hi", "hello", "在吗"]
        if any(q.strip().startswith(kw) for kw in greeting_keywords) and len(q) < 10:
            return Intent.OTHER

        return None

    async def _llm_intent_recognition(self, question: str) -> Intent:
        """调用 LLM 进行意图识别"""
        try:
            messages = self._create_messages(question)
            response = await self._call_llm(messages)

            intent_str = response.strip().upper()

            # 验证返回的意图是否合法
            if intent_str in [Intent.ORDER, Intent.POLICY, Intent.REFUND, Intent.OTHER]:
                return Intent(intent_str)
            else:
                # 容错处理
                print(f"[Router] 无法识别的意图: {intent_str}，默认 OTHER")
                return Intent.OTHER

        except Exception as e:
            print(f"[Router] 意图识别失败: {e}，默认 OTHER")
            return Intent.OTHER

    def _decide_next_agent(self, intent: Intent) -> str:
        """
        根据意图决定下一个 Agent

        Returns:
            "policy" - 政策专家
            "order" - 订单专家（也处理退货）
            "supervisor" - 监督者（用于 OTHER）
        """
        if intent == Intent.POLICY:
            return "policy"
        elif intent in [Intent.ORDER, Intent.REFUND]:
            return "order"
        else:
            return "supervisor"
