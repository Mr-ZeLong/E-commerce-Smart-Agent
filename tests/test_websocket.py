import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.core.utils import build_thread_id
from app.main import app
from app.websocket.manager import ConnectionManager


class TestBuildThreadId:
    def test_adds_user_prefix(self):
        assert build_thread_id(42, "thread-abc") == "42__thread-abc"

    def test_sanitizes_unsafe_characters(self):
        assert build_thread_id(1, "thread/abc@!") == "1__thread_abc__"

    def test_idempotent_when_already_prefixed(self):
        scoped = "99__existing"
        assert build_thread_id(99, scoped) == scoped

    def test_truncates_long_id(self):
        long_id = "x" * 200
        result = build_thread_id(1, long_id)
        assert len(result) <= 128
        assert result.startswith("1__")


class TestWebsocketSecurity:
    @pytest.fixture(autouse=True)
    def setup_client(self):
        app.state.manager = ConnectionManager()
        self.client = TestClient(app)

    def test_connect_user_scopes_thread_id(self):
        """WebSocket endpoint 应通过 build_thread_id 限定 thread_id。"""
        token = create_access_token(user_id=7, is_admin=False)
        thread_id = "my-thread"
        expected_scoped = build_thread_id(7, thread_id)

        with self.client.websocket_connect(f"/api/v1/ws/{thread_id}?token={token}"):
            assert 7 in app.state.manager.active_connections
            assert expected_scoped in app.state.manager.active_connections[7]

    def test_user_b_cannot_access_user_a_scoped_thread(self):
        """验证用户B无法订阅或访问用户A的限定线程。"""
        token_a = create_access_token(user_id=1, is_admin=False)
        token_b = create_access_token(user_id=2, is_admin=False)
        thread_id = "shared-thread"

        with (
            self.client.websocket_connect(f"/api/v1/ws/{thread_id}?token={token_a}"),
            self.client.websocket_connect(f"/api/v1/ws/{thread_id}?token={token_b}"),
        ):
            scoped_a = build_thread_id(1, thread_id)
            scoped_b = build_thread_id(2, thread_id)

            assert scoped_a in app.state.manager.thread_subscribers
            assert scoped_b in app.state.manager.thread_subscribers
            assert (
                app.state.manager.thread_subscribers[scoped_a]
                != app.state.manager.thread_subscribers[scoped_b]
            )

    def test_invalid_token_does_not_leak_details(self):
        """无效 Token 时不应向客户端暴露内部错误详情。"""
        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            self.client.websocket_connect("/api/v1/ws/some-thread?token=bad-token") as websocket,
        ):
            websocket.receive_text()

        assert exc_info.value.code == 1008
        assert exc_info.value.reason == "Authentication failed"

    def test_admin_invalid_token_does_not_leak_details(self):
        """管理员端点无效 Token 时不应向客户端暴露内部错误详情。"""
        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            self.client.websocket_connect("/api/v1/ws/admin/1?token=bad-token") as websocket,
        ):
            websocket.receive_text()

        assert exc_info.value.code == 1008
        assert exc_info.value.reason == "Authentication failed"

    def test_admin_id_mismatch_does_not_leak_details(self):
        """管理员 ID 不匹配时不应向客户端暴露内部错误详情。"""
        token = create_access_token(user_id=5, is_admin=True)
        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            self.client.websocket_connect(f"/api/v1/ws/admin/999?token={token}") as websocket,
        ):
            websocket.receive_text()

        assert exc_info.value.code == 1008
        assert exc_info.value.reason == "Authentication failed"
