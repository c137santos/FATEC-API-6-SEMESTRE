import httpx
import pytest
from sqlalchemy import select

from backend.core.models import Distribuidora
from backend.core.schemas import DistribuidoraPayload
from backend.services.distribuidoras import (
    fetch_paginated_resources,
    upsert_distribuidoras,
)


@pytest.mark.asyncio
async def test_fetch_paginated_resources_itera_links_de_paginacao():
    def handler(request: httpx.Request) -> httpx.Response:
        if 'cursor=2' in str(request.url):
            return httpx.Response(
                status_code=200,
                json={
                    'features': [
                        {
                            'id': 'dist-2',
                            'properties': {
                                'tags': ['BDGD', 'DIST_B', '2026-01-02']
                            },
                        }
                    ],
                    'links': [],
                },
            )

        return httpx.Response(
            status_code=200,
            json={
                'features': [
                    {
                        'id': 'dist-1',
                        'properties': {
                            'tags': ['BDGD', 'DIST_A', '2026-01-01']
                        },
                    }
                ],
                'links': [
                    {
                        'rel': 'next',
                        'href': 'https://example.test/search?cursor=2',
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        resources = await fetch_paginated_resources(
            initial_url='https://example.test/search',
            client=client,
        )

    assert len(resources) == 2
    assert resources[0].id == 'dist-1'
    assert resources[0].dist_name == 'DIST_A'
    assert resources[0].date_gdb == 2026
    assert resources[1].id == 'dist-2'


@pytest.mark.asyncio
async def test_upsert_distribuidoras_insere_e_atualiza(session):
    first_batch = [
        DistribuidoraPayload(
            id='dist-10',
            dist_name='NOME_ANTIGO',
            date_gdb=2026,
        )
    ]

    second_batch = [
        DistribuidoraPayload(
            id='dist-10',
            dist_name='NOME_ATUALIZADO',
            date_gdb=2026,
        )
    ]

    assert await upsert_distribuidoras(session, first_batch) == 1
    assert await upsert_distribuidoras(session, second_batch) == 1

    rows = (
        (
            await session.execute(
                select(Distribuidora).where(Distribuidora.id == 'dist-10')
            )
        )
        .scalars()
        .all()
    )

    assert len(rows) == 1
    assert rows[0].id == 'dist-10'
    assert rows[0].date_gdb == 2026
    assert rows[0].dist_name == 'NOME_ATUALIZADO'


@pytest.mark.asyncio
async def test_upsert_distribuidoras_ignora_registros_invalidos(session):
    batch = [
        DistribuidoraPayload(
            id='dist-valida',
            dist_name='DIST_VALIDA',
            date_gdb=2026,
        ),
        DistribuidoraPayload(
            id=None,
            dist_name='SEM_ID',
            date_gdb=2026,
        ),
        DistribuidoraPayload(
            id='sem-data',
            dist_name='SEM_DATA',
            date_gdb=None,
        ),
    ]

    persisted = await upsert_distribuidoras(session, batch)
    rows = (
        (
            await session.execute(
                select(Distribuidora).where(Distribuidora.id == 'dist-valida')
            )
        )
        .scalars()
        .all()
    )

    assert persisted == 1
    assert len(rows) == 1
    assert rows[0].id == 'dist-valida'


@pytest.mark.asyncio
async def test_upsert_distribuidoras_deduplica_chave_composta_no_mesmo_batch(
    session,
):
    batch = [
        DistribuidoraPayload(
            id='dist-dup',
            dist_name='NOME_1',
            date_gdb=2026,
        ),
        DistribuidoraPayload(
            id='dist-dup',
            dist_name='NOME_2',
            date_gdb=2026,
        ),
    ]

    persisted = await upsert_distribuidoras(session, batch)
    row = (
        (
            await session.execute(
                select(Distribuidora).where(
                    Distribuidora.id == 'dist-dup',
                    Distribuidora.date_gdb == 2026,
                )
            )
        )
        .scalars()
        .one()
    )

    assert persisted == 1
    assert row.dist_name == 'NOME_2'
