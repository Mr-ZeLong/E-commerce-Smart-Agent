import json
import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.llm_factory import create_llm
from app.memory.structured_manager import StructuredMemoryManager
from app.models.memory import InteractionSummary
from app.models.state import AgentState

logger = logging.getLogger(__name__)


class SessionSummarizer:
    """Summarizes conversation threads and persists interaction summaries."""

    def __init__(self, llm: BaseChatModel | None = None):
        self.llm = llm or create_llm()
        self.memory_manager = StructuredMemoryManager()

    def should_summarize(self, state: AgentState) -> bool:
        """Return True if the conversation should be summarized.

        Summarize threads that either exceed 20 messages or naturally end
        (no human transfer, not awaiting clarification, and at least one exchange).
        """
        history = state.get("history", [])
        if len(history) > 20:
            return True
        needs_human = state.get("needs_human_transfer")
        awaiting = state.get("awaiting_clarification")
        return not needs_human and not awaiting and len(history) >= 2

    async def summarize_thread(self, messages: list[dict]) -> str:
        """Ask the LLM to summarize a conversation thread."""
        system_prompt = (
            "You are a helpful assistant. Summarize the following conversation thread "
            "in 2-3 concise sentences, capturing the key topics and outcomes."
        )
        user_prompt = (
            f"Conversation messages:\n{json.dumps(messages, ensure_ascii=False, indent=2)}"
        )
        llm_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = await self.llm.ainvoke(llm_messages)
        summary = str(response.content).strip()
        logger.info("Generated conversation summary (length=%d)", len(summary))
        return summary

    async def run(
        self,
        state: AgentState,
        session: AsyncSession,
        vector_manager=None,
    ) -> InteractionSummary | None:
        """Summarize and persist if conditions are met."""
        if not self.should_summarize(state):
            return None

        history = state.get("history", [])
        if not history:
            logger.debug("No history to summarize.")
            return None

        user_id = state.get("user_id")
        thread_id = state.get("thread_id")
        resolved_intent = state.get("current_intent")

        if user_id is None or thread_id is None:
            logger.warning("Missing user_id or thread_id in state; cannot persist summary.")
            return None

        existing = await session.exec(
            select(InteractionSummary).where(InteractionSummary.thread_id == thread_id)
        )
        if existing.one_or_none():
            logger.info("Summary already exists for thread_id=%s; skipping.", thread_id)
            return None

        summary_text = await self.summarize_thread(history)

        record = await self.memory_manager.save_interaction_summary(
            session=session,
            user_id=user_id,
            thread_id=thread_id,
            summary=summary_text,
            resolved_intent=resolved_intent,
        )
        logger.info(
            "Saved interaction summary for user_id=%s thread_id=%s",
            user_id,
            thread_id,
        )

        if vector_manager is not None:
            try:
                from app.core.utils import utc_now

                await vector_manager.upsert_message(
                    user_id=user_id,
                    thread_id=thread_id,
                    message_role="summary",
                    content=summary_text,
                    timestamp=utc_now().isoformat(),
                    intent=resolved_intent,
                )
                logger.info(
                    "Upserted summary vector for user_id=%s thread_id=%s",
                    user_id,
                    thread_id,
                )
            except Exception:
                logger.exception("Failed to upsert summary vector")

        return record
