"""Tests for ANEEL client and CNPJ enrichment service."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import select

from backend.clients.aneel import fetch_aneel_cnpj_map
from backend.core.models import Distribuidora
from backend.core.schemas import DistribuidoraPayload
from backend.services.cnpj_enrichment import enrich_distribuidoras
from backend.services.distribuidoras import upsert_distribuidoras

ANEEL_MODULE = 'backend.clients.aneel'


def _aneel_response(records: list[dict], total: int | None = None) -> dict:
    return {
        'success': True,
        'result': {
            'records': records,
            'total': total if total is not None else len(records),
        },
    }


# ── ANEEL client ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_aneel_cnpj_map_retorna_dict():
    records = [
        {'SigAgente': 'COPEL-DIS', 'NumCNPJ': '76535764000143'},
        {'SigAgente': 'CEMIG-D', 'NumCNPJ': '06981180000116'},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_aneel_response(records))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_aneel_cnpj_map(client=client)

    assert result['COPEL-DIS'] == '76535764000143'
    assert result['CEMIG-D'] == '06981180000116'


@pytest.mark.asyncio
async def test_fetch_aneel_cnpj_map_pagina_multiplas_paginas():
    page1 = [{'SigAgente': 'DIST-A', 'NumCNPJ': '11111111000191'}]
    page2 = [{'SigAgente': 'DIST-B', 'NumCNPJ': '22222222000100'}]

    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        offset = int(request.url.params.get('offset', 0))
        if offset == 0:
            return httpx.Response(200, json=_aneel_response(page1, total=2))
        return httpx.Response(200, json=_aneel_response(page2, total=2))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_aneel_cnpj_map(client=client)

    assert len(result) == 2
    assert 'DIST-A' in result
    assert 'DIST-B' in result
    assert call_count == 2


@pytest.mark.asyncio
async def test_fetch_aneel_cnpj_map_normaliza_cnpj():
    records = [{'SigAgente': 'DIST-X', 'NumCNPJ': '76.535.764/0001-43'}]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_aneel_response(records))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_aneel_cnpj_map(client=client)

    assert result['DIST-X'] == '76535764000143'


@pytest.mark.asyncio
async def test_fetch_aneel_cnpj_map_levanta_em_falha_http():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPError):
            await fetch_aneel_cnpj_map(client=client)


# ── enrichment service ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_match_aceito(session):
    await upsert_distribuidoras(
        session,
        [DistribuidoraPayload(id='e-1', dist_name='COPEL-DIS', date_gdb=2024)],
    )

    aneel_map = {'COPEL-DIS': '76535764000143'}
    counts = await enrich_distribuidoras(session, aneel_map)

    assert counts['matched'] == 1
    row = (
        await session.execute(
            select(Distribuidora).where(Distribuidora.id == 'e-1')
        )
    ).scalars().one()

    assert row.cnpj == '76535764000143'
    assert row.cnpj_match == 1.0
    assert row.cnpj_source == 'aneel_api'
    assert row.cnpj_enrichment_status == 'matched'


@pytest.mark.asyncio
async def test_enrich_match_case_insensitive(session):
    await upsert_distribuidoras(
        session,
        [DistribuidoraPayload(id='e-2', dist_name='copel-dis', date_gdb=2024)],
    )

    aneel_map = {'COPEL-DIS': '76535764000143'}
    counts = await enrich_distribuidoras(session, aneel_map)

    assert counts['matched'] == 1
    row = (
        await session.execute(
            select(Distribuidora).where(Distribuidora.id == 'e-2')
        )
    ).scalars().one()
    assert row.cnpj_enrichment_status == 'matched'


@pytest.mark.asyncio
async def test_enrich_sem_match_marca_no_match(session):
    await upsert_distribuidoras(
        session,
        [DistribuidoraPayload(id='e-3', dist_name='DIST-DESCONHECIDA', date_gdb=2024)],
    )

    aneel_map = {'COPEL-DIS': '76535764000143'}
    counts = await enrich_distribuidoras(session, aneel_map)

    assert counts['no_match'] == 1
    row = (
        await session.execute(
            select(Distribuidora).where(Distribuidora.id == 'e-3')
        )
    ).scalars().one()

    assert row.cnpj is None
    assert row.cnpj_enrichment_status == 'no_match'


@pytest.mark.asyncio
async def test_enrich_idempotente_nao_reprocessa_matched(session):
    await upsert_distribuidoras(
        session,
        [DistribuidoraPayload(id='e-4', dist_name='COPEL-DIS', date_gdb=2024)],
    )
    aneel_map = {'COPEL-DIS': '76535764000143'}

    counts1 = await enrich_distribuidoras(session, aneel_map)
    counts2 = await enrich_distribuidoras(session, aneel_map)

    assert counts1['matched'] == 1
    assert counts2['matched'] == 0
    assert counts2['no_match'] == 0


@pytest.mark.asyncio
async def test_enrich_idempotente_nao_reprocessa_no_match(session):
    await upsert_distribuidoras(
        session,
        [DistribuidoraPayload(id='e-5', dist_name='DIST-X', date_gdb=2024)],
    )
    aneel_map = {'COPEL-DIS': '76535764000143'}

    await enrich_distribuidoras(session, aneel_map)
    counts2 = await enrich_distribuidoras(session, aneel_map)

    assert counts2['matched'] == 0
    assert counts2['no_match'] == 0


# ── sync integration ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_chama_enrichment_apos_upsert(session):
    from backend.services.distribuidoras import sync_distribuidoras

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                'features': [
                    {
                        'id': 'dist-sync-1',
                        'properties': {
                            'tags': ['BDGD', 'COPEL-DIS', '2024-01-01']
                        },
                    }
                ],
                'links': [],
            },
        )

    aneel_map = {'COPEL-DIS': '76535764000143'}

    with patch(
        'backend.services.distribuidoras.fetch_aneel_cnpj_map',
        new=AsyncMock(return_value=aneel_map),
    ):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            await sync_distribuidoras(
                session=session,
                initial_url='https://example.test/search',
                client=client,
            )

    row = (
        await session.execute(
            select(Distribuidora).where(Distribuidora.id == 'dist-sync-1')
        )
    ).scalars().one()
    assert row.cnpj == '76535764000143'
    assert row.cnpj_enrichment_status == 'matched'


@pytest.mark.asyncio
async def test_sync_continua_quando_aneel_falha(session):
    from backend.services.distribuidoras import sync_distribuidoras

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                'features': [
                    {
                        'id': 'dist-sync-2',
                        'properties': {
                            'tags': ['BDGD', 'DIST-Y', '2024-01-01']
                        },
                    }
                ],
                'links': [],
            },
        )

    with patch(
        'backend.services.distribuidoras.fetch_aneel_cnpj_map',
        new=AsyncMock(side_effect=httpx.HTTPError('timeout')),
    ):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            result = await sync_distribuidoras(
                session=session,
                initial_url='https://example.test/search',
                client=client,
            )

    assert result.total_persistidas == 1
