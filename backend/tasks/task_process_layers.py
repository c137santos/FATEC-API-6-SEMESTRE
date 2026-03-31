import logging
from datetime import datetime, timezone

import fiona

from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

REQUIRED_CONJ_COLUMNS: set[str] = {'COD_ID', 'NOME', 'DIST'}


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
    logger.info(
        '[task_processar_conj] Inicio do processamento. job_id=%s gdb_path=%s',
        job_id,
        gdb_path,
    )

    records: list[dict] = []
    descartados = 0
    processed_at = datetime.now(timezone.utc).isoformat()

    with fiona.open(gdb_path, layer='CONJ') as src:
        properties = src.schema.get('properties', {})
        present_cols = set(properties.keys())
        missing = REQUIRED_CONJ_COLUMNS - present_cols
        if missing:
            raise RuntimeError(f'Camada CONJ sem colunas: {missing}')

        for feature in src:
            row = feature.get('properties') or {}
            cod_id = row.get('COD_ID')
            if cod_id is None:
                descartados += 1
                continue

            nome = row.get('NOME')
            if isinstance(nome, str):
                nome = nome.strip()

            records.append(
                {
                    'cod_id': cod_id,
                    'nome': nome,
                    'dist': row.get('DIST'),
                    'job_id': job_id,
                    'processed_at': processed_at,
                }
            )

    if not records:
        raise RuntimeError('Camada CONJ sem registros validos apos limpeza')

    logger.info(
        '[task_processar_conj] Processamento concluido. job_id=%s total=%s descartados=%s',
        job_id,
        len(records),
        descartados,
    )
    return {
        'layer': 'CONJ',
        'job_id': job_id,
        'records': records,
        'total': len(records),
        'descartados': descartados,
    }


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
