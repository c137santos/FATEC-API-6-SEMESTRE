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
    _mock_pipeline(monkeypatch)

    session.add(
        Distribuidora(
            id='item-123',
            date_gdb=2026,
            dist_name='DIST TESTE',
        )
    )
    await session.commit()

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

    with patch(_CHAIN_PATH) as mock_chain:
        mock_chain.return_value.delay.return_value = MagicMock(id='chain-id')
        response = await client.post(
            '/pipeline/trigger',
            json={'distribuidora_id': 'item-chain', 'ano': 2026},
        )

    assert response.status_code == 202
    job_id = response.json()['job_id']

    mock_chain.assert_called_once()
    sigs = mock_chain.call_args.args
    assert len(sigs) == 14

    assert sigs[0].task == 'etl.download_gdb'
    assert sigs[0].args == (job_id, 'https://www.arcgis.com/sharing/rest/content/items/item-chain/data', 'item-chain')

    assert sigs[1].task == 'etl.extrair_gdb'
    assert sigs[1].args[0] == job_id
    assert sigs[1].args[1].endswith(f'{job_id}.zip')
    assert sigs[1].args[2] == 'item-chain'

    assert sigs[2].task == 'etl.score_criticidade'
    assert sigs[2].args == (job_id, 'DIST CHAIN', 2026)

    assert sigs[3].task == 'etl.calculate_pt_pnt'
    assert sigs[3].args == (job_id, 'item-chain', 'DIST CHAIN', 2026)

    assert sigs[4].task == 'etl.render_pt_pnt'
    assert sigs[4].args == (job_id, 'item-chain', 'DIST CHAIN', 2026)

    assert sigs[5].task == 'etl.calcular_sam'
    assert sigs[5].args == (job_id, 'item-chain', 'DIST CHAIN', 2026)

    assert sigs[6].task == 'etl.mapa_criticidade'
    assert sigs[6].args == (job_id, 'item-chain', 'DIST CHAIN', 2026)

    assert sigs[7].task == 'etl.calcular_tam'
    assert sigs[7].args == (job_id, {
        "id": "item-chain",
        "dist_name": "DIST CHAIN",
        "date_gdb": 2026
    })

    assert sigs[8].task == 'etl.render_grafico_tam'
    assert sigs[8].args == (job_id,)

    assert sigs[9].task == 'etl.render_tabela_score'
    assert sigs[9].args == (job_id, 'DIST CHAIN', 2026)

    assert sigs[10].task == 'etl.render_mapa_calor'
    assert sigs[10].args == (job_id, 'DIST CHAIN', 2026)

    assert sigs[11].task == 'etl.render_sam'
    assert sigs[11].args == (job_id, 'item-chain', 'DIST CHAIN', 2026)

    assert sigs[12].task == 'etl.gerar_report'
    assert sigs[12].args == (job_id,)

    assert sigs[13].task == 'etl.cleanup_files'
    assert sigs[13].args == (job_id,)

    mock_chain.return_value.delay.assert_called_once()


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
async def test_pipeline_trigger_aneel_indisponivel_retorna_502(
    client,
    session,
    monkeypatch,
):
    session.add(
        Distribuidora(id='item-502', date_gdb=2026, dist_name='DIST TESTE')
    )
    await session.commit()

    mock_chain = MagicMock()
    mock_chain.return_value.delay.side_effect = RuntimeError('ANEEL indisponível no momento')
    monkeypatch.setattr(_CHAIN_PATH, mock_chain)

    response = await client.post(
        '/pipeline/trigger',
        json={'distribuidora_id': 'item-502', 'ano': 2026},
    )

    assert response.status_code == 502
    assert response.json()['detail'] == 'ANEEL indisponível no momento'
