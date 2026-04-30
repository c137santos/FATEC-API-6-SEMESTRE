"""Testes da rota POST /download-gdb.

Cria um app FastAPI mínimo com a rota registrada para evitar
dependências de módulos ausentes (database, core.models).
"""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, HttpUrl

from backend.tasks.task_download_gdb import task_download_gdb

_test_app = FastAPI()


class _DownloadRequest(BaseModel):
    url: HttpUrl


@_test_app.post('/download-gdb')
def download_gdb(request: _DownloadRequest):
    job_id = str(uuid.uuid4())
    try:
        task = task_download_gdb.delay(job_id, str(request.url))
        return {
            'job_id': job_id,
            'task_id': task.id,
            'status': 'queued',
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@pytest.fixture
def client():
    return TestClient(_test_app)


def test_retorna_job_id_e_task_id(client):
    fake_task = SimpleNamespace(id='celery-task-id-123')
    with (
        patch(
            'backend.tests.test_route_etl.uuid.uuid4',
            return_value='job-123',
        ),
        patch(
            'backend.tests.test_route_etl.task_download_gdb.delay',
            return_value=fake_task,
        ) as delay_mock,
    ):
        response = client.post(
            '/download-gdb',
            json={'url': 'https://example.com/file.zip'},
        )

    assert response.status_code == 200
    delay_mock.assert_called_once_with('job-123', 'https://example.com/file.zip')
    body = response.json()
    assert body['job_id'] == 'job-123'
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
    with (
        patch(
            'backend.tests.test_route_etl.uuid.uuid4',
            return_value='job-500',
        ),
        patch(
            'backend.tests.test_route_etl.task_download_gdb.delay',
            side_effect=Exception('broker down'),
        ),
    ):
        response = client.post(
            '/download-gdb',
            json={'url': 'https://example.com/file.zip'},
        )

    assert response.status_code == 500
    assert 'broker down' in response.json()['detail']
