from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG,
    pool_size=20,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db(*, create_schema: bool = False) -> None:
    import app.models  # noqa: F401

    if create_schema and settings.APP_ENV not in {"development", "test"}:
        raise RuntimeError("Automatic schema creation is restricted to isolated development and tests.")

    await engine.dispose(close=False)
    async with engine.begin() as conn:
        if create_schema:
            await conn.run_sync(Base.metadata.create_all)
        existing = await conn.run_sync(
            lambda sync_conn: set(inspect(sync_conn).get_table_names())
        )
        missing = sorted(set(Base.metadata.tables) - existing)
        if missing:
            raise RuntimeError(
                "Database schema is missing tables; apply controlled migrations: "
                + ", ".join(missing)
            )


async def close_db() -> None:
    await engine.dispose()


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
