import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.router import IntentRouterAgent, Intent
from app.intent.models import IntentCategory, IntentAction


class TestIntentRouterAgent:
    """测试意图路由Agent"""

    @pytest.fixture
    def router(self):
        return IntentRouterAgent()

    @pytest.mark.asyncio
    async def test_route_policy_question(self, router):
        """测试政策问题路由"""
        # Mock IntentRecognitionService
        mock_result = MagicMock()
        mock_result.primary_intent = IntentCategory.POLICY
        mock_result.secondary_intent = IntentAction.CONSULT
        mock_result.tertiary_intent = None
        mock_result.confidence = 0.9
        mock_result.slots = {"policy_topic": "运费政策"}
        mock_result.missing_slots = []
        mock_result.needs_clarification = False
        mock_result.to_dict.return_value = {
            "primary_intent": "POLICY",
            "secondary_intent": "CONSULT",
            "confidence": 0.9,
        }

        with patch.object(router.intent_service, 'recognize', new_callable=AsyncMock) as mock_recognize:
            mock_recognize.return_value = mock_result

            result = await router.process({
                "question": "运费怎么算？",
                "user_id": 1,
                "thread_id": "test-thread-1"
            })

            assert result.updated_state["intent"] == Intent.POLICY
            assert result.updated_state["next_agent"] == "policy"

    @pytest.mark.asyncio
    async def test_route_order_question(self, router):
        """测试订单查询路由"""
        mock_result = MagicMock()
        mock_result.primary_intent = IntentCategory.ORDER
        mock_result.secondary_intent = IntentAction.QUERY
        mock_result.tertiary_intent = None
        mock_result.confidence = 0.92
        mock_result.slots = {"order_sn": "SN12345"}
        mock_result.missing_slots = []
        mock_result.needs_clarification = False
        mock_result.to_dict.return_value = {
            "primary_intent": "ORDER",
            "secondary_intent": "QUERY",
            "confidence": 0.92,
        }

        with patch.object(router.intent_service, 'recognize', new_callable=AsyncMock) as mock_recognize:
            mock_recognize.return_value = mock_result

            result = await router.process({
                "question": "我的订单到哪了？",
                "user_id": 1,
                "thread_id": "test-thread-2"
            })

            assert result.updated_state["intent"] == Intent.ORDER
            assert result.updated_state["next_agent"] == "order"

    @pytest.mark.asyncio
    async def test_route_refund_question(self, router):
        """测试退货问题路由"""
        mock_result = MagicMock()
        mock_result.primary_intent = IntentCategory.AFTER_SALES
        mock_result.secondary_intent = IntentAction.APPLY
        mock_result.tertiary_intent = None
        mock_result.confidence = 0.95
        mock_result.slots = {"reason_category": "退货", "order_sn": "SN12345"}
        mock_result.missing_slots = []
        mock_result.needs_clarification = False
        mock_result.to_dict.return_value = {
            "primary_intent": "AFTER_SALES",
            "secondary_intent": "APPLY",
            "confidence": 0.95,
        }

        with patch.object(router.intent_service, 'recognize', new_callable=AsyncMock) as mock_recognize:
            mock_recognize.return_value = mock_result

            result = await router.process({
                "question": "我要退货，订单号 SN12345",
                "user_id": 1,
                "thread_id": "test-thread-3"
            })

            assert result.updated_state["intent"] == Intent.REFUND
            assert result.updated_state["next_agent"] == "order"  # 退货也走 order agent

    @pytest.mark.asyncio
    async def test_route_greeting(self, router):
        """测试问候语路由"""
        mock_result = MagicMock()
        mock_result.primary_intent = IntentCategory.OTHER
        mock_result.secondary_intent = IntentAction.CONSULT
        mock_result.tertiary_intent = None
        mock_result.confidence = 0.85
        mock_result.slots = {}
        mock_result.missing_slots = []
        mock_result.needs_clarification = False
        mock_result.to_dict.return_value = {
            "primary_intent": "OTHER",
            "secondary_intent": "CONSULT",
            "confidence": 0.85,
        }

        with patch.object(router.intent_service, 'recognize', new_callable=AsyncMock) as mock_recognize:
            mock_recognize.return_value = mock_result

            result = await router.process({
                "question": "你好",
                "user_id": 1,
                "thread_id": "test-thread-4"
            })

            assert result.updated_state["intent"] == Intent.OTHER
            assert result.response is not None  # 直接返回问候回复
            assert "您好" in result.response

    @pytest.mark.asyncio
    async def test_clarification_needed(self, router):
        """测试需要澄清的情况"""
        mock_result = MagicMock()
        mock_result.primary_intent = IntentCategory.ORDER
        mock_result.secondary_intent = IntentAction.QUERY
        mock_result.tertiary_intent = None
        mock_result.confidence = 0.7
        mock_result.slots = {}
        mock_result.missing_slots = ["order_sn"]
        mock_result.needs_clarification = True
        mock_result.to_dict.return_value = {
            "primary_intent": "ORDER",
            "secondary_intent": "QUERY",
            "confidence": 0.7,
        }

        mock_clarification = MagicMock()
        mock_clarification.response = "请提供您的订单号"
        mock_clarification.state = {"clarification_round": 1}

        with patch.object(router.intent_service, 'recognize', new_callable=AsyncMock) as mock_recognize:
            mock_recognize.return_value = mock_result

            with patch.object(router.intent_service, 'clarify', new_callable=AsyncMock) as mock_clarify:
                mock_clarify.return_value = mock_clarification

                result = await router.process({
                    "question": "我的订单在哪？",
                    "user_id": 1,
                    "thread_id": "test-thread-5"
                })

                assert result.updated_state["awaiting_clarification"] is True
                assert "请提供您的订单号" in result.response
