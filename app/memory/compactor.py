"""Context compaction utilities for memory management."""

import json
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class ContextCompactor:
    """Compacts conversation history into a structured summary.

    When token utilization exceeds a threshold, this compactor replaces
    the full message history with a concise summary to free up context
    window space.
    """

    def __init__(self, budget_field: str = "MEMORY_CONTEXT_TOKEN_BUDGET") -> None:
        self._budget = getattr(settings, budget_field, 2048)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count using a lightweight character heuristic."""
        return len(text) // 4

    def compact(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compact a conversation history into a summary entry.

        Args:
            history: List of message dicts with ``role`` and ``content`` keys.

        Returns:
            A list containing a single compacted summary dict, or the
            original history if compaction is not beneficial.
        """
        if not history:
            return []

        user_messages = [m.get("content", "") for m in history if m.get("role") == "user"]
        assistant_messages = [m.get("content", "") for m in history if m.get("role") == "assistant"]

        topics: list[str] = []
        if user_messages:
            first_query = user_messages[0]
            topics.append(f"用户问题: {first_query[:200]}")
        if assistant_messages:
            last_response = assistant_messages[-1]
            topics.append(f"助手回复摘要: {last_response[:200]}")

        summary_text = " | ".join(topics) if topics else "会话摘要"
        compacted = [
            {
                "role": "system",
                "content": f"[会话摘要] {summary_text}",
                "compacted": True,
                "original_turn_count": len(history),
            }
        ]

        original_tokens = self._estimate_tokens(json.dumps(history, ensure_ascii=False))
        compacted_tokens = self._estimate_tokens(json.dumps(compacted, ensure_ascii=False))
        logger.info(
            "Compacted history from %d turns (%d estimated tokens) to %d estimated tokens",
            len(history),
            original_tokens,
            compacted_tokens,
        )
        return compacted
