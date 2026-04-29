from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.schemas import (
    PipelineTriggerRequest,
    PipelineTriggerResponse,
)
from backend.database import get_session
from backend.services.etl_download import enqueue_download_gdb
from backend.services.pipeline_trigger import (
    distribuidora_job_already_triggered,
    resolve_download_url_from_aneel,
    save_distribuidora_job_tracking,
)

router = APIRouter(tags=['pipeline'])


@router.post(
    '/trigger', status_code=202, response_model=PipelineTriggerResponse
)
async def trigger_pipeline(
    request: PipelineTriggerRequest,
    session: AsyncSession = Depends(get_session),
):
    if await distribuidora_job_already_triggered(
        session,
        request.distribuidora_id,
        request.ano,
    ):
        raise HTTPException(
            status_code=409,
            detail='Pipeline já foi acionada para a distribuidora no ano informado',
        )

    try:
        download_url = await resolve_download_url_from_aneel(
            request.distribuidora_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        enqueue_result = enqueue_download_gdb(
            download_url, request.distribuidora_id
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    await save_distribuidora_job_tracking(
        session=session,
        distribuidora_id=request.distribuidora_id,
        ano=request.ano,
        job_id=enqueue_result['job_id'],
    )

    return {
        **enqueue_result,
        'distribuidora_id': request.distribuidora_id,
        'ano': request.ano,
        'download_url': download_url,
    }
