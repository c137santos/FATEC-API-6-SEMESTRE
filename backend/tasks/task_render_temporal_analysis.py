import logging

from backend.database import get_mongo_sync_db
from backend.services.temporal_analysis import render_prophet_forecast
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name='etl.render_prophet_forecast')
def task_render_prophet_forecast(job_id: str, cnpj: str) -> dict:
    logger.info(
        '[task_render_prophet_forecast] Inicio. job_id=%s cnpj=%s',
        job_id,
        cnpj,
    )

    result = render_prophet_forecast(cnpj=cnpj)

    db = get_mongo_sync_db()

    if not result['render_paths']:
        logger.warning(
            '[task_render_prophet_forecast] Nenhum gráfico gerado. job_id=%s',
            job_id,
        )
        db['jobs'].update_one(
            {'job_id': job_id},
            {'$set': {'render_paths.prophet': None}},
        )
        return {
            'job_id': job_id,
            'status': 'skipped',
            'reason': 'no_render_paths',
        }

    db['jobs'].update_one(
        {'job_id': job_id},
        {'$set': {'render_paths.prophet': result['render_paths']}},
    )

    logger.info(
        '[task_render_prophet_forecast] Concluida. job_id=%s paths=%s',
        job_id,
        result['render_paths'],
    )
    return {
        'job_id': job_id,
        'status': 'done',
        'paths': result['render_paths'],
        'skipped': result['skipped'],
    }
