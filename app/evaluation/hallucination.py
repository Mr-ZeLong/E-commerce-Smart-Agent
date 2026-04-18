"""Hallucination evaluation for RAG outputs."""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.tracing import build_llm_config

logger = logging.getLogger(__name__)

_CITATION_PATTERN = re.compile(r"\[来源:\s*[^\]]+\]")


def has_required_citations(answer: str, min_citations: int = 1) -> bool:
    """Check whether the answer contains at least ``min_citations`` citation markers."""
    return len(_CITATION_PATTERN.findall(answer)) >= min_citations


def heuristic_hallucination_score(answer: str, chunks: list[str]) -> float:
    """Heuristic hallucination score based on citation presence.

    Returns 0.0 if the answer lacks citations and chunks are provided
    (indicating potential hallucination), otherwise 1.0.
    """
    if not chunks:
        return 1.0
    if has_required_citations(answer):
        return 1.0
    return 0.0


async def llm_hallucination_score(
    question: str,
    answer: str,
    chunks: list[str],
    llm: BaseChatModel,
) -> float:
    """LLM-as-judge hallucination score.

    Asks an LLM to rate whether the answer contains any claims not supported
    by the provided chunks. Returns 1.0 for no hallucination, 0.0 for
    hallucination.
    """
    if not chunks:
        return 1.0

    chunks_text = "\n\n".join(f"Chunk {i + 1}: {c}" for i, c in enumerate(chunks))
    prompt = (
        f"Question: {question}\n\n"
        f"Retrieved Chunks:\n{chunks_text}\n\n"
        f"Answer: {answer}\n\n"
        "Does the answer contain any claims that are NOT supported by the retrieved chunks? "
        "Respond with only a number: 0 (hallucination present) or 1 (no hallucination)."
    )
    messages = [
        SystemMessage(content="You are an expert evaluator of factual consistency."),
        HumanMessage(content=prompt),
    ]
    try:
        config = build_llm_config(
            agent_name="hallucination_evaluator", tags=["evaluation", "internal"]
        )
        response = await llm.ainvoke(messages, config=config)
        content = response.content
        if isinstance(content, list):
            content = " ".join(str(item) for item in content)
        score = float(content.strip())
        return max(0.0, min(1.0, score))
    except (ValueError, TypeError):
        logger.warning("Failed to parse hallucination score from LLM response.")
        return 0.0
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM call failed during hallucination evaluation: %s", e)
        return 0.0


async def evaluate_hallucination_rate(
    records: list[dict[str, Any]],
    llm: BaseChatModel | None = None,
    use_llm_judge: bool = False,
) -> dict[str, Any]:
    """Evaluate hallucination rate across a dataset of RAG outputs.

    Each record should contain:
      - ``question``: str
      - ``answer``: str
      - ``chunks``: list[str]

    Returns a dict with ``hallucination_rate`` (0.0–1.0), ``total``,
    ``hallucinated_count``, and ``method``.
    """
    scores: list[float] = []
    for record in records:
        question = record.get("question", "")
        answer = record.get("answer", "")
        chunks = record.get("chunks", [])

        if use_llm_judge and llm is not None:
            score = await llm_hallucination_score(question, answer, chunks, llm)
        else:
            score = heuristic_hallucination_score(answer, chunks)
        scores.append(score)

    total = len(scores)
    hallucinated = sum(1 for s in scores if s < 1.0)
    rate = round(hallucinated / total, 4) if total > 0 else 0.0

    return {
        "hallucination_rate": rate,
        "total": total,
        "hallucinated_count": hallucinated,
        "meets_target": rate <= 0.05,
        "method": "llm_judge" if use_llm_judge else "citation_heuristic",
    }
