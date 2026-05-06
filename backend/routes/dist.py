import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_session
from backend.core.schemas import (
    SyncDistribuidorasResponse,
    DistributorResponse,
)
from backend.core.models import Distribuidora
from backend.services.distribuidoras import INITIAL_URL, sync_distribuidoras

router = APIRouter(tags=['distribuidoras'])
logger = logging.getLogger(__name__)


@router.get('/distributors', response_model=list[DistributorResponse])
async def get_distributors(
    session: AsyncSession = Depends(get_session),
):
    """
    Retorna a lista de distribuidoras cadastradas no PostgreSQL.

    Lista todas as distribuidoras disponíveis na tabela, ordenadas por nome (ascendente).
    Retorna dados no formato: [{"id": "<id_arcgis>", "nome": "CPFL Paulista", "ano": 2024}, ...]

    Returns:
        Lista de distribuidoras com id, nome e ano, ordenada por nome ascendente.
        Retorna lista vazia [] se não houver dados.

    Raises:
        HTTPException: Erro de conexão com o banco (HTTP 500)
    """
    try:
        # Query para buscar distribuidoras ordenadas por nome
        stmt = select(Distribuidora).order_by(Distribuidora.dist_name.asc())
        result = await session.execute(stmt)
        distribuidoras = result.scalars().all()

        # Converter para o formato de resposta
        distributors_list = [
            DistributorResponse(
                id=distribuidora.id,
                nome=distribuidora.dist_name,
                ano=distribuidora.date_gdb,
            )
            for distribuidora in distribuidoras
        ]

        logger.info(f'Retornadas {len(distributors_list)} distribuidoras')
        return distributors_list

    except Exception as e:
        logger.error(f'Erro ao buscar distribuidoras: {e}')
        raise HTTPException(
            status_code=500, detail='Erro interno ao buscar distribuidoras'
        )


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
