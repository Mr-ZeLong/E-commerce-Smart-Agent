import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.supervisor import SupervisorAgent


class TestSupervisorAgent:
    """测试监督 Agent"""

    @pytest.fixture
    def supervisor(self):
        return SupervisorAgent()

    @pytest.mark.asyncio
    async def test_coordinate_policy_flow(self, supervisor):
        """测试协调政策查询流程"""
        # Mock RouterAgent
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router:
            mock_router.return_value.updated_state = {
                "intent": "POLICY",
                "next_agent": "policy"
            }
            mock_router.return_value.response = ""

            # Mock PolicyAgent
            with patch.object(supervisor.policy_agent, 'process', new_callable=AsyncMock) as mock_policy:
                mock_policy.return_value.updated_state = {
                    "answer": "运费满100免运费",
                    "context": ["运费政策"],
                    "retrieval_result": None
                }
                mock_policy.return_value.response = "运费满100免运费"
                mock_policy.return_value.confidence = 0.85

                # Mock ConfidenceSignals
                with patch('app.confidence.signals.ConfidenceSignals') as mock_signals_class:
                    mock_signals = mock_signals_class.return_value
                    mock_signals.calculate_all = AsyncMock(return_value={
                        "rag": MagicMock(score=0.9, reason="高相似度"),
                        "llm": MagicMock(score=0.85, reason="自评估"),
                        "emotion": MagicMock(score=0.8, reason="中性")
                    })

                    result = await supervisor.coordinate({
                        "question": "运费怎么算？",
                        "user_id": 1
                    })

                    assert result["answer"] == "运费满100免运费"
                    assert "confidence_score" in result

    @pytest.mark.asyncio
    async def test_high_confidence_no_audit(self, supervisor):
        """测试高置信度不触发审核"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router:
            mock_router.return_value.updated_state = {"intent": "POLICY", "next_agent": "policy"}
            mock_router.return_value.response = ""

            with patch.object(supervisor.policy_agent, 'process', new_callable=AsyncMock) as mock_policy:
                mock_policy.return_value.response = "这是回答"
                mock_policy.return_value.confidence = 0.9
                mock_policy.return_value.updated_state = {"answer": "这是回答", "retrieval_result": None}

                with patch('app.confidence.signals.ConfidenceSignals') as mock_signals_class:
                    mock_signals = mock_signals_class.return_value
                    mock_signals.calculate_all = AsyncMock(return_value={
                        "rag": MagicMock(score=0.95, reason="高相似度"),
                        "llm": MagicMock(score=0.9, reason="自评估"),
                        "emotion": MagicMock(score=0.85, reason="中性")
                    })

                    result = await supervisor.coordinate({
                        "question": "简单问题",
                        "user_id": 1
                    })

                    assert result["needs_human_transfer"] is False
                    assert result["audit_level"] == "none"

    @pytest.mark.asyncio
    async def test_low_confidence_triggers_transfer(self, supervisor):
        """测试低置信度触发转人工"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router:
            mock_router.return_value.updated_state = {"intent": "POLICY", "next_agent": "policy"}
            mock_router.return_value.response = ""

            with patch.object(supervisor.policy_agent, 'process', new_callable=AsyncMock) as mock_policy:
                mock_policy.return_value.response = "不确定的回答"
                mock_policy.return_value.updated_state = {"answer": "不确定的回答", "retrieval_result": None}

                with patch('app.confidence.signals.ConfidenceSignals') as mock_signals_class:
                    mock_signals = mock_signals_class.return_value
                    mock_signals.calculate_all = AsyncMock(return_value={
                        "rag": MagicMock(score=0.3, reason="低相似度"),
                        "llm": MagicMock(score=0.4, reason="不确定"),
                        "emotion": MagicMock(score=0.5, reason="中性")
                    })

                    result = await supervisor.coordinate({
                        "question": "复杂问题",
                        "user_id": 1
                    })

                    assert result["needs_human_transfer"] is True
                    assert result["audit_level"] == "manual"

    @pytest.mark.asyncio
    async def test_router_direct_response(self, supervisor):
        """测试 Router 直接返回回复（闲聊）"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router:
            mock_router.return_value.response = "你好！有什么可以帮您？"
            mock_router.return_value.updated_state = {
                "intent": "OTHER",
                "next_agent": "supervisor"
            }

            result = await supervisor.coordinate({
                "question": "你好",
                "user_id": 1
            })

            assert result["answer"] == "你好！有什么可以帮您？"
            assert result["confidence_score"] == 1.0
            assert result["needs_human_transfer"] is False

    @pytest.mark.asyncio
    async def test_order_flow(self, supervisor):
        """测试订单查询流程"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router:
            mock_router.return_value.updated_state = {
                "intent": "ORDER",
                "next_agent": "order"
            }
            mock_router.return_value.response = ""

            with patch.object(supervisor.order_agent, 'process', new_callable=AsyncMock) as mock_order:
                mock_order.return_value.response = "订单状态：已发货"
                mock_order.return_value.updated_state = {
                    "answer": "订单状态：已发货",
                    "order_data": {"order_sn": "SN123"},
                    "retrieval_result": None
                }

                with patch('app.confidence.signals.ConfidenceSignals') as mock_signals_class:
                    mock_signals = mock_signals_class.return_value
                    mock_signals.calculate_all = AsyncMock(return_value={
                        "rag": MagicMock(score=0.8, reason="中等相似度"),
                        "llm": MagicMock(score=0.85, reason="自评估"),
                        "emotion": MagicMock(score=0.9, reason="正面")
                    })

                    result = await supervisor.coordinate({
                        "question": "我的订单到哪了？",
                        "user_id": 1
                    })

                    assert result["answer"] == "订单状态：已发货"
                    assert result["intent"] == "ORDER"

    @pytest.mark.asyncio
    async def test_process_interface(self, supervisor):
        """测试 process 接口符合 BaseAgent 规范"""
        with patch.object(supervisor, 'coordinate', new_callable=AsyncMock) as mock_coordinate:
            mock_coordinate.return_value = {
                "answer": "测试回答",
                "confidence_score": 0.9,
                "needs_human_transfer": False
            }

            result = await supervisor.process({
                "question": "测试问题",
                "user_id": 1
            })

            assert result.response == "测试回答"
            assert result.updated_state["confidence_score"] == 0.9

    @pytest.mark.asyncio
    async def test_unknown_agent_fallback(self, supervisor):
        """测试未知 Agent 回退处理"""
        with patch.object(supervisor.router, 'process', new_callable=AsyncMock) as mock_router:
            mock_router.return_value.updated_state = {
                "intent": "UNKNOWN",
                "next_agent": "unknown_agent"
            }
            mock_router.return_value.response = ""

            result = await supervisor.coordinate({
                "question": "未知问题",
                "user_id": 1
            })

            assert "人工客服" in result["answer"]
