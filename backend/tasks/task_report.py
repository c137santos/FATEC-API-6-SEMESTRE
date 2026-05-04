import logging
from datetime import datetime

from backend.database import get_mongo_sync_db
from backend.services.report import gerar_pdf_report
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

WAIT_COUNTDOWN = 30
MAX_WAIT_RETRIES = 120

_REQUIRED_RENDER_KEYS = {'grafico_tam', 'pt_pnt', 'tabela_score', 'mapa_calor'}


@celery_app.task(bind=True, max_retries=MAX_WAIT_RETRIES, name='etl.gerar_report')
def task_gerar_report(self, job_id: str) -> dict:
    logger.info('[task_gerar_report] Inicio. job_id=%s', job_id)
    
    db = get_mongo_sync_db()

    job_doc = db['jobs'].find_one({'job_id': job_id}, {'_id': 0})
    if not job_doc:
        logger.info('[task_gerar_report] job_id ainda não encontrado, aguardando. job_id=%s', job_id)
        raise self.retry(countdown=WAIT_COUNTDOWN)

    render_paths = job_doc.get('render_paths', {}) or {}
    missing = _REQUIRED_RENDER_KEYS - render_paths.keys()
    if missing:
        logger.info('[task_gerar_report] render_paths incompletos (%s), aguardando. job_id=%s', missing, job_id)
        raise self.retry(countdown=WAIT_COUNTDOWN)

    try:
        pdf_path = gerar_pdf_report(
            job_id=job_id,
            render_paths=render_paths,
            job_meta=job_doc,
        )
        db['jobs'].update_one(
            {'job_id': job_id},
            {'$set': {
                'report_status': 'completed',
                'report_pdf_path': pdf_path,
                'report_generated_at': datetime.utcnow(),
            }},
        )
        logger.info('[task_gerar_report] Concluida. job_id=%s path=%s', job_id, pdf_path)
        return {'job_id': job_id, 'status': 'completed', 'path': pdf_path}

    except Exception as exc:
        logger.exception('[task_gerar_report] Erro. job_id=%s', job_id)
        db['jobs'].update_one(
            {'job_id': job_id},
            {'$set': {
                'report_status': 'failed',
                'report_error': str(exc),
                'report_generated_at': datetime.utcnow(),
            }},
        )
        return {'job_id': job_id, 'status': 'failed', 'reason': str(exc)}
