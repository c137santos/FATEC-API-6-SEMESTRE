import logging
import json
import os
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path

import fiona
import pyproj
from pymongo import MongoClient, results
from shapely.geometry import mapping, shape
from shapely.ops import transform

from backend.settings import Settings
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)
SSDMT_INSERT_BATCH_SIZE = 5000


def _get_collection(name: str):
    settings = Settings()
    client = MongoClient(settings.MONGO_URI)
    return client[settings.MONGO_DB][name]


def _persist_ctmt(
    records: list[dict],
    job_id: str,
    descartados: int,
    processed_at: str,
    distribuidora_id: str | None,
) -> int:
    col = _get_collection('circuitos_mt')
    col.create_index('job_id', unique=True, background=True)
    col.replace_one(
        {'job_id': job_id},
        {
            'job_id': job_id,
            'distribuidora_id': distribuidora_id,
            'processed_at': processed_at,
            'total': len(records),
            'descartados': descartados,
            'records': records,
        },
        upsert=True,
    )
    return len(records)


def _persist_conj(
    records: list[dict],
    job_id: str,
    descartados: int,
    processed_at: str,
    distribuidora_id: str | None,
) -> int:
    col = _get_collection('conjuntos')
    col.create_index('job_id', unique=True, background=True)
    col.replace_one(
        {'job_id': job_id},
        {
            'job_id': job_id,
            'distribuidora_id': distribuidora_id,
            'processed_at': processed_at,
            'total': len(records),
            'descartados': descartados,
            'records': records,
        },
        upsert=True,
    )
    return len(records)


def _iter_ndjson(path: str):
    with Path(path).open('r', encoding='utf-8') as f:
        for line in f:
            payload = line.strip()
            if not payload:
                continue
            yield json.loads(payload)


def _to_notebook_ssdmt_tabular(
    raw: dict,
    job_id: str,
    processed_at: str,
    distribuidora_id: str | None,
) -> dict | None:
    cod_id = _normalize_required_field(raw.get('COD_ID', raw.get('cod_id')))
    ctmt = _normalize_required_field(raw.get('CTMT', raw.get('ctmt')))
    if cod_id is None or ctmt is None:
        return None

    return {
        'job_id': job_id,
        'distribuidora_id': distribuidora_id,
        'COD_ID': cod_id,
        'CTMT': ctmt,
        'CONJ': raw.get('CONJ', raw.get('conj')),
        'COMP': raw.get('COMP', raw.get('comp')),
        'DIST': raw.get('DIST', raw.get('dist')),
        'processed_at': raw.get('processed_at') or processed_at,
    }


def _to_notebook_ssdmt_geo(
    raw: dict,
    job_id: str,
    processed_at: str,
    distribuidora_id: str | None,
) -> dict | None:
    properties = raw.get('properties') or raw
    geometry = raw.get('geometry')
    if geometry is None:
        return None

    cod_id = _normalize_required_field(
        properties.get('COD_ID', properties.get('cod_id'))
    )
    ctmt = _normalize_required_field(
        properties.get('CTMT', properties.get('ctmt'))
    )
    if cod_id is None or ctmt is None:
        return None

    return {
        'job_id': job_id,
        'distribuidora_id': distribuidora_id,
        'COD_ID': cod_id,
        'CTMT': ctmt,
        'CONJ': properties.get('CONJ', properties.get('conj')),
        'COMP': properties.get('COMP', properties.get('comp')),
        'DIST': properties.get('DIST', properties.get('dist')),
        'processed_at': properties.get('processed_at') or processed_at,
        'geometry': geometry,
    }


