import csv
import logging
import os
from datetime import datetime
from pathlib import Path

import httpx
from pymongo import ASCENDING, UpdateOne

from backend.database import get_mongo_sync_db
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

TMP_DIR = Path(os.getenv('TMP_DIR', '/data/tmp/'))

CHUNK_SIZE = int(os.getenv('SSDMT_BATCH_SIZE', '10000'))


def _get_collection(name: str):
    db = get_mongo_sync_db()
    return db[name]


def _ensure_index(collection, fields: list[str]) -> None:
    index_keys = [(f, ASCENDING) for f in fields]
    index_name = '_'.join(f for f in fields) + '_unique'
    existing = {idx['name'] for idx in collection.list_indexes()}
    if index_name not in existing:
        collection.create_index(
            index_keys, unique=True, name=index_name, sparse=True
        )


def _download_csv(url: str, dest: Path) -> None:
    with httpx.stream('GET', url, follow_redirects=True, timeout=600) as r:
        r.raise_for_status()
        content_type = r.headers.get('content-type', '')
        if 'html' in content_type:
            raise ValueError(
                f'URL retornou HTML em vez de CSV. '
                f'Verifique se a URL aponta para o download direto do arquivo. '
                f'URL recebida: {url}'
            )
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, 'wb') as f:
            for chunk in r.iter_bytes(chunk_size=8192):
                f.write(chunk)


def _iter_chunks(path: Path):
    with open(path, encoding='latin-1', newline='') as f:
        reader = csv.DictReader(f, delimiter=';')
        if reader.fieldnames:
            reader.fieldnames = [col.strip() for col in reader.fieldnames]
        logger.info('[_iter_chunks] colunas=%s', reader.fieldnames)
        chunk: list[dict] = []
        for row in reader:
            chunk.append(row)
            if len(chunk) >= CHUNK_SIZE:
                yield chunk
                chunk = []
        if chunk:
            yield chunk


def _to_str(value: str) -> str | None:
    v = value.strip() if value else ''
    return v if v else None


def _to_int(value: str) -> int | None:
    v = value.strip() if value else ''
    return int(v) if v else None


def _to_float(value: str) -> float | None:
    v = value.strip().replace(',', '.') if value else ''
    return float(v) if v else None


