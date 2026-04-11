"""Offline evaluation metrics for the Golden Dataset."""

from __future__ import annotations

import logging
import re

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


def intent_accuracy(predictions: list[str], references: list[str]) -> float:
    """Compute exact-match accuracy for primary intent labels."""
    if not predictions or len(predictions) != len(references):
        return 0.0
    correct = sum(1 for p, r in zip(predictions, references, strict=False) if p == r)
    return correct / len(predictions)


def slot_recall(predictions: list[dict], references: list[dict]) -> float:
    """Compute slot recall: % of expected slot keys present in actual slots.

    Only records with non-empty ``expected_slots`` are counted.
    """
    total = 0
    recalled = 0
    for pred_slots, ref_slots in zip(predictions, references, strict=False):
        if not ref_slots:
            continue
        for key in ref_slots:
            total += 1
            if key in pred_slots:
                recalled += 1
    return recalled / total if total > 0 else 0.0


def _extract_tokens(text: str) -> set[str]:
    """Extract n-grams and words for overlap matching."""
    text_lower = text.lower()
    tokens: set[str] = set(re.findall(r"[a-zA-Z]{3,}|\d{4,}", text_lower))

    # Chinese character n-grams (2-gram and 3-gram)
    chinese_chars = re.findall(r"[\u4e00-\u9fa5]", text_lower)
    for n in (2, 3):
        for i in range(len(chinese_chars) - n + 1):
            tokens.add("".join(chinese_chars[i : i + n]))

    # Whitespace-separated tokens of length >= 2
    for t in text_lower.split():
        if len(t) >= 2:
            tokens.add(t)

    return tokens


def rag_precision(
    question: str,
    chunks: list[str],
    llm_judge: bool = False,
) -> float:
    """Compute RAG precision for top-3 chunks.

    By default uses a lightweight string-overlap heuristic suitable for
    offline evaluation.  Setting ``llm_judge=True`` logs a warning because
    the LLM-judge path is not yet implemented.
    """
    if not chunks:
        return 0.0
    if llm_judge:
        logger.warning("LLM judge for RAG precision is not implemented; falling back to heuristic.")

    top_chunks = chunks[:3]
    question_lower = question.lower()
    tokens = _extract_tokens(question)
    for chunk in top_chunks:
        chunk_lower = chunk.lower()
        if question_lower in chunk_lower:
            return 1.0
        if tokens and any(token in chunk_lower for token in tokens):
            return 1.0
    return 0.0


async def answer_correctness(
    question: str,
    expected: str,
    actual: str,
    llm: BaseChatModel,
) -> float:
    """Rate answer correctness on a 0-1 scale using an LLM-as-judge prompt."""
    if not actual:
        return 0.0

    prompt = (
        f"Question: {question}\n"
        f"Expected answer fragment: {expected}\n"
        f"Generated answer: {actual}\n\n"
        "Rate the correctness of the generated answer on a scale of 0 to 1, "
        "where 1 means perfectly correct and 0 means completely wrong. "
        "Respond with only a number between 0 and 1."
    )
    messages = [
        SystemMessage(content="You are an expert evaluator of answer correctness."),
        HumanMessage(content=prompt),
    ]
    try:
        response = await llm.ainvoke(messages)
        content = response.content
        if isinstance(content, list):
            content = " ".join(str(item) for item in content)
        score = float(content.strip())
        return max(0.0, min(1.0, score))
    except (ValueError, TypeError):
        logger.warning("Failed to parse answer correctness score from LLM response.")
        return 0.0
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM call failed during answer correctness evaluation: %s", e)
        return 0.0