def _persist_ssdmt(
    results: list[dict],
    job_id: str,
    processed_at: str,
    distribuidora_id: str | None,
) -> dict:
    ssdmt_results = [
        r
        for r in (results or [])
        if r.get('layer') in {'SSDMT', 'SSDMT_CHUNK'}
    ]
    if not ssdmt_results:
        return {
            'total': 0,
            'descartados': 0,
            'falhas_reprojecao': 0,
            'tabular_paths': [],
            'geo_paths': [],
        }

    tabular_paths: list[str] = []
    geo_paths: list[str] = []
    total_descartados = 0
    total_falhas = 0

    for result in ssdmt_results:
        total_descartados += int(result.get('descartados') or 0)
        total_falhas += int(result.get('falhas_reprojecao') or 0)

        tabular_info = result.get('ssdmt_tabular') or {}
        geo_info = result.get('ssdmt_geo') or {}

        tabular_path = tabular_info.get('path')
        geo_path = geo_info.get('path')

        if tabular_path:
            tabular_paths.append(tabular_path)
        if geo_path:
            geo_paths.append(geo_path)

    tabular_col = _get_collection('segmentos_mt_tabular')
    geo_col = _get_collection('segmentos_mt_geo')

    tabular_col.create_index([('job_id', 1)], background=True)
    tabular_col.create_index(
        [('job_id', 1), ('COD_ID', 1)],
        unique=True,
        background=True,
    )
    tabular_col.create_index([('job_id', 1), ('CONJ', 1)], background=True)
    tabular_col.create_index([('job_id', 1), ('CTMT', 1)], background=True)

    geo_col.create_index([('job_id', 1)], background=True)
    geo_col.create_index(
        [('job_id', 1), ('COD_ID', 1)],
        unique=True,
        background=True,
    )
    geo_col.create_index([('geometry', '2dsphere')], background=True)

    tabular_col.delete_many({'job_id': job_id})
    geo_col.delete_many({'job_id': job_id})

    total_inserted = 0
    tabular_batch: list[dict] = []
    geo_batch: list[dict] = []

    for path in tabular_paths:
        for raw in _iter_ndjson(path):
            doc = _to_notebook_ssdmt_tabular(
                raw,
                job_id,
                processed_at,
                distribuidora_id,
            )
            if doc is None:
                continue
            tabular_batch.append(doc)
            if len(tabular_batch) >= SSDMT_INSERT_BATCH_SIZE:
                tabular_col.insert_many(tabular_batch, ordered=False)
                total_inserted += len(tabular_batch)
                tabular_batch = []

    if tabular_batch:
        tabular_col.insert_many(tabular_batch, ordered=False)
        total_inserted += len(tabular_batch)

    for path in geo_paths:
        for raw in _iter_ndjson(path):
            doc = _to_notebook_ssdmt_geo(
                raw,
                job_id,
                processed_at,
                distribuidora_id,
            )
            if doc is None:
                continue
            geo_batch.append(doc)
            if len(geo_batch) >= SSDMT_INSERT_BATCH_SIZE:
                geo_col.insert_many(geo_batch, ordered=False)
                geo_batch = []

    if geo_batch:
        geo_col.insert_many(geo_batch, ordered=False)

    for path in tabular_paths + geo_paths:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            logger.warning(
                '[task_finalizar] Falha ao remover arquivo temporario SSDMT. job_id=%s path=%s',
                job_id,
                path,
            )

    return {
        'total': total_inserted,
        'descartados': total_descartados,
        'falhas_reprojecao': total_falhas,
        'tabular_paths': tabular_paths,
        'geo_paths': geo_paths,
    }


def _persist_unsemt(
    records: list[dict],
    job_id: str,
    descartados: int,
    processed_at: str,
    distribuidora_id: str | None,
) -> int:
    col = _get_collection('unsemt')
    col.create_index([('job_id', 1)], background=True)
    col.create_index(
        [('job_id', 1), ('cod_id', 1)], unique=True, background=True
    )
    col.create_index([('job_id', 1), ('conj', 1)], background=True)

    col.delete_many({'job_id': job_id})

    docs = []
    for r in records:
        doc = {
            **r,
            'job_id': job_id,
            'distribuidora_id': distribuidora_id,
            'processed_at': processed_at,
        }
        docs.append(doc)

    if docs:
        col.insert_many(docs, ordered=False)

    return len(records)


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
    'PNTMT_01',
    'PNTMT_02',
    'PNTMT_03',
    'PNTMT_04',
    'PNTMT_05',
    'PNTMT_06',
    'PNTMT_07',
    'PNTMT_08',
    'PNTMT_09',
    'PNTMT_10',
    'PNTMT_11',
    'PNTMT_12',
    'PNTBT_01',
    'PNTBT_02',
    'PNTBT_03',
    'PNTBT_04',
    'PNTBT_05',
    'PNTBT_06',
    'PNTBT_07',
    'PNTBT_08',
    'PNTBT_09',
    'PNTBT_10',
    'PNTBT_11',
    'PNTBT_12',
}

