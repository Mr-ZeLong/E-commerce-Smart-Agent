import logging
from typing import Any

from app.agents.base import BaseAgent
from app.core.config import settings
from app.intent.models import IntentCategory, IntentResult
from app.intent.service import IntentRecognitionService
from app.models.state import AgentState

logger = logging.getLogger(__name__)

_INTENT_MAPPINGS: dict[IntentCategory, str] = {
    IntentCategory.ORDER: "order",
    IntentCategory.AFTER_SALES: "order",
    IntentCategory.POLICY: "policy",
    IntentCategory.PRODUCT: "supervisor",
    IntentCategory.RECOMMENDATION: "supervisor",
    IntentCategory.CART: "order",
    IntentCategory.OTHER: "supervisor",
}


class IntentRouterAgent(BaseAgent):
    """意图路由Agent"""

    GREETING_RESPONSE: str = (
        "您好！我是您的智能客服助手，可以帮您查询订单、咨询政策或处理退货。请问有什么可以帮您？"
    )

    def __init__(self) -> None:
        super().__init__(name="intent_router", system_prompt=None)
        from app.core.redis import get_redis_client

        self.intent_service = IntentRecognitionService(redis_client=get_redis_client())
        logger.debug("IntentRouterAgent initialized")

    async def process(self, state: AgentState) -> dict[str, Any]:
        query = state.get("question", "")
        session_id = state.get("thread_id", "")
        user_id = state.get("user_id")
        iteration = state.get("iteration_count", 0) + 1

        logger.info(
            "Processing query for user_id=%s, session_id=%s, query='%s'", user_id, session_id, query
        )

        result = await self.intent_service.recognize(
            query=query,
            session_id=session_id,
            conversation_history=state.get("history", []),
        )
        logger.info(
            "Intent recognized: primary=%s, confidence=%.2f",
            result.primary_intent,
            result.confidence,
        )

        next_agent = self._route_by_intent(result)
        intent_name = result.primary_intent.value
        logger.debug("Routing decision: intent=%s, next_agent=%s", intent_name, next_agent)

        if iteration > settings.MAX_ROUTER_ITERATIONS:
            logger.warning("Router 迭代次数超过限制: %s", iteration)
            return {
                "response": "系统处理步数过多，请联系人工客服。",
                "updated_state": {"iteration_count": iteration, "needs_human_transfer": True},
            }

        if result.needs_clarification or result.missing_slots:
            logger.info("Clarification needed, missing_slots=%s", result.missing_slots)
            clarification = await self.intent_service.clarify(
                session_id=session_id,
                user_response=query,
            )
            return {
                "response": clarification.response,
                "updated_state": {
                    "intent_result": result.to_dict(),
                    "slots": result.slots or {},
                    "awaiting_clarification": True,
                    "clarification_state": clarification.state,
                    "next_agent": next_agent,
                    "iteration_count": iteration,
                },
            }

        updated_state = {
            "intent_result": result.to_dict(),
            "slots": result.slots or {},
            "awaiting_clarification": result.needs_clarification,
            "next_agent": next_agent,
            "iteration_count": iteration,
        }

        # retry_requested handling
        if state.get("retry_requested") and next_agent:
            current_agent = state.get("current_agent")
            if current_agent and (
                (next_agent == "policy" and current_agent == "policy_agent")
                or (next_agent == "order" and current_agent == "order_agent")
                or (next_agent == "supervisor" and current_agent == "policy_agent")
            ):
                return {
                    "response": "系统对该问题没有足够把握，已为您转接人工客服。",
                    "updated_state": {
                        **updated_state,
                        "needs_human_transfer": True,
                        "transfer_reason": "confidence_retry_routed_to_same_agent",
                    },
                }
            updated_state["retry_requested"] = False

        if intent_name == IntentCategory.OTHER.value:
            logger.info("OTHER intent detected, returning greeting response")
            return {"response": self.GREETING_RESPONSE, "updated_state": updated_state}

        if next_agent == "supervisor" and result.primary_intent in (
            IntentCategory.PRODUCT,
            IntentCategory.RECOMMENDATION,
        ):
            return {
                "response": "抱歉，目前暂时不支持商品查询和推荐服务，已为您转接人工客服。",
                "updated_state": updated_state,
            }

        if not next_agent:
            return {
                "response": "无法确定处理该请求的专业代理，请尝试换一种方式描述您的问题。",
                "updated_state": {**updated_state, "needs_human_transfer": True},
            }

        logger.info("Routing to agent: %s", next_agent)
        return {"response": "", "updated_state": updated_state}

    def _route_by_intent(self, result: IntentResult) -> str:
        return _INTENT_MAPPINGS.get(result.primary_intent, "supervisor")
