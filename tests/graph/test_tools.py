from unittest.mock import AsyncMock, patch

import pytest

from app.graph.tools import (
    check_refund_eligibility,
    query_refund_status,
    refund_tools,
    submit_refund_application,
)


@pytest.mark.asyncio
async def test_check_refund_eligibility_delegates_to_service():
    with patch("app.graph.tools._check_refund_eligibility", new_callable=AsyncMock) as mock_service:
        mock_service.return_value = "eligible"
        result = await check_refund_eligibility.ainvoke({"order_sn": "SN001", "user_id": 42})
        mock_service.assert_awaited_once_with("SN001", 42)
        assert result == "eligible"


@pytest.mark.asyncio
async def test_submit_refund_application_delegates_to_service():
    with patch(
        "app.graph.tools._submit_refund_application", new_callable=AsyncMock
    ) as mock_service:
        mock_service.return_value = "submitted"
        result = await submit_refund_application.ainvoke(
            {
                "order_sn": "SN002",
                "user_id": 7,
                "reason_detail": "reason",
                "reason_category": "QUALITY_ISSUE",
            }
        )
        mock_service.assert_awaited_once_with("SN002", 7, "reason", "QUALITY_ISSUE")
        assert result == "submitted"


@pytest.mark.asyncio
async def test_query_refund_status_delegates_to_service():
    with patch("app.graph.tools._query_refund_status", new_callable=AsyncMock) as mock_service:
        mock_service.return_value = "status"
        result = await query_refund_status.ainvoke({"user_id": 99, "refund_id": 5})
        mock_service.assert_awaited_once_with(99, 5)
        assert result == "status"


def test_refund_tools_contains_all_tools():
    assert len(refund_tools) == 3
    assert check_refund_eligibility in refund_tools
    assert submit_refund_application in refund_tools
    assert query_refund_status in refund_tools
