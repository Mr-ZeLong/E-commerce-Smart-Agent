import logging
import re

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

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


class _CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


class TestWebSocketCorrelationId:
    def test_websocket_sets_correlation_id(self):
        logger = logging.getLogger("app.api.v1.websocket")
        handler = _CaptureHandler()
        handler.addFilter(CorrelationIdFilter())
        logger.addHandler(handler)
        try:
            test_client = TestClient(app)
            try:
                with test_client.websocket_connect("/api/v1/ws/test-thread?token=invalid-token"):
                    pass
            except Exception:
                pass

            assert len(handler.records) > 0
            cid = getattr(handler.records[0], "correlation_id", None)
            assert isinstance(cid, str)
            assert len(cid) == 16
            assert cid != "-"
        finally:
            logger.removeHandler(handler)

    def test_websocket_echoes_provided_correlation_id(self):
        logger = logging.getLogger("app.api.v1.websocket")
        handler = _CaptureHandler()
        handler.addFilter(CorrelationIdFilter())
        logger.addHandler(handler)
        try:
            test_client = TestClient(app)
            try:
                with test_client.websocket_connect(
                    "/api/v1/ws/test-thread?token=invalid-token",
                    headers={"X-Correlation-ID": "my-custom-cid-1234"},
                ):
                    pass
            except Exception:
                pass

            assert len(handler.records) > 0
            cid = getattr(handler.records[0], "correlation_id", None)
            assert cid == "my-custom-cid-1234"
        finally:
            logger.removeHandler(handler)
