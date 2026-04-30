from datetime import datetime, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import Distribuidora
from backend.services.criticidade import (
    calcular_score_criticidade,
    criar_mapa_criticidade,
)
from backend.services.etl_download import enqueue_download_gdb
from backend.services.render_criticidade import (
    render_mapa_calor_criticidade,
    render_tabela_score_criticidade,
)

ARCGIS_ITEM_URL = 'https://www.arcgis.com/sharing/rest/content/items/{item_id}'
ARCGIS_DOWNLOAD_URL = (
    'https://www.arcgis.com/sharing/rest/content/items/{item_id}/data'
)
ALLOWED_ITEM_TYPES = {'Feature Service', 'File Geodatabase'}


async def _get_distribuidora_info(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
) -> tuple[str, str | None]:
    """Retorna (dist_name, job_id_atual) da distribuidora."""
    stmt = select(Distribuidora.dist_name, Distribuidora.job_id).where(
        Distribuidora.id == distribuidora_id,
        Distribuidora.date_gdb == ano,
    )
    result = await session.execute(stmt)
    row = result.one()
    return row.dist_name, row.job_id


async def distribuidora_job_already_triggered(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
) -> bool:
    stmt = select(Distribuidora.job_id).where(
        Distribuidora.id == distribuidora_id,
        Distribuidora.date_gdb == ano,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def resolve_download_url_from_aneel(
    distribuidora_id: str,
    client: httpx.AsyncClient | None = None,
) -> str:
    metadata_url = ARCGIS_ITEM_URL.format(item_id=distribuidora_id)
    params = {'f': 'json'}

    try:
        if client is None:
            async with httpx.AsyncClient(timeout=15.0) as managed_client:
                response = await managed_client.get(
                    metadata_url, params=params
                )
        else:
            response = await client.get(metadata_url, params=params)
    except httpx.HTTPError as exc:
        raise RuntimeError('ANEEL indisponível no momento') from exc

    if response.status_code == 404:
        raise LookupError('Item não encontrado na ANEEL')

    if response.status_code >= 500:
        raise RuntimeError('ANEEL indisponível no momento')

    if response.status_code >= 400:
        raise LookupError('Item não encontrado na ANEEL')

    payload = response.json()
    if 'error' in payload:
        code = payload.get('error', {}).get('code')
        if code == 404:
            raise LookupError('Item não encontrado na ANEEL')
        raise RuntimeError('ANEEL indisponível no momento')

    item_type = payload.get('type')
    if item_type not in ALLOWED_ITEM_TYPES:
        raise LookupError('Item não compatível com download GDB')

    return ARCGIS_DOWNLOAD_URL.format(item_id=distribuidora_id)


async def save_distribuidora_job_tracking(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
    job_id: str,
) -> None:
    stmt = (
        update(Distribuidora)
        .where(
            Distribuidora.id == distribuidora_id,
            Distribuidora.date_gdb == ano,
        )
        .values(
            job_id=job_id,
            processed_at=datetime.now(timezone.utc),
        )
    )
    await session.execute(stmt)
    await session.commit()


async def trigger_pipeline_flow(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
) -> dict:
    """Orquestra todos os passos da pipeline: download + criticidade + render."""
    if await distribuidora_job_already_triggered(
        session, distribuidora_id, ano
    ):
        raise ValueError(
            'Pipeline já foi acionada para a distribuidora no ano informado'
        )

    try:
        dist_name, current_job_id = await _get_distribuidora_info(
            session, distribuidora_id, ano
        )
    except NoResultFound:
        raise LookupError(
            'Distribuidora não encontrada para o ano informado'
        )

    download_url = await resolve_download_url_from_aneel(distribuidora_id)
    enqueue_result = enqueue_download_gdb(download_url, distribuidora_id)

    await save_distribuidora_job_tracking(
        session=session,
        distribuidora_id=distribuidora_id,
        ano=ano,
        job_id=enqueue_result['job_id'],
    )

    await calcular_score_criticidade(ano=ano, distribuidora=dist_name)

    await criar_mapa_criticidade(
        distribuidora=dist_name,
        ano=ano,
        distribuidora_id=distribuidora_id,
        job_id=current_job_id,
    )

    await render_tabela_score_criticidade(
        distribuidora=dist_name, ano=ano
    )
    await render_mapa_calor_criticidade(
        distribuidora=dist_name, ano=ano
    )

    return {
        **enqueue_result,
        'distribuidora_id': distribuidora_id,
        'ano': ano,
        'download_url': download_url,
    }
