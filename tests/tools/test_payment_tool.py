from datetime import datetime
from decimal import Decimal

import pytest

from app.models.order import Order, OrderStatus
from app.models.refund import RefundApplication, RefundStatus
from app.models.state import make_agent_state
from app.models.user import User
from app.tools.payment_tool import PaymentTool


@pytest.fixture
def payment_tool():
    return PaymentTool()


@pytest.mark.asyncio(loop_scope="session")
async def test_payment_tool_with_order_sn(payment_tool, db_session):
    user = User(
        username="payment_user",
        password_hash="hashed_password",
        email="payment@example.com",
        full_name="Payment User",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    assert user.id is not None

    order = Order(
        order_sn="SN20240001",
        user_id=user.id,
        status=OrderStatus.PAID,
        total_amount=Decimal("199.0"),
        shipping_address="Test Address",
    )
    db_session.add(order)
    await db_session.flush()
    await db_session.refresh(order)
    assert order.id is not None

    refund = RefundApplication(
        order_id=order.id,
        user_id=user.id,
        refund_amount=Decimal("199.0"),
        status=RefundStatus.PENDING,
        reason_detail="Test refund reason",
        created_at=datetime(2024, 1, 1, 12, 0, 0),
    )
    db_session.add(refund)
    await db_session.flush()
    await db_session.refresh(refund)
    assert refund.id is not None

    state = make_agent_state(
        question="查询支付状态 SN20240001",
        user_id=user.id,
        slots={"order_sn": "SN20240001"},
    )
    result = await payment_tool.execute(state, session=db_session)

    assert result.output["payment_status"] == "已支付"
    assert result.output["invoice_status"] == "已开票"
    assert len(result.output["refund_records"]) == 1
    assert result.output["refund_records"][0]["refund_id"] == refund.id
    assert result.output["refund_records"][0]["amount"] == 199.0
    assert result.output["refund_records"][0]["status"] == "PENDING"


@pytest.mark.asyncio(loop_scope="session")
async def test_payment_tool_without_order_sn(payment_tool, db_session):
    user = User(
        username="payment_user2",
        password_hash="hashed_password",
        email="payment2@example.com",
        full_name="Payment User 2",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    assert user.id is not None

    order = Order(
        order_sn="SN20240002",
        user_id=user.id,
        status=OrderStatus.PAID,
        total_amount=Decimal("99.0"),
        shipping_address="Test Address 2",
    )
    db_session.add(order)
    await db_session.flush()
    await db_session.refresh(order)
    assert order.id is not None

    refund = RefundApplication(
        order_id=order.id,
        user_id=user.id,
        refund_amount=Decimal("99.0"),
        status=RefundStatus.APPROVED,
        reason_detail="Test refund reason 2",
        created_at=datetime(2024, 1, 2, 12, 0, 0),
    )
    db_session.add(refund)
    await db_session.flush()
    await db_session.refresh(refund)
    assert refund.id is not None

    state = make_agent_state(
        question="查询我的退款记录",
        user_id=user.id,
    )
    result = await payment_tool.execute(state, session=db_session)

    assert result.output["payment_status"] == "未知"
    assert result.output["invoice_status"] == "未查询到发票信息"
    assert len(result.output["refund_records"]) == 1
    assert result.output["refund_records"][0]["refund_id"] == refund.id
    assert result.output["refund_records"][0]["amount"] == 99.0
    assert result.output["refund_records"][0]["status"] == "APPROVED"


@pytest.mark.asyncio(loop_scope="session")
async def test_payment_tool_no_records(payment_tool, db_session):
    user = User(
        username="payment_user3",
        password_hash="hashed_password",
        email="payment3@example.com",
        full_name="Payment User 3",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    assert user.id is not None

    state = make_agent_state(
        question="查询支付状态 SN99999999",
        user_id=user.id,
        slots={"order_sn": "SN99999999"},
    )
    result = await payment_tool.execute(state, session=db_session)

    assert result.output["payment_status"] == "未知"
    assert result.output["invoice_status"] == "未查询到发票信息"
    assert result.output["refund_records"] == []
    assert result.output["message"] == "未查询到相关支付/退款记录"
