import json
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.account import AccountAgent
from app.agents.base import BaseAgent
from app.agents.cart import CartAgent
from app.agents.complaint import ComplaintAgent
from app.agents.evaluator import ConfidenceEvaluator
from app.agents.logistics import LogisticsAgent
from app.agents.order import OrderAgent
from app.agents.payment import PaymentAgent
from app.agents.policy import PolicyAgent
from app.agents.product import ProductAgent
from app.agents.router import IntentRouterAgent
from app.agents.supervisor import SupervisorAgent
from app.context.token_budget import MemoryTokenBudget
from app.core.config import settings
from app.core.database import async_session_maker, sync_session_maker
from app.graph.parallel import build_parallel_sends
from app.memory.compactor import ContextCompactor
from app.memory.structured_manager import StructuredMemoryManager
from app.memory.summarizer import SessionSummarizer
from app.memory.vector_manager import VectorMemoryManager
from app.models.observability import SupervisorDecision
from app.models.state import AgentProcessResult, AgentState
from app.tasks.memory_tasks import extract_and_save_facts


def _log_supervisor_decision(
    thread_id: str,
    primary_intent: str | None,
    pending_intents: list[str],
    selected_agents: list[str],
    execution_mode: str,
    reasoning: str,
) -> None:
    try:
        with sync_session_maker() as session:
            log = SupervisorDecision(
                thread_id=thread_id,
                primary_intent=primary_intent,
                pending_intents=",".join(pending_intents) if pending_intents else None,
                selected_agents=",".join(selected_agents) if selected_agents else None,
                execution_mode=execution_mode,
                reasoning=reasoning,
            )
            session.add(log)
            session.commit()
    except Exception:
        logger.exception("Failed to log supervisor decision")


async def _alog_supervisor_decision(
    thread_id: str,
    primary_intent: str | None,
    pending_intents: list[str],
    selected_agents: list[str],
    execution_mode: str,
    reasoning: str,
) -> None:
    import asyncio

    await asyncio.to_thread(
        _log_supervisor_decision,
        thread_id,
        primary_intent,
        pending_intents,
        selected_agents,
        execution_mode,
        reasoning,
    )


logger = logging.getLogger(__name__)


@asynccontextmanager
async def _memory_session(session: AsyncSession | None = None):
    if session is not None:
        yield session
    else:
        async with async_session_maker() as s:
            yield s


def build_router_node(
    agent: IntentRouterAgent,
) -> Callable[
    [AgentState],
    Awaitable[Command[Literal["memory_node", "decider_node"]]],
]:
    async def router_node(
        state: AgentState,
    ) -> Command[Literal["memory_node", "decider_node"]]:
        result = await agent.process(state)
        updated = dict(result.get("updated_state") or {})

        if result.get("response"):
            return Command(goto="decider_node", update={"answer": result["response"], **updated})

        return Command(goto="memory_node", update=updated)

    return router_node


