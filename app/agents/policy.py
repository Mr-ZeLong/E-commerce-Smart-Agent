import logging
from typing import Any

from app.agents.base import AgentResult, BaseAgent
from app.models.state import RetrievalResult  # 使用新的 RetrievalResult
from app.retrieval import get_retriever

logger = logging.getLogger(__name__)

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
        super().__init__(name="policy", system_prompt=POLICY_SYSTEM_PROMPT)

    async def process(self, state: dict[str, Any]) -> AgentResult:
        """处理政策咨询"""
        question = state.get("question", "")

        # Step 1: RAG 检索
        chunks, similarities, sources = await self._retrieve_knowledge(question)

        # 构建 RetrievalResult（使用新的统一封装）
        retrieval_result = RetrievalResult(
            chunks=chunks, similarities=similarities, sources=sources
        )

        # Step 2: 构建消息并生成回复
        messages = self._create_messages(question, context={"context": chunks})

        # 标记为用户可见的输出
        response = await self._call_llm(messages, tags=["user_visible"])

        # Step 3: 置信度评估现在统一由上层 ConfidenceEvaluator 负责
        confidence = 0.0
        needs_human = False
        transfer_reason = None

        return AgentResult(
            response=response,
            updated_state={
                "retrieval_result": retrieval_result,  # 使用新的统一封装
                "context": chunks,  # 向后兼容
                "answer": response,
            },
            confidence=confidence,
            needs_human=needs_human,
            transfer_reason=transfer_reason,
        )

    async def _retrieve_knowledge(self, question: str) -> tuple[list[str], list[float], list[str]]:
        retriever = get_retriever()
        results = await retriever.retrieve(question)
        chunks = [r.content for r in results]
        similarities = [r.score for r in results]
        sources = [r.source for r in results]
        logger.info(f"[PolicyAgent] 检索到 {len(results)} 条有效结果")
        return chunks, similarities, sources
