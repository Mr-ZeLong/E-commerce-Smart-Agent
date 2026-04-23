import json
import logging
import re
from typing import Any

from langchain_core.exceptions import LangChainException
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.llm_factory import create_llm
from app.core.tracing import build_llm_config

logger = logging.getLogger(__name__)


class FactExtractor:
    """Extract user facts from a conversation turn using an LLM."""

    def __init__(self, llm: BaseChatModel | None = None):
        self.llm = llm or create_llm(model="qwen-turbo")

    async def extract_facts(
        self,
        user_id: int,
        thread_id: str,
        history: list[dict],
        answer: str,
        question: str,
    ) -> list[dict[str, Any]]:
        """Extract facts from the given question/answer pair.

        Returns a list of dicts with keys:
            - fact_type (str)
            - content (str)
            - confidence (float)

        Facts with confidence < 0.7 are dropped.
        If PII is detected in the question or answer, extraction is skipped.
        """
        combined_text = f"{question} {answer}"
        history_text = json.dumps(history, ensure_ascii=False)
        scan_text = f"{combined_text} {history_text}"
        if re.search(r"\b\d{13,19}\b", scan_text) or re.search(
            r"password[:\s]*\S+", scan_text, re.IGNORECASE
        ):
            logger.warning(
                "PII detected in conversation; skipping fact extraction for user_id=%s thread_id=%s",
                user_id,
                thread_id,
            )
            return []

        messages = self._build_messages(user_id, thread_id, history, question, answer)

        raw_content = ""
        try:
            config = build_llm_config(
                agent_name="fact_extractor",
                tags=["internal", "memory_extraction"],
                extra_metadata={"user_id": user_id, "thread_id": thread_id},
            )
            response = await self.llm.ainvoke(messages, config=config)
            raw_content = str(response.content) if hasattr(response, "content") else str(response)
            facts = json.loads(raw_content)
        except (LangChainException, json.JSONDecodeError, OSError):
            # Attempt to recover JSON from markdown wrapping
            try:
                facts = json.loads(self._extract_json_block(raw_content))
            except (json.JSONDecodeError, OSError):
                logger.exception("Failed to parse LLM response as JSON for fact extraction")
                return []

        if not isinstance(facts, list):
            logger.warning("LLM did not return a JSON array for facts")
            return []

        result: list[dict[str, Any]] = []
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            confidence = float(fact.get("confidence", 0.0))
            if confidence < 0.7:
                continue
            result.append(
                {
                    "fact_type": str(fact.get("fact_type", "general")),
                    "content": str(fact.get("content", "")),
                    "confidence": confidence,
                }
            )

        return result

    def _build_messages(
        self,
        user_id: int,
        thread_id: str,
        history: list[dict],
        question: str,
        answer: str,
    ) -> list[dict]:
        history_text = json.dumps(history, ensure_ascii=False, indent=2)
        system_msg = {
            "role": "system",
            "content": (
                "You are a fact extraction assistant. Given a user question, the assistant's answer, "
                "and the conversation history, extract a JSON array of facts about the user. "
                "Each fact must be an object with exactly these keys:\n"
                "- fact_type: string category (e.g., preference, order, account, general)\n"
                "- content: string description of the fact\n"
                "- confidence: float between 0 and 1 indicating how certain you are\n\n"
                "Only include facts with confidence >= 0.7. "
                "Do not include any markdown, explanation, or preamble. "
                "Return strictly a JSON array."
            ),
        }
        user_msg = {
            "role": "user",
            "content": (
                f"user_id: {user_id}\n"
                f"thread_id: {thread_id}\n"
                f"history: {history_text}\n"
                f"question: {question}\n"
                f"answer: {answer}\n\n"
                "Extract facts as a JSON array."
            ),
        }
        return [system_msg, user_msg]

    def _extract_json_block(self, text: str) -> str:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
        return text
