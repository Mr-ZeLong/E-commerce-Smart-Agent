# app/core/database.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

# 1. 创建异步引擎
# echo=True 会打印 SQL 日志，方便调试，生产环境请关掉
engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)

# 2. 创建 Session 工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 3. FastAPI 依赖注入函数 (Dependency)
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

# engine and session factory are ready for use
