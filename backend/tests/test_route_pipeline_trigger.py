import pytest
from celery import chain as celery_chain
from sqlalchemy import select
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from backend.core.models import Distribuidora

_CHAIN_PATH = 'backend.services.pipeline_trigger.chain'


def _mock_pipeline(monkeypatch, chain_result_id='task-1'):
    """Mocka chain().delay() para evitar conexão com Redis."""
    mock_chain = MagicMock()
    mock_chain.return_value.delay.return_value = MagicMock(id=chain_result_id)
    monkeypatch.setattr(_CHAIN_PATH, mock_chain)
    return mock_chain


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
        return 'https://www.arcgis.com/sharing/rest/content/items/item-123/data'

    _mock_pipeline(monkeypatch, chain_result_id='task-1')
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
    assert (
        body['download_url']
        == 'https://www.arcgis.com/sharing/rest/content/items/item-123/data'
    )
    assert 'job_id' in body

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
async def test_pipeline_trigger_chain_contem_todas_as_tasks(
    client,
    session,
    monkeypatch,
):
    """O chain deve conter download + 4 tasks pós-ETL com .si() (imutável)."""
    session.add(
        Distribuidora(id='item-chain', date_gdb=2026, dist_name='DIST CHAIN')
    )
    await session.commit()

    async def fake_resolve(_):
        return 'https://www.arcgis.com/sharing/rest/content/items/item-chain/data'

    monkeypatch.setattr(
        'backend.services.pipeline_trigger.resolve_download_url_from_aneel',
        fake_resolve,
    )

    with patch(_CHAIN_PATH) as mock_chain:
        mock_chain.return_value.delay.return_value = MagicMock(id='chain-id')
        response = await client.post(
            '/pipeline/trigger',
            json={'distribuidora_id': 'item-chain', 'ano': 2026},
        )

    assert response.status_code == 202
    job_id = response.json()['job_id']

    # chain foi chamado com exatamente 7 signatures (download + 5 pós-ETL)
    mock_chain.assert_called_once()
    sigs = mock_chain.call_args.args
    assert len(sigs) == 9

    assert sigs[0].task == 'etl.download_gdb'
    assert sigs[0].args == (job_id, 'https://www.arcgis.com/sharing/rest/content/items/item-chain/data', 'item-chain')

    assert sigs[1].task == 'etl.score_criticidade'
    assert sigs[1].args == (job_id, 'DIST CHAIN', 2026)
    
    assert sigs[2].task == 'etl.calculate_pt_pnt'
    assert sigs[2].args == (job_id, 'item-chain')
    
    assert sigs[3].task == 'etl.calcular_sam'
    assert sigs[3].args == (job_id, 'item-chain', 'DIST CHAIN', 2026)

    assert sigs[4].task == 'etl.mapa_criticidade'
    assert sigs[4].args == (job_id, 'item-chain', 'DIST CHAIN', 2026)
    
    assert sigs[5].task == 'etl.calcular_tam'
    assert sigs[5].args == (job_id, {
        "id": "item-chain",
        "dist_name": "DIST CHAIN",
        "date_gdb": 2026
    })

    assert sigs[6].task == 'etl.render_grafico_tam'
    assert sigs[6].args == (job_id,)

    assert sigs[7].task == 'etl.render_tabela_score'
    assert sigs[7].args == (job_id, 'DIST CHAIN', 2026)

    assert sigs[8].task == 'etl.render_mapa_calor'
    assert sigs[8].args == (job_id, 'DIST CHAIN', 2026)
    
    mock_chain.return_value.delay.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_trigger_payload_invalido_retorna_422(client):
    response = await client.post(
        '/pipeline/trigger',
        json={'distribuidora_id': 'item-123', 'ano': 'nao-inteiro'},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pipeline_trigger_distribuidora_nao_cadastrada_retorna_404(
    client,
    monkeypatch,
):
    async def fake_resolve(_):
        return 'https://url.fake/data'

    monkeypatch.setattr(
        'backend.services.pipeline_trigger.resolve_download_url_from_aneel',
        fake_resolve,
    )

    response = await client.post(
        '/pipeline/trigger',
        json={'distribuidora_id': 'id-inexistente', 'ano': 2026},
    )
    assert response.status_code == 404


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
        Distribuidora(id='item-404', date_gdb=2026, dist_name='DIST TESTE')
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
        Distribuidora(id='item-502', date_gdb=2026, dist_name='DIST TESTE')
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
