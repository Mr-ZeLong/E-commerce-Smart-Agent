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


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def db_setup():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
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
    client._test_prefix = prefix
    try:
        yield client
    finally:
        keys = []
        async for key in client.scan_iter(match=f"{prefix}*"):
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
    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
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
        key = os.environ.get("OPENAI_API_KEY", "")
        if key in ("", "sk-test", "dummy"):
            pytest.skip("OPENAI_API_KEY not set or is a dummy value")
