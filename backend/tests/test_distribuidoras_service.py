from datetime import date

import httpx
import pytest
from sqlalchemy import select

from backend.listagem_dist.models import Distribuidora
from backend.listagem_dist.schemas import DistribuidoraPayload
from backend.listagem_dist.services import (
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
                            'properties': {'tags': ['BDGD', 'DIST_B', '2026-01-02']},
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
                        'properties': {'tags': ['BDGD', 'DIST_A', '2026-01-01']},
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
    assert resources[0].nome_distribuidora == 'DIST_A'
    assert resources[0].data_gdb == date(2026, 1, 1)
    assert resources[1].id == 'dist-2'


@pytest.mark.asyncio
async def test_upsert_distribuidoras_insere_e_atualiza(session):
    first_batch = [
        DistribuidoraPayload(
            id='dist-10',
            nome_distribuidora='NOME_ANTIGO',
            data_gdb=date(2026, 2, 10),
        )
    ]

    second_batch = [
        DistribuidoraPayload(
            id='dist-10',
            nome_distribuidora='NOME_ATUALIZADO',
            data_gdb=date(2026, 2, 10),
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
    assert rows[0].data_gdb == date(2026, 2, 10)
    assert rows[0].nome_distribuidora == 'NOME_ATUALIZADO'


@pytest.mark.asyncio
async def test_upsert_distribuidoras_ignora_registros_invalidos(session):
    batch = [
        DistribuidoraPayload(
            id='dist-valida',
            nome_distribuidora='DIST_VALIDA',
            data_gdb=date(2026, 3, 1),
        ),
        DistribuidoraPayload(
            id=None,
            nome_distribuidora='SEM_ID',
            data_gdb=date(2026, 3, 2),
        ),
        DistribuidoraPayload(
            id='sem-data',
            nome_distribuidora='SEM_DATA',
            data_gdb=None,
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