def build_memory_node(
    structured_manager: StructuredMemoryManager | None = None,
    vector_manager: VectorMemoryManager | None = None,
    use_supervisor: bool = True,
    session: AsyncSession | None = None,
) -> Callable[[AgentState], Awaitable[Command]]:
    async def memory_node(state: AgentState) -> Command:
        user_id = state.get("user_id")
        thread_id = state.get("thread_id")
        history = state.get("history", [])

        last_user_message = ""
        for msg in reversed(history):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break

        memory_context: dict[str, Any] = {}

        if (
            structured_manager is not None
            and vector_manager is not None
            and user_id is not None
            and thread_id is not None
        ):
            async with _memory_session(session) as mem_session:
                try:
                    profile = await structured_manager.get_user_profile(mem_session, user_id)
                    if profile:
                        memory_context["user_profile"] = {
                            "user_id": profile.user_id,
                            "membership_level": profile.membership_level,
                            "preferred_language": profile.preferred_language,
                            "timezone": profile.timezone,
                            "total_orders": profile.total_orders,
                            "lifetime_value": profile.lifetime_value,
                        }
                except Exception:
                    logger.exception("Failed to fetch user profile for memory context")

                try:
                    preferences = await structured_manager.get_user_preferences(
                        mem_session, user_id
                    )
                    if preferences:
                        memory_context["preferences"] = [
                            {
                                "preference_key": p.preference_key,
                                "preference_value": p.preference_value,
                            }
                            for p in preferences
                        ]
                except Exception:
                    logger.exception("Failed to fetch user preferences for memory context")

                try:
                    facts = await structured_manager.get_user_facts(mem_session, user_id, limit=50)
                    if facts:
                        memory_context["structured_facts"] = [
                            {
                                "fact_type": f.fact_type,
                                "content": f.content,
                                "confidence": f.confidence,
                            }
                            for f in facts
                        ]
                except Exception:
                    logger.exception("Failed to fetch user facts for memory context")

                try:
                    summaries = await structured_manager.get_recent_summaries(
                        mem_session, user_id, limit=50
                    )
                    if summaries:
                        memory_context["interaction_summaries"] = [
                            {
                                "summary_text": s.summary_text,
                                "resolved_intent": s.resolved_intent,
                                "created_at": s.created_at.isoformat() if s.created_at else None,
                            }
                            for s in summaries
                        ]
                except Exception:
                    logger.exception("Failed to fetch interaction summaries for memory context")

            try:
                if last_user_message:
                    summary_results = await vector_manager.search_similar(
                        user_id, query_text=last_user_message, top_k=10, message_role="summary"
                    )
                    message_results = await vector_manager.search_similar(
                        user_id, query_text=last_user_message, top_k=10
                    )
                    # Filter by relevance score threshold before deduplication
                    threshold = settings.VECTOR_MEMORY_SCORE_THRESHOLD
                    filtered = [
                        p
                        for p in summary_results + message_results
                        if p.get("score", 0) >= threshold
                    ]
                    seen_contents: set[str] = set()
                    combined: list[dict] = []
                    for payload in filtered:
                        content = str(payload.get("content", ""))
                        if content and content not in seen_contents:
                            seen_contents.add(content)
                            combined.append(payload)
                    if combined:
                        memory_context["relevant_past_messages"] = [
                            {
                                "role": payload.get("message_role", "user"),
                                "content": payload.get("content", ""),
                            }
                            for payload in combined[:10]
                        ]
            except Exception:
                logger.exception("Failed to fetch vector memory for memory context")

        budgeter = MemoryTokenBudget()
        memory_context_config = state.get("memory_context_config")
        memory_context = budgeter.allocate(memory_context, config=memory_context_config)

        if not use_supervisor:
            next_agent = state.get("next_agent")
            if next_agent:
                return Command(goto=next_agent, update={"memory_context": memory_context})
            return Command(goto="decider_node", update={"memory_context": memory_context})

        return Command(goto="supervisor_node", update={"memory_context": memory_context})

    return memory_node


def build_supervisor_node(
    agent: SupervisorAgent,
) -> Callable[[AgentState], Awaitable[Command]]:
    async def supervisor_node(state: AgentState) -> Command:
        result = await agent.process(state)
        updated = dict(result.get("updated_state") or {})

        intent_result = state.get("intent_result") or {}
        await _alog_supervisor_decision(
            thread_id=state.get("thread_id", ""),
            primary_intent=intent_result.get("primary_intent"),
            pending_intents=[
                p.get("primary_intent", "")
                for p in (state.get("slots") or {}).get("pending_intents", [])
            ],
            selected_agents=updated.get("pending_agent_results", []),
            execution_mode=updated.get("execution_mode", ""),
            reasoning=updated.get("supervisor_reasoning", ""),
        )

        if result.get("response"):
            return Command(goto="synthesis_node", update={"answer": result["response"], **updated})

        mode = updated.get("execution_mode")
        targets = updated.get("pending_agent_results", [])
        next_agent = updated.get("next_agent")

        if mode == "parallel" and targets:
            return Command(goto=build_parallel_sends(targets, state), update=updated)
        if next_agent:
            return Command(goto=next_agent, update=updated)

        return Command(goto="synthesis_node", update=updated)

    return supervisor_node


