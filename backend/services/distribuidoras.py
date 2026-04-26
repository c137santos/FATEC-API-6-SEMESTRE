from datetime import datetime

import httpx
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import Distribuidora
from backend.core.schemas import (
    DistribuidoraPayload,
    SyncDistribuidorasResponse,
)

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
    dist_name = 'NAO ENCONTRADO'
    date_gdb = None

    if isinstance(tags, list) and len(tags) >= 2:
        dist_name = str(tags[-2])
        data_string = str(tags[-1])
        try:
            date_gdb = datetime.strptime(data_string, '%Y-%m-%d').year
        except ValueError:
            date_gdb = None

    return DistribuidoraPayload(
        id=resource.get('id'),
        dist_name=dist_name,
        date_gdb=date_gdb,
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
    # Avoid duplicate composite keys in the same INSERT statement.
    deduplicated_rows: dict[tuple[str, int], dict[str, object]] = {}
    for item in resources:
        if item.id is None or item.date_gdb is None:
            continue

        deduplicated_rows[(item.id, item.date_gdb)] = {
            'id': item.id,
            'date_gdb': item.date_gdb,
            'dist_name': item.dist_name,
        }

    rows = list(deduplicated_rows.values())
    if not rows:
        return 0

    stmt = insert(Distribuidora).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Distribuidora.id, Distribuidora.date_gdb],
        set_={
            'dist_name': stmt.excluded.dist_name,
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
