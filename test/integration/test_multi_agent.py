"""
多 Agent 集成测试

测试 SupervisorAgent 协调多个 Specialist Agent 的完整流程，
包括意图路由、Agent 协作和结果整合。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.base import AgentResult
from app.agents.router import Intent, RouterAgent
from app.agents.supervisor import SupervisorAgent
from app.models.state import RetrievalResult


class TestMultiAgentCoordination:
    """测试多 Agent 协作完整流程"""

    @pytest.fixture
    def supervisor(self):
        """创建 SupervisorAgent 实例"""
        return SupervisorAgent()

    @pytest.mark.asyncio
    async def test_order_query_flow(self, supervisor):
        """
        测试订单查询完整流程

        场景：用户查询订单状态
        预期流程：
        1. RouterAgent 识别 ORDER 意图
        2. Supervisor 路由到 OrderAgent
        3. OrderAgent 查询订单信息
        4. 置信度评估通过
        5. 返回订单状态
        """
        # Mock RouterAgent
        with patch.object(
            supervisor.router, "process", new_callable=AsyncMock
        ) as mock_router:
            mock_router.return_value = AgentResult(
                response="",
                updated_state={
                    "intent": Intent.ORDER,
                    "next_agent": "order",
                },
            )

            # Mock OrderAgent
            with patch.object(
                supervisor.order_agent, "process", new_callable=AsyncMock
            ) as mock_order:
                mock_order.return_value = AgentResult(
                    response="订单状态：已发货，物流单号 SF1234567890",
                    updated_state={
                        "order_data": {
                            "order_sn": "SN20240001",
                            "status": "SHIPPED",
                            "tracking_number": "SF1234567890",
                        },
                    },
                )

                # Mock ConfidenceSignals - patch where it's used (in supervisor module)
                with patch(
                    "app.confidence.signals.ConfidenceSignals"
                ) as mock_signals_class:
                    mock_signals = mock_signals_class.return_value
                    mock_signals.calculate_all = AsyncMock(
                        return_value={
                            "rag": MagicMock(
                                score=0.8, reason="订单数据匹配", metadata={}
                            ),
                            "llm": MagicMock(
                                score=0.85, reason="回答准确", metadata={}
                            ),
                            "emotion": MagicMock(
                                score=0.9, reason="中性情绪", metadata={}
                            ),
                        }
                    )

                    # 执行测试
                    result = await supervisor.coordinate(
                        {"question": "我的订单到哪了？", "user_id": 1}
                    )

                    # 验证结果
                    assert result["answer"] == "订单状态：已发货，物流单号 SF1234567890"
                    assert result["intent"] == Intent.ORDER
                    assert result["confidence_score"] == pytest.approx(0.845, 0.01)
                    assert result["needs_human_transfer"] is False
                    assert result["audit_level"] == "none"

                    # 验证调用链
                    mock_router.assert_called_once()
                    mock_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_policy_query_flow(self, supervisor):
        """
        测试政策查询完整流程

        场景：用户咨询运费政策
        预期流程：
        1. RouterAgent 识别 POLICY 意图
        2. Supervisor 路由到 PolicyAgent
        3. PolicyAgent 执行 RAG 检索
        4. 生成政策回复
        5. 置信度评估通过
        """
        with patch.object(
            supervisor.router, "process", new_callable=AsyncMock
        ) as mock_router:
            mock_router.return_value = AgentResult(
                response="",
                updated_state={
                    "intent": Intent.POLICY,
                    "next_agent": "policy",
                },
            )

            with patch.object(
                supervisor.policy_agent, "process", new_callable=AsyncMock
            ) as mock_policy:
                # 模拟 RAG 检索结果
                retrieval_result = RetrievalResult(
                    chunks=["满100元免运费", "不满100元收取6元运费"],
                    similarities=[0.95, 0.88],
                    sources=["shipping_policy.md"],
                )

                mock_policy.return_value = AgentResult(
                    response="满100元免运费，不满100元收取6元运费",
                    updated_state={
                        "retrieval_result": retrieval_result,
                        "context": retrieval_result.chunks,
                        "answer": "满100元免运费，不满100元收取6元运费",
                    },
                    confidence=0.9,
                )

                with patch(
                    "app.confidence.signals.ConfidenceSignals"
                ) as mock_signals_class:
                    mock_signals = mock_signals_class.return_value
                    mock_signals.calculate_all = AsyncMock(
                        return_value={
                            "rag": MagicMock(
                                score=0.95, reason="高相似度匹配", metadata={}
                            ),
                            "llm": MagicMock(
                                score=0.9, reason="回答完整", metadata={}
                            ),
                            "emotion": MagicMock(
                                score=0.85, reason="中性情绪", metadata={}
                            ),
                        }
                    )

                    result = await supervisor.coordinate(
                        {"question": "运费怎么算？", "user_id": 1}
                    )

                    assert "满100元免运费" in result["answer"]
                    assert result["intent"] == Intent.POLICY
                    assert result["confidence_score"] == pytest.approx(0.905, 0.01)
                    assert result["needs_human_transfer"] is False

                    # 验证置信度信号详情
                    assert "confidence_signals" in result
                    assert result["confidence_signals"]["rag"]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_refund_application_flow(self, supervisor):
        """
        测试退货申请完整流程

        场景：用户申请退货
        预期流程：
        1. RouterAgent 识别 REFUND 意图
        2. Supervisor 路由到 OrderAgent
        3. OrderAgent 检查退货资格
        4. 创建退货申请
        5. 返回申请结果
        """
        with patch.object(
            supervisor.router, "process", new_callable=AsyncMock
        ) as mock_router:
            mock_router.return_value = AgentResult(
                response="",
                updated_state={
                    "intent": Intent.REFUND,
                    "next_agent": "order",
                },
            )

            with patch.object(
                supervisor.order_agent, "process", new_callable=AsyncMock
            ) as mock_order:
                mock_order.return_value = AgentResult(
                    response="✅ 退货申请已创建，退款金额：¥199.99",
                    updated_state={
                        "order_data": {"order_sn": "SN20240002"},
                        "refund_flow_active": True,
                        "refund_data": {
                            "refund_id": 1,
                            "amount": 199.99,
                        },
                    },
                )

                with patch(
                    "app.confidence.signals.ConfidenceSignals"
                ) as mock_signals_class:
                    mock_signals = mock_signals_class.return_value
                    mock_signals.calculate_all = AsyncMock(
                        return_value={
                            "rag": MagicMock(
                                score=0.85, reason="规则匹配", metadata={}
                            ),
                            "llm": MagicMock(
                                score=0.88, reason="流程完成", metadata={}
                            ),
                            "emotion": MagicMock(
                                score=0.9, reason="中性情绪", metadata={}
                            ),
                        }
                    )

                    result = await supervisor.coordinate(
                        {
                            "question": "我要退货，订单号 SN20240002",
                            "user_id": 1,
                        }
                    )

                    assert "✅ 退货申请已创建" in result["answer"]
                    assert result["intent"] == Intent.REFUND
                    assert result["refund_flow_active"] is True
                    assert result["confidence_score"] == pytest.approx(0.8695, 0.01)

    @pytest.mark.asyncio
    async def test_greeting_direct_response(self, supervisor):
        """
        测试问候语直接回复

        场景：用户打招呼
        预期流程：
        1. RouterAgent 识别 OTHER 意图
        2. Router 直接返回问候回复
        3. Supervisor 直接返回结果（不调用 Specialist）
        """
        with patch.object(
            supervisor.router, "process", new_callable=AsyncMock
        ) as mock_router:
            mock_router.return_value = AgentResult(
                response="您好！我是您的智能客服助手",
                updated_state={
                    "intent": Intent.OTHER,
                    "next_agent": "supervisor",
                },
            )

            result = await supervisor.coordinate(
                {"question": "你好", "user_id": 1}
            )

            assert "您好" in result["answer"]
            assert result["intent"] == Intent.OTHER
            assert result["confidence_score"] == 1.0
            assert result["needs_human_transfer"] is False

    @pytest.mark.asyncio
    async def test_agent_error_handling(self, supervisor):
        """
        测试 Agent 错误处理

        场景：OrderAgent 抛出异常
        预期：Supervisor 捕获异常并返回友好错误信息
        """
        with patch.object(
            supervisor.router, "process", new_callable=AsyncMock
        ) as mock_router:
            mock_router.return_value = AgentResult(
                response="",
                updated_state={
                    "intent": Intent.ORDER,
                    "next_agent": "order",
                },
            )

            with patch.object(
                supervisor.order_agent, "process", new_callable=AsyncMock
            ) as mock_order:
                # 模拟异常
                mock_order.side_effect = Exception("数据库连接失败")

                result = await supervisor.coordinate(
                    {"question": "查询订单", "user_id": 1}
                )

                assert "抱歉" in result["answer"]
                assert result["intent"] == "ERROR"
                assert result["needs_human_transfer"] is True
                assert "system_error" in result["transfer_reason"]

    @pytest.mark.asyncio
    async def test_unknown_agent_fallback(self, supervisor):
        """
        测试未知 Agent 回退

        场景：Router 返回未知的 next_agent
        预期：返回友好提示，建议联系人工客服
        """
        with patch.object(
            supervisor.router, "process", new_callable=AsyncMock
        ) as mock_router:
            mock_router.return_value = AgentResult(
                response="",
                updated_state={
                    "intent": "UNKNOWN",
                    "next_agent": "unknown_agent",
                },
            )

            result = await supervisor.coordinate(
                {"question": "未知问题", "user_id": 1}
            )

            assert "人工客服" in result["answer"]


class TestIntentRouting:
    """测试意图路由正确性"""

    @pytest.fixture
    def router(self):
        """创建 RouterAgent 实例"""
        return RouterAgent()

    @pytest.mark.asyncio
    async def test_route_order_intent(self, router):
        """测试 ORDER 意图路由"""
        result = await router.process(
            {"question": "我的订单 SN12345 到哪了？", "user_id": 1}
        )

        assert result.updated_state["intent"] == Intent.ORDER
        assert result.updated_state["next_agent"] == "order"
        assert result.response == ""  # 不直接回复

    @pytest.mark.asyncio
    async def test_route_policy_intent(self, router):
        """测试 POLICY 意图路由"""
        result = await router.process(
            {"question": "运费怎么计算？", "user_id": 1}
        )

        assert result.updated_state["intent"] == Intent.POLICY
        assert result.updated_state["next_agent"] == "policy"

    @pytest.mark.asyncio
    async def test_route_refund_intent(self, router):
        """测试 REFUND 意图路由"""
        result = await router.process(
            {"question": "我要退货退款", "user_id": 1}
        )

        assert result.updated_state["intent"] == Intent.REFUND
        assert result.updated_state["next_agent"] == "order"

    @pytest.mark.asyncio
    async def test_route_other_intent(self, router):
        """测试 OTHER 意图路由（闲聊）"""
        result = await router.process({"question": "你好", "user_id": 1})

        assert result.updated_state["intent"] == Intent.OTHER
        assert result.updated_state["next_agent"] == "supervisor"
        assert result.response != ""  # 直接返回问候回复

    @pytest.mark.asyncio
    async def test_quick_intent_check_order(self, router):
        """测试快速意图检查 - 订单关键词"""
        # 使用快速规则匹配，不调用 LLM
        intent = router._quick_intent_check("我的订单到哪了？")

        assert intent == Intent.ORDER

    @pytest.mark.asyncio
    async def test_quick_intent_check_refund(self, router):
        """测试快速意图检查 - 退货关键词"""
        intent = router._quick_intent_check("我要退货退款")

        assert intent == Intent.REFUND

    @pytest.mark.asyncio
    async def test_quick_intent_check_greeting(self, router):
        """测试快速意图检查 - 问候语"""
        intent = router._quick_intent_check("你好")

        assert intent == Intent.OTHER


class TestAgentResultIntegration:
    """测试 Agent 结果集成"""

    @pytest.mark.asyncio
    async def test_process_interface_compliance(self):
        """
        测试 process 接口符合 BaseAgent 规范

        验证 SupervisorAgent 的 process 方法返回 AgentResult
        """
        supervisor = SupervisorAgent()

        with patch.object(
            supervisor, "coordinate", new_callable=AsyncMock
        ) as mock_coordinate:
            mock_coordinate.return_value = {
                "answer": "测试回答",
                "confidence_score": 0.9,
                "needs_human_transfer": False,
            }

            result = await supervisor.process(
                {"question": "测试问题", "user_id": 1}
            )

            assert isinstance(result, AgentResult)
            assert result.response == "测试回答"
            assert result.updated_state is not None
            assert result.updated_state["confidence_score"] == 0.9

    @pytest.mark.asyncio
    async def test_state_propagation(self):
        """
        测试状态在 Agent 间的传递

        验证 Router 识别的意图正确传递给 Specialist Agent
        """
        supervisor = SupervisorAgent()

        initial_state = {
            "question": "查询订单",
            "user_id": 1,
            "history": [{"role": "user", "content": "之前的问题"}],
        }

        with patch.object(
            supervisor.router, "process", new_callable=AsyncMock
        ) as mock_router:
            mock_router.return_value = AgentResult(
                response="",
                updated_state={
                    "intent": Intent.ORDER,
                    "next_agent": "order",
                },
            )

            with patch.object(
                supervisor.order_agent, "process", new_callable=AsyncMock
            ) as mock_order:
                mock_order.return_value = AgentResult(
                    response="订单信息",
                    updated_state={},
                )

                with patch(
                    "app.confidence.signals.ConfidenceSignals"
                ) as mock_signals_class:
                    mock_signals = mock_signals_class.return_value
                    mock_signals.calculate_all = AsyncMock(
                        return_value={
                            "rag": MagicMock(score=0.8, reason="", metadata={}),
                            "llm": MagicMock(score=0.8, reason="", metadata={}),
                            "emotion": MagicMock(score=0.8, reason="", metadata={}),
                        }
                    )

                    await supervisor.coordinate(initial_state)

                    # 验证 Router 接收原始状态
                    mock_router.assert_called_once_with(initial_state)

                    # 验证 OrderAgent 接收合并后的状态
                    call_args = mock_order.call_args[0][0]
                    assert call_args["intent"] == Intent.ORDER
                    assert call_args["next_agent"] == "order"
                    assert call_args["question"] == "查询订单"