def build_synthesis_node(
    llm: BaseChatModel,
) -> Callable[[AgentState], Awaitable[Command[Literal["evaluator_node", "supervisor_node"]]]]:
    async def synthesis_node(
        state: AgentState,
    ) -> Command[Literal["evaluator_node", "supervisor_node"]]:
        iteration = state.get("iteration_count", 0)
        sub_answers = [
            sa for sa in state.get("sub_answers", []) if sa.get("iteration") == iteration
        ]
        completed = {sa["agent"] for sa in sub_answers}
        pending = state.get("pending_agent_results") or []
        remaining = [a for a in pending if a not in completed]

        if state.get("execution_mode") == "serial" and remaining:
            return Command(goto="supervisor_node", update={})

        if len(sub_answers) == 0:
            return Command(goto="evaluator_node", update={"answer": state.get("answer", "")})

        if len(sub_answers) == 1:
            answer = sub_answers[0]["response"]
            merged: dict[str, Any] = {"current_agent": sub_answers[0]["agent"]}
            if sub_answers[0].get("updated_state"):
                merged.update(sub_answers[0]["updated_state"])
            return Command(goto="evaluator_node", update={"answer": answer, **merged})

        parts = []
        merged_state: dict[str, Any] = {}
        for sa in sub_answers:
            parts.append(f"[{sa['agent']}] {sa['response']}")
            if sa.get("updated_state"):
                merged_state.update(sa["updated_state"])

        prompt = (
            "你是一位专业的客服回复整合员。请将以下多个专家的回复整合为一段连贯、自然的回复，"
            "避免重复，突出重点，语气友好。直接输出整合后的回复内容，不要加任何前缀。\n\n"
            + "\n".join(parts)
        )
        messages = [HumanMessage(content=prompt)]
        try:
            response = await llm.ainvoke(messages)
            synthesized = str(response.content)
        except Exception as exc:
            logger.error("Synthesis LLM call failed: %s", exc)
            synthesized = "\n\n".join(parts)

        return Command(
            goto="evaluator_node",
            update={
                "answer": synthesized,
                "synthesized_answer": synthesized,
                "current_agent": sub_answers[0]["agent"],
                **merged_state,
            },
        )

    return synthesis_node


def _agent_updates(
    agent_name: str, result: AgentProcessResult, state: AgentState
) -> dict[str, Any]:
    from app.context.masking import mask_observation

    updates: dict[str, Any] = {
        "answer": result.get("response", ""),
        "sub_answers": [
            {
                "agent": agent_name,
                "response": result.get("response", ""),
                "updated_state": mask_observation(result.get("updated_state") or {}),
                "iteration": state.get("iteration_count", 0),
            }
        ],
    }
    if result.get("updated_state"):
        updates.update(mask_observation(result["updated_state"]))
    updates["current_agent"] = agent_name
    return updates


def _build_agent_node(
    agent: BaseAgent,
    agent_name: str,
    allowed_keys: list[str] | None = None,
) -> Callable[[AgentState], Awaitable[Command[Literal["evaluator_node"]]]]:
    async def _node(state: AgentState) -> Command[Literal["evaluator_node"]]:
        from app.graph.subgraphs import _filter_state

        filtered = _filter_state(state, allowed_keys) if allowed_keys else state
        result = await agent.process(filtered)
        return Command(goto="evaluator_node", update=_agent_updates(agent_name, result, state))

    return _node


def build_policy_node(
    agent: PolicyAgent,
    allowed_keys: list[str] | None = None,
) -> Callable[[AgentState], Awaitable[Command[Literal["evaluator_node"]]]]:
    return _build_agent_node(agent, "policy_agent", allowed_keys)


