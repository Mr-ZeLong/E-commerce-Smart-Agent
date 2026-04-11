import logging
from typing import Any

from app.agents.base import BaseAgent
from app.models.state import AgentState
from app.retrieval import get_retriever

logger = logging.getLogger(__name__)

POLICY_SYSTEM_PROMPT = """你是专业的电商政策咨询专家。

规则：
1. 只能依据提供的参考信息回答，严禁编造
2. 如果参考信息为空，直接回答"抱歉，暂未查询到相关规定"
3. 回答简洁明了，引用具体政策条款
4. 语气专业、客气"""


class PolicyAgent(BaseAgent):
    """政策专家 Agent"""

    def __init__(self):
        super().__init__(name="policy", system_prompt=POLICY_SYSTEM_PROMPT)

    async def process(self, state: AgentState) -> dict[str, Any]:
        question = state.get("question", "")

        chunks, similarities, sources = await self._retrieve_knowledge(question)

        retrieval_result = {"chunks": chunks, "similarities": similarities, "sources": sources}

        messages = self._create_messages(question, context={"context": chunks})

        response = await self._call_llm(messages, tags=["user_visible"])

        return {
            "response": response,
            "updated_state": {
                "retrieval_result": retrieval_result,
                "answer": response,
            },
        }

    async def _retrieve_knowledge(self, question: str) -> tuple[list[str], list[float], list[str]]:
        retriever = get_retriever()
        results = await retriever.retrieve(question)
        chunks = [r.content for r in results]
        similarities = [r.score for r in results]
        sources = [r.source for r in results]
        logger.info(f"[PolicyAgent] 检索到 {len(results)} 条有效结果")
        return chunks, similarities, sources
