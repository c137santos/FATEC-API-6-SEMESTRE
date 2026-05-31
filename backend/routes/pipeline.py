from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.audit_log import Operation
from backend.core.models import User
from backend.core.schemas import (
    BatchStatusResponse,
    BatchTriggerRequest,
    BatchTriggerResponse,
    PipelineTriggerRequest,
    PipelineTriggerResponse,
    ReportStatusResponse,
)
from backend.database import get_mongo_async_database, get_session
from backend.security import get_current_user
from backend.services.audit_log_service import write_log
from backend.services.distribuidoras import (
    get_distribuidoras_for_batch,
    get_latest_job_id,
)
from backend.services.pipeline_batch import get_last_batch, start_batch
from backend.services.pipeline_trigger import trigger_pipeline_flow
from backend.tasks.task_pipeline_batch import task_run_batch

router = APIRouter(tags=['pipeline'])


@router.post(
    '/trigger', status_code=202, response_model=PipelineTriggerResponse
)
async def trigger_pipeline(
    request: PipelineTriggerRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await trigger_pipeline_flow(
            session=session,
            distribuidora_id=request.distribuidora_id,
            ano=request.ano,
            user_email=current_user.email,
        )
        await write_log(
            operation=Operation.REPORT_REQUESTED,
            user_id=current_user.id,
            entity_name='Pipeline',
            to_value={
                'distribuidora_id': request.distribuidora_id,
                'ano': request.ano,
                'job_id': result.get('job_id'),
            },
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post('/batch', status_code=202, response_model=BatchTriggerResponse)
async def trigger_batch(
    request: BatchTriggerRequest,
    session: AsyncSession = Depends(get_session),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_async_database),
    current_user: User = Depends(get_current_user),
):
    existing = await mongo_db.batch_runs.find_one(
        {'is_running': True}, {'_id': 0}
    )
    if existing:
        raise HTTPException(
            status_code=409, detail='Já existe um lote em execução'
        )

    distribuidoras = await get_distribuidoras_for_batch(session, request.year)

    batch_id = await start_batch(
        params=request,
        user_email=current_user.email,
        mongo_db=mongo_db,
    )
    task_run_batch.delay(
        batch_id, request.model_dump(), current_user.email, distribuidoras
    )
    return BatchTriggerResponse(batch_id=batch_id)


@router.get('/batch/status', response_model=BatchStatusResponse)
async def get_batch_status(
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_async_database),
    current_user: User = Depends(get_current_user),
):
    last_batch = await get_last_batch(mongo_db)
    if last_batch is None:
        raise HTTPException(status_code=404, detail='Nenhum lote encontrado')
    return last_batch


@router.get('/report/{distribuidora_id}', response_model=ReportStatusResponse)
async def get_report_status(
    distribuidora_id: str,
    session: AsyncSession = Depends(get_session),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_async_database),
):
    job_id = await get_latest_job_id(session, distribuidora_id)

    if not job_id:
        raise HTTPException(
            status_code=404,
            detail='Nenhum job encontrado para a distribuidora informada',
        )

    job_doc = await mongo_db['jobs'].find_one({'job_id': job_id}, {'_id': 0})
    if not job_doc:
        raise HTTPException(
            status_code=404, detail='Job não encontrado no MongoDB'
        )

    return ReportStatusResponse(
        job_id=job_id,
        etl_status=job_doc.get('status', 'unknown'),
        report_status=job_doc.get('report_status', 'pending'),
        report_pdf_path=job_doc.get('report_pdf_path'),
    )


@router.get('/report/{distribuidora_id}/download')
async def download_report(
    distribuidora_id: str,
    session: AsyncSession = Depends(get_session),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_async_database),
):
    job_id = await get_latest_job_id(session, distribuidora_id)

    if not job_id:
        raise HTTPException(
            status_code=404,
            detail='Nenhum job encontrado para a distribuidora informada',
        )

    job_doc = await mongo_db['jobs'].find_one({'job_id': job_id}, {'_id': 0})
    if not job_doc:
        raise HTTPException(
            status_code=404, detail='Job não encontrado no MongoDB'
        )

    pdf_path = job_doc.get('report_pdf_path')
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(
            status_code=404,
            detail='Relatório ainda não gerado ou arquivo não encontrado',
        )

    return FileResponse(
        path=pdf_path,
        media_type='application/pdf',
        filename=f'report_{distribuidora_id}.pdf',
    )
