"""
Tests for app/main.py production-security hardening.
"""

import importlib
import sys

import httpx
import pytest
from httpx import ASGITransport

from app.core.config import settings

# Ensure app.main can be reloaded for each test
MODULE_NAME = "app.main"


@pytest.fixture(autouse=True)
def reset_module():
    """Remove app.main from sys.modules so each test gets a fresh import."""
    sys.modules.pop(MODULE_NAME, None)
    yield
    sys.modules.pop(MODULE_NAME, None)


class TestCORSDangerousComboBlock:
    def test_wildcard_cors_with_credentials_raises_runtime_error(self, monkeypatch):
        """Wildcard CORS origins combined with allow_credentials=True must fail fast."""
        monkeypatch.setattr(settings, "CORS_ORIGINS", ["*"])

        with pytest.raises(RuntimeError, match=r"CORS allow_origins=\['\*'\] combined with allow_credentials=True is not allowed"):
            importlib.import_module(MODULE_NAME)

    def test_mixed_origins_with_wildcard_raises_runtime_error(self, monkeypatch):
        """Mixed CORS origins containing wildcard must also fail fast."""
        monkeypatch.setattr(settings, "CORS_ORIGINS", ["*", "http://localhost"])

        with pytest.raises(RuntimeError, match=r"CORS allow_origins=\['\*'\] combined with allow_credentials=True is not allowed"):
            importlib.import_module(MODULE_NAME)


class TestOpenAPIDocsControl:
    @pytest.mark.asyncio
    async def test_openapi_docs_disabled_by_default(self, monkeypatch):
        """When ENABLE_OPENAPI_DOCS=False, docs endpoints should be disabled."""
        monkeypatch.setattr(settings, "ENABLE_OPENAPI_DOCS", False)

        mod = importlib.import_module(MODULE_NAME)
        app = mod.app

        assert app.openapi_url is None
        assert app.docs_url is None
        assert app.redoc_url is None

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in ("/docs", "/redoc", "/openapi.json"):
                response = await client.get(path)
                assert response.status_code == 404, f"Expected 404 for {path}, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_openapi_docs_enabled_when_configured(self, monkeypatch):
        """When ENABLE_OPENAPI_DOCS=True, docs endpoints should be available."""
        monkeypatch.setattr(settings, "ENABLE_OPENAPI_DOCS", True)

        mod = importlib.import_module(MODULE_NAME)
        app = mod.app

        assert app.openapi_url == "/openapi.json"
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in ("/docs", "/redoc", "/openapi.json"):
                response = await client.get(path)
                assert response.status_code == 200, f"Expected 200 for {path}, got {response.status_code}"
