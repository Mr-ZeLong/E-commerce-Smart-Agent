import logging

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.exc import SQLAlchemyError

from app.agents.base import BaseAgent
from app.core.config import settings
from app.intent.few_shot_loader import load_agent_examples
from app.intent.models import IntentCategory, IntentResult
from app.intent.service import IntentRecognitionService
from app.models.state import AgentProcessResult, AgentState

logger = logging.getLogger(__name__)

_INTENT_MAPPINGS: dict[IntentCategory, str] = {
    IntentCategory.ORDER: "order_agent",
    IntentCategory.AFTER_SALES: "order_agent",
    IntentCategory.POLICY: "policy_agent",
    IntentCategory.LOGISTICS: "logistics",
    IntentCategory.ACCOUNT: "account",
    IntentCategory.PAYMENT: "payment",
    IntentCategory.PRODUCT: "product",
    IntentCategory.CART: "cart",
    IntentCategory.PROMOTION: "policy_agent",
    IntentCategory.COMPLAINT: "complaint",
    IntentCategory.OTHER: "policy_agent",
}


class IntentRouterAgent(BaseAgent):
    """意图路由Agent"""

    GREETING_RESPONSE: str = (
        "您好！我是您的智能客服助手，可以帮您查询订单、咨询政策或处理退货。请问有什么可以帮您？"
    )

    def __init__(
        self,
        intent_service: IntentRecognitionService,
        llm: BaseChatModel,
        structured_manager=None,
    ) -> None:
        super().__init__(name="intent_router", llm=llm, system_prompt=None)
        self.intent_service = intent_service
        self.structured_manager = structured_manager
        self._few_shot_examples = load_agent_examples("router")
        logger.debug("IntentRouterAgent initialized")

    async def process(self, state: AgentState) -> AgentProcessResult:
        await self._load_config()
        override = await self._resolve_experiment_prompt(state)
        if override:
            self._dynamic_system_prompt = override
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

        next_agent = await self._route_by_intent(result)
        intent_name = result.primary_intent.value
        logger.debug("Routing decision: intent=%s, next_agent=%s", intent_name, next_agent)

        from app.agents.config_loader import is_agent_enabled

        if next_agent and next_agent != "supervisor" and not await is_agent_enabled(next_agent):
            logger.info("Agent %s is disabled, falling back to policy_agent", next_agent)
            next_agent = "policy_agent"
            if not await is_agent_enabled(next_agent):
                return {
                    "response": "系统无法处理该请求，已为您转接人工客服。",
                    "updated_state": {
                        "intent_result": result.model_dump(),
                        "slots": result.slots or {},
                        "awaiting_clarification": result.needs_clarification,
                        "next_agent": None,
                        "iteration_count": iteration,
                        "needs_human_transfer": True,
                        "transfer_reason": "all_routing_targets_disabled",
                    },
                }

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
                    "intent_result": result.model_dump(),
                    "slots": result.slots or {},
                    "awaiting_clarification": True,
                    "clarification_state": clarification.state.model_dump(),
                    "next_agent": next_agent,
                    "iteration_count": iteration,
                },
            }

        updated_state = {
            "intent_result": result.model_dump(),
            "slots": result.slots or {},
            "awaiting_clarification": result.needs_clarification,
            "next_agent": next_agent,
            "iteration_count": iteration,
        }

        # retry_requested handling
        if state.get("retry_requested") and next_agent:
            current_agent = state.get("current_agent")
            if current_agent and (
                (next_agent == "policy_agent" and current_agent == "policy_agent")
                or (next_agent == "order_agent" and current_agent == "order_agent")
                or (next_agent == "logistics" and current_agent == "logistics")
                or (next_agent == "account" and current_agent == "account")
                or (next_agent == "payment" and current_agent == "payment")
                or (next_agent == "product" and current_agent == "product")
                or (next_agent == "cart" and current_agent == "cart")
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
            greeting = await self._personalized_greeting(user_id)
            return {"response": greeting, "updated_state": updated_state}

        if not next_agent:
            return {
                "response": "无法确定处理该请求的专业代理，请尝试换一种方式描述您的问题。",
                "updated_state": {**updated_state, "needs_human_transfer": True},
            }

        logger.info("Routing to agent: %s", next_agent)
        return {"response": "", "updated_state": updated_state}

    async def _personalized_greeting(self, user_id: int | None) -> str:
        if self.structured_manager is None or user_id is None:
            return self.GREETING_RESPONSE
        from app.core.database import async_session_maker

        async with async_session_maker() as session:
            try:
                profile = await self.structured_manager.get_user_profile(session, user_id)
                prefix = ""
                if profile:
                    prefix = f"您好，尊敬的 {profile.membership_level} 会员！"
                summaries = await self.structured_manager.get_recent_summaries(
                    session, user_id, limit=3
                )
                unresolved_intents = {"REFUND", "AFTER_SALES", "PAYMENT"}
                for s in summaries:
                    if s.resolved_intent in unresolved_intents:
                        issue_text = (
                            "我们注意到您之前有一笔退款/售后申请仍在处理中，"
                            if s.resolved_intent in {"REFUND", "AFTER_SALES"}
                            else "我们注意到您之前有支付相关的问题尚未解决，"
                        )
                        return (
                            f"{prefix}我是您的智能客服助手。{issue_text}"
                            "我可以帮您查询最新进度，请问有什么可以帮您？"
                        )
                if prefix:
                    return (
                        f"{prefix}我是您的智能客服助手，"
                        "可以帮您查询订单、咨询政策或处理退货。请问有什么可以帮您？"
                    )
            except (SQLAlchemyError, ConnectionError, OSError):
                logger.exception("Failed to fetch user profile for greeting personalization")
        return self.GREETING_RESPONSE

    async def _route_by_intent(self, result: IntentResult) -> str:
        from app.agents.config_loader import get_target_agent_for_intent

        intent_name = (
            result.primary_intent.value
            if isinstance(result.primary_intent, IntentCategory)
            else str(result.primary_intent)
        )
        fallback = _INTENT_MAPPINGS.get(
            result.primary_intent if isinstance(result.primary_intent, IntentCategory) else None,
            "supervisor",
        )
        return await get_target_agent_for_intent(intent_name, fallback=fallback)
