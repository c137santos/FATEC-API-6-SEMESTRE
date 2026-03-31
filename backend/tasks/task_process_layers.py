import logging

from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name='etl.processar_ctmt')
def task_processar_ctmt(job_id: str, gdb_path: str) -> dict:
    logger.info('[task_processar_ctmt] Processamento placeholder. job_id=%s gdb_path=%s', job_id, gdb_path)
    return {'layer': 'CTMT', 'job_id': job_id, 'status': 'processed'}


@celery_app.task(name='etl.processar_ssdmt')
def task_processar_ssdmt(job_id: str, gdb_path: str) -> dict:
    logger.info('[task_processar_ssdmt] Processamento placeholder. job_id=%s gdb_path=%s', job_id, gdb_path)
    return {'layer': 'SSDMT', 'job_id': job_id, 'status': 'processed'}


@celery_app.task(name='etl.processar_conj')
def task_processar_conj(job_id: str, gdb_path: str) -> dict:
    logger.info('[task_processar_conj] Processamento placeholder. job_id=%s gdb_path=%s', job_id, gdb_path)
    return {'layer': 'CONJ', 'job_id': job_id, 'status': 'processed'}


@celery_app.task(name='etl.finalizar')
def task_finalizar(results: list[dict], job_id: str, zip_path: str, tmp_dir: str) -> dict:
    """Recebe resultados do chord e retorna um resumo da finalizacao."""
    logger.info(
        '[task_finalizar] Finalizacao placeholder. job_id=%s resultados=%s zip_path=%s tmp_dir=%s',
        job_id,
        len(results or []),
        zip_path,
        tmp_dir,
    )
    return {
        'job_id': job_id,
        'status': 'finished',
        'results_count': len(results or []),
        'zip_path': zip_path,
        'tmp_dir': tmp_dir,
    }
