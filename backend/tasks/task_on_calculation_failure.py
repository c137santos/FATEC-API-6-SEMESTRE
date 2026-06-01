import logging
from datetime import datetime, timezone

from backend.database import get_mongo_sync_db
from backend.tasks.celery_app import celery_app
from backend.tasks.task_cleanup_files import task_cleanup_files
from backend.tasks.task_dispatch_next_in_batch import (
    task_dispatch_next_in_batch,
)
from backend.services.pipeline_batch import _update_batch_dist_status

logger = logging.getLogger(__name__)


@celery_app.task(name='etl.on_calculation_failure')
def task_on_calculation_failure(
    job_id: str,
    batch_id: str | None = None,
    dist_id: str | None = None,
) -> None:
    logger.error(
        '[task_on_calculation_failure] Falha no chain de calculos. job_id=%s',
        job_id,
    )
    db = get_mongo_sync_db()
    db['jobs'].update_one(
        {'job_id': job_id},
        {
            '$set': {
                'report_status': 'failed',
                'report_generated_at': datetime.now(timezone.utc),
            }
        },
    )
    task_cleanup_files.apply_async(args=[job_id])
    if batch_id and dist_id:
        updated = _update_batch_dist_status(db, batch_id, dist_id, 'failed')
        if updated:
            task_dispatch_next_in_batch.apply_async(args=[batch_id])
