import logging

from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.base import BaseAgent
from app.models.state import AgentProcessResult, AgentState
from app.retrieval.retriever import HybridRetriever

logger = logging.getLogger(__name__)

POLICY_SYSTEM_PROMPT = """你是专业的电商政策咨询专家。

规则：
1. 只能依据提供的参考信息回答，严禁编造
2. 如果参考信息为空，直接回答"抱歉，暂未查询到相关规定"
3. 回答简洁明了，引用具体政策条款
4. 语气专业、客气"""


class PolicyAgent(BaseAgent):
    def __init__(self, retriever: HybridRetriever, llm: BaseChatModel):
        super().__init__(name="policy_agent", llm=llm, system_prompt=POLICY_SYSTEM_PROMPT)
        self.retriever = retriever

    async def process(self, state: AgentState) -> AgentProcessResult:
        await self._load_config()
        question = state.get("question", "")

        chunks, similarities, sources = await self._retrieve_knowledge(state)

        retrieval_result = {"chunks": chunks, "similarities": similarities, "sources": sources}

        messages = self._create_messages(
            question,
            context={"context": chunks},
            memory_context=state.get("memory_context"),
        )

        response = await self._call_llm(messages, tags=["user_visible"])

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
        chunks = [r.content for r in results]
        similarities = [r.score for r in results]
        sources = [r.source for r in results]
        logger.info("[PolicyAgent] 检索到 %s 条有效结果", len(results))
        return chunks, similarities, sources
