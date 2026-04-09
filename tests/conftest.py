import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlmodel import SQLModel

from app.core.database import engine
from app.core.limiter import limiter
from app.main import app


@pytest_asyncio.fixture(scope="session", autouse=True)
async def db_setup():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with engine.begin() as conn:
        # Drop any unmapped tables that have foreign-key constraints
        # preventing SQLModel.metadata.drop_all from succeeding.
        await conn.execute(text("DROP TABLE IF EXISTS confidence_audits CASCADE"))
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    limiter.reset()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
