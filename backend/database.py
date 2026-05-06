from collections.abc import AsyncGenerator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from pymongo.database import Database as MongoSyncDatabase
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.settings import Settings

settings = Settings()

# PostgreSQL
engine = create_async_engine(settings.DATABASE_URL)


async def get_session():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


# MongoDB Async Singleton
_mongo_async_client: AsyncIOMotorClient | None = None


def get_mongo_async_client() -> AsyncIOMotorClient:
    """Obtém cliente MongoDB assíncrono (singleton)."""
    global _mongo_async_client
    if _mongo_async_client is None:
        _mongo_async_client = AsyncIOMotorClient(settings.MONGO_URI)
    return _mongo_async_client


def get_mongo_async_db() -> AsyncIOMotorDatabase:
    """Obtém database MongoDB assíncrono."""
    return get_mongo_async_client()[settings.MONGO_DB]


async def get_mongo_async_database() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """Dependency para FastAPI com database Mongo assíncrono."""
    yield get_mongo_async_db()


# MongoDB Sync Singleton (uso em tasks Celery síncronas)
_mongo_sync_client: MongoClient | None = None


def get_mongo_sync_client() -> MongoClient:
    """Obtém cliente MongoDB síncrono (singleton)."""
    global _mongo_sync_client
    if _mongo_sync_client is None:
        _mongo_sync_client = MongoClient(settings.MONGO_URI)
    return _mongo_sync_client


def get_mongo_sync_db() -> MongoSyncDatabase:
    """Obtém database MongoDB síncrono."""
    return get_mongo_sync_client()[settings.MONGO_DB]
