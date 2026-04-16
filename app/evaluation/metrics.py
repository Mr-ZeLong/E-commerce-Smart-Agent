"""Offline evaluation metrics for the Golden Dataset."""

from __future__ import annotations

import asyncio
import json
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


def _build_rag_precision_messages(question: str, top_chunks: list[str]) -> list:
    prompt = (
        f"Question: {question}\n\n"
        "Rate the relevance of each retrieved chunk to the question on a scale of 0 to 1, "
        "where 1 means perfectly relevant and 0 means completely irrelevant. "
        "Provide a brief explanation for each rating in your reasoning, then respond with "
        'only a JSON object in the format {"scores": [score1, score2, score3]}.'
    )
    for i, chunk in enumerate(top_chunks, 1):
        prompt += f"\nChunk {i}: {chunk}"
    return [
        SystemMessage(content="You are an expert evaluator of retrieval relevance."),
        HumanMessage(content=prompt),
    ]


def _parse_rag_scores(content: str) -> list[float] | None:
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "scores" in data:
            return [float(s) for s in data["scores"]]
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    matches = re.findall(r"\b0(?:\.\d+)?\b|\b1(?:\.0*)?\b", content)
    if matches:
        return [float(m) for m in matches]
    return None


def _compute_rag_average(scores: list[float], top_chunks: list[str]) -> float:
    scores = scores[: len(top_chunks)]
    while len(scores) < len(top_chunks):
        scores.append(0.0)
    clamped = [max(0.0, min(1.0, s)) for s in scores]
    return sum(clamped) / len(clamped) if clamped else 0.0


async def _rag_precision_llm(
    question: str,
    chunks: list[str],
    llm: BaseChatModel,
) -> float:
    top_chunks = chunks[:3]
    messages = _build_rag_precision_messages(question, top_chunks)
    try:
        response = await llm.ainvoke(messages)
        content = response.content
        if isinstance(content, list):
            content = " ".join(str(item) for item in content)
        scores = _parse_rag_scores(content)
        if scores is None:
            logger.warning("Failed to parse RAG precision scores from LLM response.")
            return 0.0
        return _compute_rag_average(scores, top_chunks)
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM call failed during RAG precision evaluation: %s", e)
        return 0.0


async def rag_precision(
    question: str,
    chunks: list[str],
    llm_judge: bool = False,
    llm: BaseChatModel | None = None,
) -> float:
    """Compute RAG precision for top-3 chunks.

    By default uses a lightweight string-overlap heuristic suitable for
    offline evaluation. Setting ``llm_judge=True`` and providing an ``llm``
    uses an LLM-as-judge to rate each chunk's relevance and returns the
    average of the top-3 scores.
    """
    if not chunks:
        return 0.0
    if llm_judge and llm is not None:
        return await _rag_precision_llm(question, chunks, llm)
    if llm_judge:
        logger.warning("LLM judge for RAG precision requires an LLM; falling back to heuristic.")

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


async def batch_rag_precision(
    questions: list[str],
    chunks_list: list[list[str]],
    llm: BaseChatModel,
    max_concurrency: int = 5,
) -> list[float]:
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _evaluate(question: str, chunks: list[str]) -> float:
        async with semaphore:
            if not chunks:
                return 0.0
            return await _rag_precision_llm(question, chunks, llm)

    tasks = [_evaluate(q, c) for q, c in zip(questions, chunks_list, strict=False)]
    return await asyncio.gather(*tasks)


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
