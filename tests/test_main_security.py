"""
Tests for app/main.py production-security hardening.
"""

import importlib
import sys

import pytest

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

        with pytest.raises(RuntimeError, match=r"CORS allow_origins=\['\*'\] is not allowed"):
            importlib.import_module(MODULE_NAME)


class TestOpenAPIDocsControl:
    def test_openapi_docs_disabled_by_default(self, monkeypatch):
        """When ENABLE_OPENAPI_DOCS=False, docs endpoints should be disabled."""
        monkeypatch.setattr(settings, "ENABLE_OPENAPI_DOCS", False)

        mod = importlib.import_module(MODULE_NAME)
        app = mod.app

        assert app.openapi_url is None
        assert app.docs_url is None
        assert app.redoc_url is None

    def test_openapi_docs_enabled_when_configured(self, monkeypatch):
        """When ENABLE_OPENAPI_DOCS=True, docs endpoints should be available."""
        monkeypatch.setattr(settings, "ENABLE_OPENAPI_DOCS", True)

        mod = importlib.import_module(MODULE_NAME)
        app = mod.app

        assert app.openapi_url == "/openapi.json"
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"
