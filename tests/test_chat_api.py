import asyncio
import json
import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessageChunk

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.main import app
from app.models.state import AgentState
from app.models.user import User

EXPECTED_AGENT_STATE_KEYS = set(AgentState.__annotations__.keys())


@pytest_asyncio.fixture(scope="session")
async def auth_token():
    unique = uuid.uuid4().hex[:8]
    username = f"chat_user_{unique}"
    password = "password123"

    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password(password),
            email=f"{username}@test.com",
            full_name="Chat Test",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        token = create_access_token(user_id=user.id, is_admin=False)

    yield token


@pytest.mark.asyncio
async def test_chat_normal_streaming(client, auth_token):
    """正常流式响应：包含 token、answer 和 [DONE]"""

    received_state = {}

    async def mock_astream_events(state, config, version):
        received_state.update(state)
        chunk = AIMessageChunk(content="你好")
        yield {
            "event": "on_chat_model_stream",
            "data": {"chunk": chunk},
            "metadata": {"langgraph_node": "policy_agent", "tags": ["user_visible"]},
        }
        yield {
            "event": "on_chain_end",
            "data": {"output": {"answer": "这是最终答案"}},
            "metadata": {"langgraph_node": "policy_agent"},
        }

    mock_app_graph = AsyncMock()
    mock_app_graph.astream_events = mock_astream_events

    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = mock_app_graph
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试问题", "thread_id": "thread-1"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original

    assert response.status_code == 200
    text = response.text
    assert "data: " in text
    assert "[DONE]" in text
    assert json.dumps({"token": "你好"}, ensure_ascii=False) in text
    assert json.dumps({"token": "这是最终答案"}, ensure_ascii=False) in text
    assert set(received_state.keys()) == EXPECTED_AGENT_STATE_KEYS


@pytest.mark.asyncio
async def test_chat_metadata_streaming(client, auth_token):
    """置信度元数据在 [DONE] 前发送"""

    received_state = {}

    async def mock_astream_events(state, config, version):
        received_state.update(state)
        yield {
            "event": "on_chain_end",
            "data": {
                "output": {
                    "confidence_score": 0.85,
                    "confidence_signals": {"rag": {"score": 0.9}},
                    "needs_human_transfer": False,
                    "transfer_reason": None,
                    "audit_level": "auto",
                }
            },
            "metadata": {"langgraph_node": "decider_node"},
        }

    mock_app_graph = AsyncMock()
    mock_app_graph.astream_events = mock_astream_events

    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = mock_app_graph
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试", "thread_id": "thread-2"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original

    assert response.status_code == 200
    text = response.text
    assert '"type": "metadata"' in text
    assert '"confidence_score": 0.85' in text
    assert '"confidence_level": "high"' in text
    assert "[DONE]" in text
    metadata_pos = text.find('"type": "metadata"')
    done_pos = text.find("[DONE]")
    assert metadata_pos != -1
    assert done_pos != -1
    assert metadata_pos < done_pos
    assert set(received_state.keys()) == EXPECTED_AGENT_STATE_KEYS


@pytest.mark.asyncio
async def test_chat_503_when_app_graph_none(client, auth_token):
    """app_graph 为 None 时返回 503"""
    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = None
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试", "thread_id": "thread-3"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original

    assert response.status_code == 503
    assert "not fully initialized" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_connection_reset_handled_as_disconnect(client, auth_token):
    """astream_events 抛出 ConnectionResetError 时视为客户端断开，返回空流"""

    received_state = {}

    class _ErrorIter:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise ConnectionResetError("boom")

    def _make_error_iter(state, config, version):
        received_state.update(state)
        return _ErrorIter()

    mock_app_graph = AsyncMock()
    mock_app_graph.astream_events = _make_error_iter

    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = mock_app_graph
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试", "thread_id": "thread-4"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original

    assert response.status_code == 200
    assert response.text == ""
    assert set(received_state.keys()) == EXPECTED_AGENT_STATE_KEYS


@pytest.mark.asyncio
async def test_chat_cancelled_error_propagates(client, auth_token):
    """astream_events 抛出 CancelledError 时重新抛出，不进入通用异常处理"""

    received_state = {}

    class _CancelIter:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise asyncio.CancelledError()

    def _make_cancel_iter(state, config, version):
        received_state.update(state)
        return _CancelIter()

    mock_app_graph = AsyncMock()
    mock_app_graph.astream_events = _make_cancel_iter

    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = mock_app_graph
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试", "thread_id": "thread-5"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original

    assert response.status_code == 200
    assert response.text == ""
    assert set(received_state.keys()) == EXPECTED_AGENT_STATE_KEYS


@pytest.mark.asyncio
async def test_chat_generic_error_handled(client, auth_token):
    """astream_events 抛出未捕获通用异常时，SSE 流应返回错误消息并正常结束"""

    received_state = {}

    class _ErrorIter:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise RuntimeError("模拟内部错误")

    def _make_error_iter(state, config, version):
        received_state.update(state)
        return _ErrorIter()

    mock_app_graph = AsyncMock()
    mock_app_graph.astream_events = _make_error_iter

    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = mock_app_graph
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试", "thread_id": "thread-6"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original

    assert response.status_code == 200
    text = response.text
    assert '"error"' in text
    assert "[DONE]" in text
    assert set(received_state.keys()) == EXPECTED_AGENT_STATE_KEYS
