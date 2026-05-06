from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import Distribuidora
from backend.core.schemas import (
    PipelineTriggerRequest,
    PipelineTriggerResponse,
    ReportStatusResponse,
)
from backend.database import get_mongo_async_database, get_session
from backend.services.pipeline_trigger import trigger_pipeline_flow

router = APIRouter(tags=['pipeline'])


@router.post(
    '/trigger', status_code=202, response_model=PipelineTriggerResponse
)
async def trigger_pipeline(
    request: PipelineTriggerRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await trigger_pipeline_flow(
            session=session,
            distribuidora_id=request.distribuidora_id,
            ano=request.ano,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get(
    '/report/{distribuidora_id}', response_model=ReportStatusResponse
)
async def get_report_status(
    distribuidora_id: str,
    session: AsyncSession = Depends(get_session),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_async_database),
):
    stmt = (
        select(Distribuidora.job_id)
        .where(
            Distribuidora.id == distribuidora_id,
            Distribuidora.job_id.isnot(None),
        )
        .order_by(Distribuidora.processed_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    job_id = result.scalar_one_or_none()

    if not job_id:
        raise HTTPException(
            status_code=404,
            detail='Nenhum job encontrado para a distribuidora informada',
        )

    job_doc = await mongo_db['jobs'].find_one({'job_id': job_id}, {'_id': 0})
    if not job_doc:
        raise HTTPException(status_code=404, detail='Job não encontrado no MongoDB')

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
    stmt = (
        select(Distribuidora.job_id)
        .where(
            Distribuidora.id == distribuidora_id,
            Distribuidora.job_id.isnot(None),
        )
        .order_by(Distribuidora.processed_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    job_id = result.scalar_one_or_none()

    if not job_id:
        raise HTTPException(status_code=404, detail='Nenhum job encontrado para a distribuidora informada')

    job_doc = await mongo_db['jobs'].find_one({'job_id': job_id}, {'_id': 0})
    if not job_doc:
        raise HTTPException(status_code=404, detail='Job não encontrado no MongoDB')

    pdf_path = job_doc.get('report_pdf_path')
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail='Relatório ainda não gerado ou arquivo não encontrado')

    return FileResponse(
        path=pdf_path,
        media_type='application/pdf',
        filename=f'report_{distribuidora_id}.pdf',
    )
