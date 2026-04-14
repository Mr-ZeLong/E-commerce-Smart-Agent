import tests._db_config  # noqa: F401, I001

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlmodel import SQLModel

import app.models as _models  # noqa: F401  ensures all models are registered in SQLModel.metadata
from app.core.database import async_engine
from app.core.limiter import limiter
from app.main import app
from app.websocket.manager import ConnectionManager


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def db_setup():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS experiment_events CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS confidence_audits CASCADE"))
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest_asyncio.fixture(loop_scope="function")
async def client():
    limiter.reset()
    app.state.manager = ConnectionManager()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
