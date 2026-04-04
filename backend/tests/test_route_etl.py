"""Testes da rota POST /download-gdb.

Cria um app FastAPI mínimo com a rota registrada para evitar
dependências de módulos ausentes (database, core.models).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, HttpUrl

import uuid

from backend.tasks.task_download_gdb import task_download_gdb

_test_app = FastAPI()


class _DownloadRequest(BaseModel):
    url: HttpUrl


@_test_app.post('/download-gdb')
def download_gdb(request: _DownloadRequest):

    job_id = str(uuid.uuid4())
    try:
        task = task_download_gdb.delay(job_id, str(request.url))
        return {'job_id': job_id, 'task_id': task.id, 'status': 'queued'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@pytest.fixture
def client():
    return TestClient(_test_app)


def test_retorna_job_id_e_task_id(client):
    mock_result = MagicMock()
    mock_result.id = 'celery-task-id-123'

    with patch(
        'backend.tasks.task_download_gdb.task_download_gdb.delay',
        return_value=mock_result,
    ):
        response = client.post(
            '/download-gdb',
            json={'url': 'https://example.com/file.zip'},
        )

    assert response.status_code == 200
    body = response.json()
    assert 'job_id' in body
    assert body['task_id'] == 'celery-task-id-123'
    assert body['status'] == 'queued'


def test_url_invalida_retorna_422(client):
    response = client.post(
        '/download-gdb',
        json={'url': 'nao-e-uma-url'},
    )
    assert response.status_code == 422


def test_payload_vazio_retorna_422(client):
    response = client.post('/download-gdb', json={})
    assert response.status_code == 422


def test_erro_no_celery_retorna_500(client):
    with patch(
        'backend.tasks.task_download_gdb.task_download_gdb.delay',
        side_effect=Exception('broker down'),
    ):
        response = client.post(
            '/download-gdb',
            json={'url': 'https://example.com/file.zip'},
        )

    assert response.status_code == 500
    assert 'broker down' in response.json()['detail']
