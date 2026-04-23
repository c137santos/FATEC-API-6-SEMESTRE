from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session

from .schemas import SyncDistribuidorasRequest, SyncDistribuidorasResponse
from .services import INITIAL_URL, sync_distribuidoras

router = APIRouter(tags=['distribuidoras'])


@router.post('/sync', response_model=SyncDistribuidorasResponse)
async def sync_distribuidoras_endpoint(
    payload: SyncDistribuidorasRequest,
    session: AsyncSession = Depends(get_session),
):
    initial_url = str(payload.initial_url) if payload.initial_url else INITIAL_URL

    try:
        return await sync_distribuidoras(session=session, initial_url=initial_url)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc