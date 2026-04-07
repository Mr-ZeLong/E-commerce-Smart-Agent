# scripts/test_refund_rules.py
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import async_session_maker
from app.services.refund_service import (
    RefundApplicationService,
    RefundEligibilityChecker,
    RefundReason
)
from app.models.order import Order
from sqlmodel import select


async def test_refund_rules():
    """测试退货规则引擎"""
    
    print("=" * 60)
    print("🧪 测试退货规则引擎")
    print("=" * 60)
    
    async with async_session_maker() as session:
        
        # ========== 测试场景 1: 不可退货商品（内衣） ==========
        print("\n📋 场景 1: 申请退货 - 运动内衣（应被拒绝）")
        
        stmt = select(Order).where(Order.order_sn == "SN20240001")
        result = await session.exec(stmt)
        order1 = result.first()
        
        if order1:
            is_eligible, msg = await RefundEligibilityChecker.check_eligibility(
                order1, session
            )
            print(f"   订单号: {order1.order_sn}")
            print(f"   商品:  {order1.items[0]['name']}")
            print(f"   资格检查: {'✅ 通过' if is_eligible else '❌ 拒绝'}")
            print(f"   原因: {msg}")
        
        # ========== 测试场景 2: 正常退货（运动T恤） ==========
        print("\n📋 场景 2: 申请退货 - 运动T恤（应该成功）")
        
        stmt = select(Order).where(Order.order_sn == "SN20240003")
        result = await session. exec(stmt)
        order3 = result.first()
        
        if order3:
            is_eligible, msg = await RefundEligibilityChecker. check_eligibility(
                order3, session
            )
            print(f"   订单号: {order3.order_sn}")
            print(f"   商品: {', '.join([item['name'] for item in order3.items])}")
            print(f"   资格检查: {'✅ 通过' if is_eligible else '❌ 拒绝'}")
            print(f"   原因: {msg}")
            
            if is_eligible:
                success, message, refund_app = await RefundApplicationService.create_refund_application(
                    order_id=order3.id,  # ty:ignore[invalid-argument-type]
                    user_id=order3.user_id,
                    reason_detail="尺码偏大，想换小一号",
                    reason_category=RefundReason.SIZE_NOT_FIT,
                    session=session
                )
                print(f"   申请结果: {'✅ 成功' if success else '❌ 失败'}")
                print(f"   消息: {message}")
                if refund_app:
                    print(f"   申请ID: {refund_app.id}")
                    print(f"   退款金额: ¥{refund_app. refund_amount}")
        
        # ========== 测试场景 3: 重复申请 ==========
        print("\n📋 场景 3: 再次申请退货（应该被拒绝 - 重复申请）")
        
        if order3:
            success, message, _ = await RefundApplicationService.create_refund_application(
                order_id=order3.id,  # ty:ignore[invalid-argument-type]
                user_id=order3.user_id,
                reason_detail="测试重复申请",
                reason_category=RefundReason.OTHER,
                session=session
            )
            print(f"   申请结果: {'✅ 成功' if success else '❌ 拒绝'}")
            print(f"   消息: {message}")
        
        # ========== 测试场景 4: 跨用户攻击 ==========
        print("\n📋 场景 4: 用户2尝试退用户1的订单（安全测试）")
        
        if order3:
            success, message, _ = await RefundApplicationService.create_refund_application(
                order_id=order3.id,  # ty:ignore[invalid-argument-type]
                user_id=999,  # 假冒的用户ID
                reason_detail="恶意攻击测试",
                reason_category=RefundReason.OTHER,
                session=session
            )
            print(f"   申请结果: {'✅ 成功' if success else '❌ 拒绝'}")
            print(f"   消息: {message}")
        
        # ========== 测试场景 5: 订单状态检查 ==========
        print("\n📋 场景 5: 申请退货 - 待支付订单（应被拒绝）")
        
        stmt = select(Order).where(Order.order_sn == "SN20240002")
        result = await session.exec(stmt)
        order2 = result.first()
        
        if order2:
            is_eligible, msg = await RefundEligibilityChecker.check_eligibility(
                order2, session
            )
            print(f"   订单号:  {order2.order_sn}")
            print(f"   订单状态: {order2.status}")
            print(f"   资格检查: {'✅ 通过' if is_eligible else '❌ 拒绝'}")
            print(f"   原因: {msg}")
        
        # ========== 测试场景 6: 查询退货记录 ==========
        print("\n📋 场景 6: 查询用户1的所有退货申请")
        
        if order3:
            refund_list = await RefundApplicationService.get_user_refund_applications(
                user_id=order3.user_id,
                session=session
            )
            print(f"   找到 {len(refund_list)} 条记录")
            for refund in refund_list: 
                print(f"   - 申请ID: {refund. id} | 订单ID: {refund.order_id} | "
                      f"状态:  {refund.status} | 金额: ¥{refund.refund_amount}")
                print(f"     原因: {refund.reason_detail}")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_refund_rules())