"""
Chat API 集成测试

测试 Chat API 端点的 SSE 流式响应、置信度元数据和转人工流程
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.api.v1.chat import router as chat_router
from app.api.v1.schemas import ChatRequest
from app.core.security import create_access_token


class TestChatAPIEndpoints:
    """测试 Chat API 端点"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        test_app = FastAPI()
        test_app.include_router(chat_router, prefix="/api/v1")
        return test_app

    @pytest.fixture
    def client(self, app):
        """创建同步测试客户端"""
        return TestClient(app)

    @pytest_asyncio.fixture
    async def async_client(self, app):
        """创建异步测试客户端"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    def auth_token(self):
        """生成测试用认证 Token"""
        return create_access_token(user_id=1, is_admin=False)

    @pytest.fixture
    def auth_headers(self, auth_token):
        """生成带认证的请求头"""
        return {"Authorization": f"Bearer {auth_token}"}

    @pytest.mark.asyncio
    async def test_chat_sse_stream_response(self, async_client, auth_headers):
        """
        测试聊天 API 的 SSE 流式响应

        场景：正常聊天请求
        预期：返回 SSE 流，包含 tokens，最后包含 [DONE]
        """
        # Mock app_graph - patch where it's defined/imported
        mock_events = [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="你")},
                "metadata": {"tags": ["user_visible"]},
            },
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="好")},
                "metadata": {"tags": ["user_visible"]},
            },
            {
                "event": "on_chain_end",
                "data": {
                    "output": {
                        "confidence_score": 0.85,
                        "confidence_signals": {
                            "rag": {"score": 0.9, "reason": "高相似度"},
                            "llm": {"score": 0.85, "reason": "回答完整"},
                            "emotion": {"score": 0.8, "reason": "中性"},
                        },
                        "needs_human_transfer": False,
                        "audit_level": "none",
                    }
                },
            },
        ]

        # Patch the module where app_graph is defined
        async def mock_event_generator(*args, **kwargs):
            for event in mock_events:
                yield event

        with patch(
            "app.graph.workflow.app_graph"
        ) as mock_graph:
            mock_graph.astream_events = mock_event_generator

            response = await async_client.post(
                "/api/v1/chat",
                json={"question": "你好", "thread_id": "test_thread"},
                headers=auth_headers,
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

            # 解析 SSE 响应
            content = response.text
            assert '{"token": "你"}' in content
            assert '{"token": "好"}' in content
            assert "data: [DONE]" in content

    @pytest.mark.asyncio
    async def test_chat_response_with_metadata(self, async_client, auth_headers):
        """
        测试响应包含置信度元数据

        场景：正常聊天请求
        预期：SSE 流结束前包含元数据消息
        """
        mock_events = [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="满")},
                "metadata": {"tags": ["user_visible"]},
            },
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="100")},
                "metadata": {"tags": ["user_visible"]},
            },
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="免运费")},
                "metadata": {"tags": ["user_visible"]},
            },
            {
                "event": "on_chain_end",
                "data": {
                    "output": {
                        "confidence_score": 0.9,
                        "confidence_signals": {
                            "rag": {"score": 0.95, "reason": "高相似度匹配"},
                            "llm": {"score": 0.9, "reason": "回答完整"},
                            "emotion": {"score": 0.85, "reason": "中性情绪"},
                        },
                        "needs_human_transfer": False,
                        "transfer_reason": None,
                        "audit_level": "none",
                    }
                },
            },
        ]

        async def mock_event_generator(*args, **kwargs):
            for event in mock_events:
                yield event

        with patch(
            "app.graph.workflow.app_graph"
        ) as mock_graph:
            mock_graph.astream_events = mock_event_generator

            response = await async_client.post(
                "/api/v1/chat",
                json={"question": "运费怎么算？", "thread_id": "test_thread"},
                headers=auth_headers,
            )

            assert response.status_code == 200

            # 解析并验证元数据
            content = response.text
            lines = content.strip().split("\n\n")

            # 找到元数据行
            metadata_found = False
            for line in lines:
                if line.startswith("data: {") and "confidence_score" in line:
                    metadata_found = True
                    data_str = line[6:]  # 去掉 "data: " 前缀
                    metadata = json.loads(data_str)
                    assert metadata["type"] == "metadata"
                    assert metadata["confidence_score"] == 0.9
                    assert metadata["confidence_level"] == "high"
                    assert metadata["needs_human_transfer"] is False
                    assert metadata["audit_level"] == "none"
                    break

            assert metadata_found, "Metadata not found in response"

    @pytest.mark.asyncio
    async def test_chat_human_transfer_flow(self, async_client, auth_headers):
        """
        测试转人工流程的 API 响应

        场景：低置信度触发转人工
        预期：响应包含转人工标记和原因
        """
        mock_events = [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="非常抱歉")},
                "metadata": {"tags": ["user_visible"]},
            },
            {
                "event": "on_chain_end",
                "data": {
                    "output": {
                        "confidence_score": 0.35,
                        "confidence_signals": {
                            "rag": {"score": 0.3, "reason": "低相似度"},
                            "llm": {"score": 0.4, "reason": "不确定"},
                            "emotion": {"score": 0.35, "reason": "轻微不满"},
                        },
                        "needs_human_transfer": True,
                        "transfer_reason": "置信度不足",
                        "audit_level": "manual",
                    }
                },
            },
        ]

        async def mock_event_generator(*args, **kwargs):
            for event in mock_events:
                yield event

        with patch(
            "app.graph.workflow.app_graph"
        ) as mock_graph:
            mock_graph.astream_events = mock_event_generator

            response = await async_client.post(
                "/api/v1/chat",
                json={"question": "模糊问题", "thread_id": "test_thread"},
                headers=auth_headers,
            )

            assert response.status_code == 200

            # 验证转人工标记
            content = response.text
            assert "needs_human_transfer" in content

            lines = content.strip().split("\n\n")
            for line in lines:
                if line.startswith("data: {") and "confidence_score" in line:
                    data_str = line[6:]
                    metadata = json.loads(data_str)
                    assert metadata["needs_human_transfer"] is True
                    assert metadata["transfer_reason"] == "置信度不足"
                    assert metadata["audit_level"] == "manual"
                    assert metadata["confidence_level"] == "low"
                    break

    @pytest.mark.asyncio
    async def test_chat_unauthorized(self, async_client):
        """
        测试未授权访问

        场景：请求未携带 Token
        预期：返回 401 未授权错误
        """
        response = await async_client.post(
            "/api/v1/chat",
            json={"question": "你好", "thread_id": "test_thread"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_invalid_token(self, async_client):
        """
        测试无效 Token

        场景：请求携带无效的 Token
        预期：返回 401 未授权错误
        """
        response = await async_client.post(
            "/api/v1/chat",
            json={"question": "你好", "thread_id": "test_thread"},
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_service_unavailable(self, async_client, auth_headers):
        """
        测试服务不可用

        场景：app_graph 未初始化
        预期：返回 503 服务不可用错误
        """
        # Patch app_graph to None at the module level
        with patch("app.graph.workflow.app_graph", None):
            response = await async_client.post(
                "/api/v1/chat",
                json={"question": "你好", "thread_id": "test_thread"},
                headers=auth_headers,
            )

            assert response.status_code == 503
            assert "not fully initialized" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_chat_error_handling(self, async_client, auth_headers):
        """
        测试错误处理

        场景：流处理过程中发生错误
        预期：返回包含错误信息的 SSE 事件
        """
        async def error_generator(*args, **kwargs):
            raise Exception("测试错误")

        with patch(
            "app.graph.workflow.app_graph"
        ) as mock_graph:
            mock_graph.astream_events = error_generator

            response = await async_client.post(
                "/api/v1/chat",
                json={"question": "测试", "thread_id": "test_thread"},
                headers=auth_headers,
            )

            # 即使出错也应该返回 200，错误信息在 SSE 中
            assert response.status_code == 200
            assert "error" in response.text.lower()


class TestChatRequestValidation:
    """测试聊天请求验证"""

    @pytest.mark.asyncio
    async def test_chat_request_schema(self):
        """
        测试聊天请求 Schema

        验证请求参数的正确性
        """
        # 有效请求
        request = ChatRequest(
            question="测试问题",
            thread_id="test_thread_123",
        )
        assert request.question == "测试问题"
        assert request.thread_id == "test_thread_123"

        # 默认 thread_id
        request_default = ChatRequest(question="测试")
        assert request_default.thread_id == "default_thread"


class TestChatMetadataContent:
    """测试聊天元数据内容"""

    @pytest.mark.asyncio
    async def test_confidence_signals_detail(self, async_client, auth_headers):
        """
        测试置信度信号详情

        验证元数据包含完整的信号信息
        """
        mock_events = [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="回答")},
                "metadata": {"tags": ["user_visible"]},
            },
            {
                "event": "on_chain_end",
                "data": {
                    "output": {
                        "confidence_score": 0.75,
                        "confidence_signals": {
                            "rag": {
                                "score": 0.8,
                                "reason": "检索质量良好",
                            },
                            "llm": {
                                "score": 0.7,
                                "reason": "回答完整",
                            },
                            "emotion": {
                                "score": 0.75,
                                "reason": "无明显情绪",
                            },
                        },
                        "needs_human_transfer": False,
                        "audit_level": "auto",
                    }
                },
            },
        ]

        async def mock_event_generator(*args, **kwargs):
            for event in mock_events:
                yield event

        with patch(
            "app.graph.workflow.app_graph"
        ) as mock_graph:
            mock_graph.astream_events = mock_event_generator

            response = await async_client.post(
                "/api/v1/chat",
                json={"question": "测试", "thread_id": "test"},
                headers=auth_headers,
            )

            content = response.text
            lines = content.strip().split("\n\n")

            for line in lines:
                if line.startswith("data: {") and "confidence_signals" in line:
                    data_str = line[6:]
                    metadata = json.loads(data_str)

                    # 验证信号详情
                    signals = metadata.get("confidence_signals", {})
                    assert "rag" in signals
                    assert "llm" in signals
                    assert "emotion" in signals

                    assert signals["rag"]["score"] == 0.8
                    assert signals["rag"]["reason"] == "检索质量良好"
                    break

    @pytest.mark.asyncio
    async def test_confidence_level_calculation(self, async_client, auth_headers):
        """
        测试置信度等级计算

        验证不同分数对应正确的等级
        """
        test_cases = [
            (0.9, "high"),
            (0.75, "medium"),
            (0.5, "low"),
        ]

        for score, expected_level in test_cases:
            mock_events = [
                {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": MagicMock(content="回答")},
                    "metadata": {"tags": ["user_visible"]},
                },
                {
                    "event": "on_chain_end",
                    "data": {
                        "output": {
                            "confidence_score": score,
                            "confidence_signals": {},
                            "needs_human_transfer": score < 0.6,
                            "audit_level": "manual" if score < 0.5 else "auto",
                        }
                    },
                },
            ]

            async def mock_event_generator(*args, _events=mock_events, **kwargs):
                for event in _events:
                    yield event

            with patch(
                "app.graph.workflow.app_graph"
            ) as mock_graph:
                mock_graph.astream_events = mock_event_generator

                response = await async_client.post(
                    "/api/v1/chat",
                    json={"question": "测试", "thread_id": f"test_{score}"},
                    headers=auth_headers,
                )

                content = response.text
                lines = content.strip().split("\n\n")

                for line in lines:
                    if line.startswith("data: {") and "confidence_level" in line:
                        data_str = line[6:]
                        metadata = json.loads(data_str)
                        assert metadata["confidence_level"] == expected_level
                        break


class TestChatStreamingBehavior:
    """测试聊天流式行为"""

    @pytest.mark.asyncio
    async def test_stream_token_sequence(self, async_client, auth_headers):
        """
        测试 Token 序列

        验证 tokens 按正确顺序发送
        """
        tokens = ["订", "单", "已", "发", "货"]
        mock_events: list[dict] = [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content=token)},
                "metadata": {"tags": ["user_visible"]},
            }
            for token in tokens
        ]
        # 添加结束事件
        mock_events.append({
            "event": "on_chain_end",
            "data": {"output": {"confidence_score": 0.9}},
        })

        async def mock_event_generator(*args, **kwargs):
            for event in mock_events:
                yield event

        with patch(
            "app.graph.workflow.app_graph"
        ) as mock_graph:
            mock_graph.astream_events = mock_event_generator

            response = await async_client.post(
                "/api/v1/chat",
                json={"question": "测试", "thread_id": "test"},
                headers=auth_headers,
            )

            content = response.text

            # 验证每个 token 都在响应中
            for token in tokens:
                assert f'"token": "{token}"' in content

    @pytest.mark.asyncio
    async def test_stream_done_marker(self, async_client, auth_headers):
        """
        测试 [DONE] 标记

        验证流正常结束
        """
        mock_events = [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="完成")},
                "metadata": {"tags": ["user_visible"]},
            },
            {
                "event": "on_chain_end",
                "data": {"output": {"confidence_score": 0.9}},
            },
        ]

        async def mock_event_generator(*args, **kwargs):
            for event in mock_events:
                yield event

        with patch(
            "app.graph.workflow.app_graph"
        ) as mock_graph:
            mock_graph.astream_events = mock_event_generator

            response = await async_client.post(
                "/api/v1/chat",
                json={"question": "测试", "thread_id": "test"},
                headers=auth_headers,
            )

            content = response.text

            # 验证 [DONE] 标记
            assert "data: [DONE]" in content
            # 验证 [DONE] 在最后
            lines = [line for line in content.strip().split("\n") if line]
            assert lines[-1] == "data: [DONE]"
