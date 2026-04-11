from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.state import make_agent_state
from app.tools.logistics_tool import LogisticsTool


@pytest.fixture
def logistics_tool():
    return LogisticsTool()


@pytest.mark.asyncio
async def test_logistics_tool_found(logistics_tool):
    mock_order = MagicMock()
    mock_order.tracking_number = "SF1234567890"

    mock_result = MagicMock()
    mock_result.one_or_none.return_value = mock_order

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.exec = AsyncMock(return_value=mock_result)

    with patch(
        "app.tools.logistics_tool.async_session_maker",
        return_value=mock_session,
    ) as mock_maker:
        state = make_agent_state(question="查询物流", user_id=1, slots={"order_sn": "SN20240001"})
        result = await logistics_tool.execute(state)

    mock_maker.assert_called_once()
    assert result.output["tracking_number"] == "SF1234567890"
    assert result.output["carrier"] == "顺丰速运"
    assert result.output["status"] == "运输中"
    assert result.output["latest_update"] == "快件已到达【北京顺义集散中心】"
    assert result.output["estimated_delivery"] == "2024-01-20"


@pytest.mark.asyncio
async def test_logistics_tool_not_found(logistics_tool):
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.exec = AsyncMock(return_value=mock_result)

    with patch(
        "app.tools.logistics_tool.async_session_maker",
        return_value=mock_session,
    ) as mock_maker:
        state = make_agent_state(question="查询物流", user_id=1, slots={"order_sn": "SN99999999"})
        result = await logistics_tool.execute(state)

    mock_maker.assert_called_once()
    assert result.output["status"] == "未找到订单"


@pytest.mark.asyncio
async def test_logistics_tool_uses_kwargs_when_slots_empty(logistics_tool):
    mock_order = MagicMock()
    mock_order.tracking_number = None

    mock_result = MagicMock()
    mock_result.one_or_none.return_value = mock_order

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.exec = AsyncMock(return_value=mock_result)

    with patch(
        "app.tools.logistics_tool.async_session_maker",
        return_value=mock_session,
    ):
        state = make_agent_state(question="查询物流", user_id=1)
        result = await logistics_tool.execute(state, order_sn="SN20240002")

    assert result.output["tracking_number"] == "暂无"
    assert result.output["status"] == "运输中"
