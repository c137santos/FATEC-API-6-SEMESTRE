from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app import app
from backend.core.models import Distribuidora, User
from backend.database import get_mongo_async_database, get_session
from backend.security import get_current_user
from backend.services.pipeline_batch import _classify_distribuidoras

_FAKE_USER = User(username='testuser', email='test@test.com', password='hashed')


@pytest.fixture
def mock_batch_db():
    mock_db = MagicMock()
    mock_db.batch_runs.find_one = AsyncMock(return_value=None)
    mock_db.batch_runs.insert_one = AsyncMock()
    mock_db.batch_runs.update_one = AsyncMock()
    mock_db.jobs.find_one = AsyncMock(return_value=None)
    return mock_db


@pytest_asyncio.fixture
async def client(session, mock_batch_db):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: _FAKE_USER

    async def _mongo():
        yield mock_batch_db
    app.dependency_overrides[get_mongo_async_database] = _mongo

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as ac:
        yield ac
    app.dependency_overrides.clear()


# --- Route tests ---

@pytest.mark.asyncio
async def test_post_batch_retorna_202_com_batch_id(client, mock_batch_db):
    """Retorna 202 com batch_id quando nenhum lote está em execução."""
    with patch('asyncio.create_task'):
        response = await client.post('/pipeline/batch', json={})

    assert response.status_code == 202
    body = response.json()
    assert 'batch_id' in body
    assert body['batch_id']
    mock_batch_db.batch_runs.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_post_batch_retorna_409_quando_lote_em_execucao(client, mock_batch_db):
    """Retorna 409 quando já há documento com is_running == True em batch_runs."""
    mock_batch_db.batch_runs.find_one = AsyncMock(
        return_value={'batch_id': 'lote-antigo', 'is_running': True}
    )

    response = await client.post('/pipeline/batch', json={})

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_post_batch_retorna_401_sem_autenticacao(session, mock_batch_db):
    """Retorna 401 quando requisição não está autenticada."""
    app.dependency_overrides[get_session] = lambda: session

    async def _mongo():
        yield mock_batch_db
    app.dependency_overrides[get_mongo_async_database] = _mongo

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as ac:
            response = await ac.post('/pipeline/batch', json={})
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_batch_documento_criado_com_is_running_e_params(client, mock_batch_db):
    """Documento criado em batch_runs tem is_running: True e parâmetros corretos."""
    with patch('asyncio.create_task'):
        response = await client.post(
            '/pipeline/batch',
            json={'year': 2026, 'concurrency': 2},
        )

    assert response.status_code == 202
    doc = mock_batch_db.batch_runs.insert_one.call_args.args[0]
    assert doc['is_running'] is True
    assert doc['params']['year'] == 2026
    assert doc['params']['concurrency'] == 2
    assert doc['params']['poll_interval'] == 30
    assert doc['params']['min_wait'] == 1200


# --- _classify_distribuidoras tests ---

@pytest.mark.asyncio
async def test_classify_sem_job_id_processa(session):
    """Sem job_id → to_process com force_full=False."""
    session.add(Distribuidora(id='cls-nojob', date_gdb=2026, dist_name='DIST SEM JOB'))
    await session.commit()

    result = await session.execute(
        select(Distribuidora).where(Distribuidora.id == 'cls-nojob')
    )
    distribuidoras = result.scalars().all()

    mock_db = MagicMock()
    mock_db.jobs.find_one = AsyncMock(return_value=None)

    to_process, to_skip = await _classify_distribuidoras(distribuidoras, session, mock_db)

    assert len(to_process) == 1
    assert to_process[0]['distribuidora'].id == 'cls-nojob'
    assert to_process[0]['force_full'] is False
    assert len(to_skip) == 0


@pytest.mark.asyncio
async def test_classify_report_completed_ignora(session):
    """report_status == 'completed' → to_skip."""
    session.add(
        Distribuidora(id='cls-done', date_gdb=2026, dist_name='DIST DONE', job_id='job-done')
    )
    await session.commit()

    result = await session.execute(
        select(Distribuidora).where(Distribuidora.id == 'cls-done')
    )
    distribuidoras = result.scalars().all()

    mock_db = MagicMock()
    mock_db.jobs.find_one = AsyncMock(
        return_value={'job_id': 'job-done', 'report_status': 'completed'}
    )

    to_process, to_skip = await _classify_distribuidoras(distribuidoras, session, mock_db)

    assert len(to_process) == 0
    assert len(to_skip) == 1


