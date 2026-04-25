from unittest.mock import AsyncMock, patch

import pytest

from app.agents.complaint import ComplaintAgent
from app.models.state import make_agent_state
from tests._llm import DeterministicChatModel


@pytest.fixture
def agent(deterministic_llm):
    return ComplaintAgent(llm=deterministic_llm)


@pytest.mark.asyncio
async def test_complaint_agent_creates_ticket(agent):
    llm_response = (
        '{"category": "product_defect", "urgency": "high", '
        '"summary": "商品有瑕疵", "expected_resolution": "refund", '
        '"empathetic_response": "非常抱歉，已为您创建工单 {ticket_id}"}'
    )
    agent.llm = DeterministicChatModel(responses=[(["投诉"], llm_response)])

    with (
        patch(
            "app.agents.config_loader.get_effective_system_prompt", new=AsyncMock(return_value=None)
        ),
        patch.object(agent._tool, "create_ticket", new=AsyncMock(return_value={"ticket_id": 42})),
    ):
        state = make_agent_state(question="我要投诉商品有瑕疵")
        result = await agent.process(state)

    assert "42" in result["response"]
    assert "非常抱歉" in result["response"]
    assert result["updated_state"]["answer"] == result["response"]


@pytest.mark.asyncio
async def test_complaint_agent_ticket_creation_fails(agent):
    llm_response = (
        '{"category": "service", "urgency": "medium", '
        '"summary": "服务态度差", "expected_resolution": "apology", '
        '"empathetic_response": "已记录您的问题 {ticket_id}"}'
    )
    agent.llm = DeterministicChatModel(responses=[(["态度"], llm_response)])

    with (
        patch(
            "app.agents.config_loader.get_effective_system_prompt", new=AsyncMock(return_value=None)
        ),
        patch.object(agent._tool, "create_ticket", side_effect=RuntimeError("DB down")),
    ):
        state = make_agent_state(question="客服态度太差了")
        result = await agent.process(state)

    assert "客服团队会尽快与您联系" in result["response"]


@pytest.mark.asyncio
async def test_complaint_agent_parses_markdown_json(agent):
    llm_response = (
        "```json\n"
        '{"category": "logistics", "urgency": "high", '
        '"summary": "物流太慢", "expected_resolution": "compensation", '
        '"empathetic_response": "工单 {ticket_id} 已创建"}'
        "\n```"
    )
    agent.llm = DeterministicChatModel(responses=[(["海外"], llm_response)])

    with (
        patch(
            "app.agents.config_loader.get_effective_system_prompt", new=AsyncMock(return_value=None)
        ),
        patch.object(agent._tool, "create_ticket", new=AsyncMock(return_value={"ticket_id": 7})),
    ):
        state = make_agent_state(question="海外订单无法追踪")
        result = await agent.process(state)

    assert "7" in result["response"]
    assert "已创建" in result["response"]


@pytest.mark.asyncio
async def test_complaint_agent_parse_fallback(agent):
    agent.llm = DeterministicChatModel(responses=[(["无法"], "不是有效JSON")])

    with (
        patch(
            "app.agents.config_loader.get_effective_system_prompt", new=AsyncMock(return_value=None)
        ),
        patch.object(agent._tool, "create_ticket", new=AsyncMock(return_value={"ticket_id": 1})),
    ):
        state = make_agent_state(question="无法使用购买的优惠券")
        result = await agent.process(state)

    assert result["response"] == "不是有效JSON"


@pytest.fixture
def real_complaint_agent(real_llm):
    return ComplaintAgent(llm=real_llm)


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_complaint_agent(real_complaint_agent):
    with (
        patch(
            "app.agents.config_loader.get_effective_system_prompt", new=AsyncMock(return_value=None)
        ),
        patch.object(
            real_complaint_agent._tool,
            "create_ticket",
            new=AsyncMock(return_value={"ticket_id": 42}),
        ),
    ):
        state = make_agent_state(question="我要投诉商品有瑕疵")
        result = await real_complaint_agent.process(state)
        assert isinstance(result["response"], str)
        assert len(result["response"]) > 0
