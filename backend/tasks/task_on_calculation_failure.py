import logging
from datetime import datetime, timezone

from backend.database import get_mongo_sync_db
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name='etl.on_calculation_failure')
def task_on_calculation_failure(
    job_id: str,
    batch_id: str | None = None,
    dist_id: str | None = None,
) -> None:
    logger.error('[task_on_calculation_failure] Falha no chain de calculos. job_id=%s', job_id)
    db = get_mongo_sync_db()
    db['jobs'].update_one(
        {'job_id': job_id},
        {'$set': {
            'report_status': 'failed',
            'report_generated_at': datetime.now(timezone.utc),
        }},
    )
    if batch_id and dist_id:
        from backend.services.pipeline_batch import _update_batch_dist_status
        _update_batch_dist_status(db, batch_id, dist_id, 'failed')
