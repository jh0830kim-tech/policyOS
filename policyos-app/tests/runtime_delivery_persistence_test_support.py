"""Shared non-plugin support for CP8 PostgreSQL persistence tests."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.runtime.persistence import (
    RUNTIME_EFFECT_PERSISTENCE_TABLES,
    RUNTIME_PERSISTENCE_TABLES,
)


@asynccontextmanager
async def runtime_delivery_session_factory(
    database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(database_url)
    tables = (*RUNTIME_PERSISTENCE_TABLES, *RUNTIME_EFFECT_PERSISTENCE_TABLES)
    async with engine.begin() as connection:
        for table in reversed(tables):
            await connection.run_sync(
                lambda sync, item=table: item.drop(sync, checkfirst=True)
            )
        for table in tables:
            await connection.run_sync(lambda sync, item=table: item.create(sync))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        async with engine.begin() as connection:
            for table in reversed(tables):
                await connection.run_sync(
                    lambda sync, item=table: item.drop(sync, checkfirst=True)
                )
        await engine.dispose()


__all__ = ("runtime_delivery_session_factory",)
