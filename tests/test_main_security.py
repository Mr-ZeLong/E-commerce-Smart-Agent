"""
Tests for app/main.py production-security hardening.
"""

import importlib
import os
import sys

import httpx
import pytest
from httpx import ASGITransport

# Ensure app.main can be reloaded for each test
MODULE_NAME = "app.main"
CONFIG_MODULE = "app.core.config"


from fastapi import FastAPI


@pytest.fixture(autouse=True)
def reset_module():
    """Remove app.main and app.core.config from sys.modules so each test gets a fresh import."""
    # Save original env vars
    orig_cors = os.environ.get("CORS_ORIGINS", None)
    orig_docs = os.environ.get("ENABLE_OPENAPI_DOCS", None)

    sys.modules.pop(MODULE_NAME, None)
    sys.modules.pop(CONFIG_MODULE, None)

    yield

    # Restore env vars
    if orig_cors is not None:
        os.environ["CORS_ORIGINS"] = orig_cors
    else:
        os.environ.pop("CORS_ORIGINS", None)

    if orig_docs is not None:
        os.environ["ENABLE_OPENAPI_DOCS"] = orig_docs
    else:
        os.environ.pop("ENABLE_OPENAPI_DOCS", None)

    sys.modules.pop(MODULE_NAME, None)
    sys.modules.pop(CONFIG_MODULE, None)


class TestCORSDangerousComboBlock:
    @pytest.mark.asyncio
    async def test_wildcard_cors_with_credentials_raises_runtime_error(self):
        """Wildcard CORS origins combined with allow_credentials=True must fail fast."""
        os.environ["CORS_ORIGINS"] = '["*"]'

        mod = importlib.import_module(MODULE_NAME)
        with pytest.raises(
            RuntimeError,
            match=r"CORS allow_origins=\['\*'\] combined with allow_credentials=True is not allowed",
        ):
            async with mod.lifespan(FastAPI()):
                pass

    @pytest.mark.asyncio
    async def test_mixed_origins_with_wildcard_raises_runtime_error(self):
        """Mixed CORS origins containing wildcard must also fail fast."""
        os.environ["CORS_ORIGINS"] = '["*", "http://localhost"]'

        mod = importlib.import_module(MODULE_NAME)
        with pytest.raises(
            RuntimeError,
            match=r"CORS allow_origins=\['\*'\] combined with allow_credentials=True is not allowed",
        ):
            async with mod.lifespan(FastAPI()):
                pass


class TestOpenAPIDocsControl:
    @pytest.mark.asyncio
    async def test_openapi_docs_disabled_by_default(self):
        """When ENABLE_OPENAPI_DOCS=False, docs endpoints should be disabled."""
        os.environ["ENABLE_OPENAPI_DOCS"] = "false"

        mod = importlib.import_module(MODULE_NAME)
        app = mod.app

        assert app.openapi_url is None
        assert app.docs_url is None
        assert app.redoc_url is None

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for path in ("/docs", "/redoc", "/openapi.json"):
                response = await client.get(path)
                assert response.status_code == 404, (
                    f"Expected 404 for {path}, got {response.status_code}"
                )

    @pytest.mark.asyncio
    async def test_openapi_docs_enabled_when_configured(self):
        """When ENABLE_OPENAPI_DOCS=True, docs endpoints should be available."""
        os.environ["ENABLE_OPENAPI_DOCS"] = "true"

        mod = importlib.import_module(MODULE_NAME)
        app = mod.app

        assert app.openapi_url == "/openapi.json"
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for path in ("/docs", "/redoc", "/openapi.json"):
                response = await client.get(path)
                assert response.status_code == 200, (
                    f"Expected 200 for {path}, got {response.status_code}"
                )
