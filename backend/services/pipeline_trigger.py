import httpx
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import Distribuidora

ARCGIS_ITEM_URL = 'https://www.arcgis.com/sharing/rest/content/items/{item_id}'
ARCGIS_DOWNLOAD_URL = (
    'https://www.arcgis.com/sharing/rest/content/items/{item_id}/data'
)
ALLOWED_ITEM_TYPES = {'Feature Service', 'File Geodatabase'}


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
            processed_at=datetime.utcnow(),
        )
    )
    await session.execute(stmt)
    await session.commit()
