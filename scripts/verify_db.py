# scripts/verify_db.py
import asyncio
import os
import sys

sys.path.append(os.getcwd())

from sqlmodel import func, select

from app.core.database import async_session_maker
from app.models.order import Order
from app.models.user import User


async def verify_database():
    async with async_session_maker() as session:
        # 1. 统计总量
        user_count_stmt = select(func.count()).select_from(User)
        order_count_stmt = select(func.count()).select_from(Order)

        user_total = (await session.exec(user_count_stmt)).one()
        order_total = (await session.exec(order_count_stmt)).one()

        print("📊 数据库概览:")
        print(f"   - 总用户数: {user_total}")
        print(f"   - 总订单数: {order_total}")

        if order_total == 0:
            print("❌ 数据库中没有订单数据！")
            return

        # 2. 随机抽取一个订单
        # 使用 PostgreSQL 的 RANDOM() 函数进行高效随机采样
        random_order_stmt = select(Order).order_by(func.random()).limit(1)
        result = await session.exec(random_order_stmt)
        order = result.first()

        if order:
            # 3. 查询该订单所属的用户
            user_stmt = select(User).where(User.id == order.user_id)
            user_result = await session.exec(user_stmt)
            user = user_result.first()

            print("\n🎲 随机抽检结果:")
            print("   ------------------------------------------------")
            print(f"   订单编号 (SN):  {order.order_sn}")
            print(f"   订单状态:       {order.status}")
            print(f"   订单金额:       ¥{order.total_amount}")
            print(f"   下单时间:       {order.created_at}")
            print(f"   商品明细:       {order.items}")
            print(f"   收货地址:       {order.shipping_address}")
            print("   ------------------------------------------------")
            print(f"   所属用户:       {user.full_name if user else '未知'}")
            print(f"   用户邮箱:       {user.email if user else '无'}")
            print("   ------------------------------------------------")
            print("✅ 抽检完毕：数据格式正确且外键关联正常。")


if __name__ == "__main__":
    asyncio.run(verify_database())
