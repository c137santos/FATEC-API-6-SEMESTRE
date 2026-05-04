import logging
from datetime import datetime

from celery.signals import task_failure

from backend.database import get_mongo_sync_db

logger = logging.getLogger(__name__)


@task_failure.connect
def on_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **_):
    """
    Captura qualquer falha de task Celery e marca o job como failed no MongoDB.
    Só atua se o primeiro argumento da task for um job_id conhecido.
    Não sobrescreve jobs já concluídos com sucesso.
    """
    if not args or not isinstance(args[0], str):
        return

    job_id = args[0]

    try:
        db = get_mongo_sync_db()
        result = db['jobs'].update_one(
            {
                'job_id': job_id,
                'status': {'$nin': ['completed']},
            },
            {
                '$set': {
                    'status': 'failed',
                    'report_status': 'failed',
                    'error': str(exception),
                    'failed_task': sender.name,
                    'failed_at': datetime.utcnow(),
                }
            },
        )

        if result.modified_count:
            logger.error(
                '[on_task_failure] Job marcado como failed. job_id=%s task=%s erro=%s',
                job_id, sender.name, exception,
            )
    except Exception:
        logger.exception(
            '[on_task_failure] Falha ao registrar erro no MongoDB. job_id=%s', job_id
        )
