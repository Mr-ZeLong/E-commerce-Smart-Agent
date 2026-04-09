# app/confidence/signals.py
# ruff: noqa: S101
import asyncio
import re
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import settings
from app.models.state import AgentState


@dataclass
class SignalResult:
    """信号计算结果"""
    score: float
    reason: str
    metadata: dict | None = None


@dataclass
class RAGSignal:
    """基于检索质量计算置信度"""

    async def calculate(
        self,
        similarities: list[float],
        chunks: list[str],
        query: str,
    ) -> SignalResult:
        """计算 RAG 信号"""
        if not similarities:
            return SignalResult(score=0.0, reason="无检索结果")

        avg_sim = sum(similarities) / len(similarities)
        max_sim = max(similarities)

        # 计算覆盖率
        query_words = set(query.lower().split())
        covered_words = set()
        for chunk in chunks:
            chunk_words = set(chunk.lower().split())
            covered_words.update(query_words & chunk_words)

        coverage = len(covered_words) / len(query_words) if query_words else 0.0
        # Note: similarities now come from reranker/RRF instead of 1.0 - cosine_distance.
        # Thresholds may need recalibration once Golden Dataset is available.
        score = max_sim * 0.4 + avg_sim * 0.3 + coverage * 0.3

        return SignalResult(
            score=min(max(score, 0.0), 1.0),
            reason=f"最高:{max_sim:.2f} 平均:{avg_sim:.2f} 覆盖:{coverage:.2f}",
            metadata={
                "max_similarity": max_sim,
                "avg_similarity": avg_sim,
                "coverage": coverage,
            }
        )


@dataclass
class LLMSignal:
    """LLM 自我评估信号"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.CONFIDENCE.EVALUATION_MODEL,  # type: ignore
            api_key=SecretStr(settings.OPENAI_API_KEY),  # type: ignore
            base_url=settings.OPENAI_BASE_URL,  # type: ignore
            temperature=0,
        )

    def _parse_confidence_score(self, text: str) -> float | None:
        """
        健壮地解析置信度分数（修复版）
        支持格式："0.85", "85%", "置信度：0.85"
        """
        if not text:
            return None

        text = text.strip()

        # 优先匹配带百分号的
        percent_match = re.search(r'(\d+\.?\d*)\s*%', text)
        if percent_match:
            try:
                value = float(percent_match.group(1))
                # 处理 85% 或 0.85%
                return min(max(value / 100, 0.0), 1.0)
            except (ValueError, TypeError):
                pass

        # 匹配其他格式
        patterns = [
            r'置信度[：:]\s*(\d+\.?\d*)',
            r'分数[是:：]\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    value = float(match.group(1))
                    # 如果值大于1，视为百分比
                    if value > 1.0:
                        value = value / 100
                    return min(max(value, 0.0), 1.0)
                except (ValueError, TypeError):
                    continue

        return None

    async def calculate(
        self,
        query: str,
        context: list[str],
        generated_answer: str,
    ) -> SignalResult:
        """计算 LLM 信号，带重试机制（标记为内部调用）"""
        prompt = f"""评估回答置信度（0-1）：
