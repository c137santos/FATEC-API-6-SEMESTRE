from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.settings import Settings

db_url = db_url = Settings().DATABASE_URL.replace("postgresql+psycopg://", "postgresql+asyncpg://")
engine = create_async_engine(db_url)


async def get_session():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
