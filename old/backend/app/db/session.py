"""Async engine + session factory + FastAPI dependency.

The engine is created lazily from ``settings.database_url`` so importing this module never
opens a connection (keeps the app bootable / tests light). Pooling is tuned in Step 23.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(settings.database_url, pool_pre_ping=True, future=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session
