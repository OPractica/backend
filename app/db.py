from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


NO_OVERLAP = """
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'bookings_no_overlap') THEN
    ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap
      EXCLUDE USING gist (seat_id WITH =, tstzrange(starts_at, ends_at) WITH &&)
      WHERE (status = 'confirmed');
  END IF;
END $$;
"""


async def init_db() -> None:
    from app import models  # noqa: F401  (register tables)

    async with engine.begin() as conn:
        if conn.dialect.name == "sqlite":
            await conn.run_sync(Base.metadata.create_all)  # quick local tests; PostgreSQL uses Alembic
        if conn.dialect.name == "postgresql":
            # The database itself refuses two overlapping bookings for one seat (race-condition guard).
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
            await conn.execute(text(NO_OVERLAP))
