from datetime import UTC, datetime

import pytest
from sqlmodel import select

from app.core.database import async_session_maker, engine
from app.models.user import User


async def init_db():
    from sqlmodel import SQLModel

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


@pytest.mark.asyncio
async def test_create_and_query_user():
    await init_db()
    async with async_session_maker() as session:
        # 清理可能存在的旧测试数据
        result = await session.exec(select(User).where(User.username == "test_alice_pytest"))
        existing = result.one_or_none()
        if existing:
            await session.delete(existing)
            await session.commit()

        now = datetime.now(UTC).replace(tzinfo=None)
        user = User(
            username="test_alice_pytest",
            email="alice_pytest@test.com",
            full_name="Alice Test",
            phone="13800138001",
            password_hash="fakehash",
            is_admin=False,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        result = await session.exec(select(User).where(User.username == "test_alice_pytest"))
        found = result.one_or_none()
        assert found is not None
        assert found.email == "alice_pytest@test.com"
