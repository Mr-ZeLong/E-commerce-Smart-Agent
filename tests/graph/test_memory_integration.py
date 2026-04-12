from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.types import Command

from app.graph.nodes import build_memory_node
from app.models.state import make_agent_state


@pytest.mark.asyncio
async def test_memory_node_routes_to_supervisor():
    mock_structured = AsyncMock()
    mock_structured.get_user_profile.return_value = MagicMock(
        user_id=1,
        membership_level="gold",
        preferred_language="zh",
        timezone="Asia/Shanghai",
        total_orders=5,
        lifetime_value=1000.0,
    )
    mock_structured.get_user_facts.return_value = [
        MagicMock(fact_type="preference", content="fast shipping", confidence=0.9),
    ]

    mock_vector = AsyncMock()
    mock_vector.search_similar.return_value = [
        {"message_role": "user", "content": "previous question"},
    ]

    node = build_memory_node(
        structured_manager=mock_structured,
        vector_manager=mock_vector,
        use_supervisor=True,
    )
    state = make_agent_state(
        question="hello again",
        user_id=1,
        thread_id="t1",
        history=[{"role": "user", "content": "hello again"}],
    )
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "supervisor_node"
    assert result.update is not None
    assert "memory_context" in result.update
    assert result.update["memory_context"]["user_profile"]["membership_level"] == "gold"
    assert len(result.update["memory_context"]["structured_facts"]) == 1
    assert len(result.update["memory_context"]["relevant_past_messages"]) == 1


@pytest.mark.asyncio
async def test_memory_node_handles_structured_exception():
    mock_structured = AsyncMock()
    mock_structured.get_user_profile.side_effect = Exception("db error")
    mock_structured.get_user_facts.return_value = []

    mock_vector = AsyncMock()
    mock_vector.search_similar.return_value = []

    node = build_memory_node(
        structured_manager=mock_structured,
        vector_manager=mock_vector,
        use_supervisor=True,
    )
    state = make_agent_state(
        question="hello",
        user_id=1,
        thread_id="t1",
        history=[{"role": "user", "content": "hello"}],
    )
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "supervisor_node"
    assert result.update is not None
    assert "memory_context" in result.update
    assert "user_profile" not in result.update["memory_context"]


@pytest.mark.asyncio
async def test_memory_node_handles_vector_exception():
    mock_structured = AsyncMock()
    mock_structured.get_user_profile.return_value = None
    mock_structured.get_user_facts.return_value = []

    mock_vector = AsyncMock()
    mock_vector.search_similar.side_effect = Exception("qdrant error")

    node = build_memory_node(
        structured_manager=mock_structured,
        vector_manager=mock_vector,
        use_supervisor=True,
    )
    state = make_agent_state(
        question="hello",
        user_id=1,
        thread_id="t1",
        history=[{"role": "user", "content": "hello"}],
    )
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "supervisor_node"
    assert result.update is not None
    assert "memory_context" in result.update
    assert "relevant_past_messages" not in result.update["memory_context"]


@pytest.mark.asyncio
async def test_memory_node_no_managers():
    node = build_memory_node(structured_manager=None, vector_manager=None)
    state = make_agent_state(
        question="hello",
        user_id=1,
        thread_id="t1",
        history=[{"role": "user", "content": "hello"}],
    )
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "supervisor_node"
    assert result.update is not None
    assert result.update["memory_context"] == {}
