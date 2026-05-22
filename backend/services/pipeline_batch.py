import logging
import uuid
from datetime import datetime, timezone

from celery import chain
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.database import Database as MongoSyncDatabase
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from backend.core.models import Distribuidora, DistribuidoraCnpj
from backend.core.schemas import BatchTriggerRequest
from backend.database import engine, get_mongo_sync_db, sync_engine
from backend.services.pipeline_trigger import ARCGIS_DOWNLOAD_URL, DOWNLOAD_DIR
from backend.tasks.task_descompact_gdb import task_descompact_gdb
from backend.tasks.task_download_gdb import task_download_gdb

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Async helpers — used by FastAPI routes
# ---------------------------------------------------------------------------


async def get_last_batch(mongo_db: AsyncIOMotorDatabase) -> dict | None:
    return await mongo_db.batch_runs.find_one(
        {}, {'_id': 0}, sort=[('started_at', -1)]
    )


async def start_batch(
    params: BatchTriggerRequest,
    user_email: str,
    mongo_db: AsyncIOMotorDatabase,
    distribuidoras: list[dict],
) -> str:

    batch_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await mongo_db.batch_runs.insert_one({
        'batch_id': batch_id,
        'is_running': True,
        'started_at': now,
        'finished_at': None,
        'params': params.model_dump(),
        'user_email': user_email,
        'counts': {
            'total': 0,
            'pending': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0,
            'skipped': 0,
        },
        'distribuidoras': [],
    })

    from backend.tasks.task_pipeline_batch import task_run_batch
    task_run_batch.delay(batch_id, params.model_dump(), user_email, distribuidoras)

    return batch_id


def _classify_distribuidoras(
    distribuidoras: list[dict],
    db: MongoSyncDatabase,
) -> tuple[list[dict], list[dict]]:
    to_process: list[dict] = []
    to_skip: list[dict] = []

    for dist in distribuidoras:
        if dist['job_id'] is None:
            to_process.append({'distribuidora': dist, 'force_full': False})
            continue

        job_doc = db.jobs.find_one({'job_id': dist['job_id']}, {'_id': 0})
        report_status = job_doc.get('report_status') if job_doc else None

        if report_status == 'completed':
            to_skip.append({'distribuidora': dist})
        else:
            to_process.append({'distribuidora': dist, 'force_full': True})

    return to_process, to_skip


def _pg_ops_for_batch(dist_id: str, ano: int, job_id: str) -> str | None:
    with Session(sync_engine) as session:
        cnpj = session.execute(
            select(DistribuidoraCnpj.cnpj).where(
                DistribuidoraCnpj.dist_id == dist_id,
                DistribuidoraCnpj.cnpj_enrichment_status == 'matched',
            )
        ).scalar_one_or_none()

        if cnpj is None:
            return None

        session.execute(
            update(Distribuidora)
            .where(Distribuidora.id == dist_id, Distribuidora.date_gdb == ano)
            .values(
                job_id=job_id,
                processed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        session.commit()
        return cnpj


def _update_batch_dist_status(
    db: MongoSyncDatabase,
    batch_id: str,
    dist_id: str,
    status: str,
    error: str | None = None,
) -> None:
    result = db.batch_runs.find_one_and_update(
        {'batch_id': batch_id},
        {
            '$set': {
                f'distribuidoras.$[elem].status': status,
                f'distribuidoras.$[elem].error': error,
            },
            '$inc': {f'counts.{status}': 1, 'counts.pending': -1},
        },
        array_filters=[{'elem.id': dist_id}],
        return_document=True,
    )
    if result and result['counts'].get('pending', 0) <= 0:
        db.batch_runs.update_one(
            {'batch_id': batch_id},
            {'$set': {'is_running': False, 'finished_at': datetime.now(timezone.utc)}},
        )


def _trigger_pipeline_sync(
    dist: dict,
    user_email: str,
    db: MongoSyncDatabase,
    batch_id: str,
) -> str:
    dist_id = dist['id']
    ano = dist['date_gdb']
    sig_agente = dist['dist_name'].replace('_', ' ')

    old_job_id = dist.get('job_id')

    job_id = str(uuid.uuid4())
    zip_path = str(DOWNLOAD_DIR / f'{job_id}.zip')

    cnpj = _pg_ops_for_batch(dist_id, ano, job_id)

    if cnpj is None:
        raise LookupError(f'Distribuidora {dist_id} sem CNPJ associado')

    chain(
        task_download_gdb.si(job_id, ARCGIS_DOWNLOAD_URL.format(item_id=dist_id), dist_id),
        task_descompact_gdb.si(job_id, zip_path, dist_id),
    ).delay()

    if old_job_id:
        for col_name in (
            'jobs', 'circuitos_mt', 'conjuntos', 'segmentos_mt_tabular',
            'segmentos_mt_geo', 'unsemt', 'score_criticidade', 'mapa_criticidade',
        ):
            db[col_name].delete_many({'job_id': old_job_id})
        logger.info('[batch] Dados do job anterior removidos. old_job_id=%s dist_id=%s', old_job_id, dist_id)

    db.jobs.insert_one({
        'job_id': job_id,
        'distribuidora_id': dist_id,
        'dist_name': sig_agente,
        'ano_gdb': ano,
        'cnpj': cnpj,
        'batch_id': batch_id,
        'trigger_calculations': True,
        'status': 'started',
        'user_email': user_email,
        'created_at': datetime.now(timezone.utc),
    })

    logger.info('[batch] Pipeline disparada. job_id=%s dist_id=%s', job_id, dist_id)
    return job_id


def _run_batch(
    batch_id: str,
    params: BatchTriggerRequest,
    user_email: str,
    distribuidoras: list[Distribuidora],
) -> None:
    db = get_mongo_sync_db()
    logger.info('[batch] Iniciando execução. batch_id=%s', batch_id)

    to_process, to_skip = _classify_distribuidoras(distribuidoras, db)
    logger.info(
        '[batch] batch_id=%s total=%d processar=%d pular=%d',
        batch_id, len(distribuidoras), len(to_process), len(to_skip),
    )

    dist_list = [
        {'id': item['distribuidora']['id'], 'nome': item['distribuidora']['dist_name'],
         'ano': item['distribuidora']['date_gdb'], 'status': 'pending', 'error': None}
        for item in to_process
    ] + [
        {'id': item['distribuidora']['id'], 'nome': item['distribuidora']['dist_name'],
         'ano': item['distribuidora']['date_gdb'], 'status': 'skipped', 'error': None}
        for item in to_skip
    ]

    db.batch_runs.update_one(
        {'batch_id': batch_id},
        {'$set': {
            'distribuidoras': dist_list,
            'counts': {
                'total': len(distribuidoras),
                'pending': len(to_process),
                'processing': 0,
                'completed': 0,
                'failed': 0,
                'skipped': len(to_skip),
            },
        }},
    )

    if not to_process:
        db.batch_runs.update_one(
            {'batch_id': batch_id},
            {'$set': {'is_running': False, 'finished_at': datetime.now(timezone.utc)}},
        )
        logger.info('[batch] Nenhuma distribuidora para processar. batch_id=%s', batch_id)
        return

    for item in to_process:
        dist = item['distribuidora']
        dist_id = dist['id']
        try:
            _trigger_pipeline_sync(dist, user_email, db, batch_id)
            logger.info('[batch] Pipeline disparada. dist_id=%s batch_id=%s', dist_id, batch_id)
        except Exception as exc:
            logger.exception('[batch] Falha ao disparar dist_id=%s', dist_id)
            _update_batch_dist_status(db, batch_id, dist_id, 'failed', str(exc))
