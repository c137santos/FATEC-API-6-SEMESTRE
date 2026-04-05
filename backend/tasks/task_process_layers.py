import logging
import json
import os
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path

import fiona
import pyproj
from shapely.geometry import mapping, shape
from shapely.ops import transform

from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

REQUIRED_CTMT_COLUMNS: set[str] = {
    'COD_ID',
    'NOME',
    'DIST',
    'ENE_01',
    'ENE_02',
    'ENE_03',
    'ENE_04',
    'ENE_05',
    'ENE_06',
    'ENE_07',
    'ENE_08',
    'ENE_09',
    'ENE_10',
    'ENE_11',
    'ENE_12',
    'PERD_A3a',
    'PERD_A4',
    'PERD_B',
    'PERD_MED',
    'PERD_A3aA4',
    'PERD_A3a_B',
    'PERD_A4A3a',
    'PERD_A4_B',
    'PERD_B_A3a',
    'PERD_B_A4',
}

REQUIRED_CONJ_COLUMNS: set[str] = {'COD_ID', 'NOME', 'DIST'}
REQUIRED_SSDMT_COLUMNS: set[str] = {'COD_ID', 'CTMT', 'CONJ', 'COMP', 'DIST'}
SSDMT_BATCH_SIZE = int(os.getenv('SSDMT_BATCH_SIZE', '10000'))
SSDMT_PROGRESS_LOG_INTERVAL_BATCHES = int(
    os.getenv('SSDMT_PROGRESS_LOG_INTERVAL_BATCHES', '25')
)
SSDMT_REPROJECTION_FAILURE_LIMIT = 0.01


def _normalize_required_field(value):
    if isinstance(value, str):
        value = value.strip()
    if value in (None, ''):
        return None
    return value


def _get_source_crs(src) -> pyproj.CRS:
    crs_candidates = []

    if getattr(src, 'crs', None):
        crs_candidates.append(src.crs)

    if getattr(src, 'crs_wkt', None):
        crs_candidates.append(src.crs_wkt)

    for crs_input in crs_candidates:
        try:
            return pyproj.CRS.from_user_input(crs_input)
        except Exception:
            continue

    raise RuntimeError('Camada SSDMT sem CRS identificavel no arquivo')


