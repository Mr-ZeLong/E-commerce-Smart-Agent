"""Token budget management for context optimization."""

import json
from abc import ABC, abstractmethod
from typing import Any

from app.core.config import settings


class TokenBudget(ABC):
    """Abstract base class for token budget managers."""

    def __init__(self) -> None:
        self._encoder = None
        try:
            import tiktoken

            self._encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._encoder = None

    def estimate_tokens(self, text: str) -> int:
        """Estimate the number of tokens in a text string.

        Uses tiktoken if available, otherwise falls back to ``len(text) // 4``.

        Args:
            text: The text to estimate.

        Returns:
            Estimated token count.
        """
        if self._encoder is not None:
            return len(self._encoder.encode(text))
        return len(text) // 4

    @abstractmethod
    def allocate(self, context: dict) -> dict:
        """Allocate a context dictionary within the token budget."""

        raise NotImplementedError


class MemoryTokenBudget(TokenBudget):
    """Token budget manager for memory context.

    Prunes lowest-priority memory fields first to keep the total estimated
    token count within ``settings.MEMORY_CONTEXT_TOKEN_BUDGET``.
    """

    _PRIORITY_KEYS = [
        "user_profile",
        "preferences",
        "structured_facts",
        "interaction_summaries",
        "relevant_past_messages",
    ]

    def _count_context_tokens(self, context: dict) -> int:
        """Count tokens for a serialized context dictionary.

        Args:
            context: The context dictionary to count.

        Returns:
            Estimated token count for the serialized dictionary.
        """
        serialized = json.dumps(context, ensure_ascii=False, default=str)
        return self.estimate_tokens(serialized)

    def allocate(self, context: dict, config: dict[str, Any] | None = None) -> dict:
        """Return a pruned memory context that fits within the token budget.

        Prunes lowest-priority fields first while preserving higher-priority
        data. Fields are prioritized in this order (high -> low):
        ``user_profile`` > ``preferences`` > ``structured_facts`` >
        ``interaction_summaries`` > ``relevant_past_messages``.

        For list fields, items are dropped from the end until the budget is
        met or the field is empty.

        Missing keys are handled gracefully (treated as empty).

        Args:
            context: The raw memory context dictionary.
            config: Optional override configuration. Supports
                ``memory_token_budget`` to override the global setting.

        Returns:
            A new dictionary containing the pruned memory context.
        """
        budget = settings.MEMORY_CONTEXT_TOKEN_BUDGET
        if config is not None:
            budget_override = config.get("memory_token_budget")
            if budget_override is not None:
                budget = budget_override
        result: dict = {}
        for key in self._PRIORITY_KEYS:
            if key in context and context[key] is not None:
                result[key] = context[key]

        while self._count_context_tokens(result) > budget:
            pruned = False
            for key in reversed(self._PRIORITY_KEYS):
                if key not in result:
                    continue
                value = result[key]
                if isinstance(value, list) and value:
                    trimmed = value[:-1]
                    if trimmed:
                        result[key] = trimmed
                    else:
                        del result[key]
                    pruned = True
                    break
                if key != "user_profile":
                    del result[key]
                    pruned = True
                    break
            if not pruned:
                break

        return result
