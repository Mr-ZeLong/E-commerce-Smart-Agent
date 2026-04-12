# scripts/seed_data.py
import asyncio
import os
import sys

sys.path.append(os.getcwd())

from sqlmodel import select

from typing import Any

from app.core.database import async_session_maker
from app.models.memory import AgentConfig, RoutingRule
from app.models.order import Order, OrderStatus
from app.models.user import User

_DEFAULT_AGENT_CONFIGS: list[dict[str, Any]] = [
    {
        "agent_name": "policy_agent",
        "system_prompt": '你是专业的电商政策咨询专家。\n\n规则：\n1. 只能依据提供的参考信息回答，严禁编造\n2. 如果参考信息为空，直接回答"抱歉，暂未查询到相关规定"\n3. 回答简洁明了，引用具体政策条款\n4. 语气专业、客气',
        "confidence_threshold": 0.7,
        "max_retries": 2,
        "enabled": True,
    },
    {
        "agent_name": "order_agent",
        "system_prompt": "你是专业的电商订单处理助手。\n\n规则：\n1. 准确查询订单信息，清晰列出订单号、状态、金额\n2. 处理退货申请时，先检查资格再提交\n3. 订单数据必须来自数据库，严禁编造\n4. 语气友好，解答用户疑问",
        "confidence_threshold": 0.7,
        "max_retries": 2,
        "enabled": True,
    },
    {
        "agent_name": "product",
        "system_prompt": "你是专业的商品查询助手。\n\n规则：\n1. 根据用户问题搜索商品目录，提供准确的商品信息\n2. 如果用户询问具体参数且目录中有该参数，直接作答\n3. 如果参数不在目录中，基于检索到的商品描述进行推理并明确说明\n4. 严禁编造不存在的商品信息\n5. 语气友好，帮助用户找到合适的商品",
        "confidence_threshold": 0.7,
        "max_retries": 2,
        "enabled": True,
    },
    {
        "agent_name": "cart",
        "system_prompt": "你是专业的购物车管理助手。\n\n规则：\n1. 帮助用户查询、添加、修改购物车商品\n2. 准确反映购物车状态和数量\n3. 语气友好，提供购买建议",
        "confidence_threshold": 0.7,
        "max_retries": 2,
        "enabled": True,
    },
    {
        "agent_name": "logistics",
        "system_prompt": "你是专业的物流查询助手。\n\n规则：\n1. 根据订单号查询物流信息并清晰展示\n2. 物流数据来自系统查询，严禁编造\n3. 语气友好，解答用户疑问",
        "confidence_threshold": 0.7,
        "max_retries": 2,
        "enabled": True,
    },
    {
        "agent_name": "account",
        "system_prompt": "你是专业的电商账户服务助手。\n\n规则：\n1. 语气友好、亲切\n2. 准确展示用户账户信息、会员等级、余额和优惠券\n3. 不透露敏感信息如密码\n4. 严禁编造数据，所有信息必须来自工具返回结果",
        "confidence_threshold": 0.7,
        "max_retries": 2,
        "enabled": True,
    },
    {
        "agent_name": "payment",
        "system_prompt": "你是专业的电商支付助手。\n\n规则：\n1. 准确告知用户支付状态、发票信息、退款记录\n2. 语气友好，数据清晰\n3. 未查询到记录时给出积极引导",
        "confidence_threshold": 0.7,
        "max_retries": 2,
        "enabled": True,
    },
]