def _process_ssdmt_window(
    *,
    task_label: str,
    layer_label: str,
    job_id: str,
    gdb_path: str,
    start_index: int = 0,
    window_size: int | None = None,
    allow_empty: bool = False,
    file_suffix: str = '',
) -> dict:
    descartados = 0
    total_lidos = 0
    total_validos = 0
    falhas_reprojecao = 0
    total_geo_registros = 0
    processed_at = datetime.now(timezone.utc).isoformat()
    gdb_dir = Path(gdb_path)
    geo_path = gdb_dir.parent / f'{job_id}_ssdmt_geo{file_suffix}.ndjson'
    tabular_path = (
        gdb_dir.parent / f'{job_id}_ssdmt_tabular{file_suffix}.ndjson'
    )

    with (
        fiona.open(gdb_path, layer='SSDMT') as src,
        geo_path.open('w', encoding='utf-8') as geo_writer,
        tabular_path.open('w', encoding='utf-8') as tabular_writer,
    ):
        properties = src.schema.get('properties', {})
        present_cols = set(properties.keys())
        missing = REQUIRED_SSDMT_COLUMNS - present_cols
        if missing:
            raise RuntimeError(f'Camada SSDMT sem colunas: {missing}')

        src_crs = _get_source_crs(src)
        transformer = pyproj.Transformer.from_crs(
            src_crs,
            'EPSG:4326',
            always_xy=True,
        )

        stop_index = None
        if window_size is not None:
            stop_index = start_index + window_size

        source_iter = islice(src, start_index, stop_index)
        batch_index = 0
        while True:
            batch = list(islice(source_iter, SSDMT_BATCH_SIZE))
            if not batch:
                break

            batch_index += 1
            for feature in batch:
                total_lidos += 1

                row = feature.get('properties') or {}
                cod_id = _normalize_required_field(row.get('COD_ID'))
                ctmt = _normalize_required_field(row.get('CTMT'))

                if cod_id is None or ctmt is None:
                    descartados += 1
                    continue

                raw_geometry = feature.get('geometry')
                if not raw_geometry:
                    descartados += 1
                    continue

                try:
                    geom = shape(raw_geometry)
                    geom_reproj = transform(transformer.transform, geom)
                    geom_geojson = mapping(geom_reproj)
                except Exception:
                    falhas_reprojecao += 1
                    continue

                conj = row.get('CONJ')
                comp = row.get('COMP')
                dist = row.get('DIST')

                tabular_record = {
                    'cod_id': cod_id,
                    'ctmt': ctmt,
                    'conj': conj,
                    'comp': comp,
                    'dist': dist,
                    'job_id': job_id,
                    'processed_at': processed_at,
                }
                tabular_writer.write(
                    json.dumps(tabular_record, ensure_ascii=False) + '\n'
                )

                geo_writer.write(
                    json.dumps(
                        {
                            'type': 'Feature',
                            'properties': {
                                'cod_id': cod_id,
                                'ctmt': ctmt,
                                'conj': conj,
                                'comp': comp,
                                'dist': dist,
                                'job_id': job_id,
                                'processed_at': processed_at,
                            },
                            'geometry': geom_geojson,
                        },
                        ensure_ascii=False,
                    )
                    + '\n'
                )
                total_validos += 1
                total_geo_registros += 1

            if (
                batch_index == 1
                or batch_index % SSDMT_PROGRESS_LOG_INTERVAL_BATCHES == 0
            ):
                logger.info(
                    '[%s] Batch processado. job_id=%s start=%s size=%s batch=%s lidos=%s validos=%s descartados=%s falhas_reprojecao=%s',
                    task_label,
                    job_id,
                    start_index,
                    window_size,
                    batch_index,
                    total_lidos,
                    total_validos,
                    descartados,
                    falhas_reprojecao,
                )

    percentual_falhas = (falhas_reprojecao / total_lidos) if total_lidos > 0 else 0.0

    if percentual_falhas > SSDMT_REPROJECTION_FAILURE_LIMIT:
        raise RuntimeError(
            'Camada SSDMT com falha de reprojecao acima do limite: '
            f'total_lidos={total_lidos} descartados={descartados} '
            f'falhas_reprojecao={falhas_reprojecao} '
            f'percentual_falhas={percentual_falhas:.4f}'
        )

    if total_validos == 0 and not allow_empty:
        raise RuntimeError(
            'Camada SSDMT sem registros validos apos limpeza: '
            f'total_lidos={total_lidos} descartados={descartados} '
            f'falhas_reprojecao={falhas_reprojecao}'
        )

    logger.info(
        '[%s] Processamento concluido. job_id=%s start=%s size=%s total=%s descartados=%s falhas_reprojecao=%s',
        task_label,
        job_id,
        start_index,
        window_size,
        total_validos,
        descartados,
        falhas_reprojecao,
    )

    return {
        'layer': layer_label,
        'job_id': job_id,
        'ssdmt_tabular': {
            'storage_type': 'ndjson',
            'path': str(tabular_path),
            'records_count': total_validos,
        },
        'ssdmt_geo': {
            'storage_type': 'ndjson',
            'path': str(geo_path),
            'records_count': total_geo_registros,
            'crs': 'EPSG:4326',
        },
        'total': total_validos,
        'total_lidos': total_lidos,
        'descartados': descartados,
        'falhas_reprojecao': falhas_reprojecao,
        'window': {
            'start_index': start_index,
            'size': window_size,
        },
    }


