import pytest
from sqlalchemy import select

from backend.core.models import Distribuidora


@pytest.mark.asyncio
async def test_pipeline_trigger_retorna_202_quando_valido(
    client,
    session,
    monkeypatch,
):
    session.add(
        Distribuidora(
            id='item-123',
            date_gdb=2026,
            dist_name='DIST TESTE',
        )
    )
    await session.commit()

    async def fake_resolve(_distribuidora_id):
        return (
            'https://www.arcgis.com/sharing/rest/content/items/item-123/data'
        )

    def fake_enqueue(_url):
        return {
            'job_id': 'job-1',
            'task_id': 'task-1',
            'status': 'queued',
        }

    monkeypatch.setattr(
        'backend.routes.pipeline.resolve_download_url_from_aneel',
        fake_resolve,
    )
    monkeypatch.setattr(
        'backend.routes.pipeline.enqueue_download_gdb', fake_enqueue
    )

    response = await client.post(
        '/pipeline/trigger',
        json={'distribuidora_id': 'item-123', 'ano': 2026},
    )

    assert response.status_code == 202
    assert response.json() == {
        'job_id': 'job-1',
        'task_id': 'task-1',
        'status': 'queued',
        'distribuidora_id': 'item-123',
        'ano': 2026,
        'download_url': 'https://www.arcgis.com/sharing/rest/content/items/item-123/data',
    }

    persisted = (
        (
            await session.execute(
                select(Distribuidora).where(
                    Distribuidora.id == 'item-123',
                    Distribuidora.date_gdb == 2026,
                )
            )
        )
        .scalars()
        .one()
    )
    assert persisted.job_id == 'job-1'
    assert persisted.processed_at is not None


@pytest.mark.asyncio
async def test_pipeline_trigger_payload_invalido_retorna_422(client):
    response = await client.post(
        '/pipeline/trigger',
        json={'distribuidora_id': 'item-123', 'ano': 'nao-inteiro'},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pipeline_trigger_distribuidora_nao_encontrada_retorna_404(
    client,
):
    response = await client.post(
        '/pipeline/trigger',
        json={'distribuidora_id': 'item-nao-existe', 'ano': 2026},
    )

    assert response.status_code == 404
    assert (
        response.json()['detail']
        == 'Distribuidora não encontrada para o ano informado'
    )


@pytest.mark.asyncio
async def test_pipeline_trigger_item_inexistente_aneel_retorna_404(
    client,
    session,
    monkeypatch,
):
    session.add(
        Distribuidora(
            id='item-404',
            date_gdb=2026,
            dist_name='DIST TESTE',
        )
    )
    await session.commit()

    async def fake_resolve(_distribuidora_id):
        raise LookupError('Item não encontrado na ANEEL')

    monkeypatch.setattr(
        'backend.routes.pipeline.resolve_download_url_from_aneel',
        fake_resolve,
    )

    response = await client.post(
        '/pipeline/trigger',
        json={'distribuidora_id': 'item-404', 'ano': 2026},
    )

    assert response.status_code == 404
    assert response.json()['detail'] == 'Item não encontrado na ANEEL'


@pytest.mark.asyncio
async def test_pipeline_trigger_aneel_indisponivel_retorna_502(
    client,
    session,
    monkeypatch,
):
    session.add(
        Distribuidora(
            id='item-502',
            date_gdb=2026,
            dist_name='DIST TESTE',
        )
    )
    await session.commit()

    async def fake_resolve(_distribuidora_id):
        raise RuntimeError('ANEEL indisponível no momento')

    monkeypatch.setattr(
        'backend.routes.pipeline.resolve_download_url_from_aneel',
        fake_resolve,
    )

    response = await client.post(
        '/pipeline/trigger',
        json={'distribuidora_id': 'item-502', 'ano': 2026},
    )

    assert response.status_code == 502
    assert response.json()['detail'] == 'ANEEL indisponível no momento'
