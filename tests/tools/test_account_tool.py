import pytest

from app.models.state import make_agent_state
from app.models.user import User
from app.tools.account_tool import AccountTool, _MEMBERSHIP_LEVELS
from app.tools.base import ToolResult


@pytest.fixture
def account_tool():
    return AccountTool()


@pytest.mark.asyncio(loop_scope="session")
async def test_execute_returns_account_data(account_tool, db_session):
    user = User(
        username="test_user",
        password_hash="hashed_password",
        email="test@example.com",
        full_name="Test User",
        phone="13800138000",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    assert user.id is not None

    state = make_agent_state(question="查询我的账户", user_id=user.id)
    result = await account_tool.execute(state, session=db_session)

    expected_level = _MEMBERSHIP_LEVELS[user.id % len(_MEMBERSHIP_LEVELS)]
    expected_balance = round(128.50 + (user.id * 10.25), 2)
    expected_coupons = 2 if user.id % 2 == 0 else 1

    assert isinstance(result, ToolResult)
    assert result.output["username"] == "test_user"
    assert result.output["email"] == "test@example.com"
    assert result.output["full_name"] == "Test User"
    assert result.output["phone"] == "13800138000"
    assert result.output["membership_level"] == expected_level
    assert result.output["account_balance"] == expected_balance
    assert len(result.output["coupons"]) == expected_coupons
    assert result.source == "account_tool"


@pytest.mark.asyncio(loop_scope="session")
async def test_execute_user_not_found(account_tool, db_session):
    state = make_agent_state(question="查询账户", user_id=999999)
    result = await account_tool.execute(state, session=db_session)

    assert isinstance(result, ToolResult)
    assert "error" in result.output
    assert "未找到用户" in result.output["error"]


@pytest.mark.asyncio(loop_scope="session")
async def test_execute_missing_user_id(account_tool, db_session):
    state = {"question": "查询账户", "user_id": None}  # type: ignore[assignment]
    result = await account_tool.execute(state, session=db_session)

    assert isinstance(result, ToolResult)
    assert "error" in result.output
    assert "无法识别用户身份" in result.output["error"]


@pytest.mark.asyncio(loop_scope="session")
async def test_membership_level_deterministic(account_tool, db_session):
    user = User(
        username="test_user_4",
        password_hash="hashed_password",
        email="test4@example.com",
        full_name="Test User 4",
        phone="13800138004",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    assert user.id is not None

    expected_level = _MEMBERSHIP_LEVELS[user.id % len(_MEMBERSHIP_LEVELS)]

    state = make_agent_state(question="查询账户", user_id=user.id)
    result = await account_tool.execute(state, session=db_session)

    assert result.output["membership_level"] == expected_level
