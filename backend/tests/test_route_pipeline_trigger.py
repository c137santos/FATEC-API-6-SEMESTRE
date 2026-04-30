import pytest
from sqlalchemy import select
from types import SimpleNamespace
from unittest.mock import MagicMock

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

    fake_task = SimpleNamespace(id='task-1')
    mock_delay = MagicMock(return_value=fake_task)
    monkeypatch.setattr(
        'backend.services.pipeline_trigger.task_download_gdb.delay',
        mock_delay,
    )
    monkeypatch.setattr(
        'backend.services.pipeline_trigger.resolve_download_url_from_aneel',
        fake_resolve,
    )

    response = await client.post(
        '/pipeline/trigger',
        json={'distribuidora_id': 'item-123', 'ano': 2026},
    )

    assert response.status_code == 202
    body = response.json()
    assert body['task_id'] == 'task-1'
    assert body['status'] == 'queued'
    assert body['distribuidora_id'] == 'item-123'
    assert body['ano'] == 2026
    assert body['download_url'] == 'https://www.arcgis.com/sharing/rest/content/items/item-123/data'
    assert 'job_id' in body

    mock_delay.assert_called_once()

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
    assert persisted.job_id == body['job_id']
    assert persisted.processed_at is not None


@pytest.mark.asyncio
async def test_pipeline_trigger_payload_invalido_retorna_422(client):
    response = await client.post(
        '/pipeline/trigger',
        json={'distribuidora_id': 'item-123', 'ano': 'nao-inteiro'},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pipeline_trigger_ja_acionada_retorna_409(
    client,
    session,
    monkeypatch,
):
    session.add(
        Distribuidora(
            id='item-duplicado',
            date_gdb=2026,
            dist_name='DIST TESTE',
            job_id='job-ja-existente',
        )
    )
    await session.commit()

    async def fake_resolve(_distribuidora_id):
        pytest.fail('Não deveria resolver URL para pipeline já acionada')

    monkeypatch.setattr(
        'backend.services.pipeline_trigger.resolve_download_url_from_aneel',
        fake_resolve,
    )
    monkeypatch.setattr(
        'backend.services.pipeline_trigger.task_download_gdb.delay',
        lambda *a, **kw: pytest.fail('Não deveria enfileirar pipeline já acionada'),
    )

    response = await client.post(
        '/pipeline/trigger',
        json={'distribuidora_id': 'item-duplicado', 'ano': 2026},
    )

    assert response.status_code == 409
    assert (
        response.json()['detail']
        == 'Pipeline já foi acionada para a distribuidora no ano informado'
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
        'backend.services.pipeline_trigger.resolve_download_url_from_aneel',
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
        'backend.services.pipeline_trigger.resolve_download_url_from_aneel',
        fake_resolve,
    )

    response = await client.post(
        '/pipeline/trigger',
        json={'distribuidora_id': 'item-502', 'ano': 2026},
    )

    assert response.status_code == 502
    assert response.json()['detail'] == 'ANEEL indisponível no momento'
