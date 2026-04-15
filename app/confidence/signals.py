# app/confidence/signals.py
import asyncio
import re
from collections.abc import Mapping
from typing import Any

from langchain_core.exceptions import LangChainException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.core.config import settings
from app.core.utils import clamp_score

NEGATIVE_WORDS = frozenset(settings.NEGATIVE_WORDS)
URGENT_WORDS = frozenset(settings.URGENT_WORDS)
POSITIVE_WORDS = frozenset(settings.POSITIVE_WORDS)


class LLMConfidenceScore(BaseModel):
    score: float


class SignalResult(BaseModel):
    """信号计算结果"""

    score: float
    reason: str
    metadata: dict | None = None


class ConfidenceSignalCalculator:
    """Encapsulates emotion signal calculation with overridable word lists."""

    def __init__(
        self,
        negative_words: set[str] | frozenset[str] | list[str] | None = None,
        urgent_words: set[str] | frozenset[str] | list[str] | None = None,
        positive_words: set[str] | frozenset[str] | list[str] | None = None,
        history_rounds: int | None = None,
    ) -> None:
        self.negative_words = (
            frozenset(negative_words) if negative_words is not None else NEGATIVE_WORDS
        )
        self.urgent_words = frozenset(urgent_words) if urgent_words is not None else URGENT_WORDS
        self.positive_words = (
            frozenset(positive_words) if positive_words is not None else POSITIVE_WORDS
        )
        self.history_rounds = (
            history_rounds
            if history_rounds is not None
            else settings.CONFIDENCE.EMOTION_HISTORY_ROUNDS
        )

    async def calculate_emotion_signal(
        self,
        query: str,
        history: list[dict],
    ) -> SignalResult:
        """用户情感检测信号"""
        recent_history = (
            history[-self.history_rounds :] if len(history) >= self.history_rounds else history
        )

        all_texts = [msg.get("content", "") for msg in recent_history] + [query]
        all_text = " ".join(all_texts).lower()

        negative_count = sum(1 for w in self.negative_words if w in all_text)
        urgent_count = sum(1 for w in self.urgent_words if w in all_text)
        positive_count = sum(1 for w in self.positive_words if w in all_text)

        if negative_count >= 3 or urgent_count >= 2:
            score = max(0.0, 0.3 - negative_count * 0.05)
            emotion_type = "high_frustration"
            reason = f"高挫败感(负面词{negative_count},紧急词{urgent_count})"
        elif negative_count >= 1:
            score = max(0.3, 0.6 - negative_count * 0.1)
            emotion_type = "mild_frustration"
            reason = f"轻微不满(负面词{negative_count})"
        elif positive_count > 0:
            score = min(1.0, 0.8 + positive_count * 0.05)
            emotion_type = "positive"
            reason = f"正面情绪(正面词{positive_count})"
        else:
            score = 0.7
            emotion_type = "neutral"
            reason = "无明显情绪"

        return SignalResult(
            score=score,
            reason=reason,
            metadata={
                "emotion_type": emotion_type,
                "negative_count": negative_count,
                "urgent_count": urgent_count,
                "positive_count": positive_count,
            },
        )


def _extract_tokens(text: str) -> set[str]:
    """提取中英文混合 token：中文字符单独提取，英文按空格分词保留长度>2的词。"""
    chinese_chars = set(re.findall(r"[\u4e00-\u9fff]", text))
    words = {w.lower() for w in re.findall(r"[a-zA-Z0-9]+", text) if len(w) > 2}
    return chinese_chars | words


async def calculate_rag_signal(
    similarities: list[float],
    chunks: list[str],
    query: str,
) -> SignalResult:
    """基于检索质量计算置信度"""
    if not similarities:
        return SignalResult(score=0.0, reason="无检索结果")

    mapped_similarities = [0.5 + s * 0.5 for s in similarities]
    avg_sim = sum(mapped_similarities) / len(mapped_similarities)
    max_sim = max(mapped_similarities)

    query_tokens = _extract_tokens(query)
    covered_tokens = set()
    for chunk in chunks:
        chunk_tokens = _extract_tokens(chunk)
        covered_tokens.update(query_tokens & chunk_tokens)

    coverage = len(covered_tokens) / len(query_tokens) if query_tokens else 0.0
    score = max_sim * 0.4 + avg_sim * 0.3 + coverage * 0.3

    return SignalResult(
        score=clamp_score(score),
        reason=f"最高:{max_sim:.2f} 平均:{avg_sim:.2f} 覆盖:{coverage:.2f}",
        metadata={
            "max_similarity": max_sim,
            "avg_similarity": avg_sim,
            "coverage": coverage,
            "raw_similarities": similarities,
        },
    )


