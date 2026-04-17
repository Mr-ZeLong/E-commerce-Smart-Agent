import datetime

import pytest

from app.agents.base import BaseAgent
from app.models.state import AgentState
from tests._llm import DeterministicChatModel


class DummyAgent(BaseAgent):
    async def process(self, state: AgentState):
        _ = state
        return {"response": "ok", "updated_state": {}}


@pytest.fixture
def agent():
    return DummyAgent(
        name="test", llm=DeterministicChatModel(), system_prompt="You are a test agent."
    )


def test_create_messages_with_system_prompt_only(agent):
    messages = agent._create_messages("hello")
    assert len(messages) == 2
    assert messages[0].content == "You are a test agent."
    assert messages[1].content == f"今天是 {datetime.date.today().isoformat()}。\n\nhello"


def test_create_messages_with_context(agent):
    messages = agent._create_messages(
        "what is my order status?",
        context={"order_data": {"order_sn": "ORD123", "status": "shipped"}},
    )
    assert len(messages) == 2
    assert "ORD123" in messages[1].content
    assert "shipped" in messages[1].content


def test_create_messages_with_memory_context(agent):
    messages = agent._create_messages(
        "recommend something",
        memory_context={
            "structured_facts": [
                {"fact_type": "preference", "content": "likes tech gadgets"},
            ],
            "user_profile": {"membership_level": "gold", "total_orders": 10},
            "relevant_past_messages": [
                {"role": "user", "content": "iPhone 15"},
                {"role": "assistant", "content": "great choice"},
            ],
        },
    )
    assert len(messages) == 2
    content = messages[1].content
    assert "likes tech gadgets" in content
    assert "membership_level" in content
    assert "gold" in content
    assert "iPhone 15" in content
    assert "Assistant: great choice" in content
    assert "[用户问题]:" in content


def test_create_messages_with_context_and_memory(agent):
    messages = agent._create_messages(
        "hello",
        context={"context": ["policy A"]},
        memory_context={
            "structured_facts": [{"fact_type": "general", "content": "vip user"}],
        },
    )
    content = messages[1].content
    assert "policy A" in content
    assert "vip user" in content


def test_create_messages_empty_memory_context(agent):
    messages = agent._create_messages(
        "hello",
        memory_context={},
    )
    assert len(messages) == 2
    assert messages[1].content == f"今天是 {datetime.date.today().isoformat()}。\n\nhello"


def test_create_messages_no_system_prompt():
    agent_no_prompt = DummyAgent(name="test2", llm=DeterministicChatModel())
    messages = agent_no_prompt._create_messages("hello")
    assert len(messages) == 1
    assert messages[0].content == f"今天是 {datetime.date.today().isoformat()}。\n\nhello"


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_call_llm_with_real_llm(real_llm):
    agent = DummyAgent(name="test_real", llm=real_llm, system_prompt="You are a helpful assistant.")
    messages = agent._create_messages("Say 'hello' and nothing else.")
    response = await agent._call_llm(messages)
    assert isinstance(response, str)
    assert len(response) > 0
