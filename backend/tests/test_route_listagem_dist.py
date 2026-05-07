import pytest

from backend.core.schemas import DistribuidoraPayload


@pytest.mark.asyncio
async def test_sync_distribuidoras_endpoint_retorna_totais(
    client, monkeypatch
):
    async def fake_fetch(_initial_url, **kwargs):
        return [
            DistribuidoraPayload(
                id='dist-1',
                dist_name='DIST_A',
                date_gdb=2026,
            ),
            DistribuidoraPayload(
                id='dist-2',
                dist_name='DIST_B',
                date_gdb=2026,
            ),
        ]

    async def fake_aneel_map():
        return {}

    monkeypatch.setattr(
        'backend.services.distribuidoras.fetch_paginated_resources',
        fake_fetch,
    )
    monkeypatch.setattr(
        'backend.services.distribuidoras.fetch_aneel_cnpj_map',
        fake_aneel_map,
    )

    response = await client.post('/dist/sync', json={})

    assert response.status_code == 200
    assert response.json() == {'total_recebidas': 2, 'total_persistidas': 2}


@pytest.mark.asyncio
async def test_sync_distribuidoras_endpoint_erro_externo_retorna_502(
    client,
    monkeypatch,
):
    async def fake_fetch(_initial_url, **kwargs):
        raise RuntimeError('Falha ao consumir API ArcGIS Hub')

    monkeypatch.setattr(
        'backend.services.distribuidoras.fetch_paginated_resources',
        fake_fetch,
    )

    response = await client.post('/dist/sync', json={})

    assert response.status_code == 502
    assert response.json()['detail'] == 'Falha ao consumir API ArcGIS Hub'