def build_order_node(
    agent: OrderAgent,
    allowed_keys: list[str] | None = None,
) -> Callable[[AgentState], Awaitable[Command[Literal["evaluator_node"]]]]:
    return _build_agent_node(agent, "order_agent", allowed_keys)


def build_logistics_node(
    agent: LogisticsAgent,
    allowed_keys: list[str] | None = None,
) -> Callable[[AgentState], Awaitable[Command[Literal["evaluator_node"]]]]:
    return _build_agent_node(agent, "logistics", allowed_keys)


def build_account_node(
    agent: AccountAgent,
    allowed_keys: list[str] | None = None,
) -> Callable[[AgentState], Awaitable[Command[Literal["evaluator_node"]]]]:
    return _build_agent_node(agent, "account", allowed_keys)


def build_payment_node(
    agent: PaymentAgent,
    allowed_keys: list[str] | None = None,
) -> Callable[[AgentState], Awaitable[Command[Literal["evaluator_node"]]]]:
    return _build_agent_node(agent, "payment", allowed_keys)


def build_product_node(
    agent: ProductAgent,
    allowed_keys: list[str] | None = None,
) -> Callable[[AgentState], Awaitable[Command[Literal["evaluator_node"]]]]:
    return _build_agent_node(agent, "product", allowed_keys)


def build_cart_node(
    agent: CartAgent,
    allowed_keys: list[str] | None = None,
) -> Callable[[AgentState], Awaitable[Command[Literal["evaluator_node"]]]]:
    return _build_agent_node(agent, "cart", allowed_keys)


def build_complaint_node(
    agent: ComplaintAgent,
    allowed_keys: list[str] | None = None,
) -> Callable[[AgentState], Awaitable[Command[Literal["evaluator_node"]]]]:
    return _build_agent_node(agent, "complaint", allowed_keys)


def build_evaluator_node(
    evaluator: ConfidenceEvaluator,
) -> Callable[[AgentState], Awaitable[Command[Literal["decider_node", "router_node"]]]]:
    async def evaluator_node(
        state: AgentState,
    ) -> Command[Literal["decider_node", "router_node"]]:
        if state.get("needs_human_transfer"):
            return Command(goto="decider_node", update={})

        from app.agents.config_loader import get_agent_config

        current_agent = state.get("current_agent") or "policy_agent"
        agent_config = await get_agent_config(current_agent)
        confidence_threshold = agent_config.confidence_threshold if agent_config else None
        max_retries = agent_config.max_retries if agent_config else settings.MAX_EVALUATOR_RETRIES

        eval_result = await evaluator.evaluate(
            answer=state.get("answer", ""),
            question=state.get("question", ""),
            history=state.get("history", []),
            retrieval_result=state.get("retrieval_result"),
            confidence_threshold=confidence_threshold,
        )

        if (
            eval_result.get("confidence_score", 0) < settings.CONFIDENCE_RETRY_THRESHOLD
            and state.get("iteration_count", 0) <= max_retries
        ):
            return Command(
                goto="router_node",
                update={
                    "retry_requested": True,
                    "confidence_score": eval_result["confidence_score"],
                    "confidence_signals": eval_result.get("confidence_signals"),
                },
            )

        return Command(goto="decider_node", update=eval_result)

    return evaluator_node


def _decider_node_logic(state: AgentState) -> dict:
    if state.get("needs_human_transfer"):
        return {
            "answer": state.get("answer", ""),
            "confidence_score": state.get("confidence_score") or 0.0,
            "confidence_signals": state.get("confidence_signals") or {},
            "needs_human_transfer": True,
            "transfer_reason": state.get("transfer_reason") or "specialist_requested_transfer",
            "audit_level": "manual",
        }

    if state.get("confidence_score") is not None:
        return {
            "answer": state.get("answer", ""),
            "needs_human_transfer": False,
            "transfer_reason": state.get("transfer_reason"),
            "audit_level": state.get("audit_level"),
            "confidence_score": state.get("confidence_score"),
            "confidence_signals": state.get("confidence_signals"),
        }

    if state.get("answer"):
        return {
            "answer": state.get("answer", ""),
            "needs_human_transfer": False,
            "transfer_reason": None,
            "audit_level": "auto",
            "confidence_score": 1.0,
            "confidence_signals": {},
        }

    return {
        "answer": state.get("answer", ""),
        "confidence_score": 0.0,
        "confidence_signals": {},
        "needs_human_transfer": True,
        "transfer_reason": "missing_evaluation",
        "audit_level": "manual",
    }


