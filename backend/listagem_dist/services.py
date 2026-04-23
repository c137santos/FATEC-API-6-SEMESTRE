from datetime import datetime

import httpx
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Distribuidora
from .schemas import DistribuidoraPayload, SyncDistribuidorasResponse

INITIAL_URL = (
    'https://hub.arcgis.com/api/search/v1/collections/all/'
    'items?q=BDGD&type=File%20Geodatabase&limit=100'
)


def _extract_next_url(payload: dict) -> str | None:
    links = payload.get('links', [])
    for link in links:
        if link.get('rel') == 'next':
            return link.get('href')
    return None


def _extract_distribuidora(resource: dict) -> DistribuidoraPayload:
    tags = resource.get('properties', {}).get('tags', [])
    nome_distribuidora = 'NAO ENCONTRADO'
    data_gdb = None

    if isinstance(tags, list) and len(tags) >= 2:
        nome_distribuidora = str(tags[-2])
        data_string = str(tags[-1])
        try:
            data_gdb = datetime.strptime(data_string, '%Y-%m-%d').date()
        except ValueError:
            data_gdb = None

    return DistribuidoraPayload(
        id=resource.get('id'),
        nome_distribuidora=nome_distribuidora,
        data_gdb=data_gdb,
    )


async def _fetch_pages(
    initial_url: str,
    client: httpx.AsyncClient,
) -> list[DistribuidoraPayload]:
    all_resources: list[DistribuidoraPayload] = []
    next_url = initial_url

    while next_url:
        response = await client.get(next_url)
        response.raise_for_status()
        payload = response.json()

        for feature in payload.get('features', []):
            all_resources.append(_extract_distribuidora(feature))

        next_url = _extract_next_url(payload)

    return all_resources


async def fetch_paginated_resources(
    initial_url: str = INITIAL_URL,
    client: httpx.AsyncClient | None = None,
) -> list[DistribuidoraPayload]:
    try:
        if client is not None:
            return await _fetch_pages(initial_url, client)

        async with httpx.AsyncClient(timeout=30.0) as managed_client:
            return await _fetch_pages(initial_url, managed_client)
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError('Falha ao consumir API ArcGIS Hub') from exc


async def upsert_distribuidoras(
    session: AsyncSession,
    resources: list[DistribuidoraPayload],
) -> int:
    valid_resources = [
        item for item in resources if item.id is not None and item.data_gdb is not None
    ]
    if not valid_resources:
        return 0

    rows = [
        {
            'id': item.id,
            'data_gdb': item.data_gdb,
            'nome_distribuidora': item.nome_distribuidora,
        }
        for item in valid_resources
    ]

    stmt = insert(Distribuidora).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Distribuidora.id, Distribuidora.data_gdb],
        set_={
            'nome_distribuidora': stmt.excluded.nome_distribuidora,
            'updated_at': func.now(),
        },
    )
    await session.execute(stmt)
    await session.commit()
    return len(rows)


async def sync_distribuidoras(
    session: AsyncSession,
    initial_url: str = INITIAL_URL,
) -> SyncDistribuidorasResponse:
    resources = await fetch_paginated_resources(initial_url)
    total_persistidas = await upsert_distribuidoras(session, resources)
    return SyncDistribuidorasResponse(
        total_recebidas=len(resources),
        total_persistidas=total_persistidas,
    )