REQUIRED_UNSEMT_COLUMNS: set[str] = {'COD_ID', 'CONJ', 'TIP_UNID', 'SIT_ATIV'}
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
    distribuidora_id: str | None = None,
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
                    'distribuidora_id': distribuidora_id,
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
                                'distribuidora_id': distribuidora_id,
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

    percentual_falhas = (
        (falhas_reprojecao / total_lidos) if total_lidos > 0 else 0.0
    )

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
        'distribuidora_id': distribuidora_id,
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
def task_processar_ctmt(
    job_id: str,
    gdb_path: str,
    distribuidora_id: str | None = None,
) -> dict:
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
        logger.info(
            '[task_processar_ctmt] Colunas existentes na camada CTMT: %s',
            present_cols,
        )

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
                'COD_ID': cod_id,
                'NOME': nome,
                'DIST': row.get('DIST'),
                'ENE_01': row.get('ENE_01'),
                'ENE_02': row.get('ENE_02'),
                'ENE_03': row.get('ENE_03'),
                'ENE_04': row.get('ENE_04'),
                'ENE_05': row.get('ENE_05'),
                'ENE_06': row.get('ENE_06'),
                'ENE_07': row.get('ENE_07'),
                'ENE_08': row.get('ENE_08'),
                'ENE_09': row.get('ENE_09'),
                'ENE_10': row.get('ENE_10'),
                'ENE_11': row.get('ENE_11'),
                'ENE_12': row.get('ENE_12'),
                'PERD_A3a': row.get('PERD_A3a'),
                'PERD_A4': row.get('PERD_A4'),
                'PERD_B': row.get('PERD_B'),
                'PERD_MED': row.get('PERD_MED'),
                'PERD_A3aA4': row.get('PERD_A3aA4'),
                'PERD_A3a_B': row.get('PERD_A3a_B'),
                'PERD_A4A3a': row.get('PERD_A4A3a'),
                'PERD_A4_B': row.get('PERD_A4_B'),
                'PERD_B_A3a': row.get('PERD_B_A3a'),
                'PERD_B_A4': row.get('PERD_B_A4'),
                'PNTMT_01': row.get('PNTMT_01'),
                'PNTMT_02': row.get('PNTMT_02'),
                'PNTMT_03': row.get('PNTMT_03'),
                'PNTMT_04': row.get('PNTMT_04'),
                'PNTMT_05': row.get('PNTMT_05'),
                'PNTMT_06': row.get('PNTMT_06'),
                'PNTMT_07': row.get('PNTMT_07'),
                'PNTMT_08': row.get('PNTMT_08'),
                'PNTMT_09': row.get('PNTMT_09'),
                'PNTMT_10': row.get('PNTMT_10'),
                'PNTMT_11': row.get('PNTMT_11'),
                'PNTMT_12': row.get('PNTMT_12'),
                'PNTBT_01': row.get('PNTBT_01'),
                'PNTBT_02': row.get('PNTBT_02'),
                'PNTBT_03': row.get('PNTBT_03'),
                'PNTBT_04': row.get('PNTBT_04'),
                'PNTBT_05': row.get('PNTBT_05'),
                'PNTBT_06': row.get('PNTBT_06'),
                'PNTBT_07': row.get('PNTBT_07'),
                'PNTBT_08': row.get('PNTBT_08'),
                'PNTBT_09': row.get('PNTBT_09'),
                'PNTBT_10': row.get('PNTBT_10'),
                'PNTBT_11': row.get('PNTBT_11'),
                'PNTBT_12': row.get('PNTBT_12'),
                'job_id': job_id,
                'distribuidora_id': distribuidora_id,
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
        'distribuidora_id': distribuidora_id,
        'records': records,
        'total': len(records),
        'descartados': descartados,
    }


