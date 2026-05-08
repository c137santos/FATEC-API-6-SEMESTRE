import asyncio
import logging

import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.clients.aneel import fetch_aneel_cnpj_map
from backend.database import engine
from backend.services.cnpj_enrichment import enrich_distribuidoras
from backend.settings import Settings
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_settings = Settings()


def _retry_countdown(retries: int) -> int:
    return min(60 * (2**retries), 600)


@celery_app.task(
    bind=True, max_retries=2, default_retry_delay=60, name='dist.enrich_cnpj'
)
def task_enrich_cnpj(self) -> dict:
    logger.info('[task_enrich_cnpj] Iniciando enriquecimento CNPJ')

    async def _run() -> dict:
        mongo_client = AsyncIOMotorClient(_settings.MONGO_URI)
        try:
            mongo_db = mongo_client[_settings.MONGO_DB]
            async with AsyncSession(engine, expire_on_commit=False) as session:
                aneel_map = await fetch_aneel_cnpj_map()
                return await enrich_distribuidoras(
                    session, aneel_map, mongo_db=mongo_db
                )
        finally:
            mongo_client.close()

    try:
        counts = asyncio.run(_run())
        logger.info('[task_enrich_cnpj] Concluido: %s', counts)
        return counts
    except httpx.HTTPError as exc:
        countdown = _retry_countdown(self.request.retries)
        logger.warning(
            '[task_enrich_cnpj] Falha HTTP, retry em %ss: %s', countdown, exc
        )
        raise self.retry(exc=exc, countdown=countdown)
    except Exception as exc:
        logger.exception('[task_enrich_cnpj] Falha inesperada: %s', exc)
        raise
