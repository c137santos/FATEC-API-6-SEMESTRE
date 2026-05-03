import logging

from backend.database import get_mongo_sync_db
from backend.services.calculate_sam import calculate_sam
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

WAIT_COUNTDOWN = 30
MAX_WAIT_RETRIES = 60


@celery_app.task(
    bind=True,
    max_retries=MAX_WAIT_RETRIES,
    name='etl.calcular_sam',
)
def task_calculate_sam(
    self,
    job_id: str,
    distribuidora_id: str,
    sig_agente: str,
    ano_indice: int,
) -> dict:

    logger.info(
        '[task_calculate_sam] Inicio. job_id=%s distribuidora_id=%s',
        job_id,
        distribuidora_id,
    )

    db = get_mongo_sync_db()
    job = db['jobs'].find_one({'job_id': job_id})

    if not job or job.get('status') != 'completed':
        logger.info(
            '[task_calculate_sam] ETL ainda não concluído, '
            'aguardando. job_id=%s',
            job_id,
        )
        raise self.retry(countdown=WAIT_COUNTDOWN)

    calculate_sam(
        job_id=job_id,
        distribuidora_id=distribuidora_id,
        sig_agente=sig_agente,
        ano_indice=ano_indice,
    )

    logger.info(
        '[task_calculate_sam] Concluida. job_id=%s distribuidora_id=%s',
        job_id,
        distribuidora_id,
    )
    return {'job_id': job_id, 'status': 'done'}