@celery_app.task(name='etl.processar_ssdmt')
def task_processar_ssdmt(
    job_id: str,
    gdb_path: str,
    distribuidora_id: str | None = None,
) -> dict:
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
        distribuidora_id=distribuidora_id,
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
    distribuidora_id: str | None = None,
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
        distribuidora_id=distribuidora_id,
        start_index=start_index,
        window_size=chunk_size,
        allow_empty=True,
        file_suffix=f'_chunk_{chunk_index:05d}',
    )
    result['chunk_index'] = chunk_index
    return result


@celery_app.task(name='etl.processar_conj')
def task_processar_conj(
    job_id: str,
    gdb_path: str,
    distribuidora_id: str | None = None,
) -> dict:
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
                'distribuidora_id': distribuidora_id,
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
        'distribuidora_id': distribuidora_id,
        'records': records,
        'total': len(records),
        'descartados': descartados,
    }


@celery_app.task(name='etl.processar_unsemt')
def task_processar_unsemt(
    job_id: str,
    gdb_path: str,
    distribuidora_id: str | None = None,
) -> dict:
    logger.info(
        '[task_processar_unsemt] Inicio do processamento. job_id=%s gdb_path=%s',
        job_id,
        gdb_path,
    )

    records: list[dict] = []
    descartados = 0

    with fiona.open(gdb_path, layer='UNSEMT') as src:
        properties = src.schema.get('properties', {})
        present_cols = set(properties.keys())
        logger.info(
            '[task_processar_unsemt] Colunas existentes na camada UNSEMT: %s',
            present_cols,
        )
        missing = REQUIRED_UNSEMT_COLUMNS - present_cols
        if missing:
            raise RuntimeError(f'Camada UNSEMT sem colunas: {missing}')

        for feature in src:
            row = feature.get('properties') or {}
            cod_id = row.get('COD_ID')
            if cod_id is None:
                descartados += 1
                continue

            coordinates = None

            conj = row.get('CONJ')
            tip_unid = row.get('TIP_UNID')
            sit_ativ = row.get('SIT_ATIV')

            if tip_unid != '32' or sit_ativ != 'AT':
                descartados += 1
                continue

            geometry = feature.get('geometry')
            if not geometry or geometry['type'] != 'Point':
                descartados += 1
                continue

            coordinates = tuple(geometry['coordinates'])

            records.append({
                'cod_id': cod_id,
                'conj': conj,
                'coordinates': coordinates,
                'job_id': job_id,
                'distribuidora_id': distribuidora_id,
            })

    if not records:
        raise RuntimeError('Camada UNSEMT sem registros validos apos limpeza')

    logger.info(
        '[task_processar_unsemt] Processamento concluido. job_id=%s total=%s descartados=%s',
        job_id,
        len(records),
        descartados,
    )
    return {
        'layer': 'UNSEMT',
        'job_id': job_id,
        'distribuidora_id': distribuidora_id,
        'records': records,
        'total': len(records),
        'descartados': descartados,
    }


