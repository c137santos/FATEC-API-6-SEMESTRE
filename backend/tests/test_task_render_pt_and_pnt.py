from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.tasks.task_render_pt_and_pnt import task_render_pt_pnt

TASK_MODULE = 'backend.tasks.task_render_pt_and_pnt'

JOB_ID = 'job-render-123'
DIST_ID = 'dist-456'
SIG_AGENTE = 'ENERGISA_MS'
ANO = 2023

RECORDS = [
    {'conjunto': 'C1', 'pt_mwh': 100.0, 'pnt_mwh': 200.0},
    {'conjunto': 'C2', 'pt_mwh': 50.0, 'pnt_mwh': 300.0},
    {'conjunto': 'C3', 'pt_mwh': 0.0, 'pnt_mwh': 0.0},
]


@pytest.fixture
def mock_output_dir(tmp_path):
    with patch(f'{TASK_MODULE}._output_dir', return_value=tmp_path):
        yield tmp_path


@pytest.fixture
def mock_mongo_com_doc():
    mock_db = MagicMock()
    mock_db['pt_pnt_resultados'].find_one.return_value = {
        'job_id': JOB_ID,
        'distribuidora_id': DIST_ID,
        'records': RECORDS,
    }
    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=mock_db):
        yield mock_db


@pytest.fixture
def mock_mongo_sem_doc():
    mock_db = MagicMock()
    mock_db['pt_pnt_resultados'].find_one.return_value = None
    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=mock_db):
        yield mock_db


@pytest.fixture
def mock_mongo_sem_records():
    mock_db = MagicMock()
    mock_db['pt_pnt_resultados'].find_one.return_value = {
        'job_id': JOB_ID,
        'distribuidora_id': DIST_ID,
        'records': [],
    }
    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=mock_db):
        yield mock_db


def test_levanta_runtime_error_quando_doc_nao_encontrado(mock_mongo_sem_doc):
    with patch(f'{TASK_MODULE}.MAX_WAIT_RETRIES', 0):
        with pytest.raises(RuntimeError):
            task_render_pt_pnt.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)


def test_retorna_skipped_quando_records_vazio(mock_mongo_sem_records):
    result = task_render_pt_pnt.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert result['status'] == 'skipped'
    assert result['reason'] == 'no_records'
    assert result['job_id'] == JOB_ID


def test_retorna_done_quando_sucesso(mock_mongo_com_doc, mock_output_dir):
    result = task_render_pt_pnt.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert result['status'] == 'done'
    assert result['job_id'] == JOB_ID


def test_salva_arquivo_png(mock_mongo_com_doc, mock_output_dir):
    result = task_render_pt_pnt.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert result['path'].endswith('.png')


def test_nome_arquivo_usa_sig_agente_e_ano(mock_mongo_com_doc, mock_output_dir):
    result = task_render_pt_pnt.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert SIG_AGENTE in result['path']
    assert str(ANO) in result['path']


def test_arquivo_png_criado_em_disco(mock_mongo_com_doc, mock_output_dir):
    result = task_render_pt_pnt.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert Path(result['path']).exists()


def test_busca_doc_com_job_id_e_distribuidora_id(
    mock_mongo_com_doc, mock_output_dir
):
    task_render_pt_pnt.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    mock_mongo_com_doc['pt_pnt_resultados'].find_one.assert_called_once_with(
        {'job_id': JOB_ID, 'distribuidora_id': DIST_ID},
        {'_id': 0},
    )


# ---------------------------------------------------------------------------
# RF-1: persistência em jobs.render_paths
# ---------------------------------------------------------------------------


def test_persiste_path_no_mongo_ao_concluir(mock_mongo_com_doc, mock_output_dir):
    result = task_render_pt_pnt.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    mock_mongo_com_doc['jobs'].update_one.assert_called_once_with(
        {'job_id': JOB_ID},
        {'$set': {'render_paths.pt_pnt': result['path']}},
    )


def test_persiste_null_no_mongo_quando_skipped(mock_mongo_sem_records):
    task_render_pt_pnt.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    mock_mongo_sem_records['jobs'].update_one.assert_called_once_with(
        {'job_id': JOB_ID},
        {'$set': {'render_paths.pt_pnt': None}},
    )