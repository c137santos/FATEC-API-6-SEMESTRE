import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import Distribuidora, DistribuidoraCnpj
from backend.core.schemas import (
    CnpjLookupResponse,
    DistributorResponse,
    SyncDistribuidorasResponse,
)
from backend.database import get_session
from backend.services.distribuidoras import INITIAL_URL, sync_distribuidoras
from backend.tasks.task_enrich_cnpj import task_enrich_cnpj

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
        counts = await sync_distribuidoras(session=session, initial_url=INITIAL_URL)
        task = task_enrich_cnpj.delay()
        return SyncDistribuidorasResponse(
            total_recebidas=counts.total_recebidas,
            total_persistidas=counts.total_persistidas,
            enrichment_task_id=task.id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post('/distribuidoras/{dist_id}/cnpj-lookup', response_model=CnpjLookupResponse)
async def cnpj_lookup(
    dist_id: str,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Distribuidora).where(Distribuidora.id == dist_id).limit(1)
    result = await session.execute(stmt)
    dist = result.scalar_one_or_none()
    if dist is None:
        raise HTTPException(status_code=404, detail='Distribuidora não encontrada')

    stmt = select(DistribuidoraCnpj).where(DistribuidoraCnpj.dist_id == dist_id)
    result = await session.execute(stmt)
    cnpj_record = result.scalar_one_or_none()

    if cnpj_record and cnpj_record.cnpj_enrichment_status == 'matched':
        raise HTTPException(status_code=409, detail='Distribuidora já possui CNPJ resolvido')

    raise HTTPException(status_code=501, detail='External CNPJ lookup not yet configured')
