from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.order import Order, OrderStatus
from app.models.user import User
from app.services.order_service import OrderService


@pytest.fixture
def order_service() -> OrderService:
    return OrderService()


async def _create_test_user(session, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@test.com",
        full_name="Test User",
        password_hash=User.hash_password("testpass"),
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _create_test_order(
    session,
    user_id: int,
    order_sn: str,
    status: OrderStatus = OrderStatus.DELIVERED,
    total_amount: Decimal = Decimal("199.0"),
    created_at: datetime | None = None,
    items: list | None = None,
) -> Order:
    order = Order(
        order_sn=order_sn,
        user_id=user_id,
        status=status,
        total_amount=total_amount,
        shipping_address="Test Address",
        created_at=created_at or datetime.now(UTC),
        items=items if items is not None else [],
    )
    session.add(order)
    await session.flush()
    await session.refresh(order)
    return order


@pytest.mark.asyncio
async def test_get_order_for_user_with_order_sn(order_service: OrderService, db_session):
    """通过订单号查询订单"""
    user = await _create_test_user(db_session, "order_user_sn")
    assert user.id is not None
    await _create_test_order(db_session, user.id, "SN20240001", status=OrderStatus.SHIPPED)

    result = await order_service.get_order_for_user("SN20240001", user.id, session=db_session)

    assert result is not None
    assert result["order_sn"] == "SN20240001"
    assert result["status"] == OrderStatus.SHIPPED
    assert result["total_amount"] == 199.0


@pytest.mark.asyncio
async def test_get_order_for_user_without_order_sn(order_service: OrderService, db_session):
    """不传入订单号时返回用户最新订单"""
    user = await _create_test_user(db_session, "order_user_latest")
    assert user.id is not None
    await _create_test_order(db_session, user.id, "SN20240002", status=OrderStatus.DELIVERED)

    result = await order_service.get_order_for_user(None, user.id, session=db_session)

    assert result is not None
    assert result["order_sn"] == "SN20240002"
    assert result["status"] == OrderStatus.DELIVERED
    assert result["total_amount"] == 199.0


@pytest.mark.asyncio
async def test_handle_refund_request_success(order_service: OrderService, db_session):
    """退款申请成功路径（使用低金额避免触发风控审计/Celery）"""
    user = await _create_test_user(db_session, "refund_success_user")
    assert user.id is not None
    await _create_test_order(
        db_session,
        user.id,
        "SN20240001",
        status=OrderStatus.DELIVERED,
        total_amount=Decimal("199.0"),
        created_at=datetime.now(UTC) - timedelta(days=1),
    )

    result = await order_service.handle_refund_request(
        "我要退货，订单号 SN20240001，质量问题",
        user_id=user.id,
        thread_id="thread-1",
        session=db_session,
    )

    assert isinstance(result, dict)
    assert result["updated_state"] is not None
    assert "✅" in result["response"]
    assert result["updated_state"]["refund_flow_active"] is True
    assert result["updated_state"]["order_data"]["order_sn"] == "SN20240001"
    assert result["updated_state"]["refund_data"]["refund_id"] is not None
    assert result["updated_state"]["refund_data"]["amount"] == 199.0


@pytest.mark.asyncio
async def test_handle_refund_request_missing_order_sn(order_service: OrderService):
    """未提供订单号时返回提示"""
    result = await order_service.handle_refund_request("我要退货", user_id=1)

    assert isinstance(result, dict)
    assert result["updated_state"] is not None
    assert "请提供订单号" in result["response"]
    assert result["updated_state"]["refund_flow_active"] is False


@pytest.mark.asyncio
async def test_handle_refund_request_order_not_found(order_service: OrderService, db_session):
    """订单不存在时返回错误"""
    user = await _create_test_user(db_session, "refund_notfound_user")
    assert user.id is not None

    result = await order_service.handle_refund_request(
        "我要退货，订单号 SN99999999",
        user_id=user.id,
        session=db_session,
    )

    assert isinstance(result, dict)
    assert result["updated_state"] is not None
    assert "未找到订单" in result["response"]
    assert result["updated_state"]["refund_flow_active"] is False


# 注：以下防御分支不再进行单元测试，因为在真实 PostgreSQL 中，
# 持久化行的主键永远不会为 NULL。该分支属于防御性代码，保留在
# 生产代码中，但按照 no-mock 基础设施策略不进行测试。
#
# @pytest.mark.asyncio
# async def test_handle_refund_request_order_id_none(...):
#     ...


@pytest.mark.asyncio
async def test_handle_refund_request_refund_failed(order_service: OrderService, db_session):
    """process_refund_for_order 返回失败时返回错误消息"""
    user = await _create_test_user(db_session, "refund_failed_user")
    assert user.id is not None
    await _create_test_order(
        db_session,
        user.id,
        "SN20240001",
        status=OrderStatus.PENDING,
        total_amount=Decimal("199.0"),
        created_at=datetime.now(UTC) - timedelta(days=1),
    )

    result = await order_service.handle_refund_request(
        "我要退货，订单号 SN20240001",
        user_id=user.id,
        session=db_session,
    )

    assert isinstance(result, dict)
    assert result["updated_state"] is not None
    assert "不符合退货条件" in result["response"]
    assert result["updated_state"]["refund_flow_active"] is False
    assert result["updated_state"]["order_data"]["order_sn"] == "SN20240001"