@celery_app.task(name='etl.processar_ctmt')
def task_processar_ctmt(job_id: str, gdb_path: str) -> dict:
    logger.info(
        '[task_processar_ctmt] Inicio do processamento. job_id=%s gdb_path=%s',
        job_id,
        gdb_path,
    )

    records: list[dict] = []
    descartados = 0
    processed_at = datetime.now(timezone.utc).isoformat()

    with fiona.open(gdb_path, layer='CTMT') as src:
        properties = src.schema.get('properties', {})
        present_cols = set(properties.keys())
        missing = REQUIRED_CTMT_COLUMNS - present_cols
        if missing:
            raise RuntimeError(f'Camada CTMT sem colunas: {missing}')

        for feature in src:
            row = feature.get('properties') or {}
            cod_id = row.get('COD_ID')
            if isinstance(cod_id, str):
                cod_id = cod_id.strip()

            if not cod_id:
                descartados += 1
                continue

            nome = row.get('NOME')
            if isinstance(nome, str):
                nome = nome.strip()

            records.append({
                'cod_id': cod_id,
                'nome': nome,
                'dist': row.get('DIST'),
                'ene_01': row.get('ENE_01'),
                'ene_02': row.get('ENE_02'),
                'ene_03': row.get('ENE_03'),
                'ene_04': row.get('ENE_04'),
                'ene_05': row.get('ENE_05'),
                'ene_06': row.get('ENE_06'),
                'ene_07': row.get('ENE_07'),
                'ene_08': row.get('ENE_08'),
                'ene_09': row.get('ENE_09'),
                'ene_10': row.get('ENE_10'),
                'ene_11': row.get('ENE_11'),
                'ene_12': row.get('ENE_12'),
                'perd_a3a': row.get('PERD_A3a'),
                'perd_a4': row.get('PERD_A4'),
                'perd_b': row.get('PERD_B'),
                'perd_med': row.get('PERD_MED'),
                'perd_a3aa4': row.get('PERD_A3aA4'),
                'perd_a3a_b': row.get('PERD_A3a_B'),
                'perd_a4a3a': row.get('PERD_A4A3a'),
                'perd_a4_b': row.get('PERD_A4_B'),
                'perd_b_a3a': row.get('PERD_B_A3a'),
                'perd_b_a4': row.get('PERD_B_A4'),
                'job_id': job_id,
                'processed_at': processed_at,
            })

    if not records:
        raise RuntimeError('Camada CTMT sem registros validos apos limpeza')

    logger.info(
        '[task_processar_ctmt] Processamento concluido. job_id=%s total=%s descartados=%s',
        job_id,
        len(records),
        descartados,
    )
    return {
        'layer': 'CTMT',
        'job_id': job_id,
        'records': records,
        'total': len(records),
        'descartados': descartados,
    }


@celery_app.task(name='etl.processar_ssdmt')
def task_processar_ssdmt(job_id: str, gdb_path: str) -> dict:
    logger.info(
        '[task_processar_ssdmt] Inicio do processamento. job_id=%s gdb_path=%s',
        job_id,
        gdb_path,
    )

    return _process_ssdmt_window(
        task_label='task_processar_ssdmt',
        layer_label='SSDMT',
        job_id=job_id,
        gdb_path=gdb_path,
        start_index=0,
        window_size=None,
        allow_empty=False,
        file_suffix='',
    )


@celery_app.task(name='etl.processar_ssdmt_chunk')
def task_processar_ssdmt_chunk(
    job_id: str,
    gdb_path: str,
    chunk_index: int,
    start_index: int,
    chunk_size: int,
) -> dict:
    logger.info(
        '[task_processar_ssdmt_chunk] Inicio do processamento. job_id=%s chunk=%s start=%s size=%s gdb_path=%s',
        job_id,
        chunk_index,
        start_index,
        chunk_size,
        gdb_path,
    )

    result = _process_ssdmt_window(
        task_label='task_processar_ssdmt_chunk',
        layer_label='SSDMT_CHUNK',
        job_id=job_id,
        gdb_path=gdb_path,
        start_index=start_index,
        window_size=chunk_size,
        allow_empty=True,
        file_suffix=f'_chunk_{chunk_index:05d}',
    )
    result['chunk_index'] = chunk_index
    return result


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

            records.append({
                'cod_id': cod_id,
                'nome': nome,
                'dist': row.get('DIST'),
                'job_id': job_id,
                'processed_at': processed_at,
            })

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
def task_finalizar(
    results: list[dict], job_id: str, zip_path: str, tmp_dir: str
) -> dict:
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