@celery_app.task(name='etl.finalizar')
def task_finalizar(
    results: list[dict],
    job_id: str,
    zip_path: str,
    tmp_dir: str,
    distribuidora_id: str | None = None,
) -> dict:
    """Persiste resultados do chord no MongoDB e atualiza o status do job."""
    logger.info(
        '[task_finalizar] Inicio. job_id=%s resultados=%s',
        job_id,
        len(results or []),
    )

    processed_at = datetime.now(timezone.utc).isoformat()
    ctmt_total = 0
    conj_total = 0
    ssdmt_total = 0
    ssdmt_descartados = 0
    ssdmt_falhas_reprojecao = 0
    unsemt_total = 0

    try:
        ctmt_result = next(
            (r for r in (results or []) if r.get('layer') == 'CTMT'), None
        )
        if ctmt_result:
            ctmt_total = _persist_ctmt(
                records=ctmt_result['records'],
                job_id=job_id,
                descartados=ctmt_result['descartados'],
                processed_at=processed_at,
                distribuidora_id=distribuidora_id,
            )
            logger.info(
                '[task_finalizar] CTMT persistido. job_id=%s total=%s',
                job_id,
                ctmt_total,
            )

        conj_result = next(
            (r for r in (results or []) if r.get('layer') == 'CONJ'), None
        )
        if conj_result:
            conj_total = _persist_conj(
                records=conj_result['records'],
                job_id=job_id,
                descartados=conj_result['descartados'],
                processed_at=processed_at,
                distribuidora_id=distribuidora_id,
            )
            logger.info(
                '[task_finalizar] CONJ persistido. job_id=%s total=%s',
                job_id,
                conj_total,
            )

        ssdmt_stats = _persist_ssdmt(
            results=results or [],
            job_id=job_id,
            processed_at=processed_at,
            distribuidora_id=distribuidora_id,
        )
        ssdmt_total = ssdmt_stats['total']
        ssdmt_descartados = ssdmt_stats['descartados']
        ssdmt_falhas_reprojecao = ssdmt_stats['falhas_reprojecao']
        logger.info(
            '[task_finalizar] SSDMT persistido. job_id=%s total=%s descartados=%s falhas_reprojecao=%s',
            job_id,
            ssdmt_total,
            ssdmt_descartados,
            ssdmt_falhas_reprojecao,
        )

        unsemt_result = next(
            (r for r in (results or []) if r.get('layer') == 'UNSEMT'), None
        )
        if unsemt_result:
            unsemt_total = _persist_unsemt(
                records=unsemt_result['records'],
                job_id=job_id,
                descartados=unsemt_result['descartados'],
                processed_at=processed_at,
                distribuidora_id=distribuidora_id,
            )
        logger.info(
            '[task_finalizar] UNSEMT persistido. job_id=%s total=%s descartados=%s',
            job_id,
            unsemt_total,
            unsemt_result['descartados'] if unsemt_result else 0,
        )

        _get_collection('jobs').update_one(
            {'job_id': job_id},
            {
                '$set': {
                    'job_id': job_id,
                    'distribuidora_id': distribuidora_id,
                    'status': 'completed',
                    'ctmt_total': ctmt_total,
                    'conj_total': conj_total,
                    'ssdmt_total': ssdmt_total,
                    'ssdmt_descartados': ssdmt_descartados,
                    'unsemt_total': unsemt_total,
                    'ssdmt_falhas_reprojecao': ssdmt_falhas_reprojecao,
                    'completed_at': processed_at,
                    'updated_at': processed_at,
                    'error_message': None,
                }
            },
            upsert=True,
        )

        logger.info(
            '[task_finalizar] Concluido. job_id=%s ctmt_total=%s conj_total=%s ssdmt_total=%s unsemt_total=%s',
            job_id,
            ctmt_total,
            conj_total,
            ssdmt_total,
            unsemt_total,
        )
        return {
            'job_id': job_id,
            'distribuidora_id': distribuidora_id,
            'status': 'completed',
            'ctmt_total': ctmt_total,
            'conj_total': conj_total,
            'ssdmt_total': ssdmt_total,
            'unsemt_total': unsemt_total,
        }

    except Exception as exc:
        logger.error(
            '[task_finalizar] Falha na persistencia. job_id=%s erro=%s',
            job_id,
            exc,
        )
        try:
            _get_collection('circuitos_mt').delete_many({'job_id': job_id})
        except Exception:
            pass
        for collection_name in (
            'segmentos_mt_tabular',
            'segmentos_mt_geo',
            'conjuntos',
            'unsemt',
        ):
            try:
                _get_collection(collection_name).delete_many({
                    'job_id': job_id
                })
            except Exception:
                pass
        try:
            _get_collection('jobs').update_one(
                {'job_id': job_id},
                {
                    '$set': {
                        'status': 'failed',
                        'updated_at': datetime.now(timezone.utc).isoformat(),
                        'error_message': str(exc),
                    }
                },
                upsert=True,
            )
        except Exception:
            pass
        raise
