"""
集成测试配置和共享 fixtures

提供测试用的 Mock LLM 响应、测试数据初始化等功能
"""

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from langchain_openai import ChatOpenAI

from app.core.security import create_access_token
from app.models.order import Order, OrderStatus
from app.models.refund import RefundApplication, RefundReason, RefundStatus
from app.models.user import User


# ========== Mock LLM Fixtures ==========


@pytest.fixture
def mock_llm_response():
    """
    创建 Mock LLM 响应的辅助函数

    Returns:
        一个函数，用于创建可配置的 Mock LLM
    """

    def _create_mock(response_content: str = "Mock response") -> MagicMock:
        """创建 Mock LLM 实例"""
        mock = MagicMock(spec=ChatOpenAI)
        mock.ainvoke = AsyncMock(
            return_value=MagicMock(content=response_content)
        )
        return mock

    return _create_mock


@pytest.fixture
def mock_confidence_signals():
    """
    创建 Mock 置信度信号的辅助函数

    Returns:
        一个函数，用于创建指定分数的置信度信号
    """

    def _create_signals(
        rag_score: float = 0.8,
        llm_score: float = 0.85,
        emotion_score: float = 0.9,
    ) -> dict[str, Any]:
        """创建 Mock 置信度信号"""
        return {
            "rag": MagicMock(score=rag_score, reason=f"RAG score: {rag_score}"),
            "llm": MagicMock(score=llm_score, reason=f"LLM score: {llm_score}"),
            "emotion": MagicMock(score=emotion_score, reason=f"Emotion score: {emotion_score}"),
        }

    return _create_signals


# ========== 测试数据 Fixtures ==========


@pytest.fixture
def test_user() -> User:
    """创建测试用户（不使用数据库）"""
    user = User(
        id=1,
        username="test_user",
        password_hash=User.hash_password("test_password"),
        email="test@example.com",
        full_name="Test User",
        is_active=True,
        is_admin=False,
    )
    return user


@pytest.fixture
def test_admin() -> User:
    """创建测试管理员用户（不使用数据库）"""
    admin = User(
        id=2,
        username="test_admin",
        password_hash=User.hash_password("admin_password"),
        email="admin@example.com",
        full_name="Test Admin",
        is_active=True,
        is_admin=True,
    )
    return admin


@pytest.fixture
def test_order(test_user: User) -> Order:
    """创建测试订单（不使用数据库）"""
    assert test_user.id is not None
    order = Order(
        id=1,
        order_sn="SN20240001",
        user_id=test_user.id,
        status=OrderStatus.SHIPPED,
        total_amount=299.99,
        items=[
            {"name": "测试商品1", "qty": 1, "price": 199.99},
            {"name": "测试商品2", "qty": 1, "price": 100.00},
        ],
        tracking_number="SF1234567890",
        shipping_address="北京市朝阳区测试地址",
    )
    return order


@pytest.fixture
def test_delivered_order(test_user: User) -> Order:
    """创建已交付的测试订单（用于退货测试，不使用数据库）"""
    assert test_user.id is not None
    order = Order(
        id=2,
        order_sn="SN20240002",
        user_id=test_user.id,
        status=OrderStatus.DELIVERED,
        total_amount=199.99,
        items=[
            {"name": "可退货商品", "qty": 1, "price": 199.99},
        ],
        tracking_number="SF0987654321",
        shipping_address="北京市海淀区测试地址",
    )
    return order


@pytest.fixture
def test_refund_application(
    test_user: User,
    test_delivered_order: Order,
) -> RefundApplication:
    """创建测试退款申请（不使用数据库）"""
    assert test_user.id is not None
    assert test_delivered_order.id is not None
    refund = RefundApplication(
        id=1,
        order_id=test_delivered_order.id,
        user_id=test_user.id,
        status=RefundStatus.PENDING,
        reason_category=RefundReason.SIZE_NOT_FIT,
        reason_detail="尺码不合适，需要退货",
        refund_amount=test_delivered_order.total_amount,
    )
    return refund


# ========== 认证 Fixtures ==========


@pytest.fixture
def auth_token(test_user: User) -> str:
    """生成普通用户的认证 Token"""
    assert test_user.id is not None
    return create_access_token(user_id=test_user.id, is_admin=False)