@pytest.mark.asyncio
async def test_classify_report_failed_processa_com_force_full(session):
    """report_status == 'failed' → to_process com force_full=True."""
    session.add(
        Distribuidora(id='cls-fail', date_gdb=2026, dist_name='DIST FAIL', job_id='job-fail')
    )
    await session.commit()

    result = await session.execute(
        select(Distribuidora).where(Distribuidora.id == 'cls-fail')
    )
    distribuidoras = result.scalars().all()

    mock_db = MagicMock()
    mock_db.jobs.find_one = AsyncMock(
        return_value={'job_id': 'job-fail', 'report_status': 'failed'}
    )

    to_process, to_skip = await _classify_distribuidoras(distribuidoras, session, mock_db)

    assert len(to_process) == 1
    assert to_process[0]['force_full'] is True
    assert len(to_skip) == 0


@pytest.mark.asyncio
async def test_classify_job_ativo_ignora(session):
    """job_id existe mas sem doc no MongoDB (job em andamento) → to_skip."""
    session.add(
        Distribuidora(id='cls-active', date_gdb=2026, dist_name='DIST ACTIVE', job_id='job-running')
    )
    await session.commit()

    result = await session.execute(
        select(Distribuidora).where(Distribuidora.id == 'cls-active')
    )
    distribuidoras = result.scalars().all()

    mock_db = MagicMock()
    mock_db.jobs.find_one = AsyncMock(return_value=None)

    to_process, to_skip = await _classify_distribuidoras(distribuidoras, session, mock_db)

    assert len(to_process) == 0
    assert len(to_skip) == 1


# --- GET /pipeline/batch/status tests ---

_PARAMS_DEFAULT = {
    'year': None,
    'concurrency': 1,
    'poll_interval': 30,
    'max_attempts': 30,
    'max_retries': 1,
    'min_wait': 1200,
}

_DIST_ITEM = {'id': 'dist-1', 'nome': 'DIST 1', 'ano': 2026, 'status': 'completed', 'error': None}

_COUNTS = {
    'total': 1, 'pending': 0, 'processing': 0,
    'completed': 1, 'failed': 0, 'skipped': 0,
}


@pytest.mark.asyncio
async def test_get_batch_status_retorna_404_sem_lote(client, mock_batch_db):
    """Retorna 404 quando não existe nenhum documento em batch_runs."""
    mock_batch_db.batch_runs.find_one = AsyncMock(return_value=None)

    response = await client.get('/pipeline/batch/status')

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_batch_status_retorna_200_lote_encerrado(client, mock_batch_db):
    """Retorna 200 com is_running: False e todos os campos quando lote encerrado."""
    mock_batch_db.batch_runs.find_one = AsyncMock(return_value={
        'batch_id': 'lote-encerrado',
        'is_running': False,
        'started_at': datetime(2026, 5, 1, 12, 0, 0),
        'finished_at': datetime(2026, 5, 1, 14, 0, 0),
        'params': _PARAMS_DEFAULT,
        'user_email': 'test@test.com',
        'counts': _COUNTS,
        'distribuidoras': [_DIST_ITEM],
    })

    response = await client.get('/pipeline/batch/status')

    assert response.status_code == 200
    body = response.json()
    assert body['batch_id'] == 'lote-encerrado'
    assert body['is_running'] is False
    assert body['finished_at'] is not None
    assert body['counts']['completed'] == 1
    assert len(body['distribuidoras']) == 1
    assert body['distribuidoras'][0]['id'] == 'dist-1'
    assert body['distribuidoras'][0]['status'] == 'completed'


@pytest.mark.asyncio
async def test_get_batch_status_retorna_200_lote_em_execucao(client, mock_batch_db):
    """Retorna 200 com is_running: True quando lote ainda está rodando."""
    mock_batch_db.batch_runs.find_one = AsyncMock(return_value={
        'batch_id': 'lote-ativo',
        'is_running': True,
        'started_at': datetime(2026, 5, 1, 12, 0, 0),
        'finished_at': None,
        'params': _PARAMS_DEFAULT,
        'user_email': 'test@test.com',
        'counts': {
            'total': 3, 'pending': 1, 'processing': 1,
            'completed': 1, 'failed': 0, 'skipped': 0,
        },
        'distribuidoras': [
            {'id': 'dist-2', 'nome': 'DIST 2', 'ano': 2026, 'status': 'processing', 'error': None},
        ],
    })

    response = await client.get('/pipeline/batch/status')

    assert response.status_code == 200
    body = response.json()
    assert body['batch_id'] == 'lote-ativo'
    assert body['is_running'] is True
    assert body['finished_at'] is None
    assert body['distribuidoras'][0]['status'] == 'processing'
