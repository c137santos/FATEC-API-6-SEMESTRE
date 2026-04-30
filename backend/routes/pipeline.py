from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.schemas import (
    PipelineTriggerRequest,
    PipelineTriggerResponse,
)
from backend.database import get_session
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
