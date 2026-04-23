import asyncio
import logging
import re
import time
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.core.tracing import build_llm_config
from app.intent.few_shot_loader import load_agent_examples
from app.models.state import AgentProcessResult, AgentState
from app.retrieval.retriever import HybridRetriever, RetrievedChunk

logger = logging.getLogger(__name__)

POLICY_SYSTEM_PROMPT = """你是专业的电商政策咨询专家。

规则：
1. 只能依据提供的参考信息回答，严禁编造
2. 如果参考信息为空，直接回答"抱歉，暂未查询到相关规定"
3. 回答简洁明了，引用具体政策条款
4. 语气专业、客气
5. 在回答中标注引用来源，格式为 [来源: X]
6. 必须直接输出自然语言回答，不要输出JSON格式
7. 不要输出思考过程或分析步骤
8. 【强制】每个事实性陈述后必须附带引用标记 [来源: X]
9. 【强制】如果参考信息不足以完整回答问题，必须明确说明"根据现有信息，无法确定..."
"""

_RELEVANCE_THRESHOLD = 0.3
_ADEQUACY_CONFIDENCE_THRESHOLD = 0.6
_FALLBACK_RESPONSE = "抱歉，根据现有信息无法回答您的问题。建议您联系人工客服获取更准确的信息。"

_CITATION_PATTERN = re.compile(r"\[来源:\s*[^\]]+\]")


class GradeDocuments(BaseModel):
    binary_score: str = Field(description="'yes' or 'no'")


class RetrievalAdequacy(BaseModel):
    adequacy: str = Field(description="'yes', 'no', or 'partial'")
    confidence: float = Field(description="Confidence score 0.0-1.0")
    reason: str = Field(description="Explanation for the adequacy assessment")


class CitationVerification(BaseModel):
    has_citations: bool = Field(description="Whether the answer contains required citations")
    citation_count: int = Field(description="Number of citation markers found")
    missing_sources: list[str] = Field(
        default_factory=list, description="Sources that should have been cited"
    )


class SelfReflectionResult(BaseModel):
    quality_score: float = Field(description="Quality score 0.0-1.0")
    is_hallucination: bool = Field(description="Whether the answer contains hallucinations")
    issues: list[str] = Field(default_factory=list, description="List of quality issues found")
    improvement: str = Field(default="", description="Suggested improvement")


class SelfRAGResult(BaseModel):
    retrieval_adequacy: str = Field(default="unknown", description="yes/no/partial")
    adequacy_confidence: float = Field(default=0.0)
    adequacy_reason: str = Field(default="")
    fallback_triggered: bool = Field(default=False)
    citations_verified: bool = Field(default=False)
    citation_count: int = Field(default=0)
    self_reflection_score: float = Field(default=0.0)
    self_reflection_issues: list[str] = Field(default_factory=list)
    latency_ms: float = Field(default=0.0, description="Self-RAG overhead latency in ms")


