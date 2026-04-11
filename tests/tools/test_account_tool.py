from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.state import make_agent_state
from app.tools.account_tool import AccountTool
from app.tools.base import ToolResult


@pytest.fixture
def account_tool():
    return AccountTool()


def _mock_user(user_id: int = 1):
    user = MagicMock()
    user.id = user_id
    user.username = "test_user"
    user.email = "test@example.com"
    user.full_name = "Test User"
    user.phone = "13800138000"
    user.created_at = datetime.now(UTC)
    return user


def _make_mock_session(user=None):
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = user

    mock_session = AsyncMock()
    mock_session.exec.return_value = mock_result

    return mock_session


@pytest.mark.asyncio
async def test_execute_returns_account_data(account_tool):
    user = _mock_user(user_id=2)
    mock_session = _make_mock_session(user)

    with patch("app.tools.account_tool.async_session_maker") as mock_maker:
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        state = make_agent_state(question="查询我的账户", user_id=2)
        result = await account_tool.execute(state)

        assert isinstance(result, ToolResult)
        assert result.output["username"] == "test_user"
        assert result.output["email"] == "test@example.com"
        assert result.output["full_name"] == "Test User"
        assert result.output["phone"] == "13800138000"
        assert result.output["membership_level"] == "金卡"
        assert result.output["account_balance"] == 149.00
        assert len(result.output["coupons"]) == 2
        assert result.source == "account_tool"


@pytest.mark.asyncio
async def test_execute_user_not_found(account_tool):
    mock_session = _make_mock_session(user=None)

    with patch("app.tools.account_tool.async_session_maker") as mock_maker:
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        state = make_agent_state(question="查询账户", user_id=999)
        result = await account_tool.execute(state)

        assert isinstance(result, ToolResult)
        assert "error" in result.output
        assert "未找到用户" in result.output["error"]


@pytest.mark.asyncio
async def test_execute_missing_user_id(account_tool):
    state = {"question": "查询账户", "user_id": None}  # type: ignore[assignment]
    result = await account_tool.execute(state)

    assert isinstance(result, ToolResult)
    assert "error" in result.output
    assert "无法识别用户身份" in result.output["error"]


@pytest.mark.asyncio
async def test_membership_level_deterministic(account_tool):
    user = _mock_user(user_id=4)
    mock_session = _make_mock_session(user)

    with patch("app.tools.account_tool.async_session_maker") as mock_maker:
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        state = make_agent_state(question="查询账户", user_id=4)
        result = await account_tool.execute(state)

        assert result.output["membership_level"] == "普通会员"
