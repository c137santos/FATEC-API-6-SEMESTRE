import logging

from backend.core.schemas import BatchTriggerRequest
from backend.services.pipeline_batch import _run_batch
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='etl.run_batch')
def task_run_batch(self, batch_id: str, params_dict: dict, user_email: str, distribuidoras: list[dict]) -> dict:
    logger.info('[task_run_batch] Iniciando lote. batch_id=%s', batch_id)
    params = BatchTriggerRequest(**params_dict)
    _run_batch(batch_id, params, user_email, distribuidoras)
    logger.info('[task_run_batch] Lote concluido. batch_id=%s', batch_id)
    return {'batch_id': batch_id}
