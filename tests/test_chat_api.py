import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessageChunk

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.models.user import User


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
        token = create_access_token(user_id=user.id, is_admin=False)

    yield token


@pytest.mark.asyncio
async def test_chat_normal_streaming(client, auth_token):
    """正常流式响应：包含 token、answer 和 [DONE]"""

    async def mock_astream_events(state, config, version):
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

    with patch("app.graph.workflow.app_graph", mock_app_graph):
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试问题", "thread_id": "thread-1"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    assert response.status_code == 200
    text = response.text
    assert "data: " in text
    assert "[DONE]" in text
    assert json.dumps({"token": "你好"}, ensure_ascii=False) in text
    assert json.dumps({"token": "这是最终答案"}, ensure_ascii=False) in text


@pytest.mark.asyncio
async def test_chat_metadata_streaming(client, auth_token):
    """置信度元数据在 [DONE] 前发送"""

    async def mock_astream_events(state, config, version):
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

    with patch("app.graph.workflow.app_graph", mock_app_graph):
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试", "thread_id": "thread-2"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    assert response.status_code == 200
    text = response.text
    assert '"type": "metadata"' in text
    assert '"confidence_score": 0.85' in text
    assert '"confidence_level": "high"' in text
    assert "[DONE]" in text
    # 元数据应在 [DONE] 之前
    metadata_pos = text.find('"type": "metadata"')
    done_pos = text.find("[DONE]")
    assert metadata_pos != -1
    assert done_pos != -1
    assert metadata_pos < done_pos


@pytest.mark.asyncio
async def test_chat_503_when_app_graph_none(client, auth_token):
    """app_graph 为 None 时返回 503"""
    with patch("app.graph.workflow.app_graph", None):
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试", "thread_id": "thread-3"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    assert response.status_code == 503
    assert "not fully initialized" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_exception_handling(client, auth_token):
    """astream_events 抛出 Exception 时返回 SSE error payload"""

    class _ErrorIter:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise RuntimeError("boom")

    mock_app_graph = AsyncMock()
    mock_app_graph.astream_events = lambda state, config, version: _ErrorIter()

    with patch("app.graph.workflow.app_graph", mock_app_graph):
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试", "thread_id": "thread-4"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    assert response.status_code == 200
    assert '{"error": "系统处理出现问题，请稍后重试"}' in response.text


@pytest.mark.asyncio
async def test_chat_cancelled_error_propagates(client, auth_token):
    """astream_events 抛出 CancelledError 时重新抛出，不进入通用异常处理"""

    class _CancelIter:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise asyncio.CancelledError()

    mock_app_graph = AsyncMock()
    mock_app_graph.astream_events = lambda state, config, version: _CancelIter()

    with patch("app.graph.workflow.app_graph", mock_app_graph):
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试", "thread_id": "thread-5"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    # CancelledError 被重新抛出后，ASGI 层中断流，客户端收到空响应
    # 与通用异常处理（返回 error payload）区分
    assert response.status_code == 200
    # CancelledError causes the ASGI server to abort the stream, leaving the response body empty
    assert response.text == ""
