from decimal import Decimal

import pytest

from app.models.order import Order
from app.models.state import make_agent_state
from app.models.user import User
from app.tools.logistics_tool import LogisticsTool


@pytest.fixture
def logistics_tool():
    return LogisticsTool()


@pytest.mark.asyncio(loop_scope="session")
async def test_logistics_tool_found(logistics_tool, db_session):
    user = User(
        username="logistics_user",
        password_hash="hashed_password",
        email="logistics@example.com",
        full_name="Logistics User",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    assert user.id is not None

    order = Order(
        order_sn="SN20240001",
        user_id=user.id,
        total_amount=Decimal("100.0"),
        shipping_address="Beijing",
        tracking_number="SF1234567890",
    )
    db_session.add(order)
    await db_session.flush()

    state = make_agent_state(
        question="查询物流",
        user_id=user.id,
        slots={"order_sn": "SN20240001"},
    )
    result = await logistics_tool.execute(state, session=db_session)

    assert result.output["tracking_number"] == "SF1234567890"
    assert result.output["carrier"] == "顺丰速运"
    assert result.output["status"] == "运输中"
    assert result.output["latest_update"] == "快件已到达【北京顺义集散中心】"
    assert result.output["estimated_delivery"] == "2024-01-20"


@pytest.mark.asyncio(loop_scope="session")
async def test_logistics_tool_not_found(logistics_tool, db_session):
    user = User(
        username="logistics_user2",
        password_hash="hashed_password",
        email="logistics2@example.com",
        full_name="Logistics User 2",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    assert user.id is not None

    state = make_agent_state(
        question="查询物流",
        user_id=user.id,
        slots={"order_sn": "SN99999999"},
    )
    result = await logistics_tool.execute(state, session=db_session)

    assert result.output["status"] == "未找到订单"


@pytest.mark.asyncio(loop_scope="session")
async def test_logistics_tool_uses_kwargs_when_slots_empty(logistics_tool, db_session):
    user = User(
        username="logistics_user3",
        password_hash="hashed_password",
        email="logistics3@example.com",
        full_name="Logistics User 3",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    assert user.id is not None

    order = Order(
        order_sn="SN20240002",
        user_id=user.id,
        total_amount=Decimal("200.0"),
        shipping_address="Shanghai",
        tracking_number=None,
    )
    db_session.add(order)
    await db_session.flush()

    state = make_agent_state(question="查询物流", user_id=user.id)
    result = await logistics_tool.execute(state, session=db_session, order_sn="SN20240002")

    assert result.output["tracking_number"] == "暂无"
    assert result.output["status"] == "运输中"
