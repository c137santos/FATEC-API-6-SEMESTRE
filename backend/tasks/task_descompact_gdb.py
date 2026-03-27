import logging
import os
import zipfile
from pathlib import Path

import fiona
from celery import chord, signature

from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

TMP_DIR = Path(os.getenv('TMP_DIR', '/data/tmp/'))

REQUIRED_SCHEMA: dict[str, set[str]] = {
    'CTMT': {
        'COD_ID', 'NOME', 'DIST',
        'ENE_01', 'ENE_02', 'ENE_03', 'ENE_04',
        'ENE_05', 'ENE_06', 'ENE_07', 'ENE_08',
        'ENE_09', 'ENE_10', 'ENE_11', 'ENE_12',
        'PERD_A3a', 'PERD_A4', 'PERD_B', 'PERD_MED',
        'PERD_A3aA4', 'PERD_A3a_B', 'PERD_A4A3a', 'PERD_A4_B',
        'PERD_B_A3a', 'PERD_B_A4',
    },
    'SSDMT': {
        'COD_ID', 'CTMT', 'CONJ', 'COMP', 'DIST',
    },
    'CONJ': {'COD_ID', 'NOME', 'DIST'},
}


@celery_app.task(bind=True, name='etl.extrair_gdb')
def task_descompact_gdb(self, job_id: str, zip_path: str) -> dict:
    logger.info('[task_descompact_gdb] Inicio da extracao. job_id=%s zip_path=%s', job_id, zip_path)

    zip_p = Path(zip_path)
    tmp_dir = TMP_DIR / job_id
    tmp_dir.mkdir(parents=True, exist_ok=True)
    logger.info('[task_descompact_gdb] Diretorio temporario preparado. job_id=%s tmp_dir=%s', job_id, tmp_dir)

    try:
        with zipfile.ZipFile(zip_p) as zf:
            zf.extractall(tmp_dir)
        logger.info('[task_descompact_gdb] ZIP extraido com sucesso. job_id=%s destino=%s', job_id, tmp_dir)

        gdb_candidates = list(tmp_dir.rglob('*.gdb'))
        logger.info('[task_descompact_gdb] Candidatos .gdb encontrados. job_id=%s quantidade=%s', job_id, len(gdb_candidates))
        if not gdb_candidates:
            raise RuntimeError(
                f'Nenhum arquivo .gdb encontrado no ZIP: {zip_path}'
            )
        gdb_path = str(gdb_candidates[0])
        logger.info('[task_descompact_gdb] GDB selecionado para validacao. job_id=%s gdb_path=%s', job_id, gdb_path)

        available_layers = fiona.listlayers(gdb_path)
        logger.info('[task_descompact_gdb] Camadas disponiveis no GDB. job_id=%s layers=%s', job_id, list(available_layers))
        for layer, required_cols in REQUIRED_SCHEMA.items():
            logger.info('[task_descompact_gdb] Validando camada. job_id=%s layer=%s required_columns=%s', job_id, layer, len(required_cols))
            if layer not in available_layers:
                raise RuntimeError(f'Camada ausente no GDB: {layer}')
            with fiona.open(gdb_path, layer=layer) as src:
                present_cols = set(src.schema['properties'].keys())
                missing = required_cols - present_cols
            if missing:
                raise RuntimeError(f'Camada {layer} sem colunas: {missing}')

            logger.info('[task_descompact_gdb] Camada validada com sucesso. job_id=%s layer=%s colunas_presentes=%s', job_id, layer, len(present_cols))

        chord(
            [
                signature('etl.processar_ctmt', args=(job_id, gdb_path)),
                signature('etl.processar_ssdmt', args=(job_id, gdb_path)),
                signature('etl.processar_conj', args=(job_id, gdb_path)),
            ],
            signature('etl.finalizar', args=(job_id, zip_path, str(tmp_dir))),
        ).delay()
        logger.info('[task_descompact_gdb] Chord disparado. job_id=%s callbacks=etl.finalizar', job_id)

        result = {'job_id': job_id, 'gdb_path': gdb_path, 'status': 'extracted'}
        logger.info('[task_descompact_gdb] Task finalizada com sucesso. job_id=%s status=%s', job_id, result['status'])
        return result
    except Exception as exc:
        logger.exception('[task_descompact_gdb] Falha na extracao/validacao. job_id=%s erro=%s', job_id, exc)
        raise