def decider_node(state: AgentState) -> dict:
    return _decider_node_logic(state)


def build_decider_node(
    vector_manager=None,
) -> Callable[[AgentState], Awaitable[dict]]:
    async def _async_decider_node(state: AgentState) -> dict:
        result = _decider_node_logic(state)

        history = state.get("history", [])
        needs_human = result.get("needs_human_transfer", False)
        awaiting_clarification = state.get("awaiting_clarification")

        memory_context = state.get("memory_context") or {}
        history_text = json.dumps(history)
        memory_text = json.dumps(memory_context, ensure_ascii=False, default=str)
        context_tokens = (len(history_text) + len(memory_text)) // 4
        budget = getattr(settings, "MEMORY_CONTEXT_TOKEN_BUDGET", None)
        context_utilization = min(1.0, context_tokens / budget) if budget else 0.0
        result["context_tokens"] = context_tokens
        result["context_utilization"] = context_utilization

        summarizer = SessionSummarizer()
        memory_context_config = state.get("memory_context_config") or {}
        threshold_override = memory_context_config.get("compaction_threshold")
        compaction_threshold = (
            threshold_override
            if threshold_override is not None
            else getattr(settings, "COMPACTION_THRESHOLD", 0.75)
        )
        force_summary = len(history) > 20
        should_summarize_flag = force_summary or (
            not needs_human
            and not awaiting_clarification
            and summarizer.should_summarize(
                state, utilization=context_utilization, threshold=compaction_threshold
            )
        )

        if not needs_human and not awaiting_clarification:
            user_id = state.get("user_id")
            thread_id = state.get("thread_id")
            if user_id is not None and thread_id is not None:
                history_json = json.dumps(history)

                question = ""
                answer = ""
                for msg in reversed(history):
                    if msg.get("role") == "user" and not question:
                        question = msg.get("content", "")
                    if msg.get("role") == "assistant" and not answer:
                        answer = msg.get("content", "")
                if not question:
                    question = state.get("question", "")
                if not answer:
                    answer = state.get("answer", "")

                try:
                    extract_and_save_facts.delay(user_id, thread_id, history_json, question, answer)
                except Exception:
                    logger.exception("Failed to enqueue fact extraction")

        if should_summarize_flag:
            try:
                async with async_session_maker() as session:
                    if context_utilization > compaction_threshold:
                        compactor = ContextCompactor()
                        compacted_history = compactor.compact(history)
                        result["history"] = compacted_history
                    await summarizer.run(
                        state,
                        session,
                        vector_manager=vector_manager,
                        utilization=context_utilization,
                        threshold=compaction_threshold,
                    )
            except Exception:
                logger.exception("Failed to run session summarizer")

        answer = result.get("answer", "") or state.get("answer", "")
        if answer:
            if "history" in result:
                result["history"].append({"role": "assistant", "content": answer})
            else:
                result["history"] = [{"role": "assistant", "content": answer}]

        # Recompute context metrics after compaction and assistant append so
        # telemetry reflects the actual state that enters the checkpointer.
        final_history = result.get("history", history)
        final_history_text = json.dumps(final_history)
        final_context_tokens = (len(final_history_text) + len(memory_text)) // 4
        final_context_utilization = min(1.0, final_context_tokens / budget) if budget else 0.0
        result["context_tokens"] = final_context_tokens
        result["context_utilization"] = final_context_utilization

        return result

    return _async_decider_node