class PolicyAgent(BaseAgent):
    """Policy Q&A agent with Self-RAG implementation."""

    def __init__(self, retriever: HybridRetriever, llm: BaseChatModel):
        super().__init__(name="policy_agent", llm=llm, system_prompt=POLICY_SYSTEM_PROMPT)
        self.retriever = retriever
        self._few_shot_examples = load_agent_examples("policy")

    async def process(self, state: AgentState) -> AgentProcessResult:
        start_time = time.perf_counter()
        await self._load_config()
        override = await self._resolve_experiment_prompt(state)
        if override:
            self._dynamic_system_prompt = override
        question = state.get("question", "")

        retrieval_data = await self._retrieve_knowledge(state)
        chunks = retrieval_data["chunks"]
        similarities = retrieval_data["similarities"]
        sources = retrieval_data["sources"]
        self_rag = retrieval_data["self_rag"]

        if not chunks or self_rag.fallback_triggered:
            self_rag.latency_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "[PolicyAgent] Self-RAG fallback triggered (adequacy=%s, confidence=%.2f)",
                self_rag.retrieval_adequacy,
                self_rag.adequacy_confidence,
            )
            response = _FALLBACK_RESPONSE
            return {
                "response": response,
                "updated_state": {
                    "retrieval_result": {
                        "chunks": chunks,
                        "similarities": similarities,
                        "sources": sources,
                    },
                    "answer": response,
                    "self_rag": self_rag.model_dump(),
                },
            }

        retrieval_result = {
            "chunks": chunks,
            "similarities": similarities,
            "sources": sources,
        }

        few_shot_examples = await self._get_few_shot_examples(question)
        messages = self._create_messages(
            question,
            context={"context": chunks, "sources": sources},
            memory_context=state.get("memory_context"),
            user_context=self._build_user_context(state.get("memory_context")),
            memory_context_config=state.get("memory_context_config"),
            few_shot_examples=few_shot_examples,
        )

        metadata = self._extract_tracing_metadata(state)
        response = await self._call_llm(messages, tags=["user_visible"], metadata=metadata)

        verification_coro = self._verify_citations(response, sources)
        reflection_coro = self._self_reflect(question, response, chunks)
        try:
            verification, reflection = await asyncio.gather(
                verification_coro, reflection_coro, return_exceptions=True
            )
            if isinstance(verification, Exception):
                logger.warning("[PolicyAgent] Citation verification failed: %s", verification)
                verification = CitationVerification(
                    has_citations=_CITATION_PATTERN.search(response) is not None,
                    citation_count=len(_CITATION_PATTERN.findall(response)),
                )
            if isinstance(reflection, Exception):
                logger.warning("[PolicyAgent] Self-reflection failed: %s", reflection)
                reflection = SelfReflectionResult(quality_score=0.5, is_hallucination=False)
        except Exception as e:
            logger.warning("[PolicyAgent] Post-generation verification error: %s", e)
            verification = CitationVerification(
                has_citations=_CITATION_PATTERN.search(response) is not None,
                citation_count=len(_CITATION_PATTERN.findall(response)),
            )
            reflection = SelfReflectionResult(quality_score=0.5, is_hallucination=False)

        self_rag.citations_verified = verification.has_citations
        self_rag.citation_count = verification.citation_count
        self_rag.self_reflection_score = reflection.quality_score
        self_rag.self_reflection_issues = reflection.issues
        self_rag.latency_ms = (time.perf_counter() - start_time) * 1000

        if not verification.has_citations and chunks:
            logger.warning("[PolicyAgent] Answer lacks citations, potential hallucination risk")

        logger.info(
            "[PolicyAgent] Self-RAG completed (latency=%.1fms, adequacy=%s, citations=%s, reflection=%.2f)",
            self_rag.latency_ms,
            self_rag.retrieval_adequacy,
            self_rag.citations_verified,
            self_rag.self_reflection_score,
        )

        return {
            "response": response,
            "updated_state": {
                "retrieval_result": retrieval_result,
                "answer": response,
                "self_rag": self_rag.model_dump(),
            },
        }

    async def _retrieve_knowledge(self, state: AgentState) -> dict[str, Any]:
        question = state.get("question", "")
        results = await self.retriever.retrieve(
            question,
            conversation_history=state.get("history"),
            memory_context=state.get("memory_context"),
            variant_top_k=state.get("variant_retriever_top_k"),
            variant_reranker_enabled=state.get("variant_reranker_enabled"),
        )
        filtered = [r for r in results if r.score > _RELEVANCE_THRESHOLD]
        if not filtered:
            logger.warning("[PolicyAgent] 所有检索结果相关性均低于 %.2f", _RELEVANCE_THRESHOLD)
            return {
                "chunks": [],
                "similarities": [],
                "sources": [],
                "self_rag": SelfRAGResult(
                    retrieval_adequacy="no",
                    adequacy_confidence=0.0,
                    adequacy_reason="No documents passed relevance threshold",
                    fallback_triggered=True,
                ),
            }

        grades = await self._grade_documents(question, filtered)
        graded_filtered = [
            doc for doc, grade in zip(filtered, grades, strict=True) if grade.binary_score == "yes"
        ]
        if not graded_filtered:
            logger.warning("[PolicyAgent] 所有文档被评分器标记为不相关")
            return {
                "chunks": [],
                "similarities": [],
                "sources": [],
                "self_rag": SelfRAGResult(
                    retrieval_adequacy="no",
                    adequacy_confidence=0.0,
                    adequacy_reason="All documents graded as irrelevant",
                    fallback_triggered=True,
                ),
            }

        adequacy = await self._assess_retrieval_adequacy(question, graded_filtered)

        chunks = [r.content for r in graded_filtered]
        similarities = [r.score for r in graded_filtered]
        sources = [r.source for r in graded_filtered]

        fallback_triggered = adequacy.adequacy == "no" or (
            adequacy.adequacy == "partial" and adequacy.confidence < _ADEQUACY_CONFIDENCE_THRESHOLD
        )

        self_rag = SelfRAGResult(
            retrieval_adequacy=adequacy.adequacy,
            adequacy_confidence=adequacy.confidence,
            adequacy_reason=adequacy.reason,
            fallback_triggered=fallback_triggered,
        )

        if fallback_triggered:
            logger.info(
                "[PolicyAgent] Retrieval adequacy: %s (confidence=%.2f). Fallback triggered.",
                adequacy.adequacy,
                adequacy.confidence,
            )
            return {
                "chunks": [],
                "similarities": similarities,
                "sources": sources,
                "self_rag": self_rag,
            }

        logger.info(
            "[PolicyAgent] 检索到 %s 条有效结果 (adequacy=%s)",
            len(graded_filtered),
            adequacy.adequacy,
        )
        return {
            "chunks": chunks,
            "similarities": similarities,
            "sources": sources,
            "self_rag": self_rag,
        }

    async def _grade_documents(
        self, question: str, documents: list[RetrievedChunk]
    ) -> list[GradeDocuments]:
        grade_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "评估以下文档与用户问题的相关性，只回答 'yes' 或 'no'。",
                ),
                ("human", "问题：{question}\n\n文档：{document}"),
            ]
        )
        grader = grade_prompt | self.llm.with_structured_output(GradeDocuments)
        config = build_llm_config(
            agent_name="policy_agent_grader", tags=["internal", "rag_grading"]
        )
        tasks = [
            grader.ainvoke({"question": question, "document": doc.content}, config=config)
            for doc in documents
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        grades: list[GradeDocuments] = []
        for idx, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.warning("[PolicyAgent] 文档评分失败 (doc %s): %s", idx, result)
                grades.append(GradeDocuments(binary_score="yes"))
            elif isinstance(result, dict):
                grades.append(GradeDocuments(binary_score=result.get("binary_score", "yes")))
            elif isinstance(result, GradeDocuments):
                grades.append(result)
            else:
                logger.warning(
                    "[PolicyAgent] Unexpected grade type (doc %s): %s", idx, type(result)
                )
                grades.append(GradeDocuments(binary_score="yes"))
        return grades

    async def _assess_retrieval_adequacy(
        self, question: str, documents: list[RetrievedChunk]
    ) -> RetrievalAdequacy:
        if not documents:
            return RetrievalAdequacy(adequacy="no", confidence=0.0, reason="No documents retrieved")

        docs_text = "\n\n".join(f"[{i + 1}] {doc.content[:500]}" for i, doc in enumerate(documents))
        prompt = (
            f"用户问题：{question}\n\n"
            f"检索到的参考信息：\n{docs_text}\n\n"
            "请评估这些参考信息是否足以完整、准确地回答用户的问题。\n"
            "- 'yes': 信息充分，可以准确回答\n"
            "- 'partial': 信息部分充分，可以回答部分内容但可能不完整\n"
            "- 'no': 信息不充分，无法可靠回答\n"
            "请同时给出置信度评分（0.0-1.0）和简要理由。"
        )
        messages = [
            ("system", "你是检索质量评估专家。请严格评估参考信息是否足以回答问题。"),
            ("human", prompt),
        ]
        adequacy_prompt = ChatPromptTemplate.from_messages(messages)
        evaluator = adequacy_prompt | self.llm.with_structured_output(RetrievalAdequacy)
        config = build_llm_config(
            agent_name="policy_agent_adequacy", tags=["internal", "self_rag", "adequacy"]
        )
        try:
            result = await evaluator.ainvoke({}, config=config)
            if isinstance(result, dict):
                return RetrievalAdequacy(
                    adequacy=result.get("adequacy", "yes"),
                    confidence=float(result.get("confidence", 0.5)),
                    reason=result.get("reason", ""),
                )
            if isinstance(result, RetrievalAdequacy):
                return result
            logger.warning("[PolicyAgent] Unexpected adequacy type: %s", type(result))
            return RetrievalAdequacy(
                adequacy="yes", confidence=0.5, reason="Fallback due to unexpected type"
            )
        except Exception as e:
            logger.warning("[PolicyAgent] Retrieval adequacy assessment failed: %s", e)
            return RetrievalAdequacy(
                adequacy="yes", confidence=0.5, reason=f"Assessment failed: {e}"
            )

    async def _verify_citations(self, answer: str, sources: list[str]) -> CitationVerification:
        citations = _CITATION_PATTERN.findall(answer)
        has_citations = len(citations) > 0

        cited_sources: set[str] = set()
        for citation in citations:
            source_name = citation.replace("[来源:", "").replace("]", "").strip()
            cited_sources.add(source_name)

        missing = [s for s in sources if s not in cited_sources]

        return CitationVerification(
            has_citations=has_citations,
            citation_count=len(citations),
            missing_sources=missing,
        )

    async def _self_reflect(
        self, question: str, answer: str, chunks: list[str]
    ) -> SelfReflectionResult:
        if not chunks:
            return SelfReflectionResult(quality_score=0.5, is_hallucination=False)

        chunks_text = "\n\n".join(f"[{i + 1}] {c[:400]}" for i, c in enumerate(chunks))
        prompt = (
            f"用户问题：{question}\n\n"
            f"生成的回答：{answer}\n\n"
            f"参考信息：\n{chunks_text}\n\n"
            "请评估回答质量：\n"
            "1. 回答是否基于参考信息（无幻觉）\n"
            "2. 回答是否完整回应了问题\n"
            "3. 回答是否准确引用了参考信息\n"
            "给出质量评分（0.0-1.0）、是否包含幻觉、发现的问题列表。"
        )
        messages = [
            ("system", "你是回答质量评估专家。严格检测回答中的幻觉和事实错误。"),
            ("human", prompt),
        ]
        reflect_prompt = ChatPromptTemplate.from_messages(messages)
        evaluator = reflect_prompt | self.llm.with_structured_output(SelfReflectionResult)
        config = build_llm_config(
            agent_name="policy_agent_reflection", tags=["internal", "self_rag", "reflection"]
        )
        try:
            result = await evaluator.ainvoke({}, config=config)
            if isinstance(result, dict):
                return SelfReflectionResult(
                    quality_score=float(result.get("quality_score", 0.5)),
                    is_hallucination=bool(result.get("is_hallucination", False)),
                    issues=result.get("issues", []),
                    improvement=result.get("improvement", ""),
                )
            if isinstance(result, SelfReflectionResult):
                return result
            logger.warning("[PolicyAgent] Unexpected reflection type: %s", type(result))
            return SelfReflectionResult(quality_score=0.5, is_hallucination=False)
        except Exception as e:
            logger.warning("[PolicyAgent] Self-reflection failed: %s", e)
            return SelfReflectionResult(quality_score=0.5, is_hallucination=False)
