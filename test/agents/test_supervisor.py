from unittest.mock import AsyncMock, patch

import pytest

from app.agents.base import AgentResult
from app.agents.supervisor import SupervisorAgent


class TestSupervisorAgent:
    """测试监督 Agent"""

    @pytest.fixture
    def supervisor(self):
        return SupervisorAgent()

    @pytest.mark.asyncio
    async def test_coordinate_policy_flow(self, supervisor):
        """测试协调政策查询流程"""
        with patch.object(
            supervisor.orchestrator, 'route_and_execute', new_callable=AsyncMock
        ) as mock_orch:
            mock_orch.return_value = AgentResult(
                response="运费满100免运费",
                updated_state={
                    "_router_intent": "POLICY",
                    "_router_next_agent": "policy",
                    "retrieval_result": None,
                },
                confidence=0.85,
                needs_human=False,
            )

            with patch.object(
                supervisor.evaluator, 'evaluate', new_callable=AsyncMock
            ) as mock_eval:
                mock_eval.return_value = {
                    "confidence_score": 0.88,
                    "confidence_signals": {
                        "rag": {"score": 0.9, "reason": "高相似度"},
                        "llm": {"score": 0.85, "reason": "自评估"},
                        "emotion": {"score": 0.8, "reason": "中性"},
                    },
                    "needs_human_transfer": False,
                    "transfer_reason": None,
                    "audit_level": "none",
                }

                result = await supervisor.coordinate({
                    "question": "运费怎么算？",
                    "user_id": 1
                })

                assert result["answer"] == "运费满100免运费"
                assert "confidence_score" in result
                assert result["intent"] == "POLICY"
                assert result["needs_human_transfer"] is False

    @pytest.mark.asyncio
    async def test_high_confidence_no_audit(self, supervisor):
        """测试高置信度不触发审核"""
        with patch.object(
            supervisor.orchestrator, 'route_and_execute', new_callable=AsyncMock
        ) as mock_orch:
            mock_orch.return_value = AgentResult(
                response="这是回答",
                updated_state={
                    "_router_intent": "POLICY",
                    "_router_next_agent": "policy",
                    "retrieval_result": None,
                },
                confidence=0.9,
                needs_human=False,
            )

            with patch.object(
                supervisor.evaluator, 'evaluate', new_callable=AsyncMock
            ) as mock_eval:
                mock_eval.return_value = {
                    "confidence_score": 0.95,
                    "confidence_signals": {
                        "rag": {"score": 0.95, "reason": "高相似度"},
                        "llm": {"score": 0.9, "reason": "自评估"},
                        "emotion": {"score": 0.85, "reason": "中性"},
                    },
                    "needs_human_transfer": False,
                    "transfer_reason": None,
                    "audit_level": "none",
                }

                result = await supervisor.coordinate({
                    "question": "简单问题",
                    "user_id": 1
                })

                assert result["needs_human_transfer"] is False
                assert result["audit_level"] == "none"

    @pytest.mark.asyncio
    async def test_low_confidence_triggers_transfer(self, supervisor):
        """测试低置信度触发转人工"""
        with patch.object(
            supervisor.orchestrator, 'route_and_execute', new_callable=AsyncMock
        ) as mock_orch:
            mock_orch.return_value = AgentResult(
                response="不确定的回答",
                updated_state={
                    "_router_intent": "POLICY",
                    "_router_next_agent": "policy",
                    "retrieval_result": None,
                },
                needs_human=False,
            )

            with patch.object(
                supervisor.evaluator, 'evaluate', new_callable=AsyncMock
            ) as mock_eval:
                mock_eval.return_value = {
                    "confidence_score": 0.35,
                    "confidence_signals": {
                        "rag": {"score": 0.3, "reason": "低相似度"},
                        "llm": {"score": 0.4, "reason": "不确定"},
                        "emotion": {"score": 0.5, "reason": "中性"},
                    },
                    "needs_human_transfer": True,
                    "transfer_reason": "置信度不足",
                    "audit_level": "manual",
                }

                result = await supervisor.coordinate({
                    "question": "复杂问题",
                    "user_id": 1
                })

                assert result["needs_human_transfer"] is True
                assert result["audit_level"] == "manual"

    @pytest.mark.asyncio
    async def test_router_direct_response(self, supervisor):
        """测试 Router 直接返回回复（闲聊）"""
        with patch.object(
            supervisor.orchestrator, 'route_and_execute', new_callable=AsyncMock
        ) as mock_orch:
            mock_orch.return_value = AgentResult(
                response="你好！有什么可以帮您？",
                updated_state={"intent": "OTHER"}
            )

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
        with patch.object(
            supervisor.orchestrator, 'route_and_execute', new_callable=AsyncMock
        ) as mock_orch:
            mock_orch.return_value = AgentResult(
                response="订单状态：已发货",
                updated_state={
                    "_router_intent": "ORDER",
                    "_router_next_agent": "order",
                    "order_data": {"order_sn": "SN123"},
                    "retrieval_result": None,
                },
                needs_human=False,
            )

            with patch.object(
                supervisor.evaluator, 'evaluate', new_callable=AsyncMock
            ) as mock_eval:
                mock_eval.return_value = {
                    "confidence_score": 0.85,
                    "confidence_signals": {
                        "rag": {"score": 0.8, "reason": "中等相似度"},
                        "llm": {"score": 0.85, "reason": "自评估"},
                        "emotion": {"score": 0.9, "reason": "正面"},
                    },
                    "needs_human_transfer": False,
                    "transfer_reason": None,
                    "audit_level": "none",
                }

                result = await supervisor.coordinate({
                    "question": "我的订单到哪了？",
                    "user_id": 1
                })

                assert result["answer"] == "订单状态：已发货"
                assert result["intent"] == "ORDER"
                assert result["order_data"]["order_sn"] == "SN123"

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
        with patch.object(
            supervisor.orchestrator, 'route_and_execute', new_callable=AsyncMock
        ) as mock_orch:
            mock_orch.return_value = AgentResult(
                response="抱歉，我暂时无法处理这个问题。如需帮助，请联系人工客服。",
                updated_state={
                    "_router_intent": "UNKNOWN",
                    "_router_next_agent": "unknown_agent",
                }
            )

            with patch.object(
                supervisor.evaluator, 'evaluate', new_callable=AsyncMock
            ) as mock_eval:
                mock_eval.return_value = {
                    "confidence_score": 0.5,
                    "confidence_signals": {},
                    "needs_human_transfer": False,
                    "transfer_reason": None,
                    "audit_level": "auto",
                }

                result = await supervisor.coordinate({
                    "question": "未知问题",
                    "user_id": 1
                })

                assert "人工客服" in result["answer"]

    @pytest.mark.asyncio
    async def test_specialist_requests_human_transfer(self, supervisor):
        """测试 Specialist 主动请求人工接管"""
        with patch.object(
            supervisor.orchestrator, 'route_and_execute', new_callable=AsyncMock
        ) as mock_orch:
            mock_orch.return_value = AgentResult(
                response="这个问题需要人工处理",
                updated_state={
                    "_router_intent": "POLICY",
                    "_router_next_agent": "policy",
                },
                confidence=0.3,
                needs_human=True,
                transfer_reason="policy_edge_case",
            )

            result = await supervisor.coordinate({
                "question": "特殊问题",
                "user_id": 1
            })

            assert result["needs_human_transfer"] is True
            assert result["transfer_reason"] == "policy_edge_case"
            assert result["audit_level"] == "manual"

    @pytest.mark.asyncio
    async def test_orchestrator_empty_state_error(self, supervisor):
        """测试 orchestrator 返回空路由状态错误"""
        with patch.object(
            supervisor.orchestrator, 'route_and_execute', new_callable=AsyncMock
        ) as mock_orch:
            mock_orch.return_value = AgentResult(
                response="系统内部错误，请稍后重试。",
                updated_state={
                    "_error": True,
                    "_error_reason": "empty_router_state",
                    "intent": None,
                }
            )

            result = await supervisor.coordinate({
                "question": "任何问题",
                "user_id": 1
            })

            assert result["needs_human_transfer"] is True
            assert result["transfer_reason"] == "系统内部错误"

    @pytest.mark.asyncio
    async def test_orchestrator_no_next_agent_error(self, supervisor):
        """测试 orchestrator 返回无法路由错误"""
        with patch.object(
            supervisor.orchestrator, 'route_and_execute', new_callable=AsyncMock
        ) as mock_orch:
            mock_orch.return_value = AgentResult(
                response="无法确定处理该请求的专业代理，请尝试换一种方式描述您的问题。",
                updated_state={
                    "_error": True,
                    "_error_reason": "no_next_agent",
                    "intent": "UNKNOWN",
                }
            )

            result = await supervisor.coordinate({
                "question": "模糊问题",
                "user_id": 1
            })

            assert result["needs_human_transfer"] is True
            assert result["transfer_reason"] == "无法路由到合适的代理"
