import pytest

from app.agents.router import RouterAgent, Intent


class TestRouterAgent:
    """测试路由 Agent"""

    @pytest.fixture
    def router(self):
        return RouterAgent()

    @pytest.mark.asyncio
    async def test_route_policy_question(self, router):
        """测试政策问题路由"""
        result = await router.process({
            "question": "运费怎么算？",
            "user_id": 1
        })

        assert result.updated_state["intent"] == Intent.POLICY
        assert result.updated_state["next_agent"] == "policy"

    @pytest.mark.asyncio
    async def test_route_order_question(self, router):
        """测试订单查询路由"""
        result = await router.process({
            "question": "我的订单到哪了？",
            "user_id": 1
        })

        assert result.updated_state["intent"] == Intent.ORDER
        assert result.updated_state["next_agent"] == "order"

    @pytest.mark.asyncio
    async def test_route_refund_question(self, router):
        """测试退货问题路由"""
        result = await router.process({
            "question": "我要退货，订单号 SN12345",
            "user_id": 1
        })

        assert result.updated_state["intent"] == Intent.REFUND
        assert result.updated_state["next_agent"] == "order"  # 退货也走 order agent

    @pytest.mark.asyncio
    async def test_route_greeting(self, router):
        """测试问候语路由"""
        result = await router.process({
            "question": "你好",
            "user_id": 1
        })

        assert result.updated_state["intent"] == Intent.OTHER
        assert result.response is not None  # 直接返回问候回复
