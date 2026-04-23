"""Safety test fixtures — override DB fixtures since safety tests are stateless."""

import pytest


@pytest.fixture(scope="session")
def db_setup():
    """Override: safety tests do not need a database."""
    yield


@pytest.fixture(scope="function")
def _truncate_leaky_tables():
    """Override: safety tests do not need table truncation."""
    yield