async def calculate_llm_signal(
    query: str,
    context: list[str],
    generated_answer: str,
    llm: BaseChatModel,
) -> SignalResult:
    """计算 LLM 自我评估信号"""
    _ = context
    structured_llm = llm.with_structured_output(LLMConfidenceScore, method="json_mode")

    prompt = f"""评估回答置信度（0-1）：
问题：{query}
回答：{generated_answer}
只返回数字："""

    try:
        raw = await structured_llm.ainvoke(
            [HumanMessage(content=prompt)],
            config={"tags": ["confidence_eval", "internal"]},
        )
        if not isinstance(raw, LLMConfidenceScore):
            raise TypeError(f"Unexpected LLM response type: {type(raw).__name__}")
        score = clamp_score(raw.score)
        return SignalResult(
            score=score,
            reason="LLM自评估",
            metadata={"raw_response": str(raw.score)[:200]},
        )
    except (LangChainException, ConnectionError) as e:
        raise RuntimeError("LLM confidence evaluation failed") from e


async def calculate_emotion_signal(
    query: str,
    history: list[dict],
    history_rounds: int = 3,
) -> SignalResult:
    """用户情感检测信号"""
    calculator = ConfidenceSignalCalculator(history_rounds=history_rounds)
    return await calculator.calculate_emotion_signal(query, history)


async def calculate_confidence_signals(
    state: Mapping[str, Any],
    generated_answer: str | None = None,
    llm: BaseChatModel | None = None,
) -> dict[str, SignalResult]:
    """计算所有置信度信号（带超时控制）"""
    try:
        return await asyncio.wait_for(
            _calculate_confidence_signals(state, generated_answer, llm),
            timeout=settings.CONFIDENCE.CALCULATION_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise RuntimeError("Confidence signal calculation timed out") from exc


async def _calculate_confidence_signals(
    state: Mapping[str, Any],
    generated_answer: str | None,
    llm: BaseChatModel | None,
) -> dict[str, SignalResult]:
    retrieval_result = state.get("retrieval_result")
    query = state.get("question", "")
    history = state.get("history", [])

    results: dict[str, SignalResult] = {}

    if retrieval_result:
        rag_coro = calculate_rag_signal(
            similarities=retrieval_result["similarities"],
            chunks=retrieval_result["chunks"],
            query=query,
        )
        emotion_coro = calculate_emotion_signal(
            query=query,
            history=history,
            history_rounds=settings.CONFIDENCE.EMOTION_HISTORY_ROUNDS,
        )
        results["rag"], results["emotion"] = await asyncio.gather(rag_coro, emotion_coro)
    else:
        results["emotion"] = await calculate_emotion_signal(
            query=query,
            history=history,
            history_rounds=settings.CONFIDENCE.EMOTION_HISTORY_ROUNDS,
        )
        results["rag"] = SignalResult(score=0.0, reason="无检索结果")

    should_skip_llm = (
        settings.CONFIDENCE.SKIP_LLM_ON_CLEAR_RAG
        and generated_answer is None
        and (
            results["rag"].score >= settings.CONFIDENCE.CLEAR_RAG_THRESHOLD_HIGH
            or results["rag"].score <= settings.CONFIDENCE.CLEAR_RAG_THRESHOLD_LOW
        )
    )

    if should_skip_llm:
        results["llm"] = SignalResult(
            score=results["rag"].score,
            reason=f"RAG信号明确({results['rag'].score:.2f})，跳过LLM",
            metadata={"skipped": True},
        )
    elif generated_answer and llm is not None:
        context = retrieval_result["chunks"] if retrieval_result else []
        results["llm"] = await calculate_llm_signal(
            query=query,
            context=context,
            generated_answer=generated_answer,
            llm=llm,
        )
    else:
        results["llm"] = SignalResult(score=0.5, reason="等待生成结果")

    return results
