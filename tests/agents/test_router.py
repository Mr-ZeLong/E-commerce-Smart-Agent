from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.router import IntentRouterAgent
from app.intent.models import ClarificationState, IntentAction, IntentCategory, IntentResult
from app.models.state import make_agent_state
from tests._llm import DeterministicChatModel


@pytest.fixture
def agent():
    mock_service = AsyncMock()
    return IntentRouterAgent(
        intent_service=mock_service,
        llm=DeterministicChatModel(),
        structured_manager=None,
    )


@pytest.mark.asyncio
async def test_router_routes_to_next_agent(agent):
    agent.intent_service.recognize.return_value = IntentResult(
        primary_intent=IntentCategory.ORDER,
        secondary_intent=IntentAction.CONSULT,
        confidence=0.9,
        needs_clarification=False,
    )

    with (
        patch(
            "app.agents.config_loader.get_target_agent_for_intent",
            new=AsyncMock(return_value="order_agent"),
        ),
        patch("app.agents.config_loader.is_agent_enabled", new=AsyncMock(return_value=True)),
    ):
        state = make_agent_state(question="查订单")
        result = await agent.process(state)

    updated = result["updated_state"]
    assert updated["next_agent"] == "order_agent"
    assert updated["intent_result"]["primary_intent"] == "ORDER"
    assert result["response"] == ""


@pytest.mark.asyncio
async def test_router_returns_clarification(agent):
    agent.intent_service.recognize.return_value = IntentResult(
        primary_intent=IntentCategory.PRODUCT,
        secondary_intent=IntentAction.CONSULT,
        confidence=0.6,
        needs_clarification=True,
        missing_slots=["product_name"],
    )
    clar_mock = MagicMock()
    clar_mock.response = "请问您想查询哪款商品？"
    clar_mock.state = ClarificationState(session_id="t1")
    agent.intent_service.clarify = AsyncMock(return_value=clar_mock)

    with (
        patch(
            "app.agents.config_loader.get_target_agent_for_intent",
            new=AsyncMock(return_value="product"),
        ),
        patch("app.agents.config_loader.is_agent_enabled", new=AsyncMock(return_value=True)),
    ):
        state = make_agent_state(question="有没有这个")
        result = await agent.process(state)

    assert "请问您想查询哪款商品？" in result["response"]
    assert result["updated_state"]["awaiting_clarification"] is True


@pytest.mark.asyncio
async def test_router_disabled_agent_fallback(agent):
    agent.intent_service.recognize.return_value = IntentResult(
        primary_intent=IntentCategory.COMPLAINT,
        secondary_intent=IntentAction.CONSULT,
        confidence=0.8,
        needs_clarification=False,
    )

    with (
        patch(
            "app.agents.config_loader.get_target_agent_for_intent",
            new=AsyncMock(return_value="complaint"),
        ),
        patch(
            "app.agents.config_loader.is_agent_enabled", new=AsyncMock(side_effect=[False, True])
        ),
    ):
        state = make_agent_state(question="我要投诉")
        result = await agent.process(state)

    assert result["updated_state"]["next_agent"] == "policy_agent"


@pytest.mark.asyncio
async def test_router_all_targets_disabled_transfers(agent):
    agent.intent_service.recognize.return_value = IntentResult(
        primary_intent=IntentCategory.COMPLAINT,
        secondary_intent=IntentAction.CONSULT,
        confidence=0.8,
        needs_clarification=False,
    )

    with (
        patch(
            "app.agents.config_loader.get_target_agent_for_intent",
            new=AsyncMock(return_value="complaint"),
        ),
        patch("app.agents.config_loader.is_agent_enabled", new=AsyncMock(return_value=False)),
    ):
        state = make_agent_state(question="我要投诉")
        result = await agent.process(state)

    assert result["updated_state"]["needs_human_transfer"] is True
    assert "人工客服" in result["response"]


@pytest.mark.asyncio
async def test_router_iteration_limit(agent):
    agent.intent_service.recognize.return_value = IntentResult(
        primary_intent=IntentCategory.ORDER,
        secondary_intent=IntentAction.CONSULT,
        confidence=0.9,
        needs_clarification=False,
    )

    with (
        patch(
            "app.agents.config_loader.get_target_agent_for_intent",
            new=AsyncMock(return_value="order_agent"),
        ),
        patch("app.agents.config_loader.is_agent_enabled", new=AsyncMock(return_value=True)),
    ):
        state = make_agent_state(question="查订单", iteration_count=10)
        result = await agent.process(state)

    assert result["updated_state"]["needs_human_transfer"] is True
    assert "步数过多" in result["response"]


@pytest.mark.asyncio
async def test_router_other_intent_greeting(agent):
    agent.intent_service.recognize.return_value = IntentResult(
        primary_intent=IntentCategory.OTHER,
        secondary_intent=IntentAction.CONSULT,
        confidence=0.9,
        needs_clarification=False,
    )

    with (
        patch(
            "app.agents.config_loader.get_target_agent_for_intent",
            new=AsyncMock(return_value="policy_agent"),
        ),
        patch("app.agents.config_loader.is_agent_enabled", new=AsyncMock(return_value=True)),
    ):
        state = make_agent_state(question="你好")
        result = await agent.process(state)

    assert "智能客服助手" in result["response"]
    assert result["updated_state"]["intent_result"]["primary_intent"] == "OTHER"


@pytest.mark.asyncio
async def test_router_retry_requested_same_agent_transfers(agent):
    agent.intent_service.recognize.return_value = IntentResult(
        primary_intent=IntentCategory.ORDER,
        secondary_intent=IntentAction.CONSULT,
        confidence=0.9,
        needs_clarification=False,
    )

    with (
        patch(
            "app.agents.config_loader.get_target_agent_for_intent",
            new=AsyncMock(return_value="order_agent"),
        ),
        patch("app.agents.config_loader.is_agent_enabled", new=AsyncMock(return_value=True)),
    ):
        state = make_agent_state(
            question="查订单",
            retry_requested=True,
            current_agent="order_agent",
        )
        result = await agent.process(state)

    assert result["updated_state"]["needs_human_transfer"] is True
    assert "转接人工客服" in result["response"]
