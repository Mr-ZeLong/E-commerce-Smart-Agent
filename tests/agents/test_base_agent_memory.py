import datetime

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

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


def test_build_history_messages_within_budget(agent):
    history = [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
        {"role": "user", "content": "second question"},
        {"role": "assistant", "content": "second answer"},
    ]
    result = agent._build_history_messages(history, budget=1000)
    assert len(result) == 4
    assert isinstance(result[0], HumanMessage)
    assert isinstance(result[1], AIMessage)
    assert result[0].content == "first question"
    assert result[1].content == "first answer"


def test_build_history_messages_truncates_when_over_budget(agent):
    long_content = "x" * 5000
    history = [
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "old"},
        {"role": "user", "content": long_content},
        {"role": "assistant", "content": "recent"},
    ]
    result = agent._build_history_messages(history, budget=100)
    assert len(result) < 4
    if result:
        assert result[-1].content == "recent"


def test_build_history_messages_empty_history(agent):
    assert agent._build_history_messages([], budget=100) == []


def test_build_history_messages_zero_budget(agent):
    history = [{"role": "user", "content": "hi"}]
    assert agent._build_history_messages(history, budget=0) == []


def test_create_messages_includes_history(agent):
    history = [
        {"role": "user", "content": "previous question"},
        {"role": "assistant", "content": "previous answer"},
    ]
    messages = agent._create_messages("new question", history=history)
    assert len(messages) > 2
    assert isinstance(messages[0], SystemMessage)
    assert messages[1].content == "previous question"
    assert messages[2].content == "previous answer"
    assert isinstance(messages[-1], HumanMessage)
    assert "new question" in messages[-1].content


def test_create_messages_without_history(agent):
    messages = agent._create_messages("hello")
    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)


def test_create_messages_respects_history_budget_override(agent):
    long_history = [
        {"role": "user", "content": "x" * 5000},
        {"role": "assistant", "content": "y" * 5000},
    ]
    config = {"history_token_budget": 50}
    messages = agent._create_messages("hello", history=long_history, memory_context_config=config)
    history_messages = [
        m
        for m in messages
        if not isinstance(m, SystemMessage)
        and not (isinstance(m, HumanMessage) and "今天是" in m.content)
    ]
    assert len(history_messages) < len(long_history)


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_call_llm_with_real_llm(real_llm):
    agent = DummyAgent(name="test_real", llm=real_llm, system_prompt="You are a helpful assistant.")
    messages = agent._create_messages("Say 'hello' and nothing else.")
    response = await agent._call_llm(messages)
    assert isinstance(response, str)
    assert len(response) > 0
