import asyncio
import logging

from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.services.cnpj_enrichment import enrich_distribuidoras
from backend.settings import Settings
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_settings = Settings()


@celery_app.task(
    bind=True, max_retries=2, default_retry_delay=60, name='dist.enrich_cnpj'
)
def task_enrich_cnpj(self) -> dict:
    logger.info('[task_enrich_cnpj] Iniciando enriquecimento CNPJ')

    async def _run() -> dict:
        local_engine = create_async_engine(_settings.DATABASE_URL)
        mongo_client = AsyncIOMotorClient(_settings.MONGO_URI)
        try:
            mongo_db = mongo_client[_settings.MONGO_DB]
            async with AsyncSession(local_engine, expire_on_commit=False) as session:
                return await enrich_distribuidoras(session, mongo_db)
        finally:
            mongo_client.close()
            await local_engine.dispose()

    try:
        counts = asyncio.run(_run())
        logger.info('[task_enrich_cnpj] Concluido: %s', counts)
        return counts
    except Exception as exc:
        logger.exception('[task_enrich_cnpj] Falha inesperada: %s', exc)
        raise
