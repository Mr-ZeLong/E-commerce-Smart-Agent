import pytest


@pytest.fixture(scope="session", autouse=True)
def db_setup():
    """Override the global db_setup fixture to avoid database connections."""
    yield
