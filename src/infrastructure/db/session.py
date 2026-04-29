from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


async def create_async_session_factory(
    db_url: str,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """dependency-injector Resource provider — async setup/teardown."""
    engine = create_async_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()