def _to_date(value: str) -> datetime | None:
    v = value.strip() if value else ''
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='etl.load_dec_fec_realizado',
)
def task_load_dec_fec_realizado(self, job_id: str, url: str) -> dict:
    logger.info('[task_load_dec_fec_realizado] Inicio. job_id=%s', job_id)

    csv_path = TMP_DIR / f'{job_id}_realizado.csv'

    try:
        logger.info(
            '[task_load_dec_fec_realizado] Baixando CSV. job_id=%s', job_id
        )
        _download_csv(url, csv_path)

        collection = _get_collection('dec_fec_realizado')
        _ensure_index(
            collection,
            [
                'sig_agente',
                'ide_conj',
                'sig_indicador',
                'ano_indice',
                'num_periodo',
            ],
        )
        total = 0

        for chunk in _iter_chunks(csv_path):
            ops = []
            for row in chunk:
                doc = {
                    'dat_geracao': _to_date(row['DatGeracaoConjuntoDados']),
                    'sig_agente': _to_str(row['SigAgente']),
                    'num_cnpj': _to_str(row['NumCNPJ']),
                    'ide_conj': _to_str(row['IdeConjUndConsumidoras']),
                    'dsc_conj': _to_str(row['DscConjUndConsumidoras']),
                    'sig_indicador': _to_str(row['SigIndicador']),
                    'ano_indice': _to_int(row['AnoIndice']),
                    'num_periodo': _to_int(row['NumPeriodoIndice']),
                    'vlr_indice': _to_float(row['VlrIndiceEnviado']),
                }
                filtro = {
                    'sig_agente': doc['sig_agente'],
                    'ide_conj': doc['ide_conj'],
                    'sig_indicador': doc['sig_indicador'],
                    'ano_indice': doc['ano_indice'],
                    'num_periodo': doc['num_periodo'],
                }
                ops.append(UpdateOne(filtro, {'$set': doc}, upsert=True))

            if ops:
                result = collection.bulk_write(ops, ordered=False)
                total += result.upserted_count + result.modified_count
                logger.info(
                    '[task_load_dec_fec_realizado] Progresso. job_id=%s linhas_salvas=%s',
                    job_id,
                    total,
                )

        logger.info(
            '[task_load_dec_fec_realizado] Concluido. job_id=%s documentos=%s',
            job_id,
            total,
        )
        return {
            'job_id': job_id,
            'status': 'done',
            'documents_upserted': total,
        }

    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning(
            '[task_load_dec_fec_realizado] Erro de rede. job_id=%s erro=%s',
            job_id,
            exc,
        )
        raise self.retry(exc=exc)
    except KeyError as exc:
        logger.exception(
            '[task_load_dec_fec_realizado] Coluna ausente. job_id=%s coluna=%s',
            job_id,
            exc,
        )
        raise
    except Exception as exc:
        logger.exception(
            '[task_load_dec_fec_realizado] Falha. job_id=%s erro=%s',
            job_id,
            exc,
        )
        raise
    finally:
        csv_path.unlink(missing_ok=True)


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='etl.load_dec_fec_limite',
)
def task_load_dec_fec_limite(self, job_id: str, url: str) -> dict:
    logger.info('[task_load_dec_fec_limite] Inicio. job_id=%s', job_id)

    csv_path = TMP_DIR / f'{job_id}_limite.csv'

    try:
        logger.info(
            '[task_load_dec_fec_limite] Baixando CSV. job_id=%s', job_id
        )
        _download_csv(url, csv_path)

        collection = _get_collection('dec_fec_limite')
        _ensure_index(
            collection,
            ['sig_agente', 'ide_conj', 'sig_indicador', 'ano_limite'],
        )
        total = 0

        for chunk in _iter_chunks(csv_path):
            ops = []
            for row in chunk:
                doc = {
                    'dat_geracao': _to_date(row['DatGeracaoConjuntoDados']),
                    'sig_agente': _to_str(row['SigAgente']),
                    'num_cnpj': _to_str(row['NumCNPJ']),
                    'ide_conj': _to_str(row['IdeConjUndConsumidoras']),
                    'dsc_conj': _to_str(row['DscConjUndConsumidoras']),
                    'sig_indicador': _to_str(row['SigIndicador']),
                    'ano_limite': _to_int(row['AnoLimiteQualidade']),
                    'vlr_limite': _to_float(row['VlrLimite']),
                }
                filtro = {
                    'sig_agente': doc['sig_agente'],
                    'ide_conj': doc['ide_conj'],
                    'sig_indicador': doc['sig_indicador'],
                    'ano_limite': doc['ano_limite'],
                }
                ops.append(UpdateOne(filtro, {'$set': doc}, upsert=True))

            if ops:
                result = collection.bulk_write(ops, ordered=False)
                total += result.upserted_count + result.modified_count

        logger.info(
            '[task_load_dec_fec_limite] Concluido. job_id=%s documentos=%s',
            job_id,
            total,
        )
        return {
            'job_id': job_id,
            'status': 'done',
            'documents_upserted': total,
        }

    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning(
            '[task_load_dec_fec_limite] Erro de rede. job_id=%s erro=%s',
            job_id,
            exc,
        )
        raise self.retry(exc=exc)
    except KeyError as exc:
        logger.exception(
            '[task_load_dec_fec_limite] Coluna ausente. job_id=%s coluna=%s',
            job_id,
            exc,
        )
        raise
    except Exception as exc:
        logger.exception(
            '[task_load_dec_fec_limite] Falha. job_id=%s erro=%s', job_id, exc
        )
        raise
    finally:
        csv_path.unlink(missing_ok=True)
