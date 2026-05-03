from unittest.mock import patch

import pytest
from celery.exceptions import Retry

from backend.tasks.task_calculate_pt_pnt import task_calculate_pt_pnt


@patch('backend.tasks.task_calculate_pt_pnt.calculate_pt_pnt')
@patch('backend.tasks.task_calculate_pt_pnt.get_mongo_sync_db')
def test_executa_quando_job_completed(mock_db, mock_calculate):
    mock_db.return_value.__getitem__.return_value.find_one.return_value = {
        'job_id': 'job-123',
        'status': 'completed',
    }

    mock_calculate.return_value = [{'conjunto': 'CONJ-01'}]

    result = task_calculate_pt_pnt('job-123', 'dist-456')

    assert result['job_id'] == 'job-123'
    assert result['status'] == 'done'
    assert result['conjuntos'] == 1


@patch('backend.tasks.task_calculate_pt_pnt.get_mongo_sync_db')
def test_reagenda_quando_job_nao_concluido(mock_db):
    mock_db.return_value.__getitem__.return_value.find_one.return_value = {
        'job_id': 'job-123',
        'status': 'running',
    }

    with pytest.raises(Retry):
        task_calculate_pt_pnt('job-123', 'dist-456')


@patch('backend.tasks.task_calculate_pt_pnt.get_mongo_sync_db')
def test_reagenda_quando_job_nao_existe(mock_db):
    mock_db.return_value.__getitem__.return_value.find_one.return_value = None

    with pytest.raises(Retry):
        task_calculate_pt_pnt('job-123', 'dist-456')


@patch('backend.tasks.task_calculate_pt_pnt.calculate_pt_pnt')
@patch('backend.tasks.task_calculate_pt_pnt.get_mongo_sync_db')
def test_retorna_zero_conjuntos(mock_db, mock_calculate):
    mock_db.return_value.__getitem__.return_value.find_one.return_value = {
        'job_id': 'job-123',
        'status': 'completed',
    }

    mock_calculate.return_value = []

    result = task_calculate_pt_pnt('job-123', 'dist-456')

    assert result['conjuntos'] == 0
