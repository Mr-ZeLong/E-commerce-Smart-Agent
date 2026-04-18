import asyncio
import logging

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
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
"""

_RELEVANCE_THRESHOLD = 0.5


class GradeDocuments(BaseModel):
    binary_score: str = Field(description="'yes' or 'no'")


class PolicyAgent(BaseAgent):
    def __init__(self, retriever: HybridRetriever, llm: BaseChatModel):
        super().__init__(name="policy_agent", llm=llm, system_prompt=POLICY_SYSTEM_PROMPT)
        self.retriever = retriever

    async def process(self, state: AgentState) -> AgentProcessResult:
        await self._load_config()
        override = await self._resolve_experiment_prompt(state)
        if override:
            self._dynamic_system_prompt = override
        question = state.get("question", "")

        chunks, similarities, sources = await self._retrieve_knowledge(state)

        if not chunks:
            response = "抱歉，暂未查询到相关规定"
            return {
                "response": response,
                "updated_state": {
                    "retrieval_result": {"chunks": [], "similarities": [], "sources": []},
                    "answer": response,
                },
            }

        retrieval_result = {"chunks": chunks, "similarities": similarities, "sources": sources}

        messages = self._create_messages(
            question,
            context={"context": chunks},
            memory_context=state.get("memory_context"),
            user_context=self._build_user_context(state.get("memory_context")),
            memory_context_config=state.get("memory_context_config"),
        )

        metadata = self._extract_tracing_metadata(state)
        response = await self._call_llm(messages, tags=["user_visible"], metadata=metadata)

        return {
            "response": response,
            "updated_state": {
                "retrieval_result": retrieval_result,
                "answer": response,
            },
        }

    async def _retrieve_knowledge(
        self, state: AgentState
    ) -> tuple[list[str], list[float], list[str]]:
        question = state.get("question", "")
        results = await self.retriever.retrieve(
            question,
            conversation_history=state.get("history"),
            memory_context=state.get("memory_context"),
        )
        filtered = [r for r in results if r.score >= _RELEVANCE_THRESHOLD]
        if not filtered:
            logger.warning("[PolicyAgent] 所有检索结果相关性均低于 %.2f", _RELEVANCE_THRESHOLD)
            return [], [], []

        graded = await self._grade_documents(question, filtered)
        relevant = [
            r for r, g in zip(filtered, graded, strict=True) if g.binary_score.lower() == "yes"
        ]
        if not relevant:
            logger.warning("[PolicyAgent] Self-RAG grader 判定无相关文档")
            return [], [], []

        chunks = [r.content for r in relevant]
        similarities = [r.score for r in relevant]
        sources = [r.source for r in relevant]
        logger.info("[PolicyAgent] 检索到 %s 条有效结果", len(relevant))
        return chunks, similarities, sources

    async def _grade_documents(
        self, question: str, documents: list[RetrievedChunk]
    ) -> list[GradeDocuments]:
        from langchain_core.prompts import ChatPromptTemplate

        grade_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "评估以下文档与用户问题的相关性，只回答 'yes' 或 'no'。",
                ),
                ("human", "问题：{question}\n\n文档：{document}"),
            ]
        )
        from app.core.tracing import build_llm_config

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
