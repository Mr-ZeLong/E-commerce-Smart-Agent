"""Tests for supervisor context isolation and conversation history integration."""

from __future__ import annotations

from unittest.mock import MagicMock

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.base import BaseAgent, _estimate_tokens
from app.graph.subgraphs import _estimate_state_tokens, _filter_state, get_agent_tools
from app.graph.workflow import _AGENT_ALLOWED_KEYS, get_agent_tool_scope
from app.models.state import AgentProcessResult, AgentState, make_agent_state


class FakeAgent(BaseAgent):
    """Fake agent for testing."""

    def __init__(self, name: str, system_prompt: str | None = None) -> None:
        mock_llm = MagicMock(spec=BaseChatModel)
        super().__init__(name=name, llm=mock_llm, system_prompt=system_prompt)

    async def process(self, state: AgentState) -> AgentProcessResult:
        return AgentProcessResult(response="test", updated_state={})


class TestContextIsolation:
    """Tests for context isolation via _AGENT_ALLOWED_KEYS."""

    def test_filter_state_removes_unauthorized_keys(self) -> None:
        state = make_agent_state(
            question="test",
            user_id=1,
            thread_id="t1",
            order_data={"order_sn": "123"},
            retrieval_result={"chunks": []},
        )
        allowed = _AGENT_ALLOWED_KEYS["policy_agent"]
        filtered = _filter_state(state, allowed)
        assert "order_data" not in filtered
        assert "retrieval_result" in filtered

    def test_filter_state_preserves_common_keys(self) -> None:
        state = make_agent_state(
            question="test",
            user_id=1,
            thread_id="t1",
            history=[{"role": "user", "content": "hi"}],
        )
        allowed = _AGENT_ALLOWED_KEYS["account"]
        filtered = _filter_state(state, allowed)
        assert filtered["question"] == "test"
        assert filtered["user_id"] == 1
        assert filtered["history"] == [{"role": "user", "content": "hi"}]

    def test_estimate_state_tokens(self) -> None:
        state = make_agent_state(question="hello world", user_id=1, thread_id="t1")
        tokens = _estimate_state_tokens(state)
        assert tokens > 0

    def test_get_agent_tool_scope_returns_tools(self) -> None:
        tools = get_agent_tool_scope("order_agent")
        assert "get_order" in tools
        assert "search_products" not in tools

    def test_get_agent_tool_scope_unknown_agent(self) -> None:
        tools = get_agent_tool_scope("unknown_agent")
        assert tools == []

    def test_get_agent_tools(self) -> None:
        tools = get_agent_tools("product")
        assert any(t["name"] == "search_products" for t in tools)


class TestConversationHistory:
    """Tests for conversation history integration in BaseAgent."""

    def test_build_history_messages_empty(self) -> None:
        agent = FakeAgent(name="test")
        result = agent._build_history_messages([], budget=100)
        assert result == []

    def test_build_history_messages_within_budget(self) -> None:
        agent = FakeAgent(name="test")
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = agent._build_history_messages(history, budget=1000)
        assert len(result) == 2
        assert isinstance(result[0], HumanMessage)
        assert isinstance(result[1], AIMessage)

    def test_build_history_messages_truncates(self) -> None:
        agent = FakeAgent(name="test")
        # Create a very long message that should exceed budget
        history = [
            {"role": "user", "content": "x" * 10000},
            {"role": "assistant", "content": "Short reply"},
        ]
        result = agent._build_history_messages(history, budget=10)
        # Should only include the most recent message if it fits
        assert len(result) <= 2

    def test_create_messages_with_history(self) -> None:
        agent = FakeAgent(name="test", system_prompt="You are a test agent.")
        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]
        messages = agent._create_messages(
            user_message="Current question",
            history=history,
        )
        assert len(messages) >= 3  # system + history + current
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[-1], HumanMessage)

    def test_create_messages_without_history(self) -> None:
        agent = FakeAgent(name="test", system_prompt="You are a test agent.")
        messages = agent._create_messages(user_message="Hello")
        assert len(messages) == 2  # system + user
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)

    def test_estimate_tokens(self) -> None:
        tokens = _estimate_tokens("Hello world")
        assert tokens > 0
        assert tokens < 100  # "Hello world" should be < 100 tokens
