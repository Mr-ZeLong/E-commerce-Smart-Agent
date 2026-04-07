import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.policy import PolicyAgent


class TestPolicyAgent:
    """测试政策 Agent"""

    @pytest.fixture
    def policy_agent(self):
        return PolicyAgent()

    @pytest.mark.asyncio
    async def test_process_with_rag_context(self, policy_agent):
        """测试有 RAG 上下文时的处理"""
        # Mock RAG 检索
        with patch.object(policy_agent, '_retrieve_knowledge', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = (
                ["运费满100免运费", "配送时效1-3天"],  # chunks
                [0.8, 0.75],  # similarities
                ["policy_doc_1", "policy_doc_2"]  # sources
            )

            # Mock LLM 调用
            with patch.object(policy_agent, '_call_llm', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = "运费满100元免运费，配送时效为1-3天。"

                result = await policy_agent.process({
                    "question": "运费怎么算？",
                    "user_id": 1
                })

                assert "运费" in result.response
                assert result.updated_state["context"] == ["运费满100免运费", "配送时效1-3天"]
                assert result.confidence is not None

    @pytest.mark.asyncio
    async def test_process_with_empty_retrieval(self, policy_agent):
        """测试 RAG 检索为空时的处理"""
        with patch.object(policy_agent, '_retrieve_knowledge', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = ([], [], [])  # 空结果

            # Mock LLM 调用
            with patch.object(policy_agent, '_call_llm', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = "抱歉，暂未查询到相关规定"

                result = await policy_agent.process({
                    "question": "请问这个政策是什么意思？",
                    "user_id": 1
                })

                # 应该返回无法回答，且置信度较低
                assert "抱歉" in result.response or "暂未查询" in result.response
                assert result.confidence is not None
                assert result.confidence < 0.5
