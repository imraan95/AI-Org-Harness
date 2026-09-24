from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Supabase's local dev stack always uses this connection string by default
# (see `supabase status`). Override with the DATABASE_URL env var for
# anything else (e.g. a hosted project, once one exists).
DEFAULT_LOCAL_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres"
)


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_LOCAL_DATABASE_URL)


def get_engine() -> AsyncEngine:
    return create_async_engine(get_database_url())


def get_session_factory(
    engine: AsyncEngine | None = None,
) -> async_sessionmaker[AsyncSession]:
    engine = engine or get_engine()
    return async_sessionmaker(engine, expire_on_commit=False)
