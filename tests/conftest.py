import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from qdrant_client import AsyncQdrantClient
from sqlmodel import Session, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models as _models  # noqa: F401  ensures all models are registered in SQLModel.metadata
import tests._db_config  # noqa: F401, I001
from app.core.config import settings
from app.core.database import async_engine, sync_engine
from app.core.limiter import limiter
from app.core.redis import create_redis_client
from app.main import app
from app.websocket.manager import ConnectionManager
from tests._llm import DeterministicChatModel


@pytest.fixture(scope="session")
def real_llm():
    """Provide a real LLM instance for tests that require actual model inference.

    Skips the test if no valid API key is configured. Uses a lower-cost model
    for testing to control costs while still exercising real LLM behavior.
    """
    key = settings.OPENAI_API_KEY.get_secret_value()
    dashscope_key = settings.DASHSCOPE_API_KEY.get_secret_value()
    if key in ("", "sk-test", "dummy") and dashscope_key in ("", "sk-test", "dummy"):
        pytest.skip("OPENAI_API_KEY or DASHSCOPE_API_KEY not set or is a dummy value")

    from app.core.llm_factory import create_llm

    test_model = os.environ.get("TEST_LLM_MODEL", "qwen-turbo")
    return create_llm(test_model, temperature=0.0, timeout=30.0)


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def db_setup():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield


@pytest_asyncio.fixture(scope="function", autouse=True, loop_scope="session")
async def _truncate_leaky_tables():
    from sqlalchemy import text

    async with async_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE message_feedbacks, quality_scores, review_tickets, token_usage_logs, optimization_suggestions, graph_execution_logs, graph_node_logs RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest_asyncio.fixture(loop_scope="function")
async def client():
    limiter.reset()
    app.state.manager = ConnectionManager()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def db_session():
    async with async_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        await session.begin_nested()
        try:
            yield session
        finally:
            await session.rollback()
            await conn.rollback()
            await session.close()


@pytest.fixture
def db_sync_session():
    with sync_engine.connect() as conn:
        trans = conn.begin()
        session = Session(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            session.close()
            trans.rollback()


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def redis_client():
    client = create_redis_client()
    prefix = f"test:{uuid.uuid4().hex}:"
    object.__setattr__(client, "_test_prefix", prefix)
    try:
        yield client
    finally:
        keys = []
        stored_prefix = object.__getattribute__(client, "_test_prefix")
        async for key in client.scan_iter(match=f"{stored_prefix}*"):
            keys.append(key)
        if keys:
            await client.delete(*keys)
        await client.aclose()


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def redis_checkpointer(redis_client):
    from langgraph.checkpoint.redis import AsyncRedisSaver

    keys = []
    async for key in redis_client.scan_iter(match="checkpoint*"):
        keys.append(key)
    if keys:
        await redis_client.delete(*keys)

    saver = AsyncRedisSaver(redis_client=redis_client)
    await saver.setup()
    yield saver


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def qdrant_client():
    qdrant_key = settings.QDRANT_API_KEY.get_secret_value()
    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=qdrant_key if qdrant_key else None,
        timeout=settings.QDRANT_TIMEOUT,
    )
    collection_name = f"test_{uuid.uuid4().hex}"
    try:
        yield client, collection_name
    finally:
        await client.delete_collection(collection_name)
        await client.close()


@pytest.fixture
def deterministic_llm():
    return DeterministicChatModel()


def pytest_runtest_setup(item):
    if any(mark.name == "requires_llm" for mark in item.iter_markers()):
        key = settings.OPENAI_API_KEY.get_secret_value()
        dashscope_key = settings.DASHSCOPE_API_KEY.get_secret_value()
        if key in ("", "sk-test", "dummy") and dashscope_key in ("", "sk-test", "dummy"):
            pytest.skip("OPENAI_API_KEY or DASHSCOPE_API_KEY not set or is a dummy value")
