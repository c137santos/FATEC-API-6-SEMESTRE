from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app import app
from backend.core.models import User
from backend.database import get_mongo_async_database, get_session
from backend.security import get_current_user
from backend.services.pipeline_batch import _classify_distribuidoras, _update_batch_dist_status

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
async def client(mock_batch_db):
    app.dependency_overrides[get_current_user] = lambda: _FAKE_USER

    async def _mongo():
        yield mock_batch_db

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def _session():
        yield mock_session

    app.dependency_overrides[get_mongo_async_database] = _mongo
    app.dependency_overrides[get_session] = _session

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as ac:
        yield ac
    app.dependency_overrides.clear()


# --- Route tests ---

@pytest.mark.asyncio
async def test_post_batch_retorna_202_com_batch_id(client, mock_batch_db):
    """Retorna 202 com batch_id quando nenhum lote está em execução."""
    with patch('backend.tasks.task_pipeline_batch.task_run_batch.delay'):
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
async def test_post_batch_retorna_401_sem_autenticacao(mock_batch_db):
    """Retorna 401 quando requisição não está autenticada."""
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
    with patch('backend.tasks.task_pipeline_batch.task_run_batch.delay'):
        response = await client.post(
            '/pipeline/batch',
            json={'year': 2026},
        )

    assert response.status_code == 202
    doc = mock_batch_db.batch_runs.insert_one.call_args.args[0]
    assert doc['is_running'] is True
    assert doc['params']['year'] == 2026


# --- _classify_distribuidoras tests ---

def test_classify_sem_job_id_processa():
    """Sem job_id → to_process."""
    distribuidoras = [{'id': 'cls-nojob', 'job_id': None, 'dist_name': 'DIST SEM JOB', 'date_gdb': 2026}]
    mock_db = MagicMock()

    to_process, to_skip = _classify_distribuidoras(distribuidoras, mock_db)

    assert len(to_process) == 1
    assert to_process[0]['distribuidora']['id'] == 'cls-nojob'
    assert len(to_skip) == 0


def test_classify_report_completed_ignora():
    """report_status == 'completed' → to_skip."""
    distribuidoras = [{'id': 'cls-done', 'job_id': 'job-done', 'dist_name': 'DIST DONE', 'date_gdb': 2026}]
    mock_db = MagicMock()
    mock_db.jobs.find_one.return_value = {'job_id': 'job-done', 'report_status': 'completed'}

    to_process, to_skip = _classify_distribuidoras(distribuidoras, mock_db)

    assert len(to_process) == 0
    assert len(to_skip) == 1


def test_classify_report_failed_processa():
    """report_status == 'failed' → to_process."""
    distribuidoras = [{'id': 'cls-fail', 'job_id': 'job-fail', 'dist_name': 'DIST FAIL', 'date_gdb': 2026}]
    mock_db = MagicMock()
    mock_db.jobs.find_one.return_value = {'job_id': 'job-fail', 'report_status': 'failed'}

    to_process, to_skip = _classify_distribuidoras(distribuidoras, mock_db)

    assert len(to_process) == 1
    assert len(to_skip) == 0


def test_classify_job_ativo_ignora():
    """job_id existe mas sem doc no MongoDB (job em andamento) → to_skip."""
    distribuidoras = [{'id': 'cls-active', 'job_id': 'job-running', 'dist_name': 'DIST ACTIVE', 'date_gdb': 2026}]
    mock_db = MagicMock()
    mock_db.jobs.find_one.return_value = None

    to_process, to_skip = _classify_distribuidoras(distribuidoras, mock_db)

    assert len(to_process) == 0
    assert len(to_skip) == 1


# --- GET /pipeline/batch/status tests ---

_PARAMS_DEFAULT = {
    'year': None,
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


# --- _update_batch_dist_status ---

def _sync_db(find_result):
    db = MagicMock()
    db.batch_runs.find_one_and_update.return_value = find_result
    return db


def test_update_status_retorna_true_quando_elemento_pendente():
    db = _sync_db({'counts': {'pending': 1, 'completed': 1}})
    result = _update_batch_dist_status(db, 'batch-1', 'dist-1', 'completed')
    assert result is True


def test_update_status_retorna_false_quando_elemento_nao_pendente():
    """MongoDB não encontrou doc com $elemMatch status='pending' → no-op."""
    db = _sync_db(None)
    result = _update_batch_dist_status(db, 'batch-1', 'dist-1', 'failed')
    assert result is False
    db.batch_runs.update_one.assert_not_called()


def test_update_status_filter_exige_status_pending():
    """O filtro deve conter $elemMatch com status='pending' para evitar
    duplo-decremento de counts.pending em itens já finalizados."""
    db = _sync_db({'counts': {'pending': 0}})
    _update_batch_dist_status(db, 'batch-1', 'dist-1', 'completed')
    call_filter = db.batch_runs.find_one_and_update.call_args[0][0]
    assert 'distribuidoras' in call_filter
    assert call_filter['distribuidoras']['$elemMatch']['status'] == 'pending'


def test_update_status_fecha_batch_quando_pending_zero():
    db = _sync_db({'counts': {'pending': 0, 'completed': 3}})
    _update_batch_dist_status(db, 'batch-1', 'dist-1', 'completed')
    db.batch_runs.update_one.assert_called_once()
    update_doc = db.batch_runs.update_one.call_args[0][1]
    assert update_doc['$set']['is_running'] is False
    assert 'finished_at' in update_doc['$set']


def test_update_status_nao_fecha_batch_quando_ha_pendentes():
    db = _sync_db({'counts': {'pending': 2, 'completed': 1}})
    _update_batch_dist_status(db, 'batch-1', 'dist-1', 'completed')
    db.batch_runs.update_one.assert_not_called()