_DEFAULT_ROUTING_RULES: list[dict[str, Any]] = [
    {"intent_category": "ORDER", "target_agent": "order_agent", "priority": 10},
    {"intent_category": "AFTER_SALES", "target_agent": "order_agent", "priority": 10},
    {"intent_category": "POLICY", "target_agent": "policy_agent", "priority": 10},
    {"intent_category": "LOGISTICS", "target_agent": "logistics", "priority": 10},
    {"intent_category": "ACCOUNT", "target_agent": "account", "priority": 10},
    {"intent_category": "PAYMENT", "target_agent": "payment", "priority": 10},
    {"intent_category": "PRODUCT", "target_agent": "product", "priority": 10},
    {"intent_category": "RECOMMENDATION", "target_agent": "product", "priority": 10},
    {"intent_category": "CART", "target_agent": "cart", "priority": 10},
    {"intent_category": "PROMOTION", "target_agent": "policy_agent", "priority": 10},
    {"intent_category": "COMPLAINT", "target_agent": "order_agent", "priority": 10},
    {"intent_category": "OTHER", "target_agent": "policy_agent", "priority": 10},
]


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
                password_hash=User.hash_password("test123"),
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
                shipping_address="上海市浦东新区张江高科技园区",
            )

            # 订单 2：待支付 - 全棉袜子（可退货）
            order2 = Order(
                order_sn="SN20240002",
                user_id=user.id,  # ty:ignore[invalid-argument-type]
                status=OrderStatus.PENDING,
                total_amount=50.00,
                items=[{"name": "全棉袜子", "qty": 5, "price": 10.00}],
                shipping_address="北京市朝阳区三里屯",
            )

            # ✅ 新增订单 3：已发货 - 运动T恤（可退货）
            order3 = Order(
                order_sn="SN20240003",
                user_id=user.id,  # ty:ignore[invalid-argument-type]
                status=OrderStatus.SHIPPED,  # 已发货，符合退货条件
                total_amount=199.00,
                items=[
                    {"name": "运动T恤", "qty": 1, "price": 99.00},
                    {"name": "运动短裤", "qty": 1, "price": 100.00},
                ],
                tracking_number="SF987654321",
                shipping_address="上海市浦东新区张江高科技园区",
            )

            # ✅ 新增订单 4：已签收 - 篮球鞋（可退货）
            order4 = Order(
                order_sn="SN20240004",
                user_id=user.id,  # ty:ignore[invalid-argument-type]
                status=OrderStatus.DELIVERED,  # 已签收，符合退货条件
                total_amount=599.00,
                items=[{"name": "耐克篮球鞋", "qty": 1, "price": 599.00}],
                tracking_number="SF555666777",
                shipping_address="北京市海淀区中关村",
            )

            session.add_all([order1, order2, order3, order4])

        # 3. 检查并创建默认 AgentConfig
        for cfg in _DEFAULT_AGENT_CONFIGS:
            result = await session.exec(
                select(AgentConfig).where(AgentConfig.agent_name == cfg["agent_name"])
            )
            existing = result.one_or_none()
            if not existing:
                print(f"🤖 Creating default agent config for {cfg['agent_name']}...")
                session.add(
                    AgentConfig(
                        agent_name=cfg["agent_name"],  # type: ignore[arg-type]
                        system_prompt=cfg["system_prompt"],  # type: ignore[arg-type]
                        confidence_threshold=cfg["confidence_threshold"],  # type: ignore[arg-type]
                        max_retries=cfg["max_retries"],  # type: ignore[arg-type]
                        enabled=cfg["enabled"],  # type: ignore[arg-type]
                    )
                )
                await session.flush()

        for rule_data in _DEFAULT_ROUTING_RULES:
            result = await session.exec(
                select(RoutingRule).where(
                    RoutingRule.intent_category == rule_data["intent_category"]
                )
            )
            existing = result.one_or_none()
            if not existing:
                print(f"📋 Creating routing rule for {rule_data['intent_category']}...")
                session.add(
                    RoutingRule(
                        intent_category=rule_data["intent_category"],
                        target_agent=rule_data["target_agent"],
                        priority=rule_data["priority"],
                    )
                )
                await session.flush()

        # 最终统一提交事务
        await session.commit()
        print("✅ Seed data completed.")


if __name__ == "__main__":
    asyncio.run(seed_data())
