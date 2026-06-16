"""Tests for CNPJ enrichment service (ANEEL + MongoDB dec_fec_realizado)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.clients.aneel import fetch_aneel_cnpj_map
from backend.core.models import Distribuidora, DistribuidoraCnpj
from backend.core.schemas import DistribuidoraPayload
from backend.services.cnpj_enrichment import enrich_distribuidoras
from backend.services.distribuidoras import upsert_distribuidoras

ANEEL_MODULE = 'backend.clients.aneel'
_PATCH_MAP = (
    'backend.services.cnpj_enrichment._build_sig_agente_map_from_mongo'
)
_PATCH_FETCH_ANEEL = 'backend.services.cnpj_enrichment.fetch_aneel_cnpj_map'


def _aneel_response(records: list[dict], total: int | None = None) -> dict:
    return {
        'success': True,
        'result': {
            'records': records,
            'total': total if total is not None else len(records),
        },
    }


@pytest.fixture
def mongo_mock():
    """Minimal MongoDB mock that supports awaitable insert_one on any collection."""
    mock = MagicMock()
    mock.__getitem__.return_value.insert_one = AsyncMock()
    return mock


@pytest.fixture
def patch_sig_agente_map():
    """Patches _build_sig_agente_map_from_mongo; set .return_value per test."""
    with patch(_PATCH_MAP, new_callable=AsyncMock, return_value={}) as m:
        yield m


@pytest.fixture
def patch_fetch_aneel():
    """Patches fetch_aneel_cnpj_map in the enrichment module; set .return_value per test."""
    with patch(_PATCH_FETCH_ANEEL, new_callable=AsyncMock, return_value={}) as m:
        yield m


# ── ANEEL client ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_aneel_cnpj_map_retorna_dict():
    records = [
        {'SigAgente': 'COPEL-DIS', 'NumCNPJ': '76535764000143'},
        {'SigAgente': 'CEMIG-D', 'NumCNPJ': '06981180000116'},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_aneel_response(records))

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
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

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
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

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        result = await fetch_aneel_cnpj_map(client=client)

    assert result['DIST-X'] == '76535764000143'


@pytest.mark.asyncio
async def test_fetch_aneel_strip_espacos_sig_agente():
    """SigAgente com espaços no retorno da API deve ser normalizado via strip."""
    records = [
        {'SigAgente': 'AME                 ', 'NumCNPJ': '12345678000195'}
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_aneel_response(records))

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        result = await fetch_aneel_cnpj_map(client=client)

    assert 'AME' in result
    assert 'AME                 ' not in result
    assert result['AME'] == '12345678000195'


@pytest.mark.asyncio
async def test_fetch_aneel_cnpj_map_levanta_em_falha_http():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(httpx.HTTPError):
            await fetch_aneel_cnpj_map(client=client)


# ── ANEEL pass 1 ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_aneel_match_exato(session, mongo_mock, patch_fetch_aneel):
    """Distribuidora com match exato na API ANEEL → cnpj_source='aneel'."""
    await upsert_distribuidoras(
        session,
        [DistribuidoraPayload(id='an-1', dist_name='COPEL-DIS', date_gdb=2024)],
    )
    patch_fetch_aneel.return_value = {'COPEL-DIS': '76535764000143'}
    counts = await enrich_distribuidoras(session, mongo_mock)

    assert counts['matched'] == 1
    cnpj_row = (
        (
            await session.execute(
                select(DistribuidoraCnpj).where(
                    DistribuidoraCnpj.dist_id == 'an-1'
                )
            )
        )
        .scalars()
        .one()
    )
    assert cnpj_row.cnpj == '76535764000143'
    assert cnpj_row.cnpj_match == 1.0
    assert cnpj_row.cnpj_source == 'aneel'
    assert cnpj_row.cnpj_enrichment_status == 'matched'


@pytest.mark.asyncio
async def test_enrich_aneel_fuzzy_match(session, mongo_mock, patch_fetch_aneel):
    """Distribuidora com match fuzzy na API ANEEL → cnpj_source='aneel'."""
    await upsert_distribuidoras(
        session,
        [
            DistribuidoraPayload(
                id='an-2', dist_name='COPEL DISTRIBUICAO', date_gdb=2024
            )
        ],
    )
    patch_fetch_aneel.return_value = {'COPEL-DIS': '76535764000143'}

    with patch('backend.services.cnpj_enrichment.process') as mock_process:
        mock_process.extractOne.return_value = ('copel dis', 97, 0)
        counts = await enrich_distribuidoras(session, mongo_mock)

    assert counts['matched'] == 1
    cnpj_row = (
        (
            await session.execute(
                select(DistribuidoraCnpj).where(
                    DistribuidoraCnpj.dist_id == 'an-2'
                )
            )
        )
        .scalars()
        .one()
    )
    assert cnpj_row.cnpj == '76535764000143'
    assert cnpj_row.cnpj_match == pytest.approx(0.97)
    assert cnpj_row.cnpj_source == 'aneel'
    assert cnpj_row.cnpj_enrichment_status == 'matched'


@pytest.mark.asyncio
async def test_enrich_aneel_indisponivel_usa_fallback_mongo(
    session, mongo_mock, patch_fetch_aneel, patch_sig_agente_map
):
    """Quando ANEEL levanta HTTPError, o fallback para MongoDB deve ser usado."""
    await upsert_distribuidoras(
        session,
        [DistribuidoraPayload(id='an-3', dist_name='COPEL-DIS', date_gdb=2024)],
    )
    patch_fetch_aneel.side_effect = httpx.ConnectError('ANEEL fora do ar')
    patch_sig_agente_map.return_value = {'COPEL-DIS': '76535764000143'}

    counts = await enrich_distribuidoras(session, mongo_mock)

    assert counts['matched'] == 1
    cnpj_row = (
        (
            await session.execute(
                select(DistribuidoraCnpj).where(
                    DistribuidoraCnpj.dist_id == 'an-3'
                )
            )
        )
        .scalars()
        .one()
    )
    assert cnpj_row.cnpj == '76535764000143'
    assert cnpj_row.cnpj_source == 'dec_fec'
    assert cnpj_row.cnpj_enrichment_status == 'matched'


# ── enrichment service (MongoDB fallback / pass 2) ───────────────────────────


@pytest.mark.asyncio
async def test_enrich_match_aceito(
    session, mongo_mock, patch_fetch_aneel, patch_sig_agente_map
):
    await upsert_distribuidoras(
        session,
        [DistribuidoraPayload(id='e-1', dist_name='COPEL-DIS', date_gdb=2024)],
    )

    patch_sig_agente_map.return_value = {'COPEL-DIS': '76535764000143'}
    counts = await enrich_distribuidoras(session, mongo_mock)

    assert counts['matched'] == 1
    cnpj_row = (
        (
            await session.execute(
                select(DistribuidoraCnpj).where(
                    DistribuidoraCnpj.dist_id == 'e-1'
                )
            )
        )
        .scalars()
        .one()
    )

    assert cnpj_row.cnpj == '76535764000143'
    assert cnpj_row.cnpj_match == 1.0
    assert cnpj_row.cnpj_source == 'dec_fec'
    assert cnpj_row.cnpj_enrichment_status == 'matched'


@pytest.mark.asyncio
async def test_enrich_match_case_insensitive(
    session, mongo_mock, patch_fetch_aneel, patch_sig_agente_map
):
    await upsert_distribuidoras(
        session,
        [DistribuidoraPayload(id='e-2', dist_name='copel-dis', date_gdb=2024)],
    )

    patch_sig_agente_map.return_value = {'COPEL-DIS': '76535764000143'}
    counts = await enrich_distribuidoras(session, mongo_mock)

    assert counts['matched'] == 1
    cnpj_row = (
        (
            await session.execute(
                select(DistribuidoraCnpj).where(
                    DistribuidoraCnpj.dist_id == 'e-2'
                )
            )
        )
        .scalars()
        .one()
    )
    assert cnpj_row.cnpj_enrichment_status == 'matched'


@pytest.mark.asyncio
async def test_enrich_sem_match_marca_no_match(
    session, mongo_mock, patch_fetch_aneel, patch_sig_agente_map
):
    await upsert_distribuidoras(
        session,
        [
            DistribuidoraPayload(
                id='e-3', dist_name='DIST-DESCONHECIDA', date_gdb=2024
            )
        ],
    )

    patch_sig_agente_map.return_value = {'COPEL-DIS': '76535764000143'}
    counts = await enrich_distribuidoras(session, mongo_mock)

    assert counts['no_match'] == 1
    cnpj_row = (
        (
            await session.execute(
                select(DistribuidoraCnpj).where(
                    DistribuidoraCnpj.dist_id == 'e-3'
                )
            )
        )
        .scalars()
        .one()
    )

    assert cnpj_row.cnpj is None
    assert cnpj_row.cnpj_enrichment_status == 'no_match'
    assert cnpj_row.cnpj_match is not None
    assert 0.0 <= cnpj_row.cnpj_match <= 1.0


@pytest.mark.asyncio
async def test_enrich_idempotente_nao_reprocessa_matched(
    session, mongo_mock, patch_fetch_aneel, patch_sig_agente_map
):
    await upsert_distribuidoras(
        session,
        [DistribuidoraPayload(id='e-4', dist_name='COPEL-DIS', date_gdb=2024)],
    )
    patch_sig_agente_map.return_value = {'COPEL-DIS': '76535764000143'}

    counts1 = await enrich_distribuidoras(session, mongo_mock)
    counts2 = await enrich_distribuidoras(session, mongo_mock)

    assert counts1['matched'] == 1
    assert counts2['matched'] == 0
    assert counts2['no_match'] == 0


@pytest.mark.asyncio
async def test_enrich_idempotente_nao_reprocessa_no_match(
    session, mongo_mock, patch_fetch_aneel, patch_sig_agente_map
):
    await upsert_distribuidoras(
        session,
        [DistribuidoraPayload(id='e-5', dist_name='DIST-X', date_gdb=2024)],
    )
    patch_sig_agente_map.return_value = {'COPEL-DIS': '76535764000143'}

    await enrich_distribuidoras(session, mongo_mock)
    counts2 = await enrich_distribuidoras(session, mongo_mock)

    assert counts2['matched'] == 0
    assert counts2['no_match'] == 0


# ── sync integration ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_retorna_totais_corretos(session):
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

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        result = await sync_distribuidoras(
            session=session,
            initial_url='https://example.test/search',
            client=client,
        )

    assert result.total_recebidas == 1
    assert result.total_persistidas == 1


# ── fuzzy match ───────────────────────────────────────────────────────────────


async def _drain_pending(session):
    """Insert a no_match row in distribuidora_cnpj for every distribuidora not yet enriched."""
    already_enriched = select(DistribuidoraCnpj.dist_id)
    pending_ids = (
        await session.execute(
            select(Distribuidora.id)
            .where(Distribuidora.id.not_in(already_enriched))
            .distinct()
        )
    ).all()
    for (dist_id,) in pending_ids:
        await session.execute(
            pg_insert(DistribuidoraCnpj)
            .values(dist_id=dist_id, cnpj_enrichment_status='no_match')
            .on_conflict_do_nothing()
        )
    await session.commit()


@pytest.mark.asyncio
async def test_fuzzy_match_aceito(
    session, mongo_mock, patch_fetch_aneel, patch_sig_agente_map
):
    await _drain_pending(session)
    await upsert_distribuidoras(
        session,
        [
            DistribuidoraPayload(
                id='fz-1', dist_name='COPEL DISTRIBUICAO', date_gdb=2024
            )
        ],
    )
    patch_sig_agente_map.return_value = {'COPEL-DIS': '76535764000143'}

    with patch('backend.services.cnpj_enrichment.process') as mock_process:
        mock_process.extractOne.return_value = ('copel dis', 97, 0)
        counts = await enrich_distribuidoras(session, mongo_mock)

    assert counts['matched'] == 1
    cnpj_row = (
        (
            await session.execute(
                select(DistribuidoraCnpj).where(
                    DistribuidoraCnpj.dist_id == 'fz-1'
                )
            )
        )
        .scalars()
        .one()
    )

    assert cnpj_row.cnpj == '76535764000143'
    assert cnpj_row.cnpj_match == pytest.approx(0.97)
    assert cnpj_row.cnpj_source == 'dec_fec'
    assert cnpj_row.cnpj_enrichment_status == 'matched'


@pytest.mark.asyncio
async def test_fuzzy_match_rejeitado(
    session, mongo_mock, patch_fetch_aneel, patch_sig_agente_map
):
    await _drain_pending(session)
    await upsert_distribuidoras(
        session,
        [
            DistribuidoraPayload(
                id='fz-2', dist_name='DIST-TOTALMENTE-DIFERENTE', date_gdb=2024
            )
        ],
    )
    patch_sig_agente_map.return_value = {'COPEL-DIS': '76535764000143'}

    with patch('backend.services.cnpj_enrichment.process') as mock_process:
        mock_process.extractOne.return_value = ('copel dis', 60, 0)
        counts = await enrich_distribuidoras(session, mongo_mock)

    assert counts['no_match'] == 1
    cnpj_row = (
        (
            await session.execute(
                select(DistribuidoraCnpj).where(
                    DistribuidoraCnpj.dist_id == 'fz-2'
                )
            )
        )
        .scalars()
        .one()
    )

    assert cnpj_row.cnpj is None
    assert cnpj_row.cnpj_enrichment_status == 'no_match'
    assert cnpj_row.cnpj_match == pytest.approx(0.60)


@pytest.mark.asyncio
async def test_fuzzy_rejeitado_grava_log_mongo(
    session, patch_fetch_aneel, patch_sig_agente_map
):
    await _drain_pending(session)
    await upsert_distribuidoras(
        session,
        [
            DistribuidoraPayload(
                id='fz-3', dist_name='DIST-DIFERENTE', date_gdb=2024
            )
        ],
    )
    patch_sig_agente_map.return_value = {'COPEL-DIS': '76535764000143'}

    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock()
    mock_mongo = MagicMock()
    mock_mongo.__getitem__ = MagicMock(return_value=mock_collection)

    with patch('backend.services.cnpj_enrichment.process') as mock_process:
        mock_process.extractOne.return_value = ('copel dis', 60, 0)
        await enrich_distribuidoras(session, mock_mongo)

    mock_collection.insert_one.assert_called_once()
    doc = mock_collection.insert_one.call_args[0][0]
    assert doc['dist_id'] == 'fz-3'
    assert doc['dist_name'] == 'DIST-DIFERENTE'
    assert doc['mongo_sig_agente'] == 'COPEL-DIS'
    assert doc['mongo_cnpj'] == '76535764000143'
    assert doc['match_score'] == pytest.approx(0.60)
    assert 'attempted_at' in doc


@pytest.mark.asyncio
async def test_no_match_sem_candidato_grava_zero_no_postgres(
    session, mongo_mock, patch_fetch_aneel, patch_sig_agente_map
):
    """Quando dec_fec_realizado está vazio (nenhum candidato fuzzy), cnpj_match deve ser 0.0."""
    await _drain_pending(session)
    await upsert_distribuidoras(
        session,
        [
            DistribuidoraPayload(
                id='fz-5', dist_name='DIST-SEM-CANDIDATO', date_gdb=2024
            )
        ],
    )

    patch_sig_agente_map.return_value = {}
    counts = await enrich_distribuidoras(session, mongo_mock)

    assert counts['no_match'] == 1
    cnpj_row = (
        (
            await session.execute(
                select(DistribuidoraCnpj).where(
                    DistribuidoraCnpj.dist_id == 'fz-5'
                )
            )
        )
        .scalars()
        .one()
    )

    assert cnpj_row.cnpj is None
    assert cnpj_row.cnpj_enrichment_status == 'no_match'
    assert cnpj_row.cnpj_match == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_no_match_sem_candidato_grava_log_mongo_com_zero(
    session, patch_fetch_aneel, patch_sig_agente_map
):
    """Quando não há candidato fuzzy, o log Mongo deve ter match_score=0.0 e campos nulos."""
    await _drain_pending(session)
    await upsert_distribuidoras(
        session,
        [
            DistribuidoraPayload(
                id='fz-6', dist_name='DIST-SEM-CANDIDATO-MONGO', date_gdb=2024
            )
        ],
    )

    patch_sig_agente_map.return_value = {}

    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock()
    mock_mongo = MagicMock()
    mock_mongo.__getitem__ = MagicMock(return_value=mock_collection)

    await enrich_distribuidoras(session, mock_mongo)

    mock_collection.insert_one.assert_called_once()
    doc = mock_collection.insert_one.call_args[0][0]
    assert doc['dist_id'] == 'fz-6'
    assert doc['mongo_sig_agente'] is None
    assert doc['mongo_cnpj'] is None
    assert doc['match_score'] == pytest.approx(0.0)
    assert 'attempted_at' in doc


@pytest.mark.parametrize(
    'dist_id,dist_name,aneel_key,expected_cnpj',
    [
        ('cp-1', 'CPFL_PAULISTA', 'CPFL-PAULISTA', '33050196000188'),
        ('ca-1', 'COOPERALIANCA', 'COOPERALIANÇA', '83647990000181'),
        ('rge-1', 'RGE_SUL', 'RGE SUL', '02016440000162'),
    ],
)
@pytest.mark.asyncio
async def test_enrich_match_normalization(
    session,
    mongo_mock,
    patch_fetch_aneel,
    patch_sig_agente_map,
    dist_id,
    dist_name,
    aneel_key,
    expected_cnpj,
):
    await _drain_pending(session)
    await upsert_distribuidoras(
        session,
        [DistribuidoraPayload(id=dist_id, dist_name=dist_name, date_gdb=2024)],
    )

    patch_sig_agente_map.return_value = {aneel_key: expected_cnpj}
    counts = await enrich_distribuidoras(session, mongo_mock)

    assert counts['matched'] == 1
    cnpj_row = (
        (
            await session.execute(
                select(DistribuidoraCnpj).where(
                    DistribuidoraCnpj.dist_id == dist_id
                )
            )
        )
        .scalars()
        .one()
    )

    assert cnpj_row.cnpj == expected_cnpj
    assert cnpj_row.cnpj_match == 1.0
    assert cnpj_row.cnpj_enrichment_status == 'matched'


@pytest.mark.asyncio
async def test_no_match_nao_retentado_em_novo_sync(
    session, mongo_mock, patch_fetch_aneel, patch_sig_agente_map
):
    await _drain_pending(session)
    await upsert_distribuidoras(
        session,
        [
            DistribuidoraPayload(
                id='fz-4', dist_name='DIST-SEM-MATCH', date_gdb=2024
            )
        ],
    )
    patch_sig_agente_map.return_value = {'COPEL-DIS': '76535764000143'}

    with patch('backend.services.cnpj_enrichment.process') as mock_process:
        mock_process.extractOne.return_value = ('copel dis', 50, 0)
        counts1 = await enrich_distribuidoras(session, mongo_mock)

    assert counts1['no_match'] == 1

    with patch('backend.services.cnpj_enrichment.process') as mock_process:
        mock_process.extractOne.return_value = ('copel dis', 50, 0)
        counts2 = await enrich_distribuidoras(session, mongo_mock)

    assert counts2['matched'] == 0
    assert counts2['no_match'] == 0
    assert counts2['pending'] == 0
