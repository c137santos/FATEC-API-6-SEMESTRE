import pytest
from unittest.mock import MagicMock, patch, call
from celery.exceptions import Retry

from backend.tasks.task_report import task_gerar_report

TASK_MODULE = 'backend.tasks.task_report'
SERVICE_MODULE = 'backend.services.report'
JOB_ID = 'job-report-abc'

_JOB_DOC = {
    'job_id': JOB_ID,
    'dist_name': 'ENEL',
    'ano_gdb': 2024,
    'status': 'completed',
    'render_paths': {
        'grafico_tam': '/output/images/grafico_tam_job-report-abc.png',
        'pt_pnt': '/output/images/pt_pnt_ENEL_2024.png',
        'tabela_score': None,
        'mapa_calor': None,
    },
}


def _make_db(job_doc=_JOB_DOC):
    jobs_col = MagicMock()
    jobs_col.find_one.return_value = job_doc

    db = MagicMock()
    db.__getitem__.side_effect = lambda name: {'jobs': jobs_col}.get(name, MagicMock())
    return db


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


def test_task_report_retorna_completed_quando_sucesso(tmp_path):
    db = _make_db()
    fake_pdf = str(tmp_path / 'report.pdf')

    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{TASK_MODULE}.gerar_pdf_report', return_value=fake_pdf) as mock_gerar,
    ):
        result = task_gerar_report.run(JOB_ID)

    assert result['status'] == 'completed'
    assert result['job_id'] == JOB_ID
    assert result['path'] == fake_pdf
    mock_gerar.assert_called_once_with(
        job_id=JOB_ID,
        render_paths=_JOB_DOC['render_paths'],
        job_meta=_JOB_DOC,
    )


def test_task_report_persiste_completed_no_mongo(tmp_path):
    db = _make_db()
    fake_pdf = str(tmp_path / 'report.pdf')

    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{TASK_MODULE}.gerar_pdf_report', return_value=fake_pdf),
    ):
        task_gerar_report.run(JOB_ID)

    update_call = db['jobs'].update_one.call_args
    filter_doc, update_doc = update_call.args
    assert filter_doc == {'job_id': JOB_ID}
    assert update_doc['$set']['report_status'] == 'completed'
    assert update_doc['$set']['report_pdf_path'] == fake_pdf
    assert 'report_generated_at' in update_doc['$set']


# ---------------------------------------------------------------------------
# job not found
# ---------------------------------------------------------------------------


def test_task_report_dispara_retry_quando_job_nao_encontrado():
    db = _make_db(job_doc=None)

    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db):
        with pytest.raises(Retry):
            task_gerar_report.run(JOB_ID)


# ---------------------------------------------------------------------------
# disk write failure
# ---------------------------------------------------------------------------


def test_task_report_persiste_failed_quando_erro_de_escrita():
    db = _make_db()

    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(
            f'{TASK_MODULE}.gerar_pdf_report',
            side_effect=OSError('Permission denied'),
        ),
    ):
        result = task_gerar_report.run(JOB_ID)

    assert result['status'] == 'failed'
    assert 'Permission denied' in result['reason']

    update_call = db['jobs'].update_one.call_args
    _, update_doc = update_call.args
    assert update_doc['$set']['report_status'] == 'failed'
    assert 'Permission denied' in update_doc['$set']['report_error']


# ---------------------------------------------------------------------------
# render_paths absent (dados insuficientes)
# ---------------------------------------------------------------------------


def test_task_report_dispara_retry_quando_render_paths_incompleto():
    """render_paths ausente ou sem as chaves obrigatórias → retry aguardando renders."""
    job_doc_sem_paths = {**_JOB_DOC, 'render_paths': None}
    db = _make_db(job_doc=job_doc_sem_paths)

    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db):
        with pytest.raises(Retry):
            task_gerar_report.run(JOB_ID)


# ---------------------------------------------------------------------------
# GET /pipeline/report/{distribuidora_id} route
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_report_status_retorna_404_quando_job_nao_existe(client):
    response = await client.get('/pipeline/report/dist-inexistente')
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_report_status_retorna_pending_quando_report_nao_gerado(
    session,
):
    from unittest.mock import AsyncMock

    from httpx import ASGITransport, AsyncClient

    from backend.app import app
    from backend.core.models import Distribuidora
    from backend.database import get_mongo_async_database, get_session

    session.add(
        Distribuidora(
            id='dist-report-test',
            date_gdb=2024,
            dist_name='DIST REPORT',
            job_id='job-report-route-test',
        )
    )
    await session.commit()

    mock_job = {'job_id': 'job-report-route-test', 'status': 'completed'}
    mock_db = MagicMock()
    mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=mock_job)

    async def _session():
        yield session

    async def _mongo():
        yield mock_db

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_mongo_async_database] = _mongo
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as ac:
            response = await ac.get('/pipeline/report/dist-report-test')
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_mongo_async_database, None)

    assert response.status_code == 200
    body = response.json()
    assert body['job_id'] == 'job-report-route-test'
    assert body['etl_status'] == 'completed'
    assert body['report_status'] == 'pending'
    assert body['report_pdf_path'] is None


@pytest.mark.asyncio
async def test_get_report_status_retorna_completed_quando_pdf_gerado(session):
    from unittest.mock import AsyncMock

    from httpx import ASGITransport, AsyncClient

    from backend.app import app
    from backend.core.models import Distribuidora
    from backend.database import get_mongo_async_database, get_session

    session.add(
        Distribuidora(
            id='dist-report-done',
            date_gdb=2024,
            dist_name='DIST DONE',
            job_id='job-report-done',
        )
    )
    await session.commit()

    mock_job = {
        'job_id': 'job-report-done',
        'status': 'completed',
        'report_status': 'completed',
        'report_pdf_path': '/output/reports/job-report-done/report.pdf',
    }
    mock_db = MagicMock()
    mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=mock_job)

    async def _session():
        yield session

    async def _mongo():
        yield mock_db

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_mongo_async_database] = _mongo
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as ac:
            response = await ac.get('/pipeline/report/dist-report-done')
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_mongo_async_database, None)

    assert response.status_code == 200
    body = response.json()
    assert body['report_status'] == 'completed'
    assert body['report_pdf_path'] == '/output/reports/job-report-done/report.pdf'
