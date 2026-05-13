import asyncio
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import Distribuidora
from backend.core.schemas import BatchTriggerRequest
from backend.services.pipeline_trigger import trigger_pipeline_flow


async def get_last_batch(mongo_db: AsyncIOMotorDatabase) -> dict | None:
    return await mongo_db.batch_runs.find_one(
        {}, {'_id': 0}, sort=[('started_at', -1)]
    )


async def start_batch(
    params: BatchTriggerRequest,
    user_email: str,
    session: AsyncSession,
    mongo_db: AsyncIOMotorDatabase,
) -> str:
    existing = await mongo_db.batch_runs.find_one({'is_running': True}, {'_id': 0})
    if existing:
        raise ValueError('Já existe um lote em execução')

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

    asyncio.create_task(
        _run_batch(batch_id, params, user_email, session, mongo_db)
    )

    return batch_id


async def _classify_distribuidoras(
    distribuidoras: list[Distribuidora],
    session: AsyncSession,
    mongo_db: AsyncIOMotorDatabase,
) -> tuple[list[dict], list[dict]]:
    """Classifica distribuidoras em to_process e to_skip.

    Cada item de to_process: {'distribuidora': Distribuidora, 'force_full': bool}
    Cada item de to_skip:    {'distribuidora': Distribuidora}
    """
    to_process: list[dict] = []
    to_skip: list[dict] = []

    for dist in distribuidoras:
        if dist.job_id is None:
            to_process.append({'distribuidora': dist, 'force_full': False})
            continue

        job_doc = await mongo_db.jobs.find_one({'job_id': dist.job_id}, {'_id': 0})
        report_status = job_doc.get('report_status') if job_doc else None

        if report_status == 'failed':
            to_process.append({'distribuidora': dist, 'force_full': True})
        elif report_status == 'completed':
            to_skip.append({'distribuidora': dist})
        else:
            # No doc yet or still running — treat as active
            to_skip.append({'distribuidora': dist})

    return to_process, to_skip


async def _dispatch_and_poll(
    item: dict,
    batch_id: str,
    params: BatchTriggerRequest,
    user_email: str,
    session: AsyncSession,
    mongo_db: AsyncIOMotorDatabase,
) -> None:
    dist: Distribuidora = item['distribuidora']
    force_full: bool = item['force_full']
    dist_id = dist.id
    ano = dist.date_gdb

    await mongo_db.batch_runs.update_one(
        {'batch_id': batch_id, 'distribuidoras.id': dist_id},
        {
            '$set': {'distribuidoras.$.status': 'processing'},
            '$inc': {'counts.processing': 1, 'counts.pending': -1},
        },
    )

    final_status = 'failed'
    error = None
    try:
        result = await trigger_pipeline_flow(
            session=session,
            distribuidora_id=dist_id,
            ano=ano,
            user_email=user_email,
            force_full=force_full,
        )
        job_id = result['job_id']

        await asyncio.sleep(params.min_wait)

        for _ in range(params.max_attempts):
            job_doc = await mongo_db.jobs.find_one({'job_id': job_id}, {'_id': 0})
            if job_doc:
                report_status = job_doc.get('report_status')
                if report_status in ('completed', 'failed'):
                    final_status = report_status
                    error = job_doc.get('error')
                    break
            await asyncio.sleep(params.poll_interval)
        else:
            error = 'Timeout no polling'

    except Exception as exc:
        error = str(exc)

    await mongo_db.batch_runs.update_one(
        {'batch_id': batch_id, 'distribuidoras.id': dist_id},
        {
            '$set': {
                'distribuidoras.$.status': final_status,
                'distribuidoras.$.error': error,
            },
            '$inc': {'counts.processing': -1, f'counts.{final_status}': 1},
        },
    )


async def _run_batch(
    batch_id: str,
    params: BatchTriggerRequest,
    user_email: str,
    session: AsyncSession,
    mongo_db: AsyncIOMotorDatabase,
) -> None:
    try:
        stmt = select(Distribuidora)
        if params.year is not None:
            stmt = stmt.where(Distribuidora.date_gdb == params.year)
        result = await session.execute(stmt)
        distribuidoras = result.scalars().all()

        to_process, to_skip = await _classify_distribuidoras(distribuidoras, session, mongo_db)

        dist_list = [
            {'id': item['distribuidora'].id, 'nome': item['distribuidora'].dist_name,
             'ano': item['distribuidora'].date_gdb, 'status': 'pending', 'error': None}
            for item in to_process
        ] + [
            {'id': item['distribuidora'].id, 'nome': item['distribuidora'].dist_name,
             'ano': item['distribuidora'].date_gdb, 'status': 'skipped', 'error': None}
            for item in to_skip
        ]

        await mongo_db.batch_runs.update_one(
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

        for i in range(0, len(to_process), params.concurrency):
            group = to_process[i:i + params.concurrency]
            await asyncio.gather(*(
                _dispatch_and_poll(item, batch_id, params, user_email, session, mongo_db)
                for item in group
            ))

    finally:
        await mongo_db.batch_runs.update_one(
            {'batch_id': batch_id},
            {'$set': {
                'is_running': False,
                'finished_at': datetime.now(timezone.utc),
            }},
        )
