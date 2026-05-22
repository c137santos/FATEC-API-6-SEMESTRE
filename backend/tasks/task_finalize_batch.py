import logging
from datetime import datetime, timezone

from backend.database import get_mongo_sync_db
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name='etl.finalize_batch')
def task_finalize_batch(
    job_id: str,
    batch_id: str | None = None,
    dist_id: str | None = None,
) -> dict:
    logger.info('[task_finalize_batch] Inicio. job_id=%s', job_id)
    db = get_mongo_sync_db()
    db['jobs'].update_one(
        {'job_id': job_id},
        {'$set': {
            'report_status': 'completed',
            'report_generated_at': datetime.now(timezone.utc),
        }},
    )
    if batch_id and dist_id:
        from backend.services.pipeline_batch import _update_batch_dist_status
        _update_batch_dist_status(db, batch_id, dist_id, 'completed')
    logger.info('[task_finalize_batch] Concluido. job_id=%s', job_id)
    return {'job_id': job_id, 'status': 'completed'}
