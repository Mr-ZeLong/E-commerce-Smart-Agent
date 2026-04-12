import logging

from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.base import BaseAgent
from app.graph.parallel import plan_dispatch
from app.models.state import AgentProcessResult, AgentState

logger = logging.getLogger(__name__)

_INTENT_TO_AGENT: dict[str, str] = {
    "ORDER": "order_agent",
    "AFTER_SALES": "order_agent",
    "POLICY": "policy_agent",
    "LOGISTICS": "logistics",
    "ACCOUNT": "account",
    "PAYMENT": "payment",
    "PRODUCT": "product",
    "CART": "cart",
    "RECOMMENDATION": "product",
    "PROMOTION": "policy_agent",
    "COMPLAINT": "order_agent",
    "OTHER": "policy_agent",
}


class SupervisorAgent(BaseAgent):
    def __init__(self, llm: BaseChatModel):
        super().__init__(name="supervisor", llm=llm, system_prompt=None)

    async def process(self, state: AgentState) -> AgentProcessResult:
        await self._load_config()
        from app.agents.config_loader import is_agent_enabled

        intent_result = state.get("intent_result") or {}
        primary = intent_result.get("primary_intent")
        slots = state.get("slots") or {}
        pending = slots.get("pending_intents", [])
        iteration = state.get("iteration_count", 0)
        completed = {
            sa["agent"] for sa in state.get("sub_answers", []) if sa.get("iteration") == iteration
        }

        from app.agents.config_loader import get_target_agent_for_intent

        primary_str = str(primary) if primary is not None else "OTHER"
        primary_agent = await get_target_agent_for_intent(
            primary_str, fallback=_INTENT_TO_AGENT.get(primary_str, "policy_agent")
        )
        if not await is_agent_enabled(primary_agent):
            logger.info("Agent %s is disabled, falling back to policy_agent", primary_agent)
            primary_agent = "policy_agent"
            if not await is_agent_enabled(primary_agent):
                logger.error("Fallback policy_agent is also disabled; forcing human transfer")
                return {
                    "response": "",
                    "updated_state": {
                        "next_agent": None,
                        "execution_mode": "serial",
                        "pending_agent_results": [],
                        "supervisor_reasoning": "Target and fallback agents disabled",
                        "needs_human_transfer": True,
                        "transfer_reason": "all_routing_targets_disabled",
                    },
                }

        plan_agents = [primary_agent]
        plan_intents = [primary_str]
        seen = {primary_agent}
        for p in pending:
            pname = p.get("primary_intent")
            if not pname:
                continue
            pagent = await get_target_agent_for_intent(
                str(pname), fallback=_INTENT_TO_AGENT.get(str(pname), "policy_agent")
            )
            if not await is_agent_enabled(pagent):
                logger.info("Agent %s is disabled, skipping in plan", pagent)
                continue
            if pagent not in seen:
                plan_agents.append(pagent)
                plan_intents.append(str(pname))
                seen.add(pagent)

        mode, targets = plan_dispatch(plan_agents, plan_intents, list(completed))
        logger.info(
            "Supervisor routing primary_intent=%s mode=%s targets=%s completed=%s",
            primary_str,
            mode,
            targets,
            completed,
        )

        if mode == "done":
            return {
                "response": "",
                "updated_state": {
                    "next_agent": None,
                    "execution_mode": "serial",
                    "pending_agent_results": [],
                    "supervisor_reasoning": "All agents completed",
                },
            }

        reasoning = f"Dispatch {mode}: {', '.join(targets)}"
        return {
            "response": "",
            "updated_state": {
                "next_agent": targets[0] if targets else None,
                "execution_mode": mode,
                "pending_agent_results": plan_agents,
                "supervisor_reasoning": reasoning,
            },
        }
