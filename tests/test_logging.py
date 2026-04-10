import logging
import re
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.logging import (
    CorrelationIdFilter,
    correlation_id,
    generate_correlation_id,
    set_correlation_id,
)
from app.main import app


@pytest.fixture(autouse=True)
def reset_correlation_id():
    yield
    correlation_id.set(None)


class TestCorrelationIdFilter:
    def test_injects_correlation_id_into_record(self):
        filter_ = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        set_correlation_id("abc123")
        result = filter_.filter(record)

        assert result is True
        assert getattr(record, "correlation_id") == "abc123"  # noqa: B009

    def test_defaults_to_dash_when_no_correlation_id(self):
        filter_ = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        # Reset contextvar to default
        correlation_id.set(None)
        result = filter_.filter(record)

        assert result is True
        assert getattr(record, "correlation_id") == "-"  # noqa: B009


class TestSetCorrelationId:
    def test_sets_contextvar_value(self):
        set_correlation_id("ctx-value-42")
        assert correlation_id.get() == "ctx-value-42"

    def test_overwrites_existing_value(self):
        set_correlation_id("first")
        set_correlation_id("second")
        assert correlation_id.get() == "second"


class TestGenerateCorrelationId:
    def test_returns_16_character_hex_string(self):
        cid = generate_correlation_id()
        assert isinstance(cid, str)
        assert len(cid) == 16
        assert re.fullmatch(r"[0-9a-f]{16}", cid) is not None


class TestMiddlewareIntegration:
    @pytest.mark.asyncio
    async def test_middleware_returns_correlation_id(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert "X-Correlation-ID" in response.headers
            assert len(response.headers["X-Correlation-ID"]) == 16

    @pytest.mark.asyncio
    async def test_middleware_echoes_provided_correlation_id(self):
        custom_cid = "abcd1234efgh5678"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health", headers={"X-Correlation-ID": custom_cid})
            assert response.status_code == 200
            assert response.headers["X-Correlation-ID"] == custom_cid


class TestWebSocketCorrelationId:
    def test_websocket_sets_correlation_id(self):
        from starlette.testclient import TestClient

        with patch("app.api.v1.websocket.set_correlation_id") as mock_set:
            test_client = TestClient(app)
            try:
                with test_client.websocket_connect("/api/v1/ws/test-thread"):
                    pass
            except Exception:
                pass
            mock_set.assert_called_once()
            cid = mock_set.call_args[0][0]
            assert isinstance(cid, str)
            assert len(cid) == 16

    def test_websocket_echoes_provided_correlation_id(self):
        from starlette.testclient import TestClient

        with patch("app.api.v1.websocket.set_correlation_id") as mock_set:
            test_client = TestClient(app)
            try:
                with test_client.websocket_connect(
                    "/api/v1/ws/test-thread",
                    headers={"X-Correlation-ID": "my-custom-cid-1234"},
                ):
                    pass
            except Exception:
                pass
            mock_set.assert_called_once_with("my-custom-cid-1234")
