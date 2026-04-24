# app/core/database.py
from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

_async_connect_args = {
    "timeout": settings.DB_CONNECT_TIMEOUT,
    "server_settings": {"application_name": "ecommerce-agent", "jit": "off"},
}

_sync_connect_args = {
    "connect_timeout": settings.DB_CONNECT_TIMEOUT,
    "options": "-c application_name=ecommerce-agent -c jit=off",
}

# 异步引擎与 Session 工厂（FastAPI / Agent 使用）
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    connect_args=_async_connect_args,
)
async_session_maker = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

# 同步引擎与 Session 工厂（Celery 任务使用）
sync_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    connect_args=_sync_connect_args,
)
sync_session_maker = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


def get_sync_session() -> Generator[Session, None, None]:
    with sync_session_maker() as session:
        yield session


# engine and session factory are ready for use
