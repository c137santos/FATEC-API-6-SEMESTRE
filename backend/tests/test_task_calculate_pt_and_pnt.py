from unittest.mock import patch

import pytest
from celery.exceptions import Retry

from backend.tasks.task_calculate_pt_pnt import task_calculate_pt_pnt

JOB_ID = 'job-123'
DIST_ID = 'dist-456'
SIG_AGENTE = 'ENERGISA MS'
ANO = 2023


@patch('backend.tasks.task_calculate_pt_pnt.calculate_pt_pnt')
@patch('backend.tasks.task_calculate_pt_pnt.get_mongo_sync_db')
def test_executa_quando_job_completed(mock_db, mock_calculate):
    mock_db.return_value.__getitem__.return_value.find_one.return_value = {
        'job_id': JOB_ID,
        'status': 'completed',
    }
    mock_calculate.return_value = [{'conjunto': 'CONJ-01'}]

    result = task_calculate_pt_pnt(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert result['job_id'] == JOB_ID
    assert result['status'] == 'done'
    assert result['conjuntos'] == 1


@patch('backend.tasks.task_calculate_pt_pnt.get_mongo_sync_db')
def test_reagenda_quando_job_nao_concluido(mock_db):
    mock_db.return_value.__getitem__.return_value.find_one.return_value = {
        'job_id': JOB_ID,
        'status': 'running',
    }

    with pytest.raises(Retry):
        task_calculate_pt_pnt(JOB_ID, DIST_ID, SIG_AGENTE, ANO)


@patch('backend.tasks.task_calculate_pt_pnt.get_mongo_sync_db')
def test_reagenda_quando_job_nao_existe(mock_db):
    mock_db.return_value.__getitem__.return_value.find_one.return_value = None

    with pytest.raises(Retry):
        task_calculate_pt_pnt(JOB_ID, DIST_ID, SIG_AGENTE, ANO)


@patch('backend.tasks.task_calculate_pt_pnt.calculate_pt_pnt')
@patch('backend.tasks.task_calculate_pt_pnt.get_mongo_sync_db')
def test_retorna_zero_conjuntos(mock_db, mock_calculate):
    mock_db.return_value.__getitem__.return_value.find_one.return_value = {
        'job_id': JOB_ID,
        'status': 'completed',
    }
    mock_calculate.return_value = []

    result = task_calculate_pt_pnt(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert result['conjuntos'] == 0


@patch('backend.tasks.task_calculate_pt_pnt.calculate_pt_pnt')
@patch('backend.tasks.task_calculate_pt_pnt.get_mongo_sync_db')
def test_chama_calculate_pt_pnt_com_parametros_corretos(mock_db, mock_calculate):
    mock_db.return_value.__getitem__.return_value.find_one.return_value = {
        'job_id': JOB_ID,
        'status': 'completed',
    }
    mock_calculate.return_value = []

    task_calculate_pt_pnt(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    mock_calculate.assert_called_once_with(
        distribuidora_id=DIST_ID,
        job_id=JOB_ID,
        sig_agente=SIG_AGENTE,
        ano=ANO,
    )