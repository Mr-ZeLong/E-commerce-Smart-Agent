"""Token Efficiency evaluation metric."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def token_efficiency(
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Calculate token efficiency as a ratio of input tokens to total tokens.

    Higher values indicate the model is making more efficient use of the
    provided context relative to its output length. A value of 1.0 means
    only input tokens were used (no output), while a value near 0.0 means
    very little input relative to a large output.

    Args:
        input_tokens: Number of input/prompt tokens.
        output_tokens: Number of output/completion tokens.

    Returns:
        A float between 0.0 and 1.0 representing token efficiency.
    """
    if input_tokens < 0 or output_tokens < 0:
        logger.warning(
            "Token counts must be non-negative: input=%d, output=%d",
            input_tokens,
            output_tokens,
        )
        return 0.0

    total = input_tokens + output_tokens
    if total == 0:
        logger.warning("Total tokens is zero; returning 0.0 efficiency.")
        return 0.0

    return input_tokens / total
