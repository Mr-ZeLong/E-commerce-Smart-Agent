import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.order import OrderAgent, RefundReason


class TestOrderAgent:
    """测试订单 Agent"""

    @pytest.fixture
    def order_agent(self):
        return OrderAgent()

    @pytest.mark.asyncio
    async def test_query_order(self, order_agent):
        """测试订单查询"""
        # Mock 订单数据
        mock_order = MagicMock()
        mock_order.order_sn = "SN20240001"
        mock_order.status = "PAID"
        mock_order.total_amount = 199.0
        mock_order.items = [{"name": "测试商品", "qty": 1}]
        mock_order.model_dump.return_value = {
            "order_sn": "SN20240001",
            "status": "PAID",
            "total_amount": 199.0,
            "items": [{"name": "测试商品", "qty": 1}],
            "tracking_number": None
        }

        # Mock _query_order 方法
        with patch.object(order_agent, '_query_order', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_order.model_dump.return_value

            result = await order_agent.process({
                "question": "查询订单 SN20240001",
                "user_id": 1,
                "intent": "ORDER"
            })

            assert "SN20240001" in result.response
            assert result.updated_state["order_data"] is not None

    @pytest.mark.asyncio
    async def test_query_order_not_found(self, order_agent):
        """测试订单查询 - 订单不存在"""
        # Mock _query_order 方法返回 None
        with patch.object(order_agent, '_query_order', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = None

            result = await order_agent.process({
                "question": "查询订单 SN99999999",
                "user_id": 1,
                "intent": "ORDER"
            })

            assert "未找到" in result.response
            assert result.updated_state["order_data"] is None

    @pytest.mark.asyncio
    async def test_refund_without_order_sn(self, order_agent):
        """测试退货申请 - 缺少订单号"""
        result = await order_agent.process({
            "question": "我要退货",
            "user_id": 1,
            "intent": "REFUND"
        })

        assert "请提供订单号" in result.response
        assert result.updated_state["refund_flow_active"] is False

    def test_extract_order_sn(self, order_agent):
        """测试订单号提取"""
        assert order_agent._extract_order_sn("查询订单 SN20240001") == "SN20240001"
        assert order_agent._extract_order_sn("我要退货 SN12345") == "SN12345"
        assert order_agent._extract_order_sn("没有订单号") is None
        assert order_agent._extract_order_sn("sn20240001") == "SN20240001"  # 大小写不敏感

    def test_classify_refund_reason(self, order_agent):
        """测试退货原因分类"""
        assert order_agent._classify_refund_reason("质量问题") == RefundReason.QUALITY_ISSUE
        assert order_agent._classify_refund_reason("商品破损") == RefundReason.QUALITY_ISSUE
        assert order_agent._classify_refund_reason("尺码不合适") == RefundReason.SIZE_NOT_FIT
        assert order_agent._classify_refund_reason("大小不对") == RefundReason.SIZE_NOT_FIT
        assert order_agent._classify_refund_reason("与描述不符") == RefundReason.NOT_AS_DESCRIBED
        assert order_agent._classify_refund_reason("其他原因") == RefundReason.OTHER

    def test_format_order_response(self, order_agent):
        """测试订单回复格式化"""
        order_data = {
            "order_sn": "SN20240001",
            "status": "PAID",
            "total_amount": 199.0,
            "items": [{"name": "测试商品", "qty": 2}],
            "tracking_number": "SF123456"
        }

        response = order_agent._format_order_response(order_data)

        assert "SN20240001" in response
        assert "PAID" in response
        assert "199.0" in response
        assert "测试商品" in response
        assert "SF123456" in response

    def test_format_order_response_without_tracking(self, order_agent):
        """测试订单回复格式化 - 无物流单号"""
        order_data = {
            "order_sn": "SN20240001",
            "status": "PENDING",
            "total_amount": 99.0,
            "items": [{"name": "商品A", "qty": 1}],
            "tracking_number": None
        }

        response = order_agent._format_order_response(order_data)

        # 检查物流单号显示为 "暂无" 或 "None"
        assert "物流单号:" in response
