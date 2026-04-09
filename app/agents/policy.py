from app.agents.base import AgentResult, BaseAgent
from app.models.state import RetrievalResult  # 使用新的 RetrievalResult
from app.retrieval import get_retriever

POLICY_SYSTEM_PROMPT = """你是专业的电商政策咨询专家。

规则：
1. 只能依据提供的参考信息回答，严禁编造
2. 如果参考信息为空，直接回答"抱歉，暂未查询到相关规定"
3. 回答简洁明了，引用具体政策条款
4. 语气专业、客气"""


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

        # 标记为用户可见的输出
        response = await self._call_llm(messages, tags=["user_visible"])

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
        retriever = get_retriever()
        results = await retriever.retrieve(question)
        chunks = [r.content for r in results]
        similarities = [r.score for r in results]
        sources = [r.source for r in results]
        print(f"[PolicyAgent] 检索到 {len(results)} 条有效结果")
        return chunks, similarities, sources

    def _estimate_confidence(
        self,
        chunks: list[str],
        similarities: list[float]
    ) -> float:
        if not chunks:
            return 0.0
        if similarities:
            avg_sim = sum(similarities) / len(similarities)
            # Direct mapping without arbitrary stretching; thresholds will be tuned after data collection
            if avg_sim >= 0.65:
                return 0.8
            elif avg_sim >= 0.45:
                return 0.5
            else:
                return 0.2
        return 0.5 if len(chunks) > 0 else 0.0
