from langchain_core.messages import HumanMessage
from sqlmodel import select

from app.agents.base import AgentResult, BaseAgent
from app.core.database import async_session_maker
from app.models.knowledge import KnowledgeChunk
from app.models.state import RetrievalResult  # 使用新的 RetrievalResult


POLICY_SYSTEM_PROMPT = """你是专业的电商政策咨询专家。

规则：
1. 只能依据提供的参考信息回答，严禁编造
2. 如果参考信息为空，直接回答"抱歉，暂未查询到相关规定"
3. 回答简洁明了，引用具体政策条款
4. 语气专业、客气"""


SIMILARITY_THRESHOLD = 0.5


class PolicyAgent(BaseAgent):
    """
    政策专家 Agent

    职责：
    1. 执行 RAG 检索获取相关政策
    2. 基于检索结果生成准确回答
    3. 计算回答置信度
    """

    def __init__(self):
        super().__init__(
            name="policy",
            system_prompt=POLICY_SYSTEM_PROMPT
        )

    async def process(self, state: dict) -> AgentResult:
        """处理政策咨询"""
        question = state.get("question", "")

        # Step 1: RAG 检索
        chunks, similarities, sources = await self._retrieve_knowledge(question)

        # 构建 RetrievalResult（使用新的统一封装）
        retrieval_result = RetrievalResult(
            chunks=chunks,
            similarities=similarities,
            sources=sources
        )

        # Step 2: 构建消息并生成回复
        messages = self._create_messages(
            question,
            context={"context": chunks}
        )

        response = await self._call_llm(messages)

        # Step 3: 计算置信度（初步估计）
        confidence = self._estimate_confidence(chunks, similarities)

        return AgentResult(
            response=response,
            updated_state={
                "retrieval_result": retrieval_result,  # 使用新的统一封装
                "context": chunks,  # 向后兼容
                "answer": response
            },
            confidence=confidence
        )

    async def _retrieve_knowledge(
        self,
        question: str
    ) -> tuple[list[str], list[float], list[str]]:
        """
        执行 RAG 检索

        Returns:
            (chunks, similarities, sources)
        """
        from app.graph.nodes import embedding_model

        # 生成查询向量
        query_vector = await embedding_model.aembed_query(question)

        async with async_session_maker() as session:
            distance_col = KnowledgeChunk.embedding.cosine_distance(query_vector).label("distance")  # type: ignore

            stmt = (
                select(KnowledgeChunk, distance_col)
                .where(KnowledgeChunk.is_active)
                .order_by(distance_col)
                .limit(5)
            )
            result = await session.exec(stmt)
            results = result.all()

        # 过滤并收集结果
        valid_chunks = []
        distances = []
        sources = []

        for chunk, distance in results:
            distances.append(float(distance))
            sources.append(chunk.source or "unknown")
            if distance < SIMILARITY_THRESHOLD:
                valid_chunks.append(chunk.content)

        # 将距离转换为相似度 (1 - distance)
        similarities = [1.0 - d for d in distances]

        print(f"[PolicyAgent] 检索到 {len(results)} 条，有效 {len(valid_chunks)} 条")

        return valid_chunks, similarities, sources

    def _estimate_confidence(
        self,
        chunks: list[str],
        similarities: list[float]
    ) -> float:
        """
        初步估计置信度（完整置信度在置信度节点计算）
        """
        if not chunks:
            return 0.0

        if similarities:
            avg_similarity = sum(similarities) / len(similarities)
            # 简单映射：相似度越高置信度越高
            if avg_similarity >= 0.7:
                return 0.8
            elif avg_similarity >= 0.5:
                return 0.5
            else:
                return 0.2

        return 0.5 if len(chunks) > 0 else 0.0
