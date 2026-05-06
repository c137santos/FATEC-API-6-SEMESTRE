import logging

from backend.database import get_mongo_sync_db
from backend.services.calculate_pt_and_pnt import calculate_pt_pnt
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

WAIT_COUNTDOWN = 30
MAX_WAIT_RETRIES = 60


@celery_app.task(
    bind=True, max_retries=MAX_WAIT_RETRIES, name='etl.calculate_pt_pnt'
)
def task_calculate_pt_pnt(self, job_id: str, distribuidora_id: str, sig_agente: str, ano: int) -> dict:
    logger.info('[task_calculate_pt_pnt] Inicio. job_id=%s', job_id)

    db = get_mongo_sync_db()
    job = db['jobs'].find_one({'job_id': job_id})

    if not job or job.get('status') != 'completed':
        logger.info(
            (
                '[task_calculate_pt_pnt] ETL ainda nao concluida, '
                'reagendando. job_id=%s'
            ),
            job_id,
        )
        raise self.retry(countdown=WAIT_COUNTDOWN)

    results = calculate_pt_pnt(
        distribuidora_id=distribuidora_id,
        job_id=job_id,
        sig_agente=sig_agente,
        ano=ano
    )

    logger.info('[task_calculate_pt_pnt] Concluida. job_id=%s', job_id)

    return {
        'job_id': job_id,
        'status': 'done',
        'conjuntos': len(results),
    }