@pytest.fixture
def admin_auth_token(test_admin: User) -> str:
    """生成管理员的认证 Token"""
    assert test_admin.id is not None
    return create_access_token(user_id=test_admin.id, is_admin=True)


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    """生成带认证的请求头"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_auth_headers(admin_auth_token: str) -> dict[str, str]:
    """生成带管理员认证的请求头"""
    return {"Authorization": f"Bearer {admin_auth_token}"}


# ========== Agent Mock Fixtures ==========


@pytest.fixture
def mock_supervisor_agent():
    """Mock SupervisorAgent 的完整协调流程"""
    with patch("app.agents.supervisor.SupervisorAgent") as mock_class:
        mock_instance = MagicMock()

        # 模拟 coordinate 方法
        async def mock_coordinate(state: dict) -> dict:
            """模拟协调流程"""
            question = state.get("question", "")

            # 根据问题内容返回不同的模拟结果
            if "订单" in question or "SN" in question:
                return {
                    "answer": "订单状态：已发货，物流单号 SF1234567890",
                    "intent": "ORDER",
                    "confidence_score": 0.85,
                    "confidence_signals": {
                        "rag": {"score": 0.8, "reason": "订单数据匹配"},
                        "llm": {"score": 0.85, "reason": "回答准确"},
                        "emotion": {"score": 0.9, "reason": "中性情绪"},
                    },
                    "needs_human_transfer": False,
                    "audit_level": "none",
                }
            elif "运费" in question or "政策" in question:
                return {
                    "answer": "满100元免运费",
                    "intent": "POLICY",
                    "confidence_score": 0.9,
                    "confidence_signals": {
                        "rag": {"score": 0.95, "reason": "高相似度匹配"},
                        "llm": {"score": 0.9, "reason": "回答完整"},
                        "emotion": {"score": 0.85, "reason": "中性情绪"},
                    },
                    "needs_human_transfer": False,
                    "audit_level": "none",
                }
            elif "退货" in question:
                return {
                    "answer": "✅ 退货申请已创建，退款金额：¥199.99",
                    "intent": "REFUND",
                    "confidence_score": 0.88,
                    "confidence_signals": {
                        "rag": {"score": 0.85, "reason": "规则匹配"},
                        "llm": {"score": 0.88, "reason": "流程完成"},
                        "emotion": {"score": 0.9, "reason": "中性情绪"},
                    },
                    "needs_human_transfer": False,
                    "audit_level": "none",
                    "refund_flow_active": True,
                }
            elif "生气" in question or "投诉" in question:
                return {
                    "answer": "非常抱歉给您带来不好的体验",
                    "intent": "POLICY",
                    "confidence_score": 0.4,
                    "confidence_signals": {
                        "rag": {"score": 0.5, "reason": "部分匹配"},
                        "llm": {"score": 0.4, "reason": "不确定"},
                        "emotion": {"score": 0.2, "reason": "高挫败感"},
                    },
                    "needs_human_transfer": True,
                    "audit_level": "manual",
                    "transfer_reason": "置信度不足",
                }
            else:
                return {
                    "answer": "您好！我是您的智能客服助手",
                    "intent": "OTHER",
                    "confidence_score": 1.0,
                    "confidence_signals": {
                        "rag": {"score": 1.0, "reason": "直接回复"},
                        "llm": {"score": 1.0, "reason": "直接回复"},
                        "emotion": {"score": 1.0, "reason": "直接回复"},
                    },
                    "needs_human_transfer": False,
                    "audit_level": "none",
                }

        mock_instance.coordinate = mock_coordinate
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_router_agent():
    """Mock RouterAgent 的意图识别"""
    with patch("app.agents.router.RouterAgent") as mock_class:
        mock_instance = MagicMock()

        async def mock_process(state: dict):
            """模拟意图识别"""
            from app.agents.base import AgentResult
            from app.agents.router import Intent

            question = state.get("question", "").lower()

            if any(kw in question for kw in ["订单", "物流", "到哪了", "sn"]):
                intent = Intent.ORDER
                next_agent = "order"
                response = ""
            elif any(kw in question for kw in ["运费", "政策", "退货规则", "可以退吗"]):
                intent = Intent.POLICY
                next_agent = "policy"
                response = ""
            elif any(kw in question for kw in ["退货", "退款", "不要了"]):
                intent = Intent.REFUND
                next_agent = "order"
                response = ""
            elif any(kw in question for kw in ["你好", "您好", "hi", "hello"]):
                intent = Intent.OTHER
                next_agent = "supervisor"
                response = "您好！我是您的智能客服助手"
            else:
                intent = Intent.POLICY
                next_agent = "policy"
                response = ""

            return AgentResult(
                response=response,
                updated_state={
                    "intent": intent,
                    "next_agent": next_agent,
                },
            )

        mock_instance.process = mock_process
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_order_agent():
    """Mock OrderAgent 的订单处理"""
    with patch("app.agents.order.OrderAgent") as mock_class:
        mock_instance = MagicMock()

        async def mock_process(state: dict):
            """模拟订单处理"""
            from app.agents.base import AgentResult

            intent = state.get("intent")
            question = state.get("question", "")

            if intent == "REFUND":
                # 模拟退货处理
                return AgentResult(
                    response="✅ 退货申请已创建，退款金额：¥199.99",
                    updated_state={
                        "order_data": {"order_sn": "SN20240002"},
                        "refund_flow_active": True,
                        "refund_data": {
                            "refund_id": 1,
                            "amount": 199.99,
                        },
                    },
                )
            else:
                # 模拟订单查询
                return AgentResult(
                    response="订单状态：已发货，物流单号 SF1234567890",
                    updated_state={
                        "order_data": {
                            "order_sn": "SN20240001",
                            "status": "SHIPPED",
                            "tracking_number": "SF1234567890",
                        },
                    },
                )

        mock_instance.process = mock_process
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_policy_agent():
    """Mock PolicyAgent 的政策查询"""
    with patch("app.agents.policy.PolicyAgent") as mock_class:
        mock_instance = MagicMock()

        async def mock_process(state: dict):
            """模拟政策查询"""
            from app.agents.base import AgentResult
            from app.models.state import RetrievalResult

            question = state.get("question", "")

            # 模拟 RAG 检索结果
            retrieval_result = RetrievalResult(
                chunks=["满100元免运费", "退货需在7天内申请"],
                similarities=[0.95, 0.88],
                sources=["policy_v1.md", "policy_v2.md"],
            )

            if "运费" in question:
                response = "满100元免运费"
            elif "退货" in question:
                response = "退货需在7天内申请，商品需保持原状"
            else:
                response = "根据平台政策..."

            return AgentResult(
                response=response,
                updated_state={
                    "retrieval_result": retrieval_result,
                    "context": retrieval_result.chunks,
                    "answer": response,
                },
                confidence=0.85,
            )

        mock_instance.process = mock_process
        mock_class.return_value = mock_instance
        yield mock_instance


# ========== 置信度信号 Mock Fixtures ==========


@pytest.fixture
def mock_high_confidence_signals():
    """模拟高置信度信号"""
    with patch("app.confidence.signals.ConfidenceSignals") as mock_class:
        mock_instance = MagicMock()
        mock_instance.calculate_all = AsyncMock(return_value={
            "rag": MagicMock(score=0.95, reason="高相似度匹配", metadata={}),
            "llm": MagicMock(score=0.9, reason="回答完整", metadata={}),
            "emotion": MagicMock(score=0.85, reason="中性情绪", metadata={}),
        })
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_low_confidence_signals():
    """模拟低置信度信号"""
    with patch("app.confidence.signals.ConfidenceSignals") as mock_class:
        mock_instance = MagicMock()
        mock_instance.calculate_all = AsyncMock(return_value={
            "rag": MagicMock(score=0.3, reason="低相似度", metadata={}),
            "llm": MagicMock(score=0.4, reason="不确定", metadata={}),
            "emotion": MagicMock(score=0.5, reason="中性", metadata={}),
        })
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_negative_emotion_signals():
    """模拟负面情感信号（触发人工接管）"""
    with patch("app.confidence.signals.ConfidenceSignals") as mock_class:
        mock_instance = MagicMock()
        mock_instance.calculate_all = AsyncMock(return_value={
            "rag": MagicMock(score=0.6, reason="中等相似度", metadata={}),
            "llm": MagicMock(score=0.5, reason="一般", metadata={}),
            "emotion": MagicMock(score=0.2, reason="高挫败感(负面词3,紧急词1)", metadata={
                "emotion_type": "high_frustration",
                "negative_count": 3,
            }),
        })
        mock_class.return_value = mock_instance
        yield mock_instance


# ========== 应用和客户端 Fixtures ==========


@pytest.fixture
def app():
    """创建测试用的 FastAPI 应用实例"""
    from fastapi import FastAPI
    from app.api.v1.chat import router as chat_router

    test_app = FastAPI()
    test_app.include_router(chat_router, prefix="/api/v1")

    return test_app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest_asyncio.fixture
async def async_client(app):
    """创建异步测试客户端"""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ========== 事件循环 Fixture ==========


@pytest.fixture(scope="session")
def event_loop():
    """创建会话级别的事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
