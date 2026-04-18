"""Tone Consistency evaluation metric using LLM-as-Judge."""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.tracing import build_llm_config

logger = logging.getLogger(__name__)


async def tone_consistency(
    conversation_turns: list[dict[str, str]],
    llm: BaseChatModel,
) -> float:
    """Rate whether the agent's tone is consistent and professional across conversation turns.

    Uses an LLM-as-judge to evaluate tone consistency on a scale of 0 to 1,
    where 1 means perfectly consistent and professional, and 0 means highly
    inconsistent or unprofessional.

    Args:
        conversation_turns: List of conversation turns, each containing at least
            ``role`` ("user" or "assistant") and ``content`` keys.
        llm: Language model to use as the judge.

    Returns:
        A score between 0.0 and 1.0 representing tone consistency.
    """
    if not conversation_turns:
        return 0.0

    agent_turns = [t for t in conversation_turns if t.get("role") == "assistant"]
    if len(agent_turns) < 2:
        logger.warning(
            "Tone consistency requires at least 2 agent turns; found %d.",
            len(agent_turns),
        )
        return 1.0

    turns_text = "\n\n".join(
        f"Turn {i + 1}: {turn['content']}" for i, turn in enumerate(agent_turns)
    )

    prompt = (
        "Evaluate the tone consistency and professionalism of the following "
        "agent responses across multiple conversation turns.\n\n"
        f"{turns_text}\n\n"
        "Rate the overall tone consistency on a scale of 0 to 1, where 1 means "
        "perfectly consistent and professional across all turns, and 0 means "
        "highly inconsistent or unprofessional. Consider factors such as: "
        "formality level, politeness, empathy, clarity, and whether the tone "
        "remains appropriate for a customer service context.\n\n"
        "Respond with only a number between 0 and 1."
    )

    messages = [
        SystemMessage(
            content="You are an expert evaluator of conversational tone and professionalism."
        ),
        HumanMessage(content=prompt),
    ]

    try:
        config = build_llm_config(agent_name="tone_evaluator", tags=["evaluation", "internal"])
        response = await llm.ainvoke(messages, config=config)
        content = response.content
        if isinstance(content, list):
            content = " ".join(str(item) for item in content)
        score = float(content.strip())
        return max(0.0, min(1.0, score))
    except (ValueError, TypeError):
        logger.warning("Failed to parse tone consistency score from LLM response.")
        return 0.0
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM call failed during tone consistency evaluation: %s", e)
        return 0.0
