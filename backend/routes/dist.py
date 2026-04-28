from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.core.schemas import SyncDistribuidorasResponse
from backend.services.distribuidoras import INITIAL_URL, sync_distribuidoras

router = APIRouter(tags=['distribuidoras'])


@router.post('/sync', response_model=SyncDistribuidorasResponse)
async def sync_distribuidoras_endpoint(
    session: AsyncSession = Depends(get_session),
):
    try:
        return await sync_distribuidoras(
            session=session, initial_url=INITIAL_URL
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
