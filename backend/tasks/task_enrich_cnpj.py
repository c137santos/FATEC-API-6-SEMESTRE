import asyncio
import logging

from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import engine
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
        # Descarta conexões herdadas do processo pai (fork) para evitar
        # "Future attached to a different loop" no novo event loop do worker.
        # Deve rodar dentro do asyncio.run para que o asyncpg feche conexões no contexto async correto.
        await engine.dispose()
        mongo_client = AsyncIOMotorClient(_settings.MONGO_URI)
        try:
            mongo_db = mongo_client[_settings.MONGO_DB]
            async with AsyncSession(engine, expire_on_commit=False) as session:
                return await enrich_distribuidoras(session, mongo_db)
        finally:
            mongo_client.close()

    try:
        counts = asyncio.run(_run())
        logger.info('[task_enrich_cnpj] Concluido: %s', counts)
        return counts
    except Exception as exc:
        logger.exception('[task_enrich_cnpj] Falha inesperada: %s', exc)
        raise
