# scripts/seed_data.py
import asyncio
import os
import sys

sys.path.append(os.getcwd())

from sqlmodel import select

from app.core.database import async_session_maker
from app.models.order import Order, OrderStatus
from app.models.user import User


async def seed_data():
    async with async_session_maker() as session:
        # 1. 检查用户是否已存在
        result = await session.exec(select(User).where(User.username == "test_user"))
        user = result.first()

        if not user:
            print("🌱 Creating test user...")
            user = User(
                username="test_user",
                email="test@example.com",
                full_name="张三",
                password_hash=User.hash_password("test123")
            )
            session.add(user)
            await session.flush()

        # 2. 检查并创建 Mock 订单
        result = await session.exec(select(Order).where(Order.user_id == user.id))
        orders = result.all()

        if not orders:
            print("📦 Creating mock orders...")

            # 订单 1：已发货 - 运动内衣（不可退货）
            order1 = Order(
                order_sn="SN20240001",
                user_id=user.id,  # ty:ignore[invalid-argument-type]
                status=OrderStatus.SHIPPED,
                total_amount=128.50,
                items=[{"name": "运动内衣", "qty": 1, "price": 128.50}],
                tracking_number="SF123456789",
                shipping_address="上海市浦东新区张江高科技园区"
            )

            # 订单 2：待支付 - 全棉袜子（可退货）
            order2 = Order(
                order_sn="SN20240002",
                user_id=user.id,  # ty:ignore[invalid-argument-type]
                status=OrderStatus.PENDING,
                total_amount=50.00,
                items=[{"name": "全棉袜子", "qty": 5, "price": 10.00}],
                shipping_address="北京市朝阳区三里屯"
            )

            # ✅ 新增订单 3：已发货 - 运动T恤（可退货）
            order3 = Order(
                order_sn="SN20240003",
                user_id=user.id,  # ty:ignore[invalid-argument-type]
                status=OrderStatus.SHIPPED,  # 已发货，符合退货条件
                total_amount=199.00,
                items=[
                    {"name": "运动T恤", "qty": 1, "price": 99.00},
                    {"name": "运动短裤", "qty": 1, "price": 100.00}
                ],
                tracking_number="SF987654321",
                shipping_address="上海市浦东新区张江高科技园区"
            )

            # ✅ 新增订单 4：已签收 - 篮球鞋（可退货）
            order4 = Order(
                order_sn="SN20240004",
                user_id=user.id,  # ty:ignore[invalid-argument-type]
                status=OrderStatus.DELIVERED,  # 已签收，符合退货条件
                total_amount=599.00,
                items=[{"name": "耐克篮球鞋", "qty": 1, "price": 599.00}],
                tracking_number="SF555666777",
                shipping_address="北京市海淀区中关村"
            )

            session.add_all([order1, order2, order3, order4])

        # 最终统一提交事务
        await session.commit()
        print("✅ Seed data completed.")

if __name__ == "__main__":
    asyncio.run(seed_data())