问题：{query}
回答：{generated_answer}
只返回数字："""

        max_retries = settings.CONFIDENCE.LLM_PARSE_MAX_RETRIES
        retry_delay = settings.CONFIDENCE.LLM_PARSE_RETRY_DELAY
        last_error = None

        for attempt in range(max_retries):
            try:
                # 标记为内部调用，避免被转发给用户
                response = await self.llm.ainvoke(
                    [{"role": "user", "content": prompt}],
                    config={"tags": ["confidence_eval", "internal"]}
                )
                raw_text = response.content if hasattr(response, 'content') else str(response)

                score = self._parse_confidence_score(str(raw_text))

                if score is not None:
                    return SignalResult(
                        score=score,
                        reason=f"LLM自评估(尝试{attempt + 1})",
                        metadata={"raw_response": raw_text[:200]}
                    )

                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))

        return SignalResult(
            score=0.5,
            reason="解析失败，使用默认值",
            metadata={"error": str(last_error) if last_error else "parse_failed"}
        )


@dataclass
class EmotionSignal:
    """用户情感检测信号（修复词典）"""

    # 扩展的情感词典
    NEGATIVE_WORDS = frozenset([
        '生气', '愤怒', '不满', '投诉', '差评', '退款', '骗子', '垃圾', '太差',
        '失望', '欺骗', '坑', '忽悠', '恶劣', '糟糕', '气愤', '恼火', '心烦'
    ])
    URGENT_WORDS = frozenset([
        '马上', '立刻', '现在', '急', '紧急', 'hurry', 'urgent', 'asap',
        '立即', '赶紧', '赶快', '快点', '等着', '急用'
    ])
    POSITIVE_WORDS = frozenset([
        '谢谢', '感谢', '满意', '好评', '不错', '好用', '推荐', '喜欢',
        '完美', '优秀', '棒', '赞', '给力', '靠谱'
    ])

    async def calculate(
        self,
        query: str,
        history: list[dict],
        history_rounds: int = 3,
    ) -> SignalResult:
        """检测用户情感状态"""
        recent_history = history[-history_rounds:] if len(history) >= history_rounds else history

        all_texts = [msg.get('content', '') for msg in recent_history] + [query]
        all_text = ' '.join(all_texts).lower()

        negative_count = sum(1 for w in self.NEGATIVE_WORDS if w in all_text)
        urgent_count = sum(1 for w in self.URGENT_WORDS if w in all_text)
        positive_count = sum(1 for w in self.POSITIVE_WORDS if w in all_text)

        # 情感计算逻辑
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
            }
        )


class ConfidenceSignals:
    """置信度信号计算器（修复 asyncio.gather 使用）"""

    def __init__(self, state: AgentState):
        self.state = state
        self.rag_signal = RAGSignal()
        self.llm_signal = LLMSignal()
        self.emotion_signal = EmotionSignal()

    async def _calculate_with_timeout(
        self,
        generated_answer: str | None = None
    ) -> dict[str, SignalResult]:
        """内部计算逻辑"""
        retrieval_result = self.state.get("retrieval_result")
        query = self.state.get("question", "")
        history = self.state.get("history", [])

        results: dict[str, SignalResult] = {}

        # === 阶段 1: 并行计算独立信号（修复版）===
        if retrieval_result:
            # 正确创建 coroutine 并使用 asyncio.gather
            rag_coro = self.rag_signal.calculate(
                similarities=retrieval_result.similarities,
                chunks=retrieval_result.chunks,
                query=query,
            )
            emotion_coro = self.emotion_signal.calculate(
                query=query,
                history=history,
                history_rounds=settings.CONFIDENCE.EMOTION_HISTORY_ROUNDS,
            )
            # 两个独立的 coroutine 可以安全地 gather
            results["rag"], results["emotion"] = await asyncio.gather(rag_coro, emotion_coro)
        else:
            # 没有检索结果，只计算情感
            results["emotion"] = await self.emotion_signal.calculate(
                query=query,
                history=history,
                history_rounds=settings.CONFIDENCE.EMOTION_HISTORY_ROUNDS,
            )
            results["rag"] = SignalResult(score=0.0, reason="无检索结果")

        # === 阶段 2: 智能跳过 LLMSignal ===
        should_skip_llm = (
            settings.CONFIDENCE.SKIP_LLM_ON_CLEAR_RAG and
            generated_answer is None and
            (
                results["rag"].score >= settings.CONFIDENCE.CLEAR_RAG_THRESHOLD_HIGH or
                results["rag"].score <= settings.CONFIDENCE.CLEAR_RAG_THRESHOLD_LOW
            )
        )

        if should_skip_llm:
            # 修复：使用 .score 访问分数
            results["llm"] = SignalResult(
                score=results["rag"].score,
                reason=f"RAG信号明确({results['rag'].score:.2f})，跳过LLM",
                metadata={"skipped": True}
            )
        elif generated_answer:
            context = retrieval_result.chunks if retrieval_result else []
            results["llm"] = await self.llm_signal.calculate(
                query=query,
                context=context,
                generated_answer=generated_answer,
            )
        else:
            results["llm"] = SignalResult(score=0.5, reason="等待生成结果")

        return results

    async def calculate_all(
        self,
        generated_answer: str | None = None
    ) -> dict[str, SignalResult]:
        """
        计算所有信号（带超时控制）
        """
        try:
            return await asyncio.wait_for(
                self._calculate_with_timeout(generated_answer),
                timeout=settings.CONFIDENCE.CALCULATION_TIMEOUT_SECONDS
            )
        except TimeoutError:
            # 超时返回保守估计
            return {
                "rag": SignalResult(score=0.5, reason="计算超时"),
                "llm": SignalResult(score=0.5, reason="计算超时"),
                "emotion": SignalResult(score=0.5, reason="计算超时"),
            